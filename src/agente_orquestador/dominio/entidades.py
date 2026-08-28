"""Entidades del Orquestador: la operación abierta sobre un incidente.

`Operacion` es el único sitio donde cambia el estado de un incidente. Nadie
asigna `operacion.estado` desde fuera: se llama a `transicionar`, que valida
contra la máquina de estados, cuenta visitas y deja rastro en el historial.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agente_orquestador.dominio.estados import (
    ESTADOS_TERMINALES,
    EstadoIncidente,
    validar_transicion,
)
from agente_orquestador.dominio.excepciones import DecisionNoCorrespondeError
from agente_orquestador.dominio.value_objects import PuntuacionTriage
from nucleo.esquemas import DecisionHumana
from nucleo.mensajes import ahora

#: Cuántas veces puede un incidente entrar al mismo estado antes de que se
#: considere un ciclo. Tres es el valor por defecto porque dos reintentos son
#: normales (un agente que se recupera, un coordinador que pide más datos) y el
#: tercero ya indica que el sistema está dando vueltas sin converger.
LIMITE_VISITAS_POR_ESTADO = 3


@dataclass(frozen=True, slots=True)
class RegistroTransicion:
    """Una entrada del historial. Inmutable: es evidencia, no estado de trabajo."""

    origen: EstadoIncidente
    solicitado: EstadoIncidente
    estado: EstadoIncidente
    aplicada: bool
    motivo: str
    momento: datetime
    decision_id: str | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "origen": str(self.origen),
            "solicitado": str(self.solicitado),
            "estado": str(self.estado),
            "aplicada": self.aplicada,
            "motivo": self.motivo,
            "momento": self.momento.isoformat(),
            "decision_id": self.decision_id,
        }


@dataclass
class Operacion:
    """Operación abierta sobre un incidente: su estado, su historia y su firma."""

    incidente_id: str
    correlacion_id: str
    estado: EstadoIncidente = EstadoIncidente.RECIBIDO
    limite_visitas: int = LIMITE_VISITAS_POR_ESTADO
    historial: list[RegistroTransicion] = field(default_factory=list)
    visitas: Counter[EstadoIncidente] = field(default_factory=Counter)
    decision: DecisionHumana | None = None
    puntuacion: PuntuacionTriage | None = None
    datos: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # El estado inicial también cuenta como visita: si el incidente vuelve a
        # RECIBIDO, la cuenta ya arranca en 1 y el ciclo se detecta igual.
        if not self.visitas:
            self.visitas[self.estado] = 1

    @property
    def terminada(self) -> bool:
        return self.estado in ESTADOS_TERMINALES

    @property
    def suspendida(self) -> bool:
        return self.estado is EstadoIncidente.SUSPENDIDO

    def transicionar(
        self,
        destino: EstadoIncidente,
        decision: DecisionHumana | None = None,
        motivo: str = "",
        momento: datetime | None = None,
    ) -> RegistroTransicion:
        """Mueve la operación a `destino`, o la suspende si detecta un ciclo.

        Nunca lanza por ciclo: devolver una transición marcada `aplicada=False`
        con destino SUSPENDIDO permite que el llamador siga operando con lo que
        tiene. Una excepción aquí tumbaría el procesamiento del lote entero por
        culpa de un solo incidente que da vueltas.
        """
        if decision is not None and decision.incidente_id != self.incidente_id:
            raise DecisionNoCorrespondeError(
                f"la decisión {decision.id} firma sobre {decision.incidente_id}, "
                f"no sobre {self.incidente_id}"
            )

        validar_transicion(self.estado, destino, decision)

        if self._cierra_ciclo(destino):
            return self._suspender_por_ciclo(destino, momento)

        return self._registrar(
            solicitado=destino,
            estado=destino,
            aplicada=True,
            motivo=motivo,
            decision=decision,
            momento=momento,
        )

    def registrar_decision(self, decision: DecisionHumana) -> None:
        """Deja la firma adherida a la operación, decida lo que decida."""
        if decision.incidente_id != self.incidente_id:
            raise DecisionNoCorrespondeError(
                f"la decisión {decision.id} firma sobre {decision.incidente_id}, "
                f"no sobre {self.incidente_id}"
            )
        self.decision = decision

    def a_dict(self) -> dict[str, Any]:
        return {
            "incidente_id": self.incidente_id,
            "correlacion_id": self.correlacion_id,
            "estado": str(self.estado),
            "visitas": {str(k): v for k, v in self.visitas.items()},
            "historial": [r.a_dict() for r in self.historial],
            "decision": self.decision.a_dict() if self.decision else None,
            "triage": self.puntuacion.a_dict() if self.puntuacion else None,
            "datos": self.datos,
        }

    # ------------------------------------------------------------------ interno
    def _cierra_ciclo(self, destino: EstadoIncidente) -> bool:
        """¿Entrar a `destino` sería volver a un estado ya agotado?

        SUSPENDIDO y los terminales quedan fuera de la cuenta: son justamente las
        salidas del ciclo, y contarlas haría imposible salir.
        """
        if destino is EstadoIncidente.SUSPENDIDO or destino in ESTADOS_TERMINALES:
            return False
        return self.visitas[destino] >= self.limite_visitas

    def _suspender_por_ciclo(
        self, destino: EstadoIncidente, momento: datetime | None
    ) -> RegistroTransicion:
        """Desvía la transición a SUSPENDIDO y deja constancia del motivo.

        Si la operación ya estaba suspendida, el registro documenta el intento de
        reanudación rechazado: el estado no cambia, pero el intento sí queda.
        """
        motivo = (
            f"ciclo detectado: {destino} visitado {self.visitas[destino]} veces "
            f"(límite {self.limite_visitas}); se suspende para revisión humana"
        )
        return self._registrar(
            solicitado=destino,
            estado=EstadoIncidente.SUSPENDIDO,
            aplicada=False,
            motivo=motivo,
            decision=None,
            momento=momento,
        )

    def _registrar(
        self,
        solicitado: EstadoIncidente,
        estado: EstadoIncidente,
        aplicada: bool,
        motivo: str,
        decision: DecisionHumana | None,
        momento: datetime | None,
    ) -> RegistroTransicion:
        registro = RegistroTransicion(
            origen=self.estado,
            solicitado=solicitado,
            estado=estado,
            aplicada=aplicada,
            motivo=motivo,
            momento=momento or ahora(),
            decision_id=decision.id if decision else None,
        )
        self.historial.append(registro)
        if self.estado != estado:
            self.visitas[estado] += 1
        self.estado = estado
        if decision is not None:
            self.decision = decision
        return registro
