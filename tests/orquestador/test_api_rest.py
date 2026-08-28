"""Tests de integración del adaptador REST del Orquestador (FastAPI TestClient)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agente_orquestador.adaptadores.entrada.api_rest import crear_app
from agente_orquestador.config.contenedor import construir_contenedor
from agente_orquestador.config.settings import Settings
from agente_orquestador.dominio.estados import EstadoIncidente
from tests.orquestador.dobles import GeoespacialFake, IngestaFake, VerificacionFake

EMERGENCIA = {
    "entrada": {"canal": "sms", "texto": "edificio colapsado en la calle 26"},
    "correlacion_id": "COR-API",
    "origen_despacho": {"lat": 4.65, "lon": -74.09},
}


@pytest.fixture
def contenedor():
    return construir_contenedor(
        settings=Settings(llm_proveedor="nulo"),
        ingesta=IngestaFake(),
        verificacion=VerificacionFake(),
        geoespacial=GeoespacialFake(),
    )


@pytest.fixture
def client(contenedor):
    return TestClient(crear_app(contenedor))


def test_health(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_emergencia_devuelve_incidentes_pendientes_de_firma(client):
    respuesta = client.post("/emergencias", json=EMERGENCIA)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["correlacion_id"] == "COR-API"
    assert cuerpo["estado_operacion"] == "pendiente_aprobacion"
    assert cuerpo["incidentes"][0]["requiere_firma"] is True
    assert cuerpo["rutas"][0]["accesible"] is True


def test_emergencia_con_campo_desconocido_es_422(client):
    respuesta = client.post("/emergencias", json={**EMERGENCIA, "inventado": 1})
    assert respuesta.status_code == 422


def test_emergencia_con_coordenada_invalida_es_422(client):
    payload = {**EMERGENCIA, "origen_despacho": {"lat": 999.0, "lon": 0.0}}
    assert client.post("/emergencias", json=payload).status_code == 422


def test_decision_aprobada_asigna(client):
    client.post("/emergencias", json=EMERGENCIA)
    respuesta = client.post(
        "/decisiones",
        json={
            "incidente_id": "INC-1",
            "aprobada": True,
            "coordinador_id": "COORD-7",
            "justificacion": "unidad disponible",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == str(EstadoIncidente.ASIGNADO)


def test_decision_rechazada_no_asigna(client):
    client.post("/emergencias", json=EMERGENCIA)
    respuesta = client.post(
        "/decisiones",
        json={
            "incidente_id": "INC-1",
            "aprobada": False,
            "coordinador_id": "COORD-7",
            "justificacion": "duplicado",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == str(EstadoIncidente.DESCARTADO)


def test_rechazo_sin_justificacion_es_400(client):
    client.post("/emergencias", json=EMERGENCIA)
    respuesta = client.post(
        "/decisiones",
        json={"incidente_id": "INC-1", "aprobada": False, "coordinador_id": "COORD-7"},
    )
    assert respuesta.status_code == 400


def test_decision_sobre_incidente_desconocido_es_404(client):
    respuesta = client.post(
        "/decisiones",
        json={
            "incidente_id": "INC-404",
            "aprobada": True,
            "coordinador_id": "C",
            "justificacion": "x",
        },
    )
    assert respuesta.status_code == 404


def test_segunda_aprobacion_es_409(client):
    client.post("/emergencias", json=EMERGENCIA)
    firma = {
        "incidente_id": "INC-1",
        "aprobada": True,
        "coordinador_id": "COORD-7",
        "justificacion": "unidad disponible",
    }
    client.post("/decisiones", json=firma)
    assert client.post("/decisiones", json=firma).status_code == 409


def test_consulta_de_operacion_y_de_auditoria(client):
    client.post("/emergencias", json=EMERGENCIA)

    operacion = client.get("/operaciones/INC-1")
    assert operacion.status_code == 200
    assert operacion.json()["correlacion_id"] == "COR-API"
    assert client.get("/operaciones/INC-404").status_code == 404

    auditoria = client.get("/auditoria/COR-API")
    assert auditoria.status_code == 200
    eventos = auditoria.json()["eventos"]
    assert eventos
    assert all(e["correlacion_id"] == "COR-API" for e in eventos)


def test_el_agente_arranca_sin_los_demas_agentes_montados():
    """Sin agentes 2/3/5 el Orquestador responde, degradando la operación."""
    contenedor = construir_contenedor(settings=Settings(llm_proveedor="nulo"))
    cliente = TestClient(crear_app(contenedor))

    respuesta = cliente.post("/emergencias", json={"entrada": {}})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["saga"]["fallidos"] == ["ingesta"]
    assert cuerpo["incidentes"] == []
