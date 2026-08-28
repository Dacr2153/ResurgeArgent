"""Puertos de salida (protocolos)."""

from __future__ import annotations

from typing import Protocol

from agente_geoespacial.dominio.entidades import GrafoVial


class LLMInterpretePort(Protocol):
    async def interpretar(self, reportes_texto: list[str]) -> list[str]:
        """Lee reportes en español y devuelve los ids de tramo vial bloqueados.

        Solo interpreta lenguaje natural. No decide la ruta ni descarta un tramo
        por su cuenta: esa decisión es del dominio (``MotorRutas``).
        """
        ...


class RepositorioGrafoPort(Protocol):
    async def obtener_grafo(self) -> GrafoVial:
        """Entrega el grafo vial vigente."""
        ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict) -> None:
        """Publica un resultado (cola, log, etc.)."""
        ...
