"""Caso de uso: verificar reportes crudos y fusionarlos en incidentes.

Cumple `nucleo.puertos.VerificacionPort` por su forma (`async def verificar`),
que es lo que le permite al Orquestador consumirlo sin conocer nada de este
agente salvo el contrato compartido.

La secuencia respeta la regla que no se rompe: el LLM opina sobre similitud
textual, el motor determinista decide la fusión.
"""

from __future__ import annotations

from agente_verificacion.aplicacion.puertos.salida import (
    PublicadorPort,
    RepositorioPort,
    SimilitudTextoPort,
)
from agente_verificacion.dominio.motor_verificacion import MotorVerificacion
from nucleo.esquemas import IncidenteVerificado, ReporteCrudo
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento, nuevo_id
from nucleo.puertos import AuditoriaPort


class VerificarReportes:
    def __init__(
        self,
        motor: MotorVerificacion,
        similitud: SimilitudTextoPort,
        publicador: PublicadorPort,
        repositorio: RepositorioPort,
        auditoria: AuditoriaPort,
    ):
        self._motor = motor
        self._similitud = similitud
        self._publicador = publicador
        self._repositorio = repositorio
        self._auditoria = auditoria

    async def verificar(self, reportes: list[ReporteCrudo]) -> list[IncidenteVerificado]:
        correlacion_id = nuevo_id()

        if not reportes:
            return []

        for reporte in reportes:
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.REPORTE_RECIBIDO,
                    agente=Agente.VERIFICACION,
                    correlacion_id=correlacion_id,
                    detalle={"reporte_id": reporte.id, "fuente_id": reporte.fuente.id},
                )
            )

        por_id = {r.id: r for r in reportes}
        pares_ids = self._motor.candidatos(reportes)
        pares_texto = [(a, b, por_id[a].texto, por_id[b].texto) for a, b in pares_ids]

        similitudes = await self._similitud.comparar(pares_texto) if pares_texto else {}

        incidentes = self._motor.fusionar(reportes, similitudes)

        for incidente in incidentes:
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.CONFIANZA_CALCULADA,
                    agente=Agente.VERIFICACION,
                    correlacion_id=correlacion_id,
                    detalle={
                        "incidente_id": incidente.id,
                        "confianza": incidente.confianza,
                        "corroboraciones": incidente.corroboraciones,
                    },
                )
            )
            if incidente.corroboraciones > 1:
                await self._auditoria.registrar(
                    EventoAuditoria(
                        tipo=TipoEvento.INCIDENTE_FUSIONADO,
                        agente=Agente.VERIFICACION,
                        correlacion_id=correlacion_id,
                        detalle={
                            "incidente_id": incidente.id,
                            "reportes_origen": list(incidente.reportes_origen),
                        },
                    )
                )
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.INCIDENTE_VERIFICADO,
                    agente=Agente.VERIFICACION,
                    correlacion_id=correlacion_id,
                    detalle=incidente.a_dict(),
                )
            )

        await self._repositorio.guardar([i.a_dict() for i in incidentes])
        await self._publicador.publicar(
            {"correlacion_id": correlacion_id, "incidentes": [i.a_dict() for i in incidentes]}
        )

        return incidentes
