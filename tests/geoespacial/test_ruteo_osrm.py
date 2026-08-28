"""Tests de RuteadorOSRM con dobles del cliente HTTP: nunca sale a la red.

Las respuestas JSON usadas como dobles tienen la misma forma que las que
devuelve realmente ``router.project-osrm.org`` (``code``, ``routes[].geometry``
en GeoJSON, ``distance`` en metros, ``duration`` en segundos) — ver la
documentación pública de la API de rutas de OSRM.
"""

from __future__ import annotations

import httpx2 as httpx
import pytest

from agente_geoespacial.adaptadores.salida.ruteo_osrm import RuteadorOSRM
from nucleo.esquemas import ModoTransporte
from nucleo.geo import Punto

ORIGEN = Punto(lat=4.7000, lon=-74.0800)
DESTINO = Punto(lat=4.7100, lon=-74.0700)


def _respuesta_ok(distancia_m: float = 1886.6, duracion_s: float = 302.4) -> dict:
    """Forma real de una respuesta de OSRM con overview=full, geometries=geojson,
    alternatives=true: una ruta principal y una alternativa."""
    ruta = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-74.0800, 4.7000], [-74.0750, 4.7050], [-74.0700, 4.7100]],
        },
        "legs": [{"steps": [], "distance": distancia_m, "duration": duracion_s}],
        "distance": distancia_m,
        "duration": duracion_s,
        "weight": duracion_s,
        "weight_name": "routability",
    }
    alternativa = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-74.0800, 4.7000], [-74.0720, 4.7020], [-74.0700, 4.7100]],
        },
        "legs": [{"steps": [], "distance": 2200.0, "duration": 400.0}],
        "distance": 2200.0,
        "duration": 400.0,
        "weight": 400.0,
        "weight_name": "routability",
    }
    return {
        "code": "Ok",
        "routes": [ruta, alternativa],
        "waypoints": [
            {"location": [-74.0800, 4.7000]},
            {"location": [-74.0700, 4.7100]},
        ],
    }


def _cliente(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_ruta_exitosa_trae_geometria_real_y_alternativas():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "driving" in str(request.url)
        return httpx.Response(200, json=_respuesta_ok())

    ruteador = RuteadorOSRM(cliente=_cliente(handler))

    resultado = await ruteador.calcular_ruta(ORIGEN, DESTINO, ModoTransporte.AUTO)

    assert resultado is not None
    assert resultado.accesible is True
    assert resultado.geometria["type"] == "LineString"
    assert len(resultado.geometria["coordinates"]) == 3
    assert resultado.distancia_km == pytest.approx(1.8866)
    assert resultado.duracion_min == pytest.approx(302.4 / 60.0)
    assert len(resultado.alternativas) == 1
    assert resultado.alternativas[0].distancia_km == pytest.approx(2.2)


@pytest.mark.asyncio
async def test_perfil_peaton_se_mapea_a_foot():
    capturado = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        return httpx.Response(200, json=_respuesta_ok())

    ruteador = RuteadorOSRM(cliente=_cliente(handler))
    await ruteador.calcular_ruta(ORIGEN, DESTINO, ModoTransporte.PEATON)

    assert "/foot/" in capturado["url"]


@pytest.mark.asyncio
async def test_servicio_caido_devuelve_none_no_lanza():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no se pudo conectar", request=request)

    ruteador = RuteadorOSRM(cliente=_cliente(handler))

    resultado = await ruteador.calcular_ruta(ORIGEN, DESTINO, ModoTransporte.AUTO)

    assert resultado is None


@pytest.mark.asyncio
async def test_timeout_devuelve_none_no_lanza():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("tardó demasiado", request=request)

    ruteador = RuteadorOSRM(cliente=_cliente(handler))

    resultado = await ruteador.calcular_ruta(ORIGEN, DESTINO, ModoTransporte.AUTO)

    assert resultado is None


@pytest.mark.asyncio
async def test_respuesta_sin_rutas_devuelve_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "NoRoute", "routes": [], "waypoints": []})

    ruteador = RuteadorOSRM(cliente=_cliente(handler))

    resultado = await ruteador.calcular_ruta(ORIGEN, DESTINO, ModoTransporte.AUTO)

    assert resultado is None


@pytest.mark.asyncio
async def test_status_http_de_error_devuelve_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    ruteador = RuteadorOSRM(cliente=_cliente(handler))

    resultado = await ruteador.calcular_ruta(ORIGEN, DESTINO, ModoTransporte.AUTO)

    assert resultado is None


@pytest.mark.asyncio
async def test_bloqueo_sobre_la_ruta_dispara_un_segundo_llamado_con_waypoint():
    """Si el tramo bloqueado cae sobre la geometría devuelta, se reintenta
    pasando por un punto intermedio (ver limitación documentada en el módulo:
    OSRM público no admite excluir tramos, así que esto es un desvío, no una
    exclusión garantizada)."""
    llamados: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        num_puntos = str(request.url).split("/")[-1].split("?")[0].count(";") + 1
        llamados.append(num_puntos)
        if num_puntos == 2:
            # Primera llamada: la ruta directa pasa justo por el punto medio
            # del tramo bloqueado (4.7050, -74.0750).
            return httpx.Response(200, json=_respuesta_ok())
        # Segunda llamada (con waypoint intermedio): ruta distinta, ya sin
        # pasar tan cerca del bloqueo.
        desviada = _respuesta_ok(distancia_m=2500.0, duracion_s=450.0)
        desviada["routes"][0]["geometry"]["coordinates"] = [
            [-74.0800, 4.7000],
            [-74.0850, 4.7040],
            [-74.0700, 4.7100],
        ]
        return httpx.Response(200, json=desviada)

    ruteador = RuteadorOSRM(cliente=_cliente(handler))
    segmento_bloqueado = (
        Punto(lat=4.7040, lon=-74.0760),
        Punto(lat=4.7060, lon=-74.0740),
    )

    resultado = await ruteador.calcular_ruta(
        ORIGEN, DESTINO, ModoTransporte.AUTO, segmentos_bloqueados=[segmento_bloqueado]
    )

    assert llamados == [2, 3]  # segunda llamada con 3 puntos: origen, desvío, destino
    assert resultado is not None
    assert resultado.distancia_km == pytest.approx(2.5)
    assert "waypoint" in resultado.motivo


@pytest.mark.asyncio
async def test_bloqueo_lejos_de_la_ruta_no_dispara_segundo_llamado():
    llamados: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        llamados.append(str(request.url))
        return httpx.Response(200, json=_respuesta_ok())

    ruteador = RuteadorOSRM(cliente=_cliente(handler))
    # A 50+ km de la ruta: no debería disparar el desvío.
    segmento_lejano = (
        Punto(lat=-33.0, lon=-70.0),
        Punto(lat=-33.01, lon=-70.01),
    )

    resultado = await ruteador.calcular_ruta(
        ORIGEN, DESTINO, ModoTransporte.AUTO, segmentos_bloqueados=[segmento_lejano]
    )

    assert len(llamados) == 1
    assert resultado is not None
