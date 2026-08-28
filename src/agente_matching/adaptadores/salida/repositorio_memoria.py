"""Repositorio en memoria: cumple RepositorioPort sin infraestructura externa."""

from __future__ import annotations


class RepositorioMemoria:
    def __init__(self):
        self.resultados: list[dict] = []

    async def guardar(self, resultado: dict) -> None:
        self.resultados.append(resultado)
