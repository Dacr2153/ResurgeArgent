"""Sustitutos para los agentes que todavía no están montados.

Los agentes 2, 3 y 5 se construyen en ramas paralelas. El Orquestador no puede
depender de que existan para arrancar, ni puede fingir que respondieron: si un
agente no está, el paso correspondiente debe **fallar de forma limpia** y dejar
que la saga decida si compensa o degrada.

Por eso estos dobles lanzan en vez de devolver vacío. Devolver una lista vacía
sería indistinguible de "no había nada que reportar", y eso sí borraría una
emergencia real del sistema sin dejar rastro.
"""

from __future__ import annotations

from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, ReporteCrudo, RespuestaGeo
from nucleo.mensajes import Agente


class AgenteNoDisponibleError(RuntimeError):
    """El agente delegado no está montado en este despliegue."""


class IngestaAusente:
    def __init__(self, agente: Agente = Agente.INGESTA) -> None:
        self._agente = agente

    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]:
        raise AgenteNoDisponibleError(f"{self._agente} no está disponible")


class VerificacionAusente:
    def __init__(self, agente: Agente = Agente.VERIFICACION) -> None:
        self._agente = agente

    async def verificar(self, reportes: list[ReporteCrudo]) -> list[IncidenteVerificado]:
        raise AgenteNoDisponibleError(f"{self._agente} no está disponible")


class GeoespacialAusente:
    def __init__(self, agente: Agente = Agente.GEOESPACIAL) -> None:
        self._agente = agente

    async def resolver_ruta(self, consulta: ConsultaGeo) -> RespuestaGeo:
        raise AgenteNoDisponibleError(f"{self._agente} no está disponible")

    async def zonas_afectadas(self, incidentes: list[IncidenteVerificado]) -> dict:
        raise AgenteNoDisponibleError(f"{self._agente} no está disponible")
