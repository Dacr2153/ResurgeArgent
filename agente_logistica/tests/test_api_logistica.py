"""Tests de integración del endpoint REST del Agente 8."""

import pytest
from fastapi.testclient import TestClient

from agente_logistica.adaptadores.entrada.api_rest import crear_app
from agente_logistica.adaptadores.llm.orquestador_nulo import OrquestadorNulo
from agente_logistica.adaptadores.salida.geographic_provider_memoria import (
    GeographicProviderMemoria,
)
from agente_logistica.adaptadores.salida.publicador_log import PublicadorLog
from agente_logistica.aplicacion.casos_uso.planificar_logistica import PlanificarLogistica
from agente_logistica.dominio import MotorLogistica

ENTRADA = {
    "asignaciones": [
        {
            "id": "A001",
            "necesidad_id": "N001",
            "recurso_id": "R001",
            "tipo": "agua",
            "origen": {"id": "A", "latitud": 4.61, "longitud": -74.08},
            "destino": {"id": "C", "latitud": 4.65, "longitud": -74.06},
            "cantidad": 500.0,
            "unidad": "litros",
            "prioridad": 10,
        }
    ],
    "vehiculos": [
        {
            "id": "V1",
            "tipo": "camion",
            "capacidad": 1000.0,
            "unidad_capacidad": "litros",
            "ubicacion": {"latitud": 4.60, "longitud": -74.09},
            "disponible": True,
        }
    ],
    "restricciones": [],
    "mapa": {
        "nodos": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
        "aristas": [
            {
                "origen": "A",
                "destino": "B",
                "distancia": 2.0,
                "tiempo": 10.0,
                "estado": "DISPONIBLE",
                "via_id": "V1",
            },
            {
                "origen": "B",
                "destino": "C",
                "distancia": 3.0,
                "tiempo": 15.0,
                "estado": "DISPONIBLE",
                "via_id": "V2",
            },
        ],
    },
}


@pytest.fixture
def client():
    motor = MotorLogistica({"alfa": 0.5, "beta": 0.5, "gamma": 0.0, "delta": 0.0})
    caso = PlanificarLogistica(
        motor, GeographicProviderMemoria(), OrquestadorNulo(), PublicadorLog()
    )
    return TestClient(crear_app(caso))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_planificar_happy_path(client):
    r = client.post("/planificar", json=ENTRADA)
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "PLANIFICADA"
    assert body["operaciones"][0]["vehiculo_id"] == "V1"
    assert body["supuestos"] == []


def test_planificar_campo_faltante(client):
    r = client.post("/planificar", json={"asignaciones": []})
    assert r.status_code == 422
