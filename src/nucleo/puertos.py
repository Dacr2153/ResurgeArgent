"""Puertos compartidos por todos los agentes.

Protocolos, no clases base: un adaptador cumple el contrato por su forma, sin
heredar de nada. Es el mismo criterio que usa `agente_matching`.

Cada operación admite un `correlacion_id` opcional. Sin él cada agente acuña el
suyo y la traza se parte en cuatro hilos inconexos: el log tendría todos los
eventos y aun así sería imposible reconstruir una sola operación de punta a
punta, que es justo lo que hay que poder hacer después de una emergencia.
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

    async def verificar(
        self,
        reportes: list[ReporteCrudo],
        correlacion_id: str | None = None,
    ) -> list[IncidenteVerificado]: ...


class GeoespacialPort(Protocol):
    """Puerto de entrada del Agente 5. Lo consume el Orquestador."""

    async def resolver_ruta(
        self,
        consulta: ConsultaGeo,
        correlacion_id: str | None = None,
    ) -> RespuestaGeo: ...

    async def zonas_afectadas(
        self,
        incidentes: list[IncidenteVerificado],
        correlacion_id: str | None = None,
    ) -> dict: ...
