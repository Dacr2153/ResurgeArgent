"""Entidades del dominio. Dataclasses inmutables, sin dependencias externas
más allá de ``nucleo`` (frontera de contratos entre agentes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agente_ingesta.dominio.value_objects import MotivoDescarte
from nucleo.esquemas import ReporteCrudo


@dataclass(frozen=True, slots=True)
class Descarte:
    """Un reporte que no entró, con el motivo y el detalle legible."""

    indice: int
    motivo: MotivoDescarte
    detalle: str

    def a_dict(self) -> dict:
        return {"indice": self.indice, "motivo": str(self.motivo), "detalle": self.detalle}


@dataclass(frozen=True, slots=True)
class ResultadoIngesta:
    """Salida de un ciclo de ``MotorIngesta.procesar``.

    ``vistos`` y ``en_ventana`` son el estado que el motor devuelve actualizado
    en vez de mutar: el motor es puro, así que quien lo llama (el caso de uso)
    es quien conserva ese estado entre llamadas.
    """

    aceptados: tuple[ReporteCrudo, ...] = field(default_factory=tuple)
    descartados: tuple[Descarte, ...] = field(default_factory=tuple)
    vistos: frozenset[str] = field(default_factory=frozenset)
    en_ventana: tuple[datetime, ...] = field(default_factory=tuple)
