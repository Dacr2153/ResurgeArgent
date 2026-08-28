"""Tests de integración del adaptador REST (FastAPI TestClient)."""

import pytest
from fastapi.testclient import TestClient

from agente_ingesta.adaptadores.entrada.api_rest import crear_app
from agente_ingesta.adaptadores.llm.extractor_nulo import ExtractorNulo
from agente_ingesta.adaptadores.salida.publicador_log import PublicadorLog
from agente_ingesta.adaptadores.salida.repositorio_memoria import RepositorioMemoria
from agente_ingesta.aplicacion.casos_uso.ingerir_reportes import IngerirReportes
from agente_ingesta.dominio import ConfigVentana, MotorIngesta
from nucleo.auditoria import AuditoriaMemoria

REPORTE_VALIDO = {
    "fuente": {"id": "ciudadano-1", "tipo": "ciudadano"},
    "canal": "sms",
    "texto": "Hay un incendio grande cerca del puente, urgente",
}


@pytest.fixture
def client():
    motor = MotorIngesta(ConfigVentana(limite=100, segundos=60.0))
    caso = IngerirReportes(
        motor, ExtractorNulo(), AuditoriaMemoria(), PublicadorLog(), RepositorioMemoria()
    )
    return TestClient(crear_app(caso))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ingesta_happy_path(client):
    r = client.post("/ingesta", json={"reportes": [REPORTE_VALIDO]})
    assert r.status_code == 200
    body = r.json()
    assert body["aceptados"] == 1
    assert len(body["reportes"]) == 1
    assert body["reportes"][0]["fuente"]["id"] == "ciudadano-1"


def test_ingesta_lote_vacio(client):
    r = client.post("/ingesta", json={"reportes": []})
    assert r.status_code == 200
    assert r.json() == {"aceptados": 0, "reportes": []}


def test_ingesta_sin_body_usa_lote_vacio(client):
    r = client.post("/ingesta", json={})
    assert r.status_code == 200
    assert r.json()["aceptados"] == 0


def test_ingesta_reportes_no_es_lista_devuelve_422(client):
    r = client.post("/ingesta", json={"reportes": "no-es-una-lista"})
    assert r.status_code == 422


def test_ingesta_item_malformado_se_descarta_sin_reventar(client):
    payload = {
        "reportes": [
            REPORTE_VALIDO,
            {"fuente": {"id": "", "tipo": "ciudadano"}, "canal": "sms", "texto": ""},
        ]
    }
    r = client.post("/ingesta", json=payload)
    assert r.status_code == 200
    assert r.json()["aceptados"] == 1


def test_ingesta_reporte_de_sensor_no_requiere_texto(client):
    payload = {
        "reportes": [
            {
                "fuente": {"id": "sensor-rio-1", "tipo": "sensor"},
                "canal": "sensor",
                "datos_sensor": {
                    "descripcion": "Nivel de río sobre umbral",
                    "categoria": "Geo",
                    "severidad": "Severe",
                    "ubicacion": {"lat": 4.6, "lon": -74.08},
                },
            }
        ]
    }
    r = client.post("/ingesta", json=payload)
    assert r.status_code == 200
    assert r.json()["aceptados"] == 1
