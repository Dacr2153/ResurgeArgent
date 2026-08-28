"""Puertos de entrada del Agente 8."""

from __future__ import annotations

from typing import Protocol


class PlanificarLogisticaUseCase(Protocol):
    async def ejecutar(self, entrada_json: dict) -> dict:
        """Planifica la logística a partir de asignaciones, vehículos y restricciones."""
        ...
