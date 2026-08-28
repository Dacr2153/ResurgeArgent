"""Puertos de salida (protocolos)."""

from __future__ import annotations

from typing import Protocol


class LLMOrquestadorPort(Protocol):
    async def normalizar(self, json_crudo: dict) -> dict:
        """Resuelve ambigüedades, imputa faltantes y marca supuestos."""
        ...

    async def justificar(self, resultado_motor: dict, contexto: dict) -> dict:
        """Añade justificaciones legibles y detecta patrones no explicados."""
        ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict) -> None:
        """Publica el resultado final (cola, log, etc.)."""
        ...


class RepositorioPort(Protocol):
    async def guardar(self, resultado: dict) -> None:
        """Persiste el resultado final."""
        ...
