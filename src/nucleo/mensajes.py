"""Sobre común de mensajes entre agentes.

La estructura sigue dos estándares que el diseño documentado adopta:

- **FIPA-ACL** aporta el acto comunicativo (`performativa`): un mensaje no solo
  lleva datos, declara qué pretende. Es lo que permite al Orquestador delegar con
  Contract Net — `CFP` convoca, `PROPOSE` oferta, `ACCEPT_PROPOSAL` adjudica.
- **EDXL-DE** aporta el sobre de distribución: identificador, emisor, momento y
  correlación, para poder reconstruir una operación completa desde el log.

`correlacion_id` es el hilo que une todos los mensajes de un mismo incidente a
través de los cuatro agentes. Sin él no hay trazabilidad de la decisión.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

VERSION_PROTOCOLO = "1.0"


class Performativa(StrEnum):
    """Actos comunicativos FIPA-ACL usados por el sistema."""

    INFORM = "inform"
    REQUEST = "request"
    CFP = "cfp"
    PROPOSE = "propose"
    REFUSE = "refuse"
    ACCEPT_PROPOSAL = "accept-proposal"
    REJECT_PROPOSAL = "reject-proposal"
    INFORM_DONE = "inform-done"
    INFORM_RESULT = "inform-result"
    FAILURE = "failure"


class Agente(StrEnum):
    """Identificadores de los agentes del sistema."""

    ORQUESTADOR = "agente-1-orquestador"
    INGESTA = "agente-2-ingesta"
    VERIFICACION = "agente-3-verificacion"
    GEOESPACIAL = "agente-5-geoespacial"
    MATCHING = "agente-7-matching"
    HUMANO = "coordinador-humano"


def ahora() -> datetime:
    """Momento actual en UTC. Único punto de lectura del reloj: los tests lo sustituyen."""
    return datetime.now(UTC)


def nuevo_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True, slots=True)
class Mensaje:
    """Sobre que envuelve cualquier intercambio entre agentes."""

    emisor: Agente
    receptor: Agente
    performativa: Performativa
    contenido: dict[str, Any]
    correlacion_id: str
    id: str = field(default_factory=nuevo_id)
    momento: datetime = field(default_factory=ahora)
    version: str = VERSION_PROTOCOLO
    responde_a: str | None = None

    def responder(
        self,
        performativa: Performativa,
        contenido: dict[str, Any],
        emisor: Agente | None = None,
    ) -> Mensaje:
        """Construye la respuesta a este mensaje conservando el hilo de correlación."""
        return Mensaje(
            emisor=emisor or self.receptor,
            receptor=self.emisor,
            performativa=performativa,
            contenido=contenido,
            correlacion_id=self.correlacion_id,
            responde_a=self.id,
        )

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "correlacion_id": self.correlacion_id,
            "responde_a": self.responde_a,
            "emisor": str(self.emisor),
            "receptor": str(self.receptor),
            "performativa": str(self.performativa),
            "momento": self.momento.isoformat(),
            "version": self.version,
            "contenido": self.contenido,
        }


class TipoEvento(StrEnum):
    """Eventos de auditoría. Todo paso relevante de cualquier agente emite uno."""

    REPORTE_RECIBIDO = "reporte_recibido"
    REPORTE_DESCARTADO = "reporte_descartado"
    REPORTE_NORMALIZADO = "reporte_normalizado"
    INCIDENTE_VERIFICADO = "incidente_verificado"
    INCIDENTE_FUSIONADO = "incidente_fusionado"
    CONFIANZA_CALCULADA = "confianza_calculada"
    RUTA_CALCULADA = "ruta_calculada"
    VIA_BLOQUEADA = "via_bloqueada"
    TRANSICION_ESTADO = "transicion_estado"
    TAREA_DELEGADA = "tarea_delegada"
    DECISION_HUMANA_REGISTRADA = "decision_humana_registrada"
    AGENTE_SIN_RESPUESTA = "agente_sin_respuesta"
    COMPENSACION_EJECUTADA = "compensacion_ejecutada"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class EventoAuditoria:
    """Registro inmutable de algo que ocurrió. Es la memoria legal del sistema."""

    tipo: TipoEvento
    agente: Agente
    correlacion_id: str
    detalle: dict[str, Any]
    id: str = field(default_factory=nuevo_id)
    momento: datetime = field(default_factory=ahora)

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": str(self.tipo),
            "agente": str(self.agente),
            "correlacion_id": self.correlacion_id,
            "momento": self.momento.isoformat(),
            "detalle": self.detalle,
        }
