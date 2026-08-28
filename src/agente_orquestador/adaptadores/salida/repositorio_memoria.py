"""Repositorio de operaciones en memoria: cumple el puerto sin infraestructura.

Guarda la referencia viva a la `Operacion`, no una copia. Es intencionado: la
operación es una entidad mutable con historial, y el caso de uso que registra la
decisión humana necesita continuar la misma historia que abrió el procesamiento
de la emergencia, no una foto de ella.
"""

from __future__ import annotations

from agente_orquestador.dominio.entidades import Operacion


class RepositorioOperacionesMemoria:
    def __init__(self) -> None:
        self._operaciones: dict[str, Operacion] = {}

    async def guardar(self, operacion: Operacion) -> None:
        self._operaciones[operacion.incidente_id] = operacion

    async def obtener(self, incidente_id: str) -> Operacion | None:
        return self._operaciones.get(incidente_id)

    async def por_correlacion(self, correlacion_id: str) -> list[Operacion]:
        return [
            o for o in self._operaciones.values() if o.correlacion_id == correlacion_id
        ]

    def todas(self) -> list[Operacion]:
        return list(self._operaciones.values())
