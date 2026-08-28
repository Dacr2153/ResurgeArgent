"""Puertos de salida (protocolos)."""

from __future__ import annotations

from typing import Protocol


class SimilitudTextoPort(Protocol):
    """Opina sobre si dos textos hablan del mismo hecho. Nunca decide la fusión.

    Recibe pares `(id_a, id_b, texto_a, texto_b)` y devuelve, para cada par, un
    score de similitud semántica en [0,1] indexado por `(id_a, id_b)`. Lo
    implementan `SimilitudNula` (léxica, sin red) y `SimilitudLLM` (semántica,
    vía proveedor externo) — el caso de uso y el motor no distinguen cuál es.
    """

    async def comparar(
        self, pares: list[tuple[str, str, str, str]]
    ) -> dict[tuple[str, str], float]: ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict) -> None:
        """Publica el resultado final (cola, log, etc.)."""
        ...


class RepositorioPort(Protocol):
    async def guardar(self, incidentes: list[dict]) -> None:
        """Persiste los incidentes verificados."""
        ...
