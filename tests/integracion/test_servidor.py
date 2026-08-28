"""Pruebas de la aplicación montada, tal como la ve el frontend.

Existen porque todas las demás inyectan sus dobles, y eso escondía dos fallos que
solo aparecían al levantar el servidor de verdad: el agente geoespacial llegaba
como una tupla y fallaba en toda petición, y sin CORS el navegador bloqueaba cada
llamada antes de que saliera.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main

DATOS = Path(__file__).resolve().parents[2] / "datos" / "reportes_demo.json"


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(main.crear_app())


@pytest.fixture
def reportes() -> list[dict]:
    with DATOS.open(encoding="utf-8") as archivo:
        return json.load(archivo)["reportes"]


def test_salud_monta_los_cinco_agentes(cliente):
    cuerpo = cliente.get("/salud").json()

    assert cuerpo["estado"] == "ok"
    assert "agente_orquestador" in cuerpo["agentes"]
    assert "agente_geoespacial" in cuerpo["agentes"]


def test_el_frontend_puede_hablar_con_la_api(cliente):
    """Sin CORS el navegador ni siquiera llega a enviar la petición."""
    respuesta = cliente.options(
        "/orquestador/emergencias",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_un_origen_desconocido_no_pasa(cliente):
    respuesta = cliente.options(
        "/orquestador/emergencias",
        headers={
            "Origin": "http://malicioso.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert respuesta.headers.get("access-control-allow-origin") is None


def test_la_saga_completa_los_tres_pasos_en_el_servidor(cliente, reportes):
    """El agente geoespacial descubierto tiene que cumplir su puerto.

    Antes llegaba como tupla y fallaba con AttributeError en cada petición, con
    la operación degradada de forma permanente sin que nadie lo notara.
    """
    respuesta = cliente.post("/orquestador/emergencias", json={"entrada": {"reportes": reportes}})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    pasos = {paso["nombre"]: paso["estado"] for paso in cuerpo["saga"]["pasos"]}
    assert pasos == {
        "ingesta": "completado",
        "verificacion": "completado",
        "geoespacial": "completado",
    }
    assert cuerpo["degradada"] is False


def test_el_lote_produce_dos_incidentes_pendientes_de_firma(cliente, reportes):
    cuerpo = cliente.post(
        "/orquestador/emergencias", json={"entrada": {"reportes": reportes}}
    ).json()

    assert cuerpo["estado_operacion"] == "pendiente_aprobacion"
    assert len(cuerpo["incidentes"]) == 2
    assert all(incidente["requiere_firma"] for incidente in cuerpo["incidentes"])


def test_la_traza_del_servidor_cubre_a_los_agentes_delegados(cliente, reportes):
    """Un solo hilo de correlación, no uno por agente."""
    cuerpo = cliente.post(
        "/orquestador/emergencias", json={"entrada": {"reportes": reportes}}
    ).json()

    auditoria = cliente.get(f"/orquestador/auditoria/{cuerpo['correlacion_id']}").json()
    eventos = auditoria.get("eventos", auditoria if isinstance(auditoria, list) else [])
    agentes = {evento["agente"] for evento in eventos}

    assert "agente-1-orquestador" in agentes
    assert "agente-2-ingesta" in agentes, "los agentes delegados deben escribir en la misma traza"


def test_el_gate_humano_se_sostiene_a_traves_de_la_api(cliente, reportes):
    cuerpo = cliente.post(
        "/orquestador/emergencias", json={"entrada": {"reportes": reportes}}
    ).json()
    objetivo = cuerpo["incidentes"][0]["incidente_id"]

    firmada = cliente.post(
        "/orquestador/decisiones",
        json={
            "incidente_id": objetivo,
            "aprobada": True,
            "coordinador_id": "coord-ungrd-07",
            "justificacion": "Recursos disponibles",
        },
    )

    assert firmada.status_code == 200
    assert firmada.json()["estado"] == "asignado"


def test_una_firma_sin_coordinador_se_rechaza_en_la_api(cliente, reportes):
    cuerpo = cliente.post(
        "/orquestador/emergencias", json={"entrada": {"reportes": reportes}}
    ).json()
    objetivo = cuerpo["incidentes"][0]["incidente_id"]

    respuesta = cliente.post(
        "/orquestador/decisiones",
        json={
            "incidente_id": objetivo,
            "aprobada": True,
            "coordinador_id": "",
            "justificacion": "sin responsable",
        },
    )

    assert respuesta.status_code == 422
