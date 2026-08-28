"""Propagación real entre nodos montados en memoria. Sin red."""

from __future__ import annotations

from dataclasses import replace

from malla.aplicacion.casos_uso.originar_reporte import OriginarReporte
from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from malla.dominio.motor_malla import ResultadoRecepcion
from nucleo.mensajes import TipoEvento
from tests.malla.conftest import TransporteMudo, construir_nodo, enlazar, reporte


async def test_el_reporte_llega_a_los_dos_vecinos():
    a, b, c = construir_nodo(), construir_nodo(), construir_nodo()
    enlazar(a, b, c)

    sobre, difusion = await a.originar.originar(reporte())

    assert difusion.alcanzados == 2
    assert sobre.id_mensaje in await b.almacen.ids_vistos()
    assert sobre.id_mensaje in await c.almacen.ids_vistos()


async def test_triangulo_no_satura_la_red():
    """A, B y C todos conectados entre sí: el sobre se entrega una vez a cada uno.

    Sin anti-bucle esta topología es la que revienta una malla: A manda a B y C,
    B reenvía a C, C reenvía a B, y así indefinidamente.
    """
    a, b, c = construir_nodo(), construir_nodo(), construir_nodo()
    enlazar(a, b, c)

    sobre, _ = await a.originar.originar(reporte())

    for nodo in (b, c):
        assert len(await nodo.almacen.pendientes()) == 1
    # A no se guarda copias extra de su propio sobre.
    assert len(await a.almacen.pendientes()) == 1
    # El número de envíos es finito y pequeño: no hay tormenta.
    total_envios = sum(len(n.transporte.enviados) for n in (a, b, c))
    assert total_envios <= 6
    assert sobre.id_mensaje


async def test_mismo_reporte_por_tres_caminos_queda_uno():
    """Tres vecinos entregan el mismo reporte al mismo nodo. Debe quedar uno."""
    destino = construir_nodo()
    emisores = [construir_nodo() for _ in range(3)]

    # El mismo reporte, palabra por palabra y con el mismo GPS: es el caso de un
    # vecindario donde tres personas retransmiten lo que les llegó.
    original = reporte()
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, original.a_dict())

    resultados = []
    for indice, emisor in enumerate(emisores):
        # Cada copia llega por una ruta distinta, con distinto número de saltos.
        copia = sobre
        for salto in range(indice + 1):
            copia = copia.avanzar(f"{emisor.id}-{salto}")
        resultados.append(await destino.recibir.recibir(copia))

    assert resultados[0].resultado is ResultadoRecepcion.ACEPTADO_Y_REENVIAR
    assert all(r.resultado is ResultadoRecepcion.DUPLICADO for r in resultados[1:])
    assert len(await destino.almacen.pendientes()) == 1


async def test_sobre_alterado_por_un_retransmisor_se_descarta_y_se_audita():
    destino = construir_nodo()
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    carga = dict(sobre.carga)
    carga["ubicacion"] = {"type": "Point", "coordinates": [-75.5, 6.2]}
    alterado = replace(sobre, carga=carga)

    decision = await destino.recibir.recibir(alterado)

    assert decision.resultado is ResultadoRecepcion.FIRMA_INVALIDA
    assert await destino.almacen.pendientes() == []
    descartes = destino.auditoria.por_tipo(str(TipoEvento.REPORTE_DESCARTADO))
    assert len(descartes) == 1
    assert descartes[0].detalle["motivo"] == "firma_invalida"


async def test_sobre_alterado_no_se_propaga_a_los_vecinos():
    destino, vecino = construir_nodo(), construir_nodo()
    enlazar(destino, vecino)
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    alterado = replace(sobre, carga=dict(sobre.carga) | {"personas_afectadas": 900})

    await destino.recibir.recibir(alterado)

    assert destino.transporte.enviados == []
    assert await vecino.almacen.pendientes() == []


async def test_nodo_aislado_guarda_el_reporte_para_despues():
    """Almacenar-y-reenviar: sin vecinos, el reporte no se pierde."""
    nodo = construir_nodo()
    aislado = OriginarReporte(
        nodo.identidad, nodo.motor, nodo.almacen, TransporteMudo(), nodo.auditoria
    )

    sobre, difusion = await aislado.originar(reporte())

    assert difusion.alcanzados == 0
    pendientes = await nodo.almacen.pendientes()
    assert [s.id_mensaje for s in pendientes] == [sobre.id_mensaje]


async def test_recepcion_legitima_queda_auditada():
    destino = construir_nodo()
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    await destino.recibir.recibir(sobre)
    recibidos = destino.auditoria.por_tipo(str(TipoEvento.REPORTE_RECIBIDO))
    assert recibidos[0].detalle["componente"] == "malla-p2p"
    assert recibidos[0].detalle["id_mensaje"] == sobre.id_mensaje
