"""Caso de uso: registrar la firma del coordinador humano sobre un incidente.

Es el otro extremo del gate. `procesar_emergencia` deja el incidente en
PENDIENTE_APROBACION y se detiene; nada avanza hasta que este caso de uso recibe
una `DecisionHumana`.

La firma se registra en la operación *antes* de intentar la transición, y se
audita pase lo que pase después. Un rechazo, o incluso un intento inválido, es
información que el post-mortem necesita tanto como una aprobación.
"""

from __future__ import annotations

from typing import Any

from agente_orquestador.aplicacion.puertos.salida import (
    PublicadorPort,
    RepositorioOperacionesPort,
)
from agente_orquestador.dominio.entidades import Operacion
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.excepciones import IncidenteDesconocidoError
from nucleo.esquemas import DecisionHumana
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento
from nucleo.puertos import AuditoriaPort


class RegistrarDecisionHumana:
    """Aplica una decisión firmada y mueve el incidente en consecuencia."""

    def __init__(
        self,
        repositorio: RepositorioOperacionesPort,
        auditoria: AuditoriaPort,
        publicador: PublicadorPort,
    ) -> None:
        self._repositorio = repositorio
        self._auditoria = auditoria
        self._publicador = publicador

    async def registrar(self, payload: dict) -> dict:
        """Registra la decisión. Lanza si el incidente o la transición no valen."""
        decision = self._construir(payload)

        operacion = await self._repositorio.obtener(decision.incidente_id)
        if operacion is None:
            raise IncidenteDesconocidoError(
                f"no hay operación abierta para el incidente {decision.incidente_id}"
            )

        operacion.registrar_decision(decision)
        await self._auditar(operacion, TipoEvento.DECISION_HUMANA_REGISTRADA, decision.a_dict())

        destino = self._destino(decision, payload)
        registro = operacion.transicionar(
            destino,
            decision=decision,
            motivo=decision.justificacion or f"decisión de {decision.coordinador_id}",
        )
        await self._auditar(
            operacion,
            TipoEvento.TRANSICION_ESTADO,
            {"incidente_id": operacion.incidente_id, **registro.a_dict()},
        )

        await self._repositorio.guardar(operacion)
        salida = operacion.a_dict()
        await self._publicador.publicar(salida)
        return salida

    @staticmethod
    def _construir(payload: dict) -> DecisionHumana:
        return DecisionHumana(
            incidente_id=str(payload["incidente_id"]),
            aprobada=bool(payload["aprobada"]),
            coordinador_id=str(payload["coordinador_id"]),
            justificacion=str(payload.get("justificacion", "")),
        )

    @staticmethod
    def _destino(decision: DecisionHumana, payload: dict[str, Any]) -> EstadoIncidente:
        """Traduce el sentido de la firma a un estado destino.

        Un rechazo cierra el incidente por defecto. `suspender=true` es la vía
        para el caso intermedio: el coordinador no lo aprueba *todavía* y pide más
        información, sin declarar que el reporte era falso.
        """
        if decision.aprobada:
            return EstadoIncidente.ASIGNADO
        if payload.get("suspender"):
            return EstadoIncidente.SUSPENDIDO
        return EstadoIncidente.DESCARTADO

    async def _auditar(
        self, operacion: Operacion, tipo: TipoEvento, detalle: dict[str, Any]
    ) -> None:
        await self._auditoria.registrar(
            EventoAuditoria(
                tipo=tipo,
                agente=Agente.ORQUESTADOR,
                correlacion_id=operacion.correlacion_id,
                detalle=detalle,
            )
        )
