"""Tests del motor determinista: agrupación, fusión, confianza, caducidad."""

from datetime import timedelta

from agente_verificacion.dominio.motor_verificacion import MotorVerificacion
from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    Fuente,
    ReporteCrudo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import Punto
from nucleo.mensajes import ahora

SITIO = Punto(lat=4.6097, lon=-74.0817)
LEJOS = Punto(lat=4.9000, lon=-74.3000)  # a decenas de km de SITIO
# A ~450 m de SITIO: dentro del radio por defecto (500 m) pero fuera de la
# "zona segura" (250 m, la mitad del radio) donde la geometría sola ya basta.
# Es justo el caso fronterizo donde el texto debe decidir.
AMBIGUO = Punto(lat=SITIO.lat + 0.45 / 111.32, lon=SITIO.lon)


def _fuente(id_="f-1", tipo=TipoFuente.CIUDADANO, reputacion=0.6) -> Fuente:
    return Fuente(id=id_, tipo=tipo, nombre=id_, reputacion=reputacion)


def _reporte(
    texto="Derrumbe en la vía principal",
    fuente=None,
    ubicacion=SITIO,
    categoria=Categoria.RESCUE,
    urgencia=Urgencia.IMMEDIATE,
    severidad=Severidad.SEVERE,
    certeza=Certeza.OBSERVED,
    recibido_en=None,
) -> ReporteCrudo:
    return ReporteCrudo(
        texto=texto,
        fuente=fuente or _fuente(),
        canal=Canal.SMS,
        ubicacion=ubicacion,
        categoria=categoria,
        urgencia=urgencia,
        severidad=severidad,
        certeza=certeza,
        recibido_en=recibido_en or ahora(),
    )


def _motor(**kwargs) -> MotorVerificacion:
    return MotorVerificacion(**kwargs)


def test_lote_vacio_no_produce_incidentes():
    assert _motor().fusionar([], {}) == []


def test_reportes_cercanos_con_texto_similar_se_fusionan_en_un_incidente():
    a = _reporte(texto="Se cayó el puente sobre el río", fuente=_fuente("f-1"))
    b = _reporte(texto="Colapsó el puente sobre el río", fuente=_fuente("f-2"))
    motor = _motor()

    pares = motor.candidatos([a, b])
    similitudes = {(a.id, b.id): 0.9}

    incidentes = motor.fusionar([a, b], similitudes)

    assert pares == [(a.id, b.id)]
    assert len(incidentes) == 1
    assert incidentes[0].corroboraciones == 2
    assert set(incidentes[0].reportes_origen) == {a.id, b.id}


def test_mismo_lugar_y_momento_fusiona_aunque_el_texto_no_se_parezca():
    # Misma esquina (distancia 0), misma categoría, mismo instante: la
    # evidencia espacio-temporal es abrumadora por sí sola y el texto no
    # puede bloquear la fusión, aunque la similitud textual sea 0. Es la
    # corrección directa al defecto reportado: en offline (SimilitudNula),
    # las paráfrasis reales casi nunca comparten vocabulario, así que si el
    # texto pudiera vetar, el agente nunca fusionaría nada sin LLM.
    a = _reporte(texto="Derrumbe en la vía principal", fuente=_fuente("f-1"))
    b = _reporte(texto="Choque de dos vehículos", fuente=_fuente("f-2"))
    motor = _motor()

    incidentes = motor.fusionar([a, b], {(a.id, b.id): 0.0})

    assert len(incidentes) == 1
    assert incidentes[0].corroboraciones == 2


def test_distancia_ambigua_sin_apoyo_textual_no_fusiona():
    # A ~450 m (fuera de la zona segura de 250 m, dentro del radio de 500 m):
    # la geometría sola ya no es abrumadora. Sin ninguna señal textual que la
    # respalde, dos reportes de categorías iguales pero de textos muy
    # distintos no deben fusionarse solo por caer dentro del radio.
    a = _reporte(texto="Incendio en un edificio del centro", ubicacion=SITIO, fuente=_fuente("f-1"))
    b = _reporte(texto="Incendio en una bodega del sur", ubicacion=AMBIGUO, fuente=_fuente("f-2"))
    motor = _motor()

    incidentes = motor.fusionar([a, b], {(a.id, b.id): 0.0})

    assert len(incidentes) == 2


def test_distancia_ambigua_con_apoyo_textual_fuerte_si_fusiona():
    # Mismo par ambiguo del test anterior, pero ahora el puerto de similitud
    # (LLM real, o un caso donde el texto sí coincide) confirma que hablan del
    # mismo hecho: aquí el texto sí aporta la información que la geometría
    # sola no tenía, y la fusión debe ocurrir.
    a = _reporte(texto="Incendio en un edificio del centro", ubicacion=SITIO, fuente=_fuente("f-1"))
    b = _reporte(
        texto="Se incendió el mismo edificio del centro", ubicacion=AMBIGUO, fuente=_fuente("f-2")
    )
    motor = _motor()

    incidentes = motor.fusionar([a, b], {(a.id, b.id): 1.0})

    assert len(incidentes) == 1
    assert incidentes[0].corroboraciones == 2


def test_incidentes_lejanos_en_espacio_no_se_fusionan_aunque_el_texto_sea_identico():
    a = _reporte(texto="Derrumbe en la vía", ubicacion=SITIO, fuente=_fuente("f-1"))
    b = _reporte(texto="Derrumbe en la vía", ubicacion=LEJOS, fuente=_fuente("f-2"))
    motor = _motor()

    # Ni siquiera se generan como candidatos: están a decenas de km.
    assert motor.candidatos([a, b]) == []

    incidentes = motor.fusionar([a, b], {(a.id, b.id): 1.0})
    assert len(incidentes) == 2


def test_categorias_distintas_no_se_fusionan():
    a = _reporte(categoria=Categoria.RESCUE, fuente=_fuente("f-1"))
    b = _reporte(categoria=Categoria.FIRE, fuente=_fuente("f-2"))
    motor = _motor()

    incidentes = motor.fusionar([a, b], {(a.id, b.id): 1.0})
    assert len(incidentes) == 2


def test_ventana_temporal_separa_eventos_no_relacionados():
    ahora_ = ahora()
    a = _reporte(recibido_en=ahora_, fuente=_fuente("f-1"))
    b = _reporte(recibido_en=ahora_ + timedelta(hours=48), fuente=_fuente("f-2"))
    motor = _motor()

    assert motor.candidatos([a, b]) == []
    incidentes = motor.fusionar([a, b], {})
    assert len(incidentes) == 2


def test_corroboracion_de_fuentes_distintas_da_mas_confianza_que_repetir_la_misma():
    motor = _motor()

    misma_fuente = _fuente("f-1")
    a1 = _reporte(fuente=misma_fuente)
    a2 = _reporte(fuente=misma_fuente)
    (incidente_repetido,) = motor.fusionar([a1, a2], {(a1.id, a2.id): 1.0})

    b1 = _reporte(fuente=_fuente("f-1"))
    b2 = _reporte(fuente=_fuente("f-2"))
    (incidente_distinto,) = motor.fusionar([b1, b2], {(b1.id, b2.id): 1.0})

    assert incidente_distinto.confianza > incidente_repetido.confianza


def test_fuente_poco_confiable_da_confianza_baja():
    reporte = _reporte(
        fuente=_fuente("f-1", tipo=TipoFuente.CIUDADANO, reputacion=0.2),
        certeza=Certeza.UNKNOWN,
    )
    (incidente,) = _motor().fusionar([reporte], {})

    assert incidente.corroboraciones == 1
    assert incidente.confianza < 0.2


def test_autoridad_da_mas_confianza_que_ciudadano_en_igualdad_de_condiciones():
    fresco = ahora()
    ciudadano = _reporte(
        fuente=_fuente("f-1", tipo=TipoFuente.CIUDADANO, reputacion=0.5),
        certeza=Certeza.LIKELY,
        recibido_en=fresco,
    )
    autoridad = _reporte(
        fuente=_fuente("f-2", tipo=TipoFuente.AUTORIDAD, reputacion=0.95),
        certeza=Certeza.LIKELY,
        recibido_en=fresco,
    )

    (inc_ciudadano,) = _motor().fusionar([ciudadano], {})
    (inc_autoridad,) = _motor().fusionar([autoridad], {})

    assert inc_autoridad.confianza > inc_ciudadano.confianza


def test_antiguedad_decae_la_confianza():
    fresco = _reporte(fuente=_fuente("f-1"), recibido_en=ahora())
    viejo = _reporte(fuente=_fuente("f-1"), recibido_en=ahora() - timedelta(hours=48))

    (inc_fresco,) = _motor().fusionar([fresco], {})
    (inc_viejo,) = _motor().fusionar([viejo], {})

    assert inc_viejo.confianza < inc_fresco.confianza


def test_vence_en_se_fija_segun_urgencia_y_el_incidente_caduca():
    reporte = _reporte(urgencia=Urgencia.IMMEDIATE, fuente=_fuente("f-1"))
    (incidente,) = _motor().fusionar([reporte], {})

    assert incidente.vence_en is not None
    assert incidente.esta_vigente(incidente.verificado_en)
    assert not incidente.esta_vigente(incidente.vence_en + timedelta(seconds=1))


def test_contradiccion_de_severidad_queda_en_metadatos():
    a = _reporte(severidad=Severidad.MINOR, fuente=_fuente("f-1", reputacion=0.3))
    b = _reporte(severidad=Severidad.EXTREME, fuente=_fuente("f-2", reputacion=0.9))
    (incidente,) = _motor().fusionar([a, b], {(a.id, b.id): 1.0})

    assert "contradiccion_severidad" in incidente.metadatos
    # La fuente más confiable (mayor peso) debe determinar la severidad ganadora.
    assert incidente.severidad == Severidad.EXTREME


def test_reportes_origen_lista_todos_los_fusionados():
    reportes = [_reporte(fuente=_fuente(f"f-{i}")) for i in range(5)]
    pares = {}
    for i in range(5):
        for j in range(i + 1, 5):
            pares[(reportes[i].id, reportes[j].id)] = 0.8

    (incidente,) = _motor().fusionar(reportes, pares)

    assert set(incidente.reportes_origen) == {r.id for r in reportes}
    assert incidente.corroboraciones == 5
