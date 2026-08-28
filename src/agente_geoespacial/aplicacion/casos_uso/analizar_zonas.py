"""Caso de uso: agrupar incidentes verificados en zonas afectadas.

Delgado a propósito: toda la lógica (rejilla, agregación de severidad, geometría)
vive en ``MotorZonas``, puro y determinista. Este caso de uso solo cumple
``AnalizarZonasUseCase`` / la otra mitad de ``nucleo.puertos.GeoespacialPort``.
"""

from __future__ import annotations

from agente_geoespacial.dominio.motor_zonas import MotorZonas
from nucleo.esquemas import IncidenteVerificado


class AnalizarZonas:
    def __init__(self, motor: MotorZonas) -> None:
        self._motor = motor

    async def ejecutar(self, incidentes: list[IncidenteVerificado]) -> dict:
        return self._motor.agrupar(incidentes)
