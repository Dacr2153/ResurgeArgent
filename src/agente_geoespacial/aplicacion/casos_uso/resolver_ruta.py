"""Caso de uso: resolver una ruta entre dos puntos, evitando vías bloqueadas.

La regla que no se rompe:

    bloqueos = await self._llm.interpretar(reportes_texto)  # el LLM lee texto
    resultado = self._motor.calcular_ruta(consulta, bloqueos)  # el dominio decide

El LLM extrae qué tramos están bloqueados a partir de lenguaje natural ("la vía
está tapada por el derrumbe"). Nunca calcula distancias, nunca elige la ruta:
eso es enteramente responsabilidad del ``MotorRutas``, determinista.
"""

from __future__ import annotations

from agente_geoespacial.aplicacion.puertos.salida import LLMInterpretePort, PublicadorPort
from agente_geoespacial.dominio.entidades import ResultadoRuta
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from nucleo.esquemas import ConsultaGeo, RespuestaGeo
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento
from nucleo.puertos import AuditoriaPort


class ResolverRuta:
    def __init__(
        self,
        motor: MotorRutas,
        llm: LLMInterpretePort,
        publicador: PublicadorPort,
        auditoria: AuditoriaPort,
    ) -> None:
        self._motor = motor
        self._llm = llm
        self._publicador = publicador
        self._auditoria = auditoria

    async def ejecutar(
        self,
        consulta: ConsultaGeo,
        reportes_bloqueo: list[str] | None = None,
        correlacion_id: str | None = None,
    ) -> RespuestaGeo:
        """Cumple ``ResolverRutaUseCase`` / la mitad de ``nucleo.puertos.GeoespacialPort``."""
        respuesta, _ = await self.ejecutar_detallado(consulta, reportes_bloqueo, correlacion_id)
        return respuesta

    async def ejecutar_detallado(
        self,
        consulta: ConsultaGeo,
        reportes_bloqueo: list[str] | None = None,
        correlacion_id: str | None = None,
    ) -> tuple[RespuestaGeo, ResultadoRuta]:
        """Variante que además expone las rutas alternativas (fuera del contrato de frontera).

        ``RespuestaGeo`` no tiene campo para alternativas, así que el adaptador
        REST usa esta versión para ofrecerlas; el puerto compartido con el
        Orquestador usa ``ejecutar``, que solo devuelve la ruta principal.
        """
        correlacion_id = correlacion_id or consulta.id
        reportes = reportes_bloqueo or []

        vias_bloqueadas = await self._llm.interpretar(reportes)

        resultado = self._motor.calcular_ruta(consulta, vias_bloqueadas)

        respuesta = RespuestaGeo(
            consulta_id=consulta.id,
            accesible=resultado.accesible,
            distancia_km=resultado.distancia_km,
            duracion_min=resultado.duracion_min,
            geometria=resultado.geometria,
            vias_evitadas=resultado.vias_evitadas,
            motivo=resultado.motivo,
        )

        await self._auditoria.registrar(
            EventoAuditoria(
                tipo=TipoEvento.RUTA_CALCULADA,
                agente=Agente.GEOESPACIAL,
                correlacion_id=correlacion_id,
                detalle={
                    "consulta_id": consulta.id,
                    "accesible": respuesta.accesible,
                    "distancia_km": respuesta.distancia_km,
                    "duracion_min": respuesta.duracion_min,
                    "num_alternativas": len(resultado.alternativas),
                },
            )
        )

        if vias_bloqueadas:
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.VIA_BLOQUEADA,
                    agente=Agente.GEOESPACIAL,
                    correlacion_id=correlacion_id,
                    detalle={"vias_bloqueadas": list(vias_bloqueadas), "reportes": reportes},
                )
            )

        await self._publicador.publicar(respuesta.a_dict())

        return respuesta, resultado
