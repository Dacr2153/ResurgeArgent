"""Puertos de entrada del Orquestador (protocolos)."""

from __future__ import annotations

from typing import Protocol


class ProcesarEmergenciaUseCase(Protocol):
    async def procesar(self, entrada: dict) -> dict:
        """Corre el flujo completo de una emergencia y devuelve el estado global."""
        ...


class RegistrarDecisionHumanaUseCase(Protocol):
    async def registrar(self, payload: dict) -> dict:
        """Aplica la firma del coordinador sobre un incidente pendiente."""
        ...
