"""Entidades del dominio logístico."""

from __future__ import annotations

from dataclasses import dataclass, field

from agente_logistica.dominio.value_objects import Ubicacion

# Estados de una operación logística.
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_PLANIFICADA = "PLANIFICADA"
ESTADO_EN_TRANSITO = "EN_TRANSITO"
ESTADO_COMPLETADA = "COMPLETADA"
ESTADO_BLOQUEADA = "BLOQUEADA"
ESTADO_CANCELADA = "CANCELADA"
ESTADO_REQUIERE_REPLANIFICACION = "REQUIERE_REPLANIFICACION"


@dataclass(frozen=True)
class Asignacion:
    """Asignación producida por el Agente 7 (no debe modificarse aquí)."""

    id: str
    necesidad_id: str
    recurso_id: str
    tipo: str
    origen_id: str
    destino_id: str
    origen: Ubicacion
    destino: Ubicacion
    cantidad: float
    unidad: str
    prioridad: int


@dataclass(frozen=True)
class Vehiculo:
    id: str
    tipo: str
    capacidad: float
    unidad_capacidad: str
    ubicacion: Ubicacion
    disponible: bool = True
    restricciones: tuple = ()


@dataclass(frozen=True)
class Ruta:
    origen_id: str
    destino_id: str
    nodos: tuple
    distancia: float
    tiempo_estimado: float


@dataclass(frozen=True)
class OperacionLogistica:
    id: str
    asignacion_id: str
    vehiculo_id: str | None
    ruta: Ruta | None
    cantidad: float
    viajes: int
    prioridad: int
    estado: str
    advertencias: tuple = ()
    motivo: str | None = None


@dataclass(frozen=True)
class PlanLogistico:
    id: str
    operaciones: list[OperacionLogistica] = field(default_factory=list)
    estado: str = ESTADO_PLANIFICADA
    advertencias: list = field(default_factory=list)
    fecha_generacion: str = ""


@dataclass(frozen=True)
class Arista:
    origen: str
    destino: str
    distancia: float
    tiempo: float
    estado: str
    via_id: str
    riesgo: float = 0.0


@dataclass(frozen=True)
class GrafoMovilidad:
    nodos: tuple
    aristas: tuple[Arista, ...]
