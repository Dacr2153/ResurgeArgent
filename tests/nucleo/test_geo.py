"""Pruebas de los helpers geográficos compartidos."""

import math

import pytest

from nucleo.geo import (
    GeometriaInvalidaError,
    Punto,
    bbox,
    centroide,
    haversine,
    validar_geojson,
)

BOGOTA = Punto(lat=4.7110, lon=-74.0721)
MEDELLIN = Punto(lat=6.2442, lon=-75.5812)


def test_haversine_bogota_medellin_es_realista():
    # La distancia real en línea recta ronda los 245 km.
    assert 235 < BOGOTA.distancia_a(MEDELLIN) < 255


def test_haversine_es_simetrica():
    ida = haversine(BOGOTA.lat, BOGOTA.lon, MEDELLIN.lat, MEDELLIN.lon)
    vuelta = haversine(MEDELLIN.lat, MEDELLIN.lon, BOGOTA.lat, BOGOTA.lon)
    assert math.isclose(ida, vuelta)


def test_distancia_a_si_mismo_es_cero():
    assert BOGOTA.distancia_a(BOGOTA) == pytest.approx(0.0, abs=1e-9)


def test_geojson_invierte_el_orden_a_lon_lat():
    # RFC 7946 exige [lon, lat]; confundirlo es el error clásico de integración.
    assert BOGOTA.a_geojson() == {"type": "Point", "coordinates": [-74.0721, 4.7110]}


def test_geojson_ida_y_vuelta_conserva_el_punto():
    recuperado = Punto.desde_geojson(BOGOTA.a_geojson())
    assert recuperado == BOGOTA


@pytest.mark.parametrize("lat,lon", [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)])
def test_coordenadas_fuera_de_rango_se_rechazan(lat, lon):
    with pytest.raises(GeometriaInvalidaError):
        Punto(lat=lat, lon=lon)


def test_bbox_devuelve_lon_lat_min_max():
    assert bbox([BOGOTA, MEDELLIN]) == (-75.5812, 4.7110, -74.0721, 6.2442)


def test_centroide_queda_entre_los_puntos():
    centro = centroide([BOGOTA, MEDELLIN])
    assert min(BOGOTA.lat, MEDELLIN.lat) < centro.lat < max(BOGOTA.lat, MEDELLIN.lat)


def test_bbox_sin_puntos_falla():
    with pytest.raises(GeometriaInvalidaError):
        bbox([])


def test_validar_geojson_rechaza_tipo_desconocido():
    with pytest.raises(GeometriaInvalidaError):
        validar_geojson({"type": "Circulo", "coordinates": [0, 0]})


def test_validar_geojson_rechaza_point_incompleto():
    with pytest.raises(GeometriaInvalidaError):
        validar_geojson({"type": "Point", "coordinates": [1.0]})


def test_validar_geojson_acepta_linestring():
    validar_geojson({"type": "LineString", "coordinates": [[-74.0, 4.7], [-74.1, 4.8]]})
