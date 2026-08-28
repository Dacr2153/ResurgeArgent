"""Repositorio en memoria del grafo vial: cumple ``RepositorioGrafoPort`` sin infraestructura.

En producción este puerto lo implementaría un repositorio que carga la red vial
de OpenStreetMap (ver ``README.md`` del agente); aquí basta con envolver el
``GrafoVial`` que ya se construyó en memoria, típicamente para tests o para el
grafo de demostración del contenedor.
"""

from __future__ import annotations

from agente_geoespacial.dominio.entidades import GrafoVial


class RepositorioGrafoMemoria:
    def __init__(self, grafo: GrafoVial) -> None:
        self._grafo = grafo

    async def obtener_grafo(self) -> GrafoVial:
        return self._grafo
