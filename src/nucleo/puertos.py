"""Puertos compartidos por todos los agentes.

Protocolos, no clases base: un adaptador cumple el contrato por su forma, sin
heredar de nada. Es el mismo criterio que usa `agente_matching`.
"""

from __future__ import annotations

from typing import Protocol

from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, ReporteCrudo, RespuestaGeo
from nucleo.mensajes import EventoAuditoria


class AuditoriaPort(Protocol):
    """Registro de todo lo que ocurre. Lo implementan todos los agentes."""

    async def registrar(self, evento: EventoAuditoria) -> None: ...


class IngestaPort(Protocol):
    """Puerto de entrada del Agente 2. Lo consume el Orquestador."""

    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]: ...


class VerificacionPort(Protocol):
    """Puerto de entrada del Agente 3. Lo consume el Orquestador."""

    async def verificar(self, reportes: list[ReporteCrudo]) -> list[IncidenteVerificado]: ...


class GeoespacialPort(Protocol):
    """Puerto de entrada del Agente 5. Lo consume el Orquestador."""

    async def resolver_ruta(self, consulta: ConsultaGeo) -> RespuestaGeo: ...

    async def zonas_afectadas(self, incidentes: list[IncidenteVerificado]) -> dict: ...
