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

        resultado_motor = self._serializar(resultado)

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
    def _serializar(self, resultado) -> dict:
        return {
            "asignaciones": [asdict(a) for a in resultado.asignaciones],
            "no_cubierto": [asdict(nc) for nc in resultado.no_cubierto],
            "resumen": asdict(resultado.resumen) if resultado.resumen else {},
        }
