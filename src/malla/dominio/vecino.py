"""El vecino: el otro extremo de un enlace de malla.

Un vecino no es un servidor: es otro teléfono al alcance. Por eso lleva
`capacidad_lote`, que es lo que el enlace aguanta en una sola tanda. Un enlace
Bluetooth real mueve unos pocos kilobytes por segundo; mandarle cien sobres de
golpe no es más rápido, solo hace que los urgentes salgan al final.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vecino:
    """Un nodo alcanzable por algún transporte."""

    id_nodo: str
    direccion: str
    capacidad_lote: int = 20
    transporte: str = "http"

    def __post_init__(self) -> None:
        if not self.id_nodo.strip():
            raise ValueError("un vecino requiere id_nodo")
        if self.capacidad_lote < 1:
            raise ValueError(f"capacidad_lote debe ser >= 1: {self.capacidad_lote}")
