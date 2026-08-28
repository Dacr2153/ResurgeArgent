"""Listado de operaciones: la cola que lee el tablero del coordinador.

Hasta ahora la API solo servía el detalle por id, así que el tablero no tenía de
dónde leer la cola completa. Estas pruebas cubren el nuevo `GET /operaciones` y
su filtro de alcance.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agente_orquestador.adaptadores.entrada.api_rest import crear_app
from agente_orquestador.adaptadores.salida.repositorio_memoria import (
    RepositorioOperacionesMemoria,
)
from agente_orquestador.config.contenedor import construir_contenedor
from agente_orquestador.config.settings import Settings
from agente_orquestador.dominio.entidades import Operacion
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.value_objects import PuntuacionTriage


def operacion(incidente_id: str, posicion: int, distancia_km: float | None) -> Operacion:
    op = Operacion(incidente_id=incidente_id, correlacion_id="COR-1")
    op.transicionar(EstadoIncidente.VERIFICADO, motivo="corroborado")
    if distancia_km is not None:
        op.datos["ruta"] = {"distancia_km": distancia_km}
    op.transicionar(EstadoIncidente.LOCALIZADO, motivo="localizado")
    op.puntuacion = PuntuacionTriage(
        incidente_id=incidente_id, puntuacion=1.0 - posicion / 10, posicion=posicion
    )
    op.transicionar(EstadoIncidente.PRIORIZADO, motivo=f"posición {posicion}")
    return op


@pytest.fixture
def repositorio() -> RepositorioOperacionesMemoria:
    return RepositorioOperacionesMemoria()


@pytest.fixture
def client(repositorio) -> TestClient:
    contenedor = construir_contenedor(
        settings=Settings(llm_proveedor="nulo"), repositorio=repositorio
    )
    return TestClient(crear_app(contenedor))


async def test_sin_operaciones_la_lista_es_vacia(client):
    cuerpo = client.get("/operaciones").json()

    assert cuerpo["total"] == 0
    assert cuerpo["operaciones"] == []


async def test_van_en_orden_de_triage(client, repositorio):
    await repositorio.guardar(operacion("INC-3", posicion=3, distancia_km=1.0))
    await repositorio.guardar(operacion("INC-1", posicion=1, distancia_km=1.0))

    cuerpo = client.get("/operaciones").json()

    assert [o["incidente_id"] for o in cuerpo["operaciones"]] == ["INC-1", "INC-3"]


async def test_el_alcance_de_zona_recorta_por_distancia(client, repositorio):
    await repositorio.guardar(operacion("INC-1", posicion=1, distancia_km=1.2))
    await repositorio.guardar(operacion("INC-2", posicion=2, distancia_km=8.0))

    cuerpo = client.get("/operaciones", params={"alcance": "zona", "radio_km": 3}).json()

    assert [o["incidente_id"] for o in cuerpo["operaciones"]] == ["INC-1"]


async def test_una_operacion_sin_ruta_queda_fuera_de_la_zona(client, repositorio):
    await repositorio.guardar(operacion("INC-9", posicion=1, distancia_km=None))

    zona = client.get("/operaciones", params={"alcance": "zona"}).json()
    general = client.get("/operaciones", params={"alcance": "general"}).json()

    assert zona["total"] == 0
    assert general["total"] == 1


async def test_alcance_invalido_es_422(client):
    assert client.get("/operaciones", params={"alcance": "planeta"}).status_code == 422
