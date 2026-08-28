"""Repositorio en memoria: cumple RepositorioPort sin infraestructura externa."""

from __future__ import annotations


class RepositorioMemoria:
    def __init__(self) -> None:
        self.incidentes: list[dict] = []

    async def guardar(self, incidentes: list[dict]) -> None:
        self.incidentes.extend(incidentes)
