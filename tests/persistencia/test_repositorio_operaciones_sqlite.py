"""El repositorio de operaciones en SQLite: ida y vuelta sin pérdida."""

from __future__ import annotations

import pytest

from agente_orquestador.adaptadores.salida.repositorio_sqlite import (
    RepositorioOperacionesSQLite,
)
from agente_orquestador.dominio.entidades import Operacion
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.value_objects import PuntuacionTriage
from nucleo.esquemas import DecisionHumana


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "operaciones.db"


def operacion(incidente_id: str = "INC-1", posicion: int = 1) -> Operacion:
    op = Operacion(incidente_id=incidente_id, correlacion_id="COR-1")
    op.transicionar(EstadoIncidente.VERIFICADO, motivo="corroborado")
    op.transicionar(EstadoIncidente.LOCALIZADO, motivo="ruta resuelta")
    op.datos["ruta"] = {"distancia_km": 2.4}
    op.puntuacion = PuntuacionTriage(
        incidente_id=incidente_id,
        puntuacion=0.9231456789,
        componentes={"severidad": 0.45},
        posicion=posicion,
    )
    op.transicionar(EstadoIncidente.PRIORIZADO, motivo=f"posición {posicion}")
    op.transicionar(EstadoIncidente.PENDIENTE_APROBACION, motivo="a la espera de firma")
    return op


async def test_guardar_y_obtener_conserva_historial_y_visitas(ruta):
    repositorio = RepositorioOperacionesSQLite(ruta)
    await repositorio.guardar(operacion())

    recuperada = await repositorio.obtener("INC-1")

    assert recuperada.estado is EstadoIncidente.PENDIENTE_APROBACION
    assert len(recuperada.historial) == 4
    assert recuperada.visitas[EstadoIncidente.VERIFICADO] == 1
    assert recuperada.datos["ruta"]["distancia_km"] == 2.4


async def test_la_puntuacion_no_pierde_precision(ruta):
    repositorio = RepositorioOperacionesSQLite(ruta)
    await repositorio.guardar(operacion())

    recuperada = await repositorio.obtener("INC-1")

    assert recuperada.puntuacion.puntuacion == 0.9231456789


async def test_la_firma_del_coordinador_sobrevive(ruta):
    op = operacion()
    decision = DecisionHumana(
        incidente_id="INC-1",
        aprobada=True,
        coordinador_id="coord-7",
        justificacion="brigada disponible",
    )
    op.transicionar(EstadoIncidente.ASIGNADO, decision=decision, motivo="Ana Q.")
    repositorio = RepositorioOperacionesSQLite(ruta)
    await repositorio.guardar(op)

    recuperada = await repositorio.obtener("INC-1")

    assert recuperada.decision.coordinador_id == "coord-7"
    assert recuperada.decision.aprobada is True
    assert recuperada.estado is EstadoIncidente.ASIGNADO


async def test_un_reinicio_conserva_las_operaciones(ruta):
    primera = RepositorioOperacionesSQLite(ruta)
    await primera.guardar(operacion())

    segunda = RepositorioOperacionesSQLite(ruta)
    recuperada = await segunda.obtener("INC-1")

    assert recuperada is not None
    assert recuperada.correlacion_id == "COR-1"


async def test_obtener_lo_que_no_existe_devuelve_none(ruta):
    assert await RepositorioOperacionesSQLite(ruta).obtener("INC-NADA") is None


async def test_por_correlacion_filtra(ruta):
    repositorio = RepositorioOperacionesSQLite(ruta)
    await repositorio.guardar(operacion("INC-1"))
    otra = Operacion(incidente_id="INC-2", correlacion_id="COR-2")
    await repositorio.guardar(otra)

    assert [o.incidente_id for o in await repositorio.por_correlacion("COR-1")] == ["INC-1"]


async def test_listar_va_en_orden_de_triage(ruta):
    repositorio = RepositorioOperacionesSQLite(ruta)
    await repositorio.guardar(operacion("INC-3", posicion=3))
    await repositorio.guardar(operacion("INC-1", posicion=1))
    sin_triage = Operacion(incidente_id="INC-9", correlacion_id="COR-1")
    await repositorio.guardar(sin_triage)

    assert [o.incidente_id for o in await repositorio.listar()] == ["INC-1", "INC-3", "INC-9"]
