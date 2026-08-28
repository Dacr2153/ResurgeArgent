"""Motor de planificación logística (determinista, puro).

Construye un grafo de movilidad, elimina vías bloqueadas/restringidas y, para cada
asignación (ordenada por prioridad), calcula la ruta de menor costo (shortest path)
y selecciona un vehículo compatible y disponible, determinando los viajes necesarios.

El LLM no participa aquí: distancias, tiempos, rutas y viajes son calculados por el
motor, nunca inventados.
"""

from __future__ import annotations

import math

import networkx as nx

from agente_logistica.dominio.entidades import (
    ESTADO_BLOQUEADA,
    ESTADO_PLANIFICADA,
    Asignacion,
    GrafoMovilidad,
    OperacionLogistica,
    PlanLogistico,
    Ruta,
    Vehiculo,
)

MOTIVO_DESTINO_INACCESIBLE = "DESTINO_INACCESIBLE"
MOTIVO_SIN_VEHICULO_COMPATIBLE = "SIN_VEHICULO_COMPATIBLE"


class MotorLogistica:
    def __init__(self, pesos: dict[str, float]):
        self._pesos = pesos  # {"alfa", "beta", "gamma", "delta"}

    def planificar(
        self,
        asignaciones: list[Asignacion],
        vehiculos: list[Vehiculo],
        restricciones: list[dict],
        grafo: GrafoMovilidad,
    ) -> PlanLogistico:
        vias_bloqueadas = {r["via_id"] for r in restricciones if r.get("via_id")}

        g = nx.Graph()
        g.add_nodes_from(grafo.nodos)
        for arista in grafo.aristas:
            if arista.estado == "BLOQUEADA" or arista.via_id in vias_bloqueadas:
                continue
            g.add_edge(
                arista.origen,
                arista.destino,
                weight=self._costo(arista),
                distancia=arista.distancia,
                tiempo=arista.tiempo,
            )

        disponibles = [v for v in vehiculos if v.disponible]
        ordenadas = sorted(asignaciones, key=lambda a: (-a.prioridad, a.id))

        operaciones: list[OperacionLogistica] = []
        for i, a in enumerate(ordenadas, start=1):
            operaciones.append(self._planificar_operacion(a, disponibles, g, f"OP{i:03d}"))

        return PlanLogistico(
            id="PLAN_001",
            operaciones=operaciones,
            estado=ESTADO_PLANIFICADA,
            advertencias=[],
        )

    # ------------------------------------------------------------------ por operación
    def _planificar_operacion(
        self,
        a: Asignacion,
        disponibles: list[Vehiculo],
        g: nx.Graph,
        operacion_id: str,
    ) -> OperacionLogistica:
        ruta = self._ruta(g, a.origen_id, a.destino_id)
        if ruta is None:
            return OperacionLogistica(
                id=operacion_id,
                asignacion_id=a.id,
                vehiculo_id=None,
                ruta=None,
                cantidad=a.cantidad,
                viajes=0,
                prioridad=a.prioridad,
                estado=ESTADO_BLOQUEADA,
                motivo=MOTIVO_DESTINO_INACCESIBLE,
            )

        candidatos = [v for v in disponibles if self._compatible(v, a) and v.capacidad > 0]
        if not candidatos:
            return OperacionLogistica(
                id=operacion_id,
                asignacion_id=a.id,
                vehiculo_id=None,
                ruta=ruta,
                cantidad=a.cantidad,
                viajes=0,
                prioridad=a.prioridad,
                estado=ESTADO_BLOQUEADA,
                motivo=MOTIVO_SIN_VEHICULO_COMPATIBLE,
            )

        vehiculo = min(candidatos, key=lambda v: self._clave_seleccion(v, a.cantidad))
        viajes = self._viajes(a.cantidad, vehiculo.capacidad)

        advertencias = []
        if viajes > 1:
            advertencias.append(
                f"Se requieren {viajes} viajes del vehículo {vehiculo.id} "
                f"(capacidad {vehiculo.capacidad} {vehiculo.unidad_capacidad})."
            )

        return OperacionLogistica(
            id=operacion_id,
            asignacion_id=a.id,
            vehiculo_id=vehiculo.id,
            ruta=ruta,
            cantidad=a.cantidad,
            viajes=viajes,
            prioridad=a.prioridad,
            estado=ESTADO_PLANIFICADA,
            advertencias=tuple(advertencias),
        )

    # ------------------------------------------------------------------ helpers
    def _costo(self, arista) -> float:
        alfa = self._pesos.get("alfa", 0.0)
        beta = self._pesos.get("beta", 0.0)
        gamma = self._pesos.get("gamma", 0.0)
        return alfa * arista.distancia + beta * arista.tiempo + gamma * arista.riesgo

    def _compatible(self, v: Vehiculo, a: Asignacion) -> bool:
        if not a.unidad or not v.unidad_capacidad:
            return True
        return a.unidad == v.unidad_capacidad

    def _clave_seleccion(self, v: Vehiculo, cantidad: float):
        viajes = self._viajes(cantidad, v.capacidad)
        return (viajes, v.capacidad, v.id)

    @staticmethod
    def _viajes(cantidad: float, capacidad: float) -> int:
        return math.ceil(cantidad / capacidad)

    def _ruta(self, g: nx.Graph, origen: str, destino: str) -> Ruta | None:
        if origen not in g or destino not in g:
            return None
        if origen == destino:
            return Ruta(
                origen_id=origen,
                destino_id=destino,
                nodos=(origen,),
                distancia=0.0,
                tiempo_estimado=0.0,
            )
        try:
            path = nx.shortest_path(g, origen, destino, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

        distancia = sum(g[u][v]["distancia"] for u, v in zip(path, path[1:]))
        tiempo = sum(g[u][v]["tiempo"] for u, v in zip(path, path[1:]))
        return Ruta(
            origen_id=origen,
            destino_id=destino,
            nodos=tuple(path),
            distancia=round(distancia, 6),
            tiempo_estimado=round(tiempo, 6),
        )
