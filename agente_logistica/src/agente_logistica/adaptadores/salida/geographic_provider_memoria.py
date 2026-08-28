"""Proveedor geográfico en memoria con un grafo de movilidad sembrable."""

from __future__ import annotations

from agente_logistica.dominio.entidades import Arista, GrafoMovilidad


class GeographicProviderMemoria:
    def __init__(self):
        self._grafo = GrafoMovilidad(nodos=(), aristas=())

    def sembrar(self, mapa: dict) -> None:
        nodos = []
        for n in mapa.get("nodos", []):
            if isinstance(n, dict):
                nodos.append(n["id"])
            else:
                nodos.append(n)

        aristas = []
        for a in mapa.get("aristas", []):
            aristas.append(
                Arista(
                    origen=a["origen"],
                    destino=a["destino"],
                    distancia=float(a.get("distancia", 0.0)),
                    tiempo=float(a.get("tiempo", 0.0)),
                    estado=a.get("estado", "DISPONIBLE"),
                    via_id=a.get("via_id", ""),
                    riesgo=float(a.get("riesgo", 0.0)),
                )
            )

        self._grafo = GrafoMovilidad(nodos=tuple(nodos), aristas=tuple(aristas))

    def obtener_grafo(self) -> GrafoMovilidad:
        return self._grafo
