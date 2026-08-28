"""Tests de integración del adaptador REST (FastAPI TestClient)."""

import pytest
from fastapi.testclient import TestClient

from agente_geoespacial.adaptadores.entrada.api_rest import crear_app
from agente_geoespacial.adaptadores.llm.interprete_nulo import InterpreteNulo
from agente_geoespacial.adaptadores.salida.publicador_log import PublicadorLog
from agente_geoespacial.aplicacion.casos_uso.analizar_zonas import AnalizarZonas
from agente_geoespacial.aplicacion.casos_uso.resolver_ruta import ResolverRuta
from agente_geoespacial.dominio.entidades import GrafoVial, NodoVial, TramoVial
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from agente_geoespacial.dominio.motor_zonas import MotorZonas
from nucleo.auditoria import AuditoriaMemoria
from nucleo.geo import Punto


def _grafo() -> GrafoVial:
    """N1, N2, N3 en escuadra (no colineales): ver docstring homónimo en
    test_resolver_ruta.py. Con puntos colineales, bloquear la diagonal T3 no
    cambiaría la distancia de forma perceptible aunque el bloqueo sí se aplique.
    """
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7050, lon=-74.0800)),  # al norte de N1
        "N3": NodoVial(id="N3", ubicacion=Punto(lat=4.7050, lon=-74.0700)),  # al este de N2
    }
    tramos = (
        TramoVial(id="T1", origen_id="N1", destino_id="N2"),
        TramoVial(id="T2", origen_id="N2", destino_id="N3"),
        TramoVial(id="T3", origen_id="N1", destino_id="N3"),  # diagonal, más corta
    )
    return GrafoVial(nodos=nodos, tramos=tramos)


@pytest.fixture
def client():
    grafo = _grafo()
    motor_rutas = MotorRutas(grafo)
    motor_zonas = MotorZonas(tamano_celda_grados=0.1)
    resolver_ruta = ResolverRuta(
        motor=motor_rutas,
        llm=InterpreteNulo(),
        publicador=PublicadorLog(),
        auditoria=AuditoriaMemoria(),
    )
    analizar_zonas = AnalizarZonas(motor=motor_zonas)
    return TestClient(crear_app((resolver_ruta, analizar_zonas)))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_rutas_happy_path(client):
    payload = {
        "origen": {"lat": 4.7000, "lon": -74.0800},
        "destino": {"lat": 4.7050, "lon": -74.0700},
        "modo": "auto",
    }
    r = client.post("/rutas", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["accesible"] is True
    assert body["geometria"]["type"] == "LineString"
    assert "alternativas" in body


def test_rutas_con_reporte_de_bloqueo_evita_la_via(client):
    payload = {
        "origen": {"lat": 4.7000, "lon": -74.0800},
        "destino": {"lat": 4.7050, "lon": -74.0700},
        "reportes_bloqueo": ["la via:T3 esta bloqueada por un derrumbe"],
    }
    r = client.post("/rutas", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "T3" in body["vias_evitadas"]


def test_rutas_evitar_zonas_bloquea_la_via_y_alarga_la_ruta(client):
    directa = client.post(
        "/rutas",
        json={
            "origen": {"lat": 4.7000, "lon": -74.0800},
            "destino": {"lat": 4.7050, "lon": -74.0700},
        },
    ).json()
    desviada = client.post(
        "/rutas",
        json={
            "origen": {"lat": 4.7000, "lon": -74.0800},
            "destino": {"lat": 4.7050, "lon": -74.0700},
            "evitar_zonas": ["T3"],
        },
    ).json()

    assert desviada["vias_evitadas"] == ["T3"]
    assert desviada["distancia_km"] > directa["distancia_km"]


def test_rutas_evitar_zonas_y_reportes_bloqueo_se_acumulan(client):
    r = client.post(
        "/rutas",
        json={
            "origen": {"lat": 4.7000, "lon": -74.0800},
            "destino": {"lat": 4.7050, "lon": -74.0700},
            "evitar_zonas": ["T3"],
            "reportes_bloqueo": ["la via:T2 quedo tapada por el derrumbe"],
        },
    )
    assert r.status_code == 200
    assert set(r.json()["vias_evitadas"]) == {"T3", "T2"}


def test_rutas_punto_fuera_del_grafo_devuelve_422(client):
    payload = {
        "origen": {"lat": -33.45, "lon": -70.66},
        "destino": {"lat": 4.7050, "lon": -74.0700},
    }
    r = client.post("/rutas", json=payload)
    assert r.status_code == 422


def test_rutas_cuerpo_invalido_devuelve_422(client):
    r = client.post("/rutas", json={"origen": {"lat": 4.7}})
    assert r.status_code == 422


def test_zonas_happy_path(client):
    payload = {
        "incidentes": [
            {
                "categoria": "Infra",
                "severidad": "Severe",
                "urgencia": "Immediate",
                "ubicacion": {"lat": 4.70, "lon": -74.08},
                "confianza": 0.9,
                "reportes_origen": ["r1"],
                "resumen": "puente caido",
            }
        ]
    }
    r = client.post("/zonas", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    assert body["features"][0]["properties"]["conteo_incidentes"] == 1


def test_zonas_sin_incidentes_devuelve_feature_collection_vacio(client):
    r = client.post("/zonas", json={"incidentes": []})
    assert r.status_code == 200
    assert r.json() == {"type": "FeatureCollection", "features": []}
