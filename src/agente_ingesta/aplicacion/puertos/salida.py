"""Puertos de salida (protocolos)."""

from __future__ import annotations

from typing import Any, Protocol


class ExtractorPort(Protocol):
    """Estructura texto libre en español. Nunca decide qué se acepta: solo
    propone campos que el motor de dominio luego valida."""

    async def extraer(self, texto: str, contexto: dict[str, Any]) -> dict[str, Any]:
        """Devuelve categoría, urgencia, severidad, ubicación mencionada,
        personas afectadas y necesidades detectadas en ``texto``."""
        ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict[str, Any]) -> None:
        """Publica el resultado de un lote (cola, log, etc.)."""
        ...


class RepositorioPort(Protocol):
    async def guardar(self, reportes: list[dict[str, Any]]) -> None:
        """Persiste los reportes aceptados de un lote."""
        ...
