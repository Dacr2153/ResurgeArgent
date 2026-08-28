"""Tests puros del motor de ingesta. Sin mocks ni I/O."""

from datetime import UTC, datetime, timedelta

from agente_ingesta.dominio import ConfigVentana, MotivoDescarte, MotorIngesta


def item(
    fuente_id="f1",
    fuente_tipo="ciudadano",
    canal="sms",
    texto="Hay un incendio grande",
    ubicacion=None,
    urgencia=None,
    **extra,
):
    d = {"fuente": {"id": fuente_id, "tipo": fuente_tipo}, "canal": canal, "texto": texto}
    if ubicacion is not None:
        d["ubicacion"] = ubicacion
    if urgencia is not None:
        d["urgencia"] = urgencia
    d.update(extra)
    return d


def motor(limite=100, segundos=60.0):
    return MotorIngesta(ConfigVentana(limite=limite, segundos=segundos))


AHORA = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------- básicos


def test_lote_vacio_no_produce_nada():
    resultado = motor().procesar([], frozenset(), (), AHORA)
    assert resultado.aceptados == ()
    assert resultado.descartados == ()
    assert resultado.vistos == frozenset()


def test_reporte_bien_formado_se_acepta():
    resultado = motor().procesar([item()], frozenset(), (), AHORA)
    assert len(resultado.aceptados) == 1
    assert resultado.descartados == ()
    assert resultado.aceptados[0].texto == "Hay un incendio grande"


def test_texto_sin_ubicacion_se_acepta_con_ubicacion_none():
    resultado = motor().procesar([item(ubicacion=None)], frozenset(), (), AHORA)
    assert len(resultado.aceptados) == 1
    assert resultado.aceptados[0].ubicacion is None


# ------------------------------------------------------------- validación


def test_item_no_es_objeto_se_descarta_formato_invalido():
    resultado = motor().procesar(["esto no es un dict"], frozenset(), (), AHORA)
    assert resultado.aceptados == ()
    assert resultado.descartados[0].motivo == MotivoDescarte.FORMATO_INVALIDO


def test_fuente_ausente_se_descarta():
    crudo = item()
    del crudo["fuente"]
    resultado = motor().procesar([crudo], frozenset(), (), AHORA)
    assert resultado.descartados[0].motivo == MotivoDescarte.FUENTE_NO_IDENTIFICADA


def test_fuente_con_tipo_desconocido_se_descarta():
    resultado = motor().procesar([item(fuente_tipo="marciano")], frozenset(), (), AHORA)
    assert resultado.descartados[0].motivo == MotivoDescarte.FUENTE_NO_IDENTIFICADA


def test_texto_vacio_se_descarta():
    resultado = motor().procesar([item(texto="   ")], frozenset(), (), AHORA)
    assert resultado.descartados[0].motivo == MotivoDescarte.TEXTO_VACIO


def test_canal_desconocido_se_descarta_formato_invalido():
    resultado = motor().procesar([item(canal="paloma-mensajera")], frozenset(), (), AHORA)
    assert resultado.descartados[0].motivo == MotivoDescarte.FORMATO_INVALIDO


def test_coordenadas_fuera_de_rango_se_descartan():
    resultado = motor().procesar(
        [item(ubicacion={"lat": 200.0, "lon": 10.0})], frozenset(), (), AHORA
    )
    assert resultado.descartados[0].motivo == MotivoDescarte.UBICACION_INVALIDA


def test_lote_mixto_no_revienta_por_un_item_invalido():
    lote = [item(fuente_id="f1"), "invalido", item(fuente_id="f2")]
    resultado = motor().procesar(lote, frozenset(), (), AHORA)
    assert len(resultado.aceptados) == 2
    assert len(resultado.descartados) == 1
    assert resultado.descartados[0].indice == 1


# ------------------------------------------------------------ idempotencia


def test_reenvio_exacto_en_el_mismo_lote_se_descarta():
    lote = [item(fuente_id="f1", texto="mismo texto"), item(fuente_id="f1", texto="mismo texto")]
    resultado = motor().procesar(lote, frozenset(), (), AHORA)
    assert len(resultado.aceptados) == 1
    assert resultado.descartados[0].motivo == MotivoDescarte.REENVIO_DUPLICADO


def test_reenvio_contra_lote_anterior_se_descarta():
    primero = motor().procesar([item(fuente_id="f1", texto="ayuda")], frozenset(), (), AHORA)
    assert len(primero.aceptados) == 1

    segundo = motor().procesar(
        [item(fuente_id="f1", texto="ayuda")], primero.vistos, primero.en_ventana, AHORA
    )
    assert segundo.aceptados == ()
    assert segundo.descartados[0].motivo == MotivoDescarte.REENVIO_DUPLICADO


def test_mismo_texto_de_fuentes_distintas_no_es_duplicado():
    lote = [item(fuente_id="f1", texto="hay fuego"), item(fuente_id="f2", texto="hay fuego")]
    resultado = motor().procesar(lote, frozenset(), (), AHORA)
    assert len(resultado.aceptados) == 2


# ------------------------------------------------------------- back-pressure


def test_saturacion_prioriza_immediate_y_autoridad():
    lote = [
        item(fuente_id="ciudadano-normal", fuente_tipo="ciudadano", texto="a"),
        item(
            fuente_id="autoridad-1",
            fuente_tipo="autoridad",
            urgencia="Immediate",
            texto="b",
        ),
        item(
            fuente_id="ciudadano-urgente",
            fuente_tipo="ciudadano",
            urgencia="Immediate",
            texto="c",
        ),
    ]
    resultado = motor(limite=2).procesar(lote, frozenset(), (), AHORA)

    ids_aceptados = {r.fuente.id for r in resultado.aceptados}
    assert ids_aceptados == {"autoridad-1", "ciudadano-urgente"}

    descartado = resultado.descartados[0]
    assert descartado.motivo == MotivoDescarte.SATURACION_VENTANA
    assert descartado.indice == 0


def test_ventana_libera_capacidad_al_expirar():
    m = motor(limite=1, segundos=60.0)
    primero = m.procesar([item(fuente_id="f1", texto="uno")], frozenset(), (), AHORA)
    assert len(primero.aceptados) == 1

    # Dentro de la ventana: no cabe un segundo reporte distinto.
    segundo = m.procesar(
        [item(fuente_id="f2", texto="dos")], primero.vistos, primero.en_ventana, AHORA
    )
    assert segundo.aceptados == ()
    assert segundo.descartados[0].motivo == MotivoDescarte.SATURACION_VENTANA

    # Pasada la ventana: la capacidad se libera.
    mas_tarde = AHORA + timedelta(seconds=120)
    tercero = m.procesar(
        [item(fuente_id="f2", texto="dos")], segundo.vistos, segundo.en_ventana, mas_tarde
    )
    assert len(tercero.aceptados) == 1


def test_descarte_por_saturacion_no_bloquea_reintento_posterior():
    m = motor(limite=1)
    lote = [item(fuente_id="f1", texto="uno"), item(fuente_id="f2", texto="dos")]
    resultado = m.procesar(lote, frozenset(), (), AHORA)
    assert len(resultado.aceptados) == 1
    assert len(resultado.descartados) == 1

    # El reporte rechazado por saturación (no por duplicado) debe poder
    # reintentarse sin que "vistos" lo bloquee como si ya hubiera entrado.
    rechazado_id = resultado.descartados[0].indice
    rechazado = lote[rechazado_id]
    reintento = m.procesar(
        [rechazado],
        resultado.vistos,
        (),  # ventana limpia: simula que ya pasó tiempo suficiente
        AHORA + timedelta(seconds=120),
    )
    assert len(reintento.aceptados) == 1
