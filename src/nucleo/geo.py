"""Helpers geográficos puros compartidos por todos los agentes.

Sin dependencias externas: cualquier agente puede importarlos sin arrastrar stack.
La representación de geometrías sigue GeoJSON RFC 7946, donde las coordenadas van
en orden [lon, lat] — al revés de como se leen normalmente. Esa inversión es la
fuente de error más común al integrar agentes, así que aquí se centraliza.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RADIO_TIERRA_KM = 6371.0

TIPOS_GEOMETRIA = frozenset(
    {"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}
)


class GeometriaInvalidaError(ValueError):
    """La geometría no cumple GeoJSON RFC 7946."""


@dataclass(frozen=True, slots=True)
class Punto:
    """Coordenada geográfica. Se lee lat/lon; se serializa lon/lat (RFC 7946)."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise GeometriaInvalidaError(f"latitud fuera de rango: {self.lat}")
        if not -180.0 <= self.lon <= 180.0:
            raise GeometriaInvalidaError(f"longitud fuera de rango: {self.lon}")

    def distancia_a(self, otro: Punto) -> float:
        """Distancia Haversine en kilómetros."""
        return haversine(self.lat, self.lon, otro.lat, otro.lon)

    def a_geojson(self) -> dict:
        return {"type": "Point", "coordinates": [self.lon, self.lat]}

    @classmethod
    def desde_geojson(cls, geometria: dict) -> Punto:
        validar_geojson(geometria)
        if geometria["type"] != "Point":
            raise GeometriaInvalidaError(f"se esperaba Point, llegó {geometria['type']}")
        lon, lat = geometria["coordinates"][0], geometria["coordinates"][1]
        return cls(lat=float(lat), lon=float(lon))


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia sobre la superficie terrestre en kilómetros."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(a))


def bbox(puntos: list[Punto]) -> tuple[float, float, float, float]:
    """Caja envolvente en formato RFC 7946: (lon_min, lat_min, lon_max, lat_max)."""
    if not puntos:
        raise GeometriaInvalidaError("bbox requiere al menos un punto")
    lats = [p.lat for p in puntos]
    lons = [p.lon for p in puntos]
    return (min(lons), min(lats), max(lons), max(lats))


def centroide(puntos: list[Punto]) -> Punto:
    """Centro aritmético de un conjunto de puntos.

    Suficiente para agrupar reportes de un mismo barrio; no corrige la curvatura
    terrestre, que a escala urbana es despreciable.
    """
    if not puntos:
        raise GeometriaInvalidaError("centroide requiere al menos un punto")
    return Punto(
        lat=sum(p.lat for p in puntos) / len(puntos),
        lon=sum(p.lon for p in puntos) / len(puntos),
    )


def validar_geojson(geometria: dict) -> None:
    """Verifica que un dict sea una geometría GeoJSON válida. Lanza si no lo es."""
    if not isinstance(geometria, dict):
        raise GeometriaInvalidaError("la geometría debe ser un objeto")
    tipo = geometria.get("type")
    if tipo not in TIPOS_GEOMETRIA:
        raise GeometriaInvalidaError(f"tipo de geometría no soportado: {tipo!r}")
    coordenadas = geometria.get("coordinates")
    if coordenadas is None:
        raise GeometriaInvalidaError("falta 'coordinates'")
    if tipo == "Point":
        if not isinstance(coordenadas, (list, tuple)) or len(coordenadas) < 2:
            raise GeometriaInvalidaError("Point requiere [lon, lat]")
        lon, lat = coordenadas[0], coordenadas[1]
        if not -180.0 <= float(lon) <= 180.0 or not -90.0 <= float(lat) <= 90.0:
            raise GeometriaInvalidaError(f"coordenadas fuera de rango: {coordenadas}")
    elif not isinstance(coordenadas, (list, tuple)) or not coordenadas:
        raise GeometriaInvalidaError(f"{tipo} requiere una lista de coordenadas no vacía")
