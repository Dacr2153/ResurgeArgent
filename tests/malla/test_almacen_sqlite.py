"""Almacenar-y-reenviar: los pendientes tienen que sobrevivir a un reinicio."""

from __future__ import annotations

from malla.adaptadores.salida.almacen_sqlite import AlmacenSQLite
from malla.aplicacion.casos_uso.originar_reporte import OriginarReporte
from malla.aplicacion.casos_uso.recibir_sobre import RecibirSobre
from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from malla.dominio.motor_malla import MotorMalla
from nucleo.auditoria import AuditoriaMemoria
from tests.malla.conftest import TransporteMudo, reporte


async def test_los_pendientes_sobreviven_al_cierre_de_la_aplicacion(tmp_path):
    """El caso real: el teléfono se queda sin batería antes de encontrar vecino."""
    ruta = tmp_path / "sobres.sqlite3"
    identidad = IdentidadNodo.generar()
    motor = MotorMalla(identidad.id_nodo)

    almacen = AlmacenSQLite(ruta)
    originar = OriginarReporte(identidad, motor, almacen, TransporteMudo(), AuditoriaMemoria())
    sobre, difusion = await originar.originar(reporte())
    assert difusion.alcanzados == 0
    almacen.cerrar()  # se cierra la aplicación

    reabierto = AlmacenSQLite(ruta)
    pendientes = await reabierto.pendientes()
    assert [s.id_mensaje for s in pendientes] == [sobre.id_mensaje]
    assert pendientes[0].carga["texto"] == sobre.carga["texto"]
    # Y la firma sigue verificando tras el viaje por disco.
    assert pendientes[0] == sobre


async def test_no_se_reprocesa_lo_ya_visto_tras_reiniciar(tmp_path):
    ruta = tmp_path / "sobres.sqlite3"
    identidad = IdentidadNodo.generar()
    motor = MotorMalla(identidad.id_nodo)
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())

    almacen = AlmacenSQLite(ruta)
    recibir = RecibirSobre(motor, almacen, TransporteMudo(), AuditoriaMemoria())
    await recibir.recibir(sobre)
    almacen.cerrar()

    reabierto = AlmacenSQLite(ruta)
    recibir_2 = RecibirSobre(motor, reabierto, TransporteMudo(), AuditoriaMemoria())
    decision = await recibir_2.recibir(sobre)
    assert str(decision.resultado) == "duplicado"
    assert len(await reabierto.pendientes()) == 1


async def test_guardar_dos_veces_el_mismo_id_no_duplica(tmp_path):
    almacen = AlmacenSQLite(tmp_path / "s.sqlite3")
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    assert await almacen.guardar(sobre) is True
    assert await almacen.guardar(sobre) is False
    assert len(await almacen.pendientes()) == 1


async def test_marcar_entregado_saca_de_pendientes(tmp_path):
    almacen = AlmacenSQLite(tmp_path / "s.sqlite3")
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    await almacen.guardar(sobre)
    assert await almacen.marcar_entregados([sobre.id_mensaje]) == 1
    assert await almacen.pendientes() == []
    # Sigue siendo "visto": no debe volver a entrar por otro camino.
    assert sobre.id_mensaje in await almacen.ids_vistos()


async def test_listar_desde_pagina_por_secuencia(tmp_path):
    almacen = AlmacenSQLite(tmp_path / "s.sqlite3")
    sobres = [
        crear_sobre_firmado(IdentidadNodo.generar(), reporte(texto=f"evento {i}").a_dict())
        for i in range(5)
    ]
    for sobre in sobres:
        await almacen.guardar(sobre)

    primera = await almacen.listar_desde(0, 2)
    assert [r.sobre.id_mensaje for r in primera] == [s.id_mensaje for s in sobres[:2]]

    segunda = await almacen.listar_desde(primera[-1].secuencia, 10)
    assert [r.sobre.id_mensaje for r in segunda] == [s.id_mensaje for s in sobres[2:]]
    assert await almacen.ultima_secuencia() == 5
