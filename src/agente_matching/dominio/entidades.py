"""Entidades del dominio. Dataclasses inmutables, sin dependencias externas."""

from __future__ import annotations

from dataclasses import dataclass, field

from agente_matching.dominio.value_objects import Prioridad, Ubicacion


@dataclass(frozen=True)
class Necesidad:
    id: str
    zona_id: str
    tipo: str
    cantidad_requerida: float
    prioridad: Prioridad
    ubicacion: Ubicacion

    def __post_init__(self) -> None:
        if self.cantidad_requerida < 0:
            raise ValueError("cantidad_requerida no puede ser negativa")


@dataclass(frozen=True)
class Recurso:
    """Stock disponible en un lugar (almacén / punto de acopio)."""

    id: str
    lugar_id: str
    tipo: str
    cantidad_disponible: float
    ubicacion: Ubicacion

    def __post_init__(self) -> None:
        if self.cantidad_disponible < 0:
            raise ValueError("cantidad_disponible no puede ser negativa")


@dataclass(frozen=True)
class Empresa:
    id: str
    nombre: str
    ubicacion: Ubicacion
    num_vehiculos: int
    num_en_transito: int = 0
    zonas_cobertura: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.num_vehiculos < 0:
            raise ValueError("num_vehiculos no puede ser negativo")
        if self.num_en_transito < 0:
            raise ValueError("num_en_transito no puede ser negativo")
        if self.num_en_transito > self.num_vehiculos:
            raise ValueError("num_en_transito no puede exceder num_vehiculos")

    def flota(self, capacidad_uniforme: float) -> float:
        return self.num_vehiculos * capacidad_uniforme

    def fraccion_transito(self) -> float:
        if self.num_vehiculos == 0:
            return 0.0
        return self.num_en_transito / self.num_vehiculos

    def cubre_zona(self, zona_id: str) -> bool:
        return self.zonas_cobertura is None or zona_id in self.zonas_cobertura


@dataclass(frozen=True)
class Vehiculo:
    id: str
    empresa_id: str
    en_transito: bool = False


@dataclass(frozen=True)
class Asignacion:
    empresa_id: str
    recurso_id: str
    necesidad_id: str
    cantidad: float
    distancia_km: float
    costo_unitario: float


@dataclass(frozen=True)
class NoCubierto:
    necesidad_id: str
    cantidad: float
    causa: str


@dataclass(frozen=True)
class ResumenMatching:
    demanda_total: float
    demanda_cubierta: float
    demanda_sin_cubrir: float
    costo_total: float
    por_empresa: dict


@dataclass(frozen=True)
class ResultadoMatching:
    asignaciones: list[Asignacion] = field(default_factory=list)
    no_cubierto: list[NoCubierto] = field(default_factory=list)
    resumen: ResumenMatching | None = None
