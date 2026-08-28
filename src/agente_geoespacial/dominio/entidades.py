"""Entidades del dominio geoespacial. Dataclasses inmutables, sin dependencias externas."""

from __future__ import annotations

from dataclasses import dataclass, field

from nucleo.geo import Punto


@dataclass(frozen=True)
class NodoVial:
    """Intersección o punto de referencia de la red vial."""

    id: str
    ubicacion: Punto


@dataclass(frozen=True)
class TramoVial:
    """Segmento de vía entre dos nodos.

    ``bidireccional`` genera arista en ambos sentidos al construir el grafo de
    cálculo; una vía de sentido único se modela con ``bidireccional=False``.
    """

    id: str
    origen_id: str
    destino_id: str
    bidireccional: bool = True

    def __post_init__(self) -> None:
        if self.origen_id == self.destino_id:
            raise ValueError(f"tramo {self.id}: origen y destino no pueden coincidir")


@dataclass(frozen=True)
class GrafoVial:
    """Red vial completa: nodos con coordenadas + tramos que los conectan.

    Es la representación "de reposo" del grafo, la que persiste el repositorio.
    El motor de rutas la traduce a un ``networkx.DiGraph`` por consulta, porque el
    peso de cada arista depende del modo de transporte pedido y de qué vías estén
    bloqueadas en ese momento — no es un dato fijo del grafo.
    """

    nodos: dict[str, NodoVial]
    tramos: tuple[TramoVial, ...]

    def __post_init__(self) -> None:
        ids_nodos = set(self.nodos)
        for tramo in self.tramos:
            if tramo.origen_id not in ids_nodos:
                raise ValueError(f"tramo {tramo.id}: nodo origen desconocido {tramo.origen_id}")
            if tramo.destino_id not in ids_nodos:
                raise ValueError(f"tramo {tramo.id}: nodo destino desconocido {tramo.destino_id}")


@dataclass(frozen=True)
class RutaAlternativa:
    """Una opción de ruta distinta a la principal, para que el Orquestador tenga plan B."""

    nodos: tuple[str, ...]
    distancia_km: float
    duracion_min: float
    geometria: dict


@dataclass(frozen=True)
class ResultadoRuta:
    """Salida interna y completa de ``MotorRutas.calcular_ruta``.

    Es más rica que ``nucleo.esquemas.RespuestaGeo`` (que no tiene espacio para
    alternativas): el caso de uso proyecta este resultado a ``RespuestaGeo`` para
    cumplir el contrato de frontera, y usa el resto (alternativas) para auditoría
    y para la respuesta extendida del adaptador REST.
    """

    accesible: bool
    distancia_km: float = 0.0
    duracion_min: float = 0.0
    geometria: dict = field(default_factory=dict)
    vias_evitadas: tuple[str, ...] = ()
    motivo: str = ""
    alternativas: tuple[RutaAlternativa, ...] = ()


@dataclass(frozen=True)
class ZonaAfectada:
    """Una celda de la rejilla con incidentes agrupados, ya lista para exponerse."""

    celda_id: str
    incidentes_ids: tuple[str, ...]
    conteo: int
    severidad_agregada: str
