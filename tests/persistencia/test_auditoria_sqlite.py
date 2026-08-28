"""La traza en SQLite: consultable y superviviente al reinicio."""

from __future__ import annotations

import pytest

from nucleo.auditoria import AuditoriaSQLite
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento


def evento(correlacion_id: str, tipo: TipoEvento, **detalle) -> EventoAuditoria:
    return EventoAuditoria(
        tipo=tipo,
        agente=Agente.ORQUESTADOR,
        correlacion_id=correlacion_id,
        detalle=detalle,
    )


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "traza.db"


async def test_registra_y_relee_por_correlacion(ruta):
    auditoria = AuditoriaSQLite(ruta)
    await auditoria.registrar(evento("COR-1", TipoEvento.TRANSICION_ESTADO, paso=1))
    await auditoria.registrar(evento("COR-2", TipoEvento.TRANSICION_ESTADO, paso=2))

    eventos = auditoria.por_correlacion("COR-1")

    assert [e.detalle["paso"] for e in eventos] == [1]


async def test_los_enums_se_rehidratan(ruta):
    auditoria = AuditoriaSQLite(ruta)
    await auditoria.registrar(evento("COR-1", TipoEvento.REPORTE_DESCARTADO, motivo="duplicado"))

    recuperado = auditoria.por_tipo("reporte_descartado")[0]

    assert recuperado.tipo is TipoEvento.REPORTE_DESCARTADO
    assert recuperado.agente is Agente.ORQUESTADOR


async def test_un_reinicio_conserva_la_traza(ruta):
    primera = AuditoriaSQLite(ruta)
    await primera.registrar(evento("COR-1", TipoEvento.ERROR, mensaje="caída del agente 3"))

    segunda = AuditoriaSQLite(ruta)

    assert [e["detalle"]["mensaje"] for e in segunda.leer()] == ["caída del agente 3"]


async def test_el_orden_es_el_de_insercion(ruta):
    auditoria = AuditoriaSQLite(ruta)
    for indice in range(5):
        await auditoria.registrar(evento("COR-1", TipoEvento.TRANSICION_ESTADO, paso=indice))

    assert [e.detalle["paso"] for e in auditoria.por_correlacion("COR-1")] == [0, 1, 2, 3, 4]
