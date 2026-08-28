"""Value objects del dominio logístico."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ubicacion:
    latitud: float
    longitud: float
    nodo_grafo: str | None = None
    direccion: str | None = None
