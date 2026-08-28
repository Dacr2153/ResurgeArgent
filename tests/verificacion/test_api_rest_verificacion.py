"""Tests de integración del adaptador REST (FastAPI TestClient)."""

import pytest
from fastapi.testclient import TestClient

from agente_verificacion.adaptadores.entrada.api_rest import crear_app
from agente_verificacion.adaptadores.llm.similitud_nula import SimilitudNula
from agente_verificacion.adaptadores.salida.publicador_log import PublicadorLog
from agente_verificacion.adaptadores.salida.repositorio_memoria import RepositorioMemoria
from agente_verificacion.aplicacion.casos_uso.verificar_reportes import VerificarReportes
from agente_verificacion.dominio.motor_verificacion import MotorVerificacion
from nucleo.auditoria import AuditoriaMemoria

REPORTE_BASE = {
    "texto": "Derrumbe en la vía principal, hay carros atrapados",
    "fuente": {"id": "c-1", "tipo": "ciudadano", "nombre": "Ana", "reputacion": 0.6},
    "canal": "sms",
    "ubicacion": {"lat": 4.6097, "lon": -74.0817},
    "categoria": "Rescue",
    "urgencia": "Immediate",
    "severidad": "Severe",
    "certeza": "Observed",
}


@pytest.fixture
def client():
    motor = MotorVerificacion()
    caso = VerificarReportes(
        motor, SimilitudNula(), PublicadorLog(), RepositorioMemoria(), AuditoriaMemoria()
    )
    return TestClient(crear_app(caso))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_verificacion_dos_reportes_del_mismo_hecho_se_fusionan(client):
    otro = {
        **REPORTE_BASE,
        "fuente": {"id": "c-2", "tipo": "ciudadano", "nombre": "Beto", "reputacion": 0.5},
        "texto": "Se cayó un derrumbe en la vía principal, hay carros atrapados",
        "ubicacion": {"lat": 4.6098, "lon": -74.0818},
    }
    payload = {"reportes": [REPORTE_BASE, otro]}

    r = client.post("/verificacion", json=payload)

    assert r.status_code == 200
    body = r.json()
    assert len(body["incidentes"]) == 1
    assert len(body["incidentes"][0]["source_reports"]) == 2


def test_verificacion_lote_vacio_devuelve_lista_vacia(client):
    r = client.post("/verificacion", json={"reportes": []})
    assert r.status_code == 200
    assert r.json() == {"incidentes": []}


def test_verificacion_cuerpo_invalido_devuelve_422(client):
    r = client.post("/verificacion", json={"reportes": [{"texto": "sin fuente ni canal"}]})
    assert r.status_code == 422
