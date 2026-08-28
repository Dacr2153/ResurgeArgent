"""Puerto de entrada (protocolo). Coincide por forma con ``nucleo.puertos.IngestaPort``:
esto es lo que consume el Orquestador."""

from __future__ import annotations

from typing import Protocol

from nucleo.esquemas import ReporteCrudo


class IngerirReportesUseCase(Protocol):
    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]:
        """Procesa un lote de reportes crudos y devuelve los aceptados."""
        ...
