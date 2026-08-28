"""Caso de uso: resolver una ruta entre dos puntos, evitando vías bloqueadas.

La regla que no se rompe:

    bloqueos = await self._llm.interpretar(reportes_texto)  # el LLM lee texto
    resultado = self._motor.calcular_ruta(consulta, bloqueos)  # el dominio decide

El LLM extrae qué tramos están bloqueados a partir de lenguaje natural ("la vía
está tapada por el derrumbe"). Nunca calcula distancias, nunca elige la ruta:
eso es enteramente responsabilidad del ``MotorRutas``, determinista.

Hay dos canales por los que puede llegar un bloqueo, y se combinan, no se elige
uno u otro:

- ``consulta.evitar_zonas``: bloqueos que otro agente ya conoce y pasa
  directamente (el caso del flujo real: Verificación detecta un derrumbe, el
  Orquestador pide una ruta que lo evite).
- ``reportes_bloqueo`` interpretados por el LLM: bloqueos que alguien contó en
  texto libre y que nadie más había estructurado todavía.
"""

from __future__ import annotations

from agente_geoespacial.aplicacion.puertos.salida import LLMInterpretePort, PublicadorPort
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from nucleo.esquemas import ConsultaGeo, RespuestaGeo, RutaAlternativa
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
        """Cumple ``ResolverRutaUseCase`` y ``nucleo.puertos.GeoespacialPort.resolver_ruta``.

        Devuelve la ruta principal con ``alternativas`` ya incluidas: no hace
        falta un método aparte para que el Orquestador vea el plan B, porque
        ahora ``RespuestaGeo`` tiene dónde ponerlo.
        """
        correlacion_id = correlacion_id or consulta.id
        reportes = reportes_bloqueo or []

        vias_reportadas_por_llm = await self._llm.interpretar(reportes)
        vias_bloqueadas = self._combinar_bloqueos(consulta.evitar_zonas, vias_reportadas_por_llm)

        resultado = self._motor.calcular_ruta(consulta, vias_bloqueadas)

        respuesta = RespuestaGeo(
            consulta_id=consulta.id,
            accesible=resultado.accesible,
            distancia_km=resultado.distancia_km,
            duracion_min=resultado.duracion_min,
            geometria=resultado.geometria,
            vias_evitadas=resultado.vias_evitadas,
            motivo=resultado.motivo,
            alternativas=tuple(
                RutaAlternativa(
                    distancia_km=alternativa.distancia_km,
                    duracion_min=alternativa.duracion_min,
                    geometria=alternativa.geometria,
                    # La alternativa se calculó sobre el mismo grafo degradado
                    # que la principal: evita exactamente las mismas vías.
                    vias_evitadas=resultado.vias_evitadas,
                )
                for alternativa in resultado.alternativas
            ),
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
                    "num_alternativas": len(respuesta.alternativas),
                },
            )
        )

        if vias_bloqueadas:
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.VIA_BLOQUEADA,
                    agente=Agente.GEOESPACIAL,
                    correlacion_id=correlacion_id,
                    detalle={
                        "vias_bloqueadas": list(vias_bloqueadas),
                        "vias_evitadas_en_consulta": list(consulta.evitar_zonas),
                        "vias_extraidas_por_llm": list(vias_reportadas_por_llm),
                        "reportes": reportes,
                    },
                )
            )

        await self._publicador.publicar(respuesta.a_dict())

        return respuesta

    @staticmethod
    def _combinar_bloqueos(
        evitar_zonas: tuple[str, ...], vias_del_llm: list[str]
    ) -> list[str]:
        """Une ambas fuentes de bloqueo sin duplicados, conservando el orden de aparición.

        Un id que no corresponde a ningún tramo del grafo no revienta nada: el
        motor simplemente no encuentra arista que remover para él y sigue de
        largo. Aun así queda en ``vias_evitadas`` de la respuesta, como
        constancia de que se pidió evitarlo.
        """
        vistos: set[str] = set()
        combinadas: list[str] = []
        for id_tramo in (*evitar_zonas, *vias_del_llm):
            if id_tramo not in vistos:
                vistos.add(id_tramo)
                combinadas.append(id_tramo)
        return combinadas
