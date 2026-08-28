"""Tests del endpoint POST /geocodificar. No sale a la red: usa un doble de
GeocodificadorPort (la parte que sí llama a Nominatim ya se prueba en
test_geocodificador_nominatim.py)."""

from __future__ import annotations

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


class GeocodificadorFalso:
    def __init__(self, punto: Punto | None):
        self._punto = punto
        self.direcciones_pedidas: list[str] = []

    async def geocodificar(self, direccion: str) -> Punto | None:
        self.direcciones_pedidas.append(direccion)
        return self._punto


def _grafo() -> GrafoVial:
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7100, lon=-74.0700)),
    }
    tramos = (TramoVial(id="T1", origen_id="N1", destino_id="N2"),)
    return GrafoVial(nodos=nodos, tramos=tramos)


def _use_cases():
    grafo = _grafo()
    resolver_ruta = ResolverRuta(
        motor=MotorRutas(grafo),
        llm=InterpreteNulo(),
        publicador=PublicadorLog(),
        auditoria=AuditoriaMemoria(),
    )
    analizar_zonas = AnalizarZonas(motor=MotorZonas(tamano_celda_grados=0.1))
    return resolver_ruta, analizar_zonas


def test_geocodificar_devuelve_el_punto():
    geocodificador = GeocodificadorFalso(Punto(lat=4.71, lon=-74.07))
    client = TestClient(crear_app(_use_cases(), geocodificador))

    r = client.post("/geocodificar", json={"direccion": "Carrera 7, Bogotá"})

    assert r.status_code == 200
    body = r.json()
    assert body["punto"] == {"type": "Point", "coordinates": [-74.07, 4.71]}
    assert geocodificador.direcciones_pedidas == ["Carrera 7, Bogotá"]


def test_geocodificar_sin_resultado_devuelve_punto_null():
    geocodificador = GeocodificadorFalso(None)
    client = TestClient(crear_app(_use_cases(), geocodificador))

    r = client.post("/geocodificar", json={"direccion": "una dirección inexistente en ningún lado"})

    assert r.status_code == 200
    assert r.json() == {"punto": None}


def test_geocodificar_sin_geocodificador_configurado_devuelve_503():
    client = TestClient(crear_app(_use_cases()))  # sin segundo argumento

    r = client.post("/geocodificar", json={"direccion": "Carrera 7, Bogotá"})

    assert r.status_code == 503


def test_geocodificar_direccion_vacia_es_422():
    geocodificador = GeocodificadorFalso(None)
    client = TestClient(crear_app(_use_cases(), geocodificador))

    r = client.post("/geocodificar", json={"direccion": ""})

    assert r.status_code == 422


@pytest.mark.parametrize("payload", [{}, {"direccion": None}])
def test_geocodificar_cuerpo_invalido_es_422(payload):
    geocodificador = GeocodificadorFalso(None)
    client = TestClient(crear_app(_use_cases(), geocodificador))

    r = client.post("/geocodificar", json=payload)

    assert r.status_code == 422
