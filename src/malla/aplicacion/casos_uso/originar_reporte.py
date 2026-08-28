"""Caso de uso: este teléfono genera un reporte y lo suelta a la malla.

Es el único momento en que se firma. A partir de aquí el sobre es inmutable para
todo el mundo, incluido este nodo.
"""

from __future__ import annotations

from typing import Any

from malla.aplicacion.casos_uso.difusion import ResultadoDifusion, difundir
from malla.aplicacion.eventos import evento, resumen_sobre
from malla.aplicacion.puertos.salida import AlmacenSobresPort, TransportePort
from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from malla.dominio.motor_malla import MotorMalla
from malla.dominio.sobre import CARGA_REPORTE, SobreMalla
from nucleo.esquemas import ReporteCrudo
from nucleo.mensajes import TipoEvento
from nucleo.puertos import AuditoriaPort


class OriginarReporte:
    """Firma un reporte propio y lo difunde."""

    def __init__(
        self,
        identidad: IdentidadNodo,
        motor: MotorMalla,
        almacen: AlmacenSobresPort,
        transporte: TransportePort,
        auditoria: AuditoriaPort,
    ) -> None:
        self._identidad = identidad
        self._motor = motor
        self._almacen = almacen
        self._transporte = transporte
        self._auditoria = auditoria

    async def originar(
        self,
        reporte: ReporteCrudo,
        ttl: int | None = None,
    ) -> tuple[SobreMalla, ResultadoDifusion]:
        """Envuelve un `ReporteCrudo`, lo firma, lo guarda y lo difunde.

        Se guarda **antes** de difundir. Si la difusión falla porque no hay
        ningún vecino al alcance —lo normal en los primeros minutos— el reporte
        no se pierde: queda pendiente y sale en cuanto aparezca alguien.
        """
        return await self.originar_carga(reporte.a_dict(), ttl=ttl)

    async def originar_carga(
        self,
        carga: dict[str, Any],
        ttl: int | None = None,
        tipo_carga: str = CARGA_REPORTE,
    ) -> tuple[SobreMalla, ResultadoDifusion]:
        sobre = crear_sobre_firmado(
            self._identidad,
            carga,
            ttl=ttl or self._motor.ttl_por_defecto,
            tipo_carga=tipo_carga,
        )
        await self._almacen.guardar(sobre)
        await self._auditoria.registrar(
            evento(
                TipoEvento.REPORTE_RECIBIDO,
                sobre.id_mensaje,
                resumen_sobre(sobre) | {"origen_local": True},
            )
        )
        resultado = await difundir(self._motor, self._transporte, sobre)
        return sobre, resultado
