"""Puerto de entrada (protocolo).

Tiene la misma forma que `nucleo.puertos.VerificacionPort`: el caso de uso lo
cumple por estructura, sin heredar de nada, así que sirve indistintamente para
inyectarlo en el Orquestador vía el contrato compartido o para tiparlo aquí
dentro del propio agente.
"""

from __future__ import annotations

from typing import Protocol

from nucleo.esquemas import IncidenteVerificado, ReporteCrudo


class VerificarReportesUseCase(Protocol):
    async def verificar(self, reportes: list[ReporteCrudo]) -> list[IncidenteVerificado]:
        """Valida, contrasta y fusiona reportes crudos en incidentes verificados."""
        ...
