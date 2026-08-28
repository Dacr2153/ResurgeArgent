"""Puertos de entrada (protocolos)."""

from __future__ import annotations

from typing import Protocol

from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, RespuestaGeo


class ResolverRutaUseCase(Protocol):
    async def ejecutar(
        self, consulta: ConsultaGeo, reportes_bloqueo: list[str] | None = None
    ) -> RespuestaGeo:
        """Resuelve una ruta entre origen y destino, evitando vías bloqueadas."""
        ...


class AnalizarZonasUseCase(Protocol):
    async def ejecutar(self, incidentes: list[IncidenteVerificado]) -> dict:
        """Agrupa incidentes verificados en zonas afectadas (GeoJSON)."""
        ...
