"""Caso de uso: ejecutar el matching de necesidades ↔ recursos ↔ empresas ↔ vehículos."""

from __future__ import annotations

from dataclasses import asdict

from agente_matching.aplicacion.puertos.salida import (
    LLMOrquestadorPort,
    PublicadorPort,
    RepositorioPort,
)
from agente_matching.dominio.entidades import Empresa, Necesidad, Recurso
from agente_matching.dominio.motor_matching import MotorMatching
from agente_matching.dominio.value_objects import Prioridad, Ubicacion


class EjecutarMatching:
    def __init__(
        self,
        motor: MotorMatching,
        llm: LLMOrquestadorPort,
        publicador: PublicadorPort,
        repositorio: RepositorioPort,
    ):
        self._motor = motor
        self._llm = llm
        self._publicador = publicador
        self._repositorio = repositorio

    async def ejecutar(self, entrada_json: dict) -> dict:
        limpio = await self._llm.normalizar(entrada_json)

        necesidades, recursos, empresas, fijas = self._parsear(limpio)

        resultado = self._motor.ejecutar(necesidades, recursos, empresas, fijas)

        resultado_motor = self._serializar(resultado, necesidades, recursos)

        final = await self._llm.justificar(resultado_motor, limpio)

        await self._repositorio.guardar(final)
        await self._publicador.publicar(final)

        return final

    # ------------------------------------------------------------------ parseo
    def _parsear(self, limpio: dict):
        necesidades = [
            Necesidad(
                id=n["id"],
                zona_id=n.get("zona_id", ""),
                tipo=n["tipo"],
                cantidad_requerida=float(n["cantidad_requerida"]),
                prioridad=Prioridad(int(n.get("prioridad", 1))),
                ubicacion=Ubicacion(**n["ubicacion"]),
                unidad=n.get("unidad", ""),
            )
            for n in limpio.get("necesidades", [])
        ]

        recursos = [
            Recurso(
                id=r["id"],
                lugar_id=r.get("lugar_id", ""),
                tipo=r["tipo"],
                cantidad_disponible=float(r["cantidad_disponible"]),
                ubicacion=Ubicacion(**r["ubicacion"]),
                unidad=r.get("unidad", ""),
            )
            for r in limpio.get("recursos", [])
        ]

        empresas = []
        for e in limpio.get("empresas", []):
            zonas = e.get("zonas_cobertura")
            zonas_cobertura = frozenset(zonas) if zonas else None
            empresas.append(
                Empresa(
                    id=e["id"],
                    nombre=e.get("nombre") or e["id"],
                    ubicacion=Ubicacion(**e["ubicacion"]),
                    num_vehiculos=int(e.get("num_vehiculos", 0)),
                    num_en_transito=int(e.get("num_en_transito", 0)),
                    zonas_cobertura=zonas_cobertura,
                )
            )

        fijas = limpio.get("asignaciones_fijas", []) or []

        return necesidades, recursos, empresas, fijas

    # ----------------------------------------------------------- serialización
    def _serializar(self, resultado, necesidades, recursos) -> dict:
        recurso_por_id = {r.id: r for r in recursos}
        necesidad_por_id = {n.id: n for n in necesidades}

        asignaciones = []
        for i, a in enumerate(resultado.asignaciones, start=1):
            recurso = recurso_por_id.get(a.recurso_id)
            necesidad = necesidad_por_id.get(a.necesidad_id)
            asignaciones.append(
                {
                    "id": f"A{i:03d}",
                    "necesidad_id": a.necesidad_id,
                    "recurso_id": a.recurso_id,
                    "empresa_id": a.empresa_id,
                    "tipo": recurso.tipo if recurso else "",
                    "origen": {
                        "id": recurso.lugar_id if recurso else "",
                        "latitud": recurso.ubicacion.lat if recurso else None,
                        "longitud": recurso.ubicacion.lon if recurso else None,
                    },
                    "destino": {
                        "id": necesidad.zona_id if necesidad else "",
                        "latitud": necesidad.ubicacion.lat if necesidad else None,
                        "longitud": necesidad.ubicacion.lon if necesidad else None,
                    },
                    "cantidad": a.cantidad,
                    "unidad": recurso.unidad if recurso else "",
                    "prioridad": necesidad.prioridad.valor if necesidad else 0,
                    "distancia_km": a.distancia_km,
                    "costo_unitario": a.costo_unitario,
                }
            )

        return {
            "asignaciones": asignaciones,
            "no_cubierto": [asdict(nc) for nc in resultado.no_cubierto],
            "resumen": asdict(resultado.resumen) if resultado.resumen else {},
        }
