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

from dataclasses import replace

from agente_geoespacial.aplicacion.puertos.salida import (
    LLMInterpretePort,
    PublicadorPort,
    RuteadorPort,
)
from agente_geoespacial.dominio.entidades import ResultadoRuta
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from nucleo.esquemas import ConsultaGeo, RespuestaGeo, RutaAlternativa
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento
from nucleo.puertos import AuditoriaPort

MOTOR_OSRM = "osrm"
MOTOR_GRAFO = "grafo"


class ResolverRuta:
    def __init__(
        self,
        motor: MotorRutas,
        llm: LLMInterpretePort,
        publicador: PublicadorPort,
        auditoria: AuditoriaPort,
        ruteador: RuteadorPort | None = None,
    ) -> None:
        self._motor = motor
        self._llm = llm
        self._publicador = publicador
        self._auditoria = auditoria
        # None (por defecto) mantiene el comportamiento histórico: solo el
        # MotorRutas propio, sin red. Con un RuteadorPort configurado (OSRM),
        # ese motor es el respaldo si OSRM no responde a tiempo — nunca al
        # revés, ver ``_resolver``.
        self._ruteador = ruteador

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

        resultado, motor_resolucion = await self._resolver(consulta, vias_bloqueadas)

        respuesta = RespuestaGeo(
            consulta_id=consulta.id,
            accesible=resultado.accesible,
            distancia_km=resultado.distancia_km,
            duracion_min=resultado.duracion_min,
            geometria=resultado.geometria,
            # Los ids a evitar son los que se pidió evitar, no los que el
            # ResultadoRuta reporta: el ruteador OSRM no conoce ids del grafo
            # interno (solo coordenadas), así que su ResultadoRuta.vias_evitadas
            # viene vacío. El grafo propio sí los conoce, pero usar siempre esta
            # fuente única evita que la respuesta dependa de qué motor resolvió.
            vias_evitadas=tuple(vias_bloqueadas),
            motivo=resultado.motivo,
            alternativas=tuple(
                RutaAlternativa(
                    distancia_km=alternativa.distancia_km,
                    duracion_min=alternativa.duracion_min,
                    geometria=alternativa.geometria,
                    # La alternativa se calculó junto a la principal, sobre las
                    # mismas vías bloqueadas.
                    vias_evitadas=tuple(vias_bloqueadas),
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
                    # Cuál de los dos motores resolvió: constancia de que, si
                    # OSRM estaba configurado, se usó (o de que se cayó al
                    # respaldo). Ver ``_resolver``.
                    "motor_resolucion": motor_resolucion,
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

    async def _resolver(
        self, consulta: ConsultaGeo, vias_bloqueadas: list[str]
    ) -> tuple[ResultadoRuta, str]:
        """Decide qué motor calcula la ruta: OSRM primero si está configurado,
        el grafo propio siempre como respaldo.

        Nunca al revés: el grafo propio (``MotorRutas``, ``networkx`` puro, sin
        red) es el que responde siempre, con o sin OSRM. Si ``self._ruteador``
        es ``None`` (configuración por defecto, ``AGENTE5_RUTEADOR=grafo``), ni
        siquiera se intenta red — el comportamiento es idéntico al que tenía
        este caso de uso antes de que existiera OSRM, así que las pruebas que
        no configuran ruteador no cambian.
        """
        if self._ruteador is None:
            return self._motor.calcular_ruta(consulta, vias_bloqueadas), MOTOR_GRAFO

        segmentos_bloqueados = self._motor.segmentos_de_tramos(vias_bloqueadas)
        try:
            resultado_osrm = await self._ruteador.calcular_ruta(
                consulta.origen, consulta.destino, consulta.modo, segmentos_bloqueados
            )
        except Exception:  # noqa: BLE001 - servicio público sin SLA, nunca tumba la ruta
            resultado_osrm = None

        if resultado_osrm is not None:
            return resultado_osrm, MOTOR_OSRM

        resultado_grafo = self._motor.calcular_ruta(consulta, vias_bloqueadas)
        nota = (
            "OSRM no respondió (caído, timeout o vacío); "
            "resuelto por el motor de respaldo (grafo)."
        )
        motivo = f"{nota} {resultado_grafo.motivo}".strip() if resultado_grafo.motivo else nota
        resultado_grafo = replace(resultado_grafo, motivo=motivo)
        return resultado_grafo, MOTOR_GRAFO

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
