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

    async def listar(self) -> list[Operacion]:
        """Todas las operaciones, en orden de triage (posición 1 primero).

        Existe para que el tablero del coordinador tenga de dónde leer la cola
        completa: hasta ahora solo se podía pedir un incidente por id, y una cola
        que hay que consultar de uno en uno no es una cola.

        Las operaciones aún sin triage van al final: no tienen posición, y
        colocarlas arriba desplazaría a incidentes ya priorizados.
        """
        sin_triage = len(self._operaciones) + 1
        return sorted(
            self._operaciones.values(),
            key=lambda o: o.puntuacion.posicion if o.puntuacion else sin_triage,
        )

    def todas(self) -> list[Operacion]:
        return list(self._operaciones.values())
