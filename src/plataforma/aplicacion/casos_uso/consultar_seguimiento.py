"""Caso de uso: estado de un reporte para quien lo envió."""

from __future__ import annotations

from plataforma.aplicacion.puertos.salida import ConsultaOperacionesPort
from plataforma.dominio.entidades import ReporteSeguimiento
from plataforma.dominio.excepciones import RecursoDesconocidoError
from plataforma.dominio.seguimiento import derivar_recorrido


class ConsultarSeguimiento:
    """Convierte la operación del Orquestador en el recorrido del ciudadano."""

    def __init__(self, operaciones: ConsultaOperacionesPort) -> None:
        self._operaciones = operaciones

    async def consultar(self, incidente_id: str) -> ReporteSeguimiento:
        estado = await self._operaciones.obtener(incidente_id)
        if estado is None:
            raise RecursoDesconocidoError(f"no hay reporte con identificador {incidente_id}")
        return derivar_recorrido(estado)
