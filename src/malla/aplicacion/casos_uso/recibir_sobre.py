"""Caso de uso: llega un sobre de un vecino.

Verificar, deduplicar, almacenar, decidir reenvío. En ese orden y sin atajos: la
verificación va antes que el almacenamiento para que un nodo malicioso no pueda
llenar el disco de un teléfono ajeno con sobres que nunca fueron firmados.
"""

from __future__ import annotations

from typing import Any

from malla.aplicacion.casos_uso.difusion import difundir
from malla.aplicacion.eventos import evento, resumen_sobre
from malla.aplicacion.puertos.salida import AlmacenSobresPort, TransportePort
from malla.dominio.motor_malla import Decision, MotorMalla, ResultadoRecepcion
from malla.dominio.sobre import CARGA_ACUSE, SobreMalla
from nucleo.mensajes import TipoEvento
from nucleo.puertos import AuditoriaPort


class RecibirSobre:
    """Punto de entrada de todo lo que llega por la malla."""

    def __init__(
        self,
        motor: MotorMalla,
        almacen: AlmacenSobresPort,
        transporte: TransportePort,
        auditoria: AuditoriaPort,
    ) -> None:
        self._motor = motor
        self._almacen = almacen
        self._transporte = transporte
        self._auditoria = auditoria

    async def recibir(self, sobre: SobreMalla) -> Decision:
        vistos = await self._almacen.ids_vistos()
        decision = self._motor.evaluar(sobre, vistos)

        if decision.es_descarte:
            # Un descarte se registra siempre. Es la única forma de detectar
            # después que alguien estuvo inyectando sobres alterados en la zona.
            await self._auditoria.registrar(
                evento(
                    TipoEvento.REPORTE_DESCARTADO,
                    sobre.id_mensaje,
                    {
                        "motivo": str(decision.resultado),
                        "detalle": decision.motivo,
                        **resumen_sobre(sobre),
                    },
                )
            )
            return decision

        if decision.resultado is ResultadoRecepcion.DUPLICADO:
            return decision

        if decision.se_almacena:
            await self._almacen.guardar(sobre)
            await self._auditoria.registrar(
                evento(TipoEvento.REPORTE_RECIBIDO, sobre.id_mensaje, resumen_sobre(sobre))
            )
            # Un acuse dice "esto ya llegó a la nube": lo que hace al recibirlo
            # es liberar los pendientes locales, para que un nodo sin internet
            # deje de arrastrar sobres que ya están a salvo.
            if sobre.tipo_carga == CARGA_ACUSE:
                await self._aplicar_acuse(sobre)

        if decision.sobre_a_reenviar is not None:
            await difundir(self._motor, self._transporte, decision.sobre_a_reenviar)

        return decision

    async def recibir_dict(self, dato: dict[str, Any]) -> Decision:
        """Variante para adaptadores: acepta el sobre ya deserializado a dict."""
        return await self.recibir(SobreMalla.desde_dict(dato))

    async def _aplicar_acuse(self, sobre: SobreMalla) -> int:
        ids = sobre.carga.get("ids_acusados", [])
        if not isinstance(ids, list):
            ids = []
        # El propio acuse se marca entregado: es trafico interno de la malla y
        # nunca se sube a la nube, asi que si quedara pendiente se arrastraria
        # para siempre en el lote de este nodo.
        return await self._almacen.marcar_entregados(
            [sobre.id_mensaje, *(str(i) for i in ids)]
        )
