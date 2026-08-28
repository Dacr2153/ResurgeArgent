"""Repositorio de vehículos en memoria (para replanificación futura)."""

from __future__ import annotations

from agente_logistica.dominio.entidades import Vehiculo


class VehicleRepositoryMemoria:
    def __init__(self, vehiculos: list[Vehiculo] | None = None):
        self._vehiculos: dict[str, Vehiculo] = {}
        for v in vehiculos or []:
            self._vehiculos[v.id] = v

    def sembrar(self, vehiculos: list[Vehiculo]) -> None:
        self._vehiculos = {v.id: v for v in vehiculos}

    def obtener_disponibles(self) -> list[Vehiculo]:
        return [v for v in self._vehiculos.values() if v.disponible]

    def obtener_por_id(self, vehicle_id: str) -> Vehiculo | None:
        return self._vehiculos.get(vehicle_id)

    def actualizar_estado(self, vehicle_id: str, estado: str) -> None:
        actual = self._vehiculos.get(vehicle_id)
        if actual is not None:
            self._vehiculos[vehicle_id] = Vehiculo(
                id=actual.id,
                tipo=actual.tipo,
                capacidad=actual.capacidad,
                unidad_capacidad=actual.unidad_capacidad,
                ubicacion=actual.ubicacion,
                disponible=(estado == "DISPONIBLE"),
                restricciones=actual.restricciones,
            )
