"""Tests de GeocodificadorNominatim y LimitadorRitmo: nunca sale a la red.

La forma de la respuesta JSON usada como doble es la que devuelve realmente
Nominatim con ``format=jsonv2`` (una lista de resultados, cada uno con
``lat``/``lon`` como strings) — ver
https://nominatim.org/release-docs/latest/api/Search/.
"""

from __future__ import annotations

import asyncio
import time

import httpx2 as httpx
import pytest

from agente_geoespacial.adaptadores.salida.geocodificador_nominatim import (
    GeocodificadorNominatim,
    LimitadorRitmo,
)


def _respuesta_jsonv2(lat: str = "4.7109886", lon: str = "-74.0721318") -> list[dict]:
    """Forma real (recortada a los campos que usa el adaptador) de un
    resultado de Nominatim jsonv2."""
    return [
        {
            "place_id": 123456,
            "licence": "Data © OpenStreetMap contributors, ODbL 1.0.",
            "osm_type": "way",
            "osm_id": 987654,
            "lat": lat,
            "lon": lon,
            "category": "highway",
            "type": "primary",
            "place_rank": 26,
            "importance": 0.3,
            "addresstype": "road",
            "name": "Carrera 7",
            "display_name": "Carrera 7, La Candelaria, Bogotá, Colombia",
            "boundingbox": ["4.7100000", "4.7120000", "-74.0730000", "-74.0710000"],
        }
    ]


def _cliente(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_geocodifica_direccion_valida():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("ResurgeAgent")
        assert request.url.params["q"] == "Carrera 7, Bogotá"
        assert request.url.params["format"] == "jsonv2"
        assert request.url.params["limit"] == "1"
        return httpx.Response(200, json=_respuesta_jsonv2())

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("Carrera 7, Bogotá")

    assert punto is not None
    assert punto.lat == pytest.approx(4.7109886)
    assert punto.lon == pytest.approx(-74.0721318)


@pytest.mark.asyncio
async def test_user_agent_propio_va_siempre_en_la_cabecera():
    capturado = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        capturado["user_agent"] = request.headers.get("user-agent")
        return httpx.Response(200, json=_respuesta_jsonv2())

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler),
        user_agent="MiApp/1.0 (contacto@ejemplo.com)",
        limitador=LimitadorRitmo(min_intervalo_seg=0.0),
    )

    await geocodificador.geocodificar("cualquier calle")

    assert capturado["user_agent"] == "MiApp/1.0 (contacto@ejemplo.com)"


@pytest.mark.asyncio
async def test_respuesta_vacia_devuelve_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("una dirección que no existe en ningún lado")

    assert punto is None


@pytest.mark.asyncio
async def test_direccion_vacia_no_llama_al_servicio():
    llamados: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        llamados.append(str(request.url))
        return httpx.Response(200, json=[])

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("   ")

    assert punto is None
    assert llamados == []


@pytest.mark.asyncio
async def test_servicio_caido_devuelve_none_no_lanza():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no se pudo conectar", request=request)

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("Carrera 7, Bogotá")

    assert punto is None


@pytest.mark.asyncio
async def test_timeout_devuelve_none_no_lanza():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("tardó demasiado", request=request)

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("Carrera 7, Bogotá")

    assert punto is None


@pytest.mark.asyncio
async def test_status_http_de_error_devuelve_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="blocked")

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("Carrera 7, Bogotá")

    assert punto is None


@pytest.mark.asyncio
async def test_respuesta_sin_lat_lon_utilizable_devuelve_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"display_name": "algo raro, sin coordenadas"}])

    geocodificador = GeocodificadorNominatim(
        cliente=_cliente(handler), limitador=LimitadorRitmo(min_intervalo_seg=0.0)
    )

    punto = await geocodificador.geocodificar("Carrera 7, Bogotá")

    assert punto is None


@pytest.mark.asyncio
async def test_limitador_de_ritmo_espera_de_verdad_entre_llamadas():
    """Política de Nominatim: máximo una petición por segundo. Aquí se prueba
    con un intervalo reducido (0.2 s) para que el test sea rápido, pero se mide
    tiempo real transcurrido, no un mock del reloj: si el limitador no
    esperara, esta prueba fallaría."""
    limitador = LimitadorRitmo(min_intervalo_seg=0.2)

    inicio = time.monotonic()
    await limitador.esperar()
    await limitador.esperar()
    await limitador.esperar()
    transcurrido = time.monotonic() - inicio

    # Tres llamadas con intervalo mínimo 0.2s: al menos 0.4s entre la primera
    # y la tercera (la primera no espera, solo marca el reloj).
    assert transcurrido >= 0.4


@pytest.mark.asyncio
async def test_limitador_de_ritmo_no_espera_si_ya_paso_suficiente_tiempo():
    limitador = LimitadorRitmo(min_intervalo_seg=0.1)

    await limitador.esperar()
    await asyncio.sleep(0.15)  # ya pasó más que el intervalo mínimo

    inicio = time.monotonic()
    await limitador.esperar()
    transcurrido = time.monotonic() - inicio

    assert transcurrido < 0.05
