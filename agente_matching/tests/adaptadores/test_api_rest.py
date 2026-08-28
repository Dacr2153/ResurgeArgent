"""Tests de integración del adaptador REST (FastAPI TestClient)."""

import pytest
from fastapi.testclient import TestClient

from agente_matching.adaptadores.entrada.api_rest import crear_app
from agente_matching.adaptadores.llm.orquestador_nulo import OrquestadorNulo
from agente_matching.adaptadores.salida.publicador_log import PublicadorLog
from agente_matching.adaptadores.salida.repositorio_memoria import RepositorioMemoria
from agente_matching.aplicacion.casos_uso.ejecutar_matching import EjecutarMatching
from agente_matching.dominio import MotorMatching

ENTRADA = {
    "necesidades": [
        {
            "id": "N1",
            "zona_id": "Z-A",
            "tipo": "agua",
            "cantidad_requerida": 100.0,
            "prioridad": 3,
            "ubicacion": {"lat": 4.7110, "lon": -74.0721},
        }
    ],
    "recursos": [
        {
            "id": "R1",
            "lugar_id": "Z-B",
            "tipo": "agua",
            "cantidad_disponible": 150.0,
            "ubicacion": {"lat": 4.6000, "lon": -74.0800},
        }
    ],
    "empresas": [
        {
            "id": "E1",
            "nombre": "Empresa A",
            "ubicacion": {"lat": 4.6500, "lon": -74.0900},
            "num_vehiculos": 20,
            "num_en_transito": 1,
        }
    ],
}


@pytest.fixture
def client():
    motor = MotorMatching(pesos={"w1": 1.0, "w2": 1.0, "w3": 100.0, "w4": 1.0})
    caso = EjecutarMatching(motor, OrquestadorNulo(), PublicadorLog(), RepositorioMemoria())
    return TestClient(crear_app(caso))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_matching_happy_path(client):
    r = client.post("/matching", json=ENTRADA)
    assert r.status_code == 200
    body = r.json()
    assert body["resumen"]["demanda_cubierta"] == 100.0
    assert body["resumen"]["demanda_sin_cubrir"] == 0.0
    assert body["supuestos"] == []
    assert body["justificaciones"] == []


def test_matching_cuerpo_no_json(client):
    r = client.post("/matching", json=[])
    assert r.status_code == 422


def test_matching_falta_campo_requerido(client):
    payload = {"necesidades": [{"id": "N1"}], "recursos": [], "empresas": []}
    r = client.post("/matching", json=payload)
    assert r.status_code == 422


def test_matching_sin_necesidades_devuelve_422(client):
    payload = {"necesidades": [], "recursos": [], "empresas": []}
    r = client.post("/matching", json=payload)
    assert r.status_code == 422
