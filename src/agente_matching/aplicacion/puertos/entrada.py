"""Puertos de entrada (protocolos)."""

from __future__ import annotations

from typing import Protocol


class EjecutarMatchingUseCase(Protocol):
    async def ejecutar(self, entrada_json: dict) -> dict:
        """Ejecuta el caso de uso completo y devuelve el resultado final."""
        ...
