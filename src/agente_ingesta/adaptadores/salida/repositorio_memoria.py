"""Repositorio en memoria: cumple ``RepositorioPort`` sin infraestructura externa."""

from __future__ import annotations

from typing import Any


class RepositorioMemoria:
    def __init__(self) -> None:
        self.lotes: list[list[dict[str, Any]]] = []

    async def guardar(self, reportes: list[dict[str, Any]]) -> None:
        self.lotes.append(reportes)
