"""Puertos de salida del Agente 8."""

from __future__ import annotations

from typing import Protocol

from agente_logistica.dominio.entidades import (
    Asignacion,
    GrafoMovilidad,
    PlanLogistico,
    Vehiculo,
)


class LogisticsPlannerPort(Protocol):
    def planificar(
        self,
        asignaciones: list[Asignacion],
        vehiculos: list[Vehiculo],
        restricciones: list[dict],
        grafo: GrafoMovilidad,
    ) -> PlanLogistico: ...


class GeographicProviderPort(Protocol):
    def sembrar(self, mapa: dict) -> None: ...

    def obtener_grafo(self) -> GrafoMovilidad: ...


class VehicleRepositoryPort(Protocol):
    def obtener_disponibles(self) -> list[Vehiculo]: ...

    def obtener_por_id(self, vehicle_id: str) -> Vehiculo | None: ...

    def actualizar_estado(self, vehicle_id: str, estado: str) -> None: ...


class LLMAgente8Port(Protocol):
    async def normalizar(self, json_crudo: dict) -> dict:
        """Interpreta/normaliza la entrada y marca supuestos."""
        ...

    async def explicar(self, plan: dict, contexto: dict) -> dict:
        """Explica el plan logístico y añade advertencias legibles."""
        ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict) -> None: ...
