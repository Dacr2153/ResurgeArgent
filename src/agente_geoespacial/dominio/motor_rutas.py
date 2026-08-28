"""Motor de rutas: cálculo de caminos sobre la red vial, puro y determinista.

Toda la inteligencia de este agente vive aquí, no en el LLM. El LLM (capa de
aplicación) solo lee reportes en texto libre y extrae qué tramos están
bloqueados; este motor es quien decide la ruta, con ``networkx.shortest_path``
sobre un grafo dirigido cuyo peso es el tiempo de viaje (no la distancia): dos
vías de igual longitud no cuestan lo mismo si una es para peatones y otra para
camiones.

La decisión central: un tramo bloqueado no se "encarece", se **remueve** del
grafo antes de calcular. Modelarlo como peso alto en vez de remoción permitiría
que el algoritmo lo cruce si no hay alternativa, lo cual es exactamente lo que no
puede pasar con un derrumbe o un puente caído.
"""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from agente_geoespacial.dominio.entidades import (
    GrafoVial,
    ResultadoRuta,
    RutaAlternativa,
)
from agente_geoespacial.dominio.excepciones import NodoDesconocidoError
from agente_geoespacial.dominio.value_objects import PERFIL_VELOCIDAD_DEFECTO, PerfilVelocidad
from nucleo.esquemas import ConsultaGeo, ModoTransporte
from nucleo.geo import Punto

RADIO_CONEXION_KM_DEFECTO = 5.0
MAX_ALTERNATIVAS_DEFECTO = 1


class MotorRutas:
    def __init__(
        self,
        grafo: GrafoVial,
        perfil_velocidad: PerfilVelocidad = PERFIL_VELOCIDAD_DEFECTO,
        radio_conexion_km: float = RADIO_CONEXION_KM_DEFECTO,
        max_alternativas: int = MAX_ALTERNATIVAS_DEFECTO,
    ) -> None:
        self._grafo = grafo
        self._perfil = perfil_velocidad
        self._radio_conexion_km = radio_conexion_km
        self._max_alternativas = max_alternativas

    # ------------------------------------------------------------------ público
    def calcular_ruta(
        self, consulta: ConsultaGeo, vias_bloqueadas: Sequence[str] = ()
    ) -> ResultadoRuta:
        origen_id = self._nodo_cercano(consulta.origen)
        destino_id = self._nodo_cercano(consulta.destino)

        if origen_id == destino_id:
            # Caso límite real: origen y destino caen en el mismo nodo. No hay
            # viaje que calcular, pero sigue siendo una ruta "accesible" válida.
            punto = self._grafo.nodos[origen_id].ubicacion
            geometria = {
                "type": "LineString",
                "coordinates": [[punto.lon, punto.lat], [punto.lon, punto.lat]],
            }
            return ResultadoRuta(
                accesible=True,
                distancia_km=0.0,
                duracion_min=0.0,
                geometria=geometria,
                vias_evitadas=tuple(vias_bloqueadas),
            )

        g = self._grafo_dirigido(consulta.modo, vias_bloqueadas)

        try:
            camino = nx.shortest_path(g, origen_id, destino_id, weight="peso_min")
        except nx.NetworkXNoPath:
            motivo = (
                f"no existe camino de {origen_id} a {destino_id} "
                f"tras remover las vías bloqueadas: {', '.join(vias_bloqueadas) or 'ninguna'}"
            )
            return ResultadoRuta(
                accesible=False, vias_evitadas=tuple(vias_bloqueadas), motivo=motivo
            )

        distancia, duracion, geometria = self._medir_camino(camino, g)
        alternativas = self._rutas_alternativas(g, origen_id, destino_id, camino)

        return ResultadoRuta(
            accesible=True,
            distancia_km=distancia,
            duracion_min=duracion,
            geometria=geometria,
            vias_evitadas=tuple(vias_bloqueadas),
            alternativas=alternativas,
        )

    def segmentos_de_tramos(self, ids_tramo: Sequence[str]) -> list[tuple[Punto, Punto]]:
        """Traduce ids de tramo del grafo interno a coordenadas (origen, destino).

        Existe para que un ruteador externo (p. ej. OSRM, que no conoce los ids
        internos del grafo propio) pueda saber *dónde* cae un bloqueo, no solo
        su id. Un id que no corresponde a ningún tramo se ignora en silencio,
        mismo criterio que ``ResolverRuta._combinar_bloqueos``.
        """
        por_id = {tramo.id: tramo for tramo in self._grafo.tramos}
        segmentos: list[tuple[Punto, Punto]] = []
        for id_tramo in ids_tramo:
            tramo = por_id.get(id_tramo)
            if tramo is None:
                continue
            origen = self._grafo.nodos[tramo.origen_id].ubicacion
            destino = self._grafo.nodos[tramo.destino_id].ubicacion
            segmentos.append((origen, destino))
        return segmentos

    # ------------------------------------------------------------------ grafo
    def _grafo_dirigido(
        self, modo: ModoTransporte, vias_bloqueadas: Sequence[str]
    ) -> nx.DiGraph:
        bloqueadas = set(vias_bloqueadas)
        velocidad = self._perfil.kmh(modo)

        g = nx.DiGraph()
        for nodo_id in self._grafo.nodos:
            g.add_node(nodo_id)

        for tramo in self._grafo.tramos:
            if tramo.id in bloqueadas:
                # Removido, no encarecido: ver docstring del módulo.
                continue
            origen = self._grafo.nodos[tramo.origen_id].ubicacion
            destino = self._grafo.nodos[tramo.destino_id].ubicacion
            distancia_km = origen.distancia_a(destino)
            peso_min = (distancia_km / velocidad) * 60.0

            g.add_edge(
                tramo.origen_id,
                tramo.destino_id,
                weight_km=distancia_km,
                peso_min=peso_min,
                tramo_id=tramo.id,
            )
            if tramo.bidireccional:
                g.add_edge(
                    tramo.destino_id,
                    tramo.origen_id,
                    weight_km=distancia_km,
                    peso_min=peso_min,
                    tramo_id=tramo.id,
                )
        return g

    def _nodo_cercano(self, punto: Punto) -> str:
        if not self._grafo.nodos:
            raise NodoDesconocidoError("el grafo vial no tiene nodos")

        mejor_id = ""
        mejor_distancia = float("inf")
        for nodo_id, nodo in self._grafo.nodos.items():
            distancia = nodo.ubicacion.distancia_a(punto)
            if distancia < mejor_distancia:
                mejor_id, mejor_distancia = nodo_id, distancia

        if mejor_distancia > self._radio_conexion_km:
            raise NodoDesconocidoError(
                f"ningún nodo del grafo está a menos de {self._radio_conexion_km} km "
                f"del punto consultado ({punto.lat}, {punto.lon})"
            )
        return mejor_id

    # ------------------------------------------------------------------ medición
    def _medir_camino(self, camino: list[str], g: nx.DiGraph) -> tuple[float, float, dict]:
        distancia_km = 0.0
        duracion_min = 0.0
        for origen_id, destino_id in zip(camino, camino[1:]):
            datos = g.get_edge_data(origen_id, destino_id)
            distancia_km += datos["weight_km"]
            duracion_min += datos["peso_min"]

        coordenadas = [
            [self._grafo.nodos[nodo_id].ubicacion.lon, self._grafo.nodos[nodo_id].ubicacion.lat]
            for nodo_id in camino
        ]
        geometria = {"type": "LineString", "coordinates": coordenadas}
        return distancia_km, duracion_min, geometria

    def _rutas_alternativas(
        self, g: nx.DiGraph, origen_id: str, destino_id: str, camino_principal: list[str]
    ) -> tuple[RutaAlternativa, ...]:
        """Al menos una segunda opción, cuando exista, para que el Orquestador tenga plan B."""
        alternativas: list[RutaAlternativa] = []
        try:
            generador = nx.shortest_simple_paths(g, origen_id, destino_id, weight="peso_min")
            for camino in generador:
                if camino == camino_principal:
                    continue
                distancia, duracion, geometria = self._medir_camino(camino, g)
                alternativas.append(
                    RutaAlternativa(
                        nodos=tuple(camino),
                        distancia_km=distancia,
                        duracion_min=duracion,
                        geometria=geometria,
                    )
                )
                if len(alternativas) >= self._max_alternativas:
                    break
        except nx.NetworkXNoPath:
            pass
        return tuple(alternativas)
