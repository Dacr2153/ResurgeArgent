"""Value objects del dominio. Sin dependencias externas."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Ubicacion:
    """Coordenadas geográficas (latitud/longitud) con distancia Haversine en km."""

    lat: float
    lon: float

    def distancia_a(self, otra: Ubicacion) -> float:
        radio_tierra_km = 6371.0
        lat1 = math.radians(self.lat)
        lat2 = math.radians(otra.lat)
        dlat = math.radians(otra.lat - self.lat)
        dlon = math.radians(otra.lon - self.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * radio_tierra_km * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Prioridad:
    """Nivel de urgencia de una necesidad. Mayor valor = más urgente."""

    valor: int

    def __post_init__(self) -> None:
        if self.valor <= 0:
            raise ValueError("Prioridad.valor debe ser un entero mayor que 0")
