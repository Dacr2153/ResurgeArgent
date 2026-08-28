"""Value objects del dominio del Orquestador.

Aquí viven los pesos del triage. Están en el dominio y no en la configuración
porque son una decisión doctrinal, no un parámetro de despliegue: cambiarlos
cambia a quién se rescata primero, y eso se revisa en un PR, no en una variable
de entorno. `Settings` puede sobreescribirlos, pero el valor por defecto es este.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from nucleo.esquemas import Severidad, Urgencia

#: Peso de cada nivel CAP de severidad, normalizado a [0,1].
#: UNKNOWN no vale 0: un incidente sin clasificar no es un incidente inofensivo.
#: Se le da un valor bajo pero por encima de MINOR-menos, para que entre a la cola
#: en vez de desaparecer de ella mientras alguien lo clasifica.
PESO_SEVERIDAD: dict[Severidad, float] = {
    Severidad.EXTREME: 1.00,
    Severidad.SEVERE: 0.75,
    Severidad.MODERATE: 0.45,
    Severidad.MINOR: 0.20,
    Severidad.UNKNOWN: 0.30,
}

#: Peso de cada nivel CAP de urgencia. PAST es casi cero porque el margen de
#: acción ya pasó: atenderlo primero no salva a nadie y desplaza a quien sí.
PESO_URGENCIA: dict[Urgencia, float] = {
    Urgencia.IMMEDIATE: 1.00,
    Urgencia.EXPECTED: 0.65,
    Urgencia.FUTURE: 0.35,
    Urgencia.PAST: 0.10,
    Urgencia.UNKNOWN: 0.30,
}

#: Escala de saturación del factor de personas afectadas, en personas.
#: Con escala logarítmica, la diferencia entre 5 y 20 afectados pesa mucho más que
#: entre 500 y 515, que es como funciona la utilidad marginal de un equipo de
#: rescate: el primer equipo enviado a un sitio salva más vidas que el décimo.
ESCALA_PERSONAS = 1000.0

#: Piso del multiplicador de confianza. Un incidente con confianza 0 no se anula:
#: conserva la mitad de su puntuación. Un reporte no corroborado de un colapso
#: estructural debe seguir por encima de una fuga de agua confirmada.
PISO_CONFIANZA = 0.5


@dataclass(frozen=True, slots=True)
class PesosTriage:
    """Ponderación relativa de los factores del triage. Deben sumar 1."""

    severidad: float = 0.45
    urgencia: float = 0.35
    personas: float = 0.20

    def __post_init__(self) -> None:
        total = self.severidad + self.urgencia + self.personas
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"los pesos del triage deben sumar 1.0, suman {total}")
        if min(self.severidad, self.urgencia, self.personas) < 0:
            raise ValueError("los pesos del triage no pueden ser negativos")


def factor_personas(personas_afectadas: int | None) -> float:
    """Normaliza el número de afectados a [0,1] con saturación logarítmica.

    `None` no es 0: significa "no sabemos cuántos", y se trata como un incidente
    pequeño pero real, no como un incidente sin víctimas.
    """
    if personas_afectadas is None:
        return 0.15
    if personas_afectadas <= 0:
        return 0.0
    return min(1.0, math.log10(1.0 + personas_afectadas) / math.log10(1.0 + ESCALA_PERSONAS))


def factor_confianza(confianza: float) -> float:
    """Multiplicador de credibilidad en [PISO_CONFIANZA, 1]."""
    return PISO_CONFIANZA + (1.0 - PISO_CONFIANZA) * max(0.0, min(1.0, confianza))


@dataclass(frozen=True, slots=True)
class PuntuacionTriage:
    """Resultado del triage para un incidente, con su desglose reproducible.

    Guardar los componentes y no solo el número es lo que hace el orden
    explicable: ante un reclamo, se puede mostrar exactamente qué sumó cada
    factor sin volver a ejecutar nada.
    """

    incidente_id: str
    puntuacion: float
    componentes: dict[str, float] = field(default_factory=dict)
    posicion: int = 0

    def a_dict(self) -> dict[str, Any]:
        return {
            "incidente_id": self.incidente_id,
            "posicion": self.posicion,
            "puntuacion": round(self.puntuacion, 6),
            "componentes": {k: round(v, 6) for k, v in self.componentes.items()},
        }
