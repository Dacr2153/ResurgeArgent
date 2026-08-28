"""Caso de uso: planificar la logística de un conjunto de asignaciones."""

from __future__ import annotations

from agente_logistica.aplicacion.puertos.salida import (
    GeographicProviderPort,
    LLMAgente8Port,
    LogisticsPlannerPort,
    PublicadorPort,
)
from agente_logistica.dominio.entidades import Asignacion, Vehiculo
from agente_logistica.dominio.value_objects import Ubicacion


class PlanificarLogistica:
    def __init__(
        self,
        planner: LogisticsPlannerPort,
        geo: GeographicProviderPort,
        llm: LLMAgente8Port,
        publicador: PublicadorPort,
    ):
        self._planner = planner
        self._geo = geo
        self._llm = llm
        self._publicador = publicador

    async def ejecutar(self, entrada_json: dict) -> dict:
        limpio = await self._llm.normalizar(entrada_json)

        asignaciones, vehiculos, restricciones = self._parsear(limpio)

        if "mapa" in limpio:
            self._geo.sembrar(limpio["mapa"])
        grafo = self._geo.obtener_grafo()

        plan = self._planner.planificar(asignaciones, vehiculos, restricciones, grafo)

        resultado = self._serializar(plan)

        final = await self._llm.explicar(resultado, limpio)

        await self._publicador.publicar(final)

        return final

    # ------------------------------------------------------------------ parseo
    def _parsear(self, limpio: dict):
        asignaciones = []
        for a in limpio.get("asignaciones", []):
            asignaciones.append(
                Asignacion(
                    id=a["id"],
                    necesidad_id=a["necesidad_id"],
                    recurso_id=a["recurso_id"],
                    tipo=a.get("tipo", ""),
                    origen_id=a["origen"]["id"],
                    destino_id=a["destino"]["id"],
                    origen=Ubicacion(
                        latitud=a["origen"]["latitud"],
                        longitud=a["origen"]["longitud"],
                    ),
                    destino=Ubicacion(
                        latitud=a["destino"]["latitud"],
                        longitud=a["destino"]["longitud"],
                    ),
                    cantidad=float(a["cantidad"]),
                    unidad=a.get("unidad", ""),
                    prioridad=int(a.get("prioridad", 1)),
                )
            )

        vehiculos = []
        for v in limpio.get("vehiculos", []):
            vehiculos.append(
                Vehiculo(
                    id=v["id"],
                    tipo=v.get("tipo", ""),
                    capacidad=float(v["capacidad"]),
                    unidad_capacidad=v.get("unidad_capacidad", ""),
                    ubicacion=Ubicacion(
                        latitud=v["ubicacion"]["latitud"],
                        longitud=v["ubicacion"]["longitud"],
                    ),
                    disponible=bool(v.get("disponible", True)),
                    restricciones=tuple(v.get("restricciones", []) or []),
                )
            )

        restricciones = limpio.get("restricciones", []) or []

        return asignaciones, vehiculos, restricciones

    # ----------------------------------------------------------- serialización
    def _serializar(self, plan) -> dict:
        return {
            "plan_id": plan.id,
            "estado": plan.estado,
            "operaciones": [
                {
                    "operacion_id": op.id,
                    "asignacion_id": op.asignacion_id,
                    "vehiculo_id": op.vehiculo_id,
                    "cantidad": op.cantidad,
                    "viajes": op.viajes,
                    "prioridad": op.prioridad,
                    "ruta": (
                        {
                            "nodos": list(op.ruta.nodos),
                            "distancia": op.ruta.distancia,
                            "tiempo_estimado": op.ruta.tiempo_estimado,
                        }
                        if op.ruta
                        else None
                    ),
                    "estado": op.estado,
                    "motivo": op.motivo,
                    "advertencias": list(op.advertencias),
                }
                for op in plan.operaciones
            ],
            "advertencias": list(plan.advertencias),
            "fecha_generacion": plan.fecha_generacion,
        }
