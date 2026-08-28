"""Caso de uso: ingerir un lote de reportes crudos.

Cumple ``nucleo.puertos.IngestaPort`` por forma (``async def ingerir(self,
entrada: dict) -> list[ReporteCrudo]``), sin heredar de nada — el mismo
criterio que usa ``agente_matching``.

La regla que no se rompe vive aquí, en el orden de las dos líneas centrales de
``ingerir``: primero el LLM (o el extractor nulo) estructura texto libre,
después el motor de dominio —puro, determinista— decide qué se acepta. El LLM
nunca decide.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agente_ingesta.aplicacion.puertos.salida import ExtractorPort, PublicadorPort, RepositorioPort
from agente_ingesta.dominio.excepciones import LoteInvalidoError
from agente_ingesta.dominio.motor_ingesta import MotorIngesta
from nucleo.esquemas import ReporteCrudo
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento, ahora, nuevo_id
from nucleo.puertos import AuditoriaPort

CAMPOS_ENRIQUECIBLES = (
    "categoria",
    "urgencia",
    "severidad",
    "certeza",
    "ubicacion",
    "personas_afectadas",
    "necesidades",
)


class IngerirReportes:
    """Orquesta enriquecimiento (LLM/sensor) + motor de dominio + auditoría."""

    def __init__(
        self,
        motor: MotorIngesta,
        extractor: ExtractorPort,
        auditoria: AuditoriaPort,
        publicador: PublicadorPort,
        repositorio: RepositorioPort,
    ) -> None:
        self._motor = motor
        self._extractor = extractor
        self._auditoria = auditoria
        self._publicador = publicador
        self._repositorio = repositorio
        # Estado de idempotencia y back-pressure entre lotes. Vive aquí, no en
        # el motor, porque el motor debe seguir siendo una función pura de sus
        # argumentos: esto es lo único con estado mutable en toda la ruta.
        self._vistos: frozenset[str] = frozenset()
        self._en_ventana: tuple[datetime, ...] = ()

    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]:
        crudos = self._validar_forma(entrada)
        correlacion_id = str(entrada.get("correlacion_id") or nuevo_id())

        limpios = [await self._enriquecer(item) for item in crudos]

        momento = ahora()
        resultado = self._motor.procesar(limpios, self._vistos, self._en_ventana, momento)
        self._vistos = resultado.vistos
        self._en_ventana = resultado.en_ventana

        for reporte in resultado.aceptados:
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.REPORTE_RECIBIDO,
                    agente=Agente.INGESTA,
                    correlacion_id=correlacion_id,
                    detalle={"reporte_id": reporte.id, "canal": str(reporte.canal)},
                )
            )
        for descarte in resultado.descartados:
            await self._auditoria.registrar(
                EventoAuditoria(
                    tipo=TipoEvento.REPORTE_DESCARTADO,
                    agente=Agente.INGESTA,
                    correlacion_id=correlacion_id,
                    detalle=descarte.a_dict(),
                )
            )

        if resultado.aceptados:
            await self._repositorio.guardar([r.a_dict() for r in resultado.aceptados])
            await self._publicador.publicar(
                {
                    "correlacion_id": correlacion_id,
                    "aceptados": len(resultado.aceptados),
                    "descartados": len(resultado.descartados),
                }
            )

        return list(resultado.aceptados)

    # ------------------------------------------------------------- validación
    @staticmethod
    def _validar_forma(entrada: dict) -> list[Any]:
        if not isinstance(entrada, dict):
            raise LoteInvalidoError("la entrada debe ser un objeto con clave 'reportes'")
        crudos = entrada.get("reportes")
        if crudos is None:
            raise LoteInvalidoError("falta la clave 'reportes' en la entrada")
        if not isinstance(crudos, list):
            raise LoteInvalidoError("'reportes' debe ser una lista")
        return crudos

    # ---------------------------------------------------------- enriquecimiento
    async def _enriquecer(self, item: Any) -> Any:
        """Rellena campos que el motor de dominio validará. Un item malformado
        se deja pasar tal cual: el motor lo descarta con el motivo correcto en
        vez de que este método reviente el lote entero."""
        if not isinstance(item, dict):
            return item

        fuente = item.get("fuente")
        fuente_tipo = fuente.get("tipo") if isinstance(fuente, dict) else None
        datos_sensor = item.get("datos_sensor")

        if (item.get("canal") == "sensor" or fuente_tipo == "sensor") and isinstance(
            datos_sensor, dict
        ):
            # Un sensor ya trae datos estructurados: pasar por el LLM sería
            # latencia y ruido innecesarios, y el enunciado del reto lo pide
            # explícito ("mapear directo sin pasar por LLM").
            enriquecido = dict(item)
            if not enriquecido.get("texto"):
                # setdefault no sirve aquí: un adaptador de entrada (p. ej. el
                # modelo Pydantic de la API) puede mandar la clave "texto"
                # presente pero en None, y setdefault no la reemplazaría.
                enriquecido["texto"] = datos_sensor.get(
                    "descripcion", "lectura automática de sensor"
                )
            return self._rellenar(enriquecido, datos_sensor)

        texto = item.get("texto", "")
        if not isinstance(texto, str) or not texto.strip():
            return item

        contexto = {"fuente": fuente, "canal": item.get("canal")}
        extraido = await self._extractor.extraer(texto, contexto)
        return self._rellenar(dict(item), extraido)

    @staticmethod
    def _rellenar(base: dict, aportes: dict) -> dict:
        """Completa en ``base`` solo lo que falta. Lo explícito en el reporte
        original siempre gana sobre lo inferido: ni el LLM ni el sensor deben
        pisar un dato que la fuente ya declaró."""
        for campo in CAMPOS_ENRIQUECIBLES:
            if base.get(campo) is None and campo in aportes:
                base[campo] = aportes[campo]
        return base
