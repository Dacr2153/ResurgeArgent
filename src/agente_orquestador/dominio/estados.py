"""Máquina de estados del incidente: la columna vertebral del Orquestador.

Un incidente avanza por una secuencia fija. La secuencia es corta a propósito:
cada estado corresponde a una pregunta que alguien tiene que poder responder
después, en frío, leyendo el log de auditoría.

    RECIBIDO              llegó algo, todavía no sabemos si es cierto
    VERIFICADO            el Agente 3 lo corroboró y le puso confianza
    LOCALIZADO            sabemos dónde está y cómo llegar (o que no se puede)
    PRIORIZADO            el triage le asignó un lugar en la cola
    PENDIENTE_APROBACION  esperando la firma del coordinador humano
    ASIGNADO              hay firma y hay recursos comprometidos
    EN_EJECUCION          el recurso va en camino
    RESUELTO              terminó

Más dos estados fuera de la línea principal:

    SUSPENDIDO            se congela sin cerrarse (timeout, ciclo, rechazo)
    DESCARTADO            se cierra sin atender (falso, duplicado, rechazado)

La regla que no se rompe: `PENDIENTE_APROBACION -> ASIGNADO` exige una
`DecisionHumana` firmada y aprobada. Ningún camino automático llega a ASIGNADO.
"""

from __future__ import annotations

from enum import StrEnum

from agente_orquestador.dominio.excepciones import (
    DecisionHumanaRequeridaError,
    DecisionRechazadaError,
    TransicionInvalidaError,
)
from nucleo.esquemas import DecisionHumana


class EstadoIncidente(StrEnum):
    """Estados por los que pasa un incidente dentro del Orquestador."""

    RECIBIDO = "recibido"
    VERIFICADO = "verificado"
    LOCALIZADO = "localizado"
    PRIORIZADO = "priorizado"
    PENDIENTE_APROBACION = "pendiente_aprobacion"
    ASIGNADO = "asignado"
    EN_EJECUCION = "en_ejecucion"
    RESUELTO = "resuelto"
    SUSPENDIDO = "suspendido"
    DESCARTADO = "descartado"


#: Estados desde los que ya no se sale. Ni el motor ni un humano los reabren:
#: reabrir una emergencia cerrada se hace creando un incidente nuevo, para que el
#: historial del anterior siga siendo una lectura fiel de lo que pasó.
ESTADOS_TERMINALES = frozenset({EstadoIncidente.RESUELTO, EstadoIncidente.DESCARTADO})

#: Transiciones que el sistema puede ejecutar solo, sin intervención humana.
#: Nótese que ASIGNADO no aparece en ningún conjunto: es inalcanzable por esta vía.
TRANSICIONES_AUTOMATICAS: dict[EstadoIncidente, frozenset[EstadoIncidente]] = {
    EstadoIncidente.RECIBIDO: frozenset(
        {EstadoIncidente.VERIFICADO, EstadoIncidente.SUSPENDIDO, EstadoIncidente.DESCARTADO}
    ),
    EstadoIncidente.VERIFICADO: frozenset(
        {EstadoIncidente.LOCALIZADO, EstadoIncidente.SUSPENDIDO, EstadoIncidente.DESCARTADO}
    ),
    EstadoIncidente.LOCALIZADO: frozenset(
        {EstadoIncidente.PRIORIZADO, EstadoIncidente.SUSPENDIDO, EstadoIncidente.DESCARTADO}
    ),
    EstadoIncidente.PRIORIZADO: frozenset(
        {
            EstadoIncidente.PENDIENTE_APROBACION,
            EstadoIncidente.SUSPENDIDO,
            EstadoIncidente.DESCARTADO,
        }
    ),
    # Un incidente puede suspenderse esperando firma (el coordinador no respondió)
    # pero jamás asignarse por esa vía.
    EstadoIncidente.PENDIENTE_APROBACION: frozenset({EstadoIncidente.SUSPENDIDO}),
    EstadoIncidente.ASIGNADO: frozenset(
        {EstadoIncidente.EN_EJECUCION, EstadoIncidente.SUSPENDIDO, EstadoIncidente.DESCARTADO}
    ),
    EstadoIncidente.EN_EJECUCION: frozenset(
        {EstadoIncidente.RESUELTO, EstadoIncidente.SUSPENDIDO}
    ),
    # Reanudar devuelve el incidente a la cola de priorización, no al punto donde
    # se cayó: mientras estuvo suspendido el contexto cambió y hay que re-triarlo.
    EstadoIncidente.SUSPENDIDO: frozenset(
        {EstadoIncidente.PRIORIZADO, EstadoIncidente.DESCARTADO}
    ),
    EstadoIncidente.RESUELTO: frozenset(),
    EstadoIncidente.DESCARTADO: frozenset(),
}

#: Transiciones que solo ocurren con una `DecisionHumana` firmada.
#: La aprobación despacha; el rechazo cierra o congela. No hay tercera opción.
TRANSICIONES_CON_DECISION_HUMANA: dict[EstadoIncidente, frozenset[EstadoIncidente]] = {
    EstadoIncidente.PENDIENTE_APROBACION: frozenset(
        {EstadoIncidente.ASIGNADO, EstadoIncidente.DESCARTADO, EstadoIncidente.SUSPENDIDO}
    ),
}

#: Destinos que exigen que la decisión venga aprobada. El resto de destinos con
#: firma son los que se alcanzan justamente porque la decisión fue un rechazo.
DESTINOS_QUE_EXIGEN_APROBACION = frozenset({EstadoIncidente.ASIGNADO})


def transiciones_posibles(origen: EstadoIncidente) -> frozenset[EstadoIncidente]:
    """Todos los destinos alcanzables desde `origen`, con o sin firma humana."""
    return TRANSICIONES_AUTOMATICAS.get(origen, frozenset()) | (
        TRANSICIONES_CON_DECISION_HUMANA.get(origen, frozenset())
    )


def validar_transicion(
    origen: EstadoIncidente,
    destino: EstadoIncidente,
    decision: DecisionHumana | None = None,
) -> None:
    """Verifica que se pueda pasar de `origen` a `destino`. Lanza si no.

    El orden de comprobación importa: primero se descarta lo imposible, y solo
    después se evalúa la firma. Así el mensaje de error distingue "esa transición
    no existe" de "esa transición existe pero te falta la firma", que son dos
    problemas distintos para quien opera el sistema.
    """
    if origen == destino:
        raise TransicionInvalidaError(
            f"transición nula no permitida: el incidente ya está en {origen}"
        )

    automaticos = TRANSICIONES_AUTOMATICAS.get(origen, frozenset())
    con_firma = TRANSICIONES_CON_DECISION_HUMANA.get(origen, frozenset())

    if destino not in automaticos and destino not in con_firma:
        raise TransicionInvalidaError(f"transición no permitida: {origen} -> {destino}")

    if destino in con_firma:
        if decision is not None:
            _validar_decision(destino, decision)
            return
        if destino in automaticos:
            # Existe también por vía automática (p. ej. la suspensión por timeout).
            return
        raise DecisionHumanaRequeridaError(
            f"{origen} -> {destino} exige una decisión humana firmada; no se recibió ninguna"
        )

    # Destino puramente automático: una firma sobra, pero no invalida nada.
    return


def _validar_decision(destino: EstadoIncidente, decision: DecisionHumana) -> None:
    """Comprueba que el sentido de la firma coincida con el destino solicitado."""
    if destino in DESTINOS_QUE_EXIGEN_APROBACION and not decision.aprobada:
        raise DecisionRechazadaError(
            f"la decisión {decision.id} del coordinador {decision.coordinador_id} "
            f"fue un rechazo: no puede llevar el incidente a {destino}"
        )
    if destino not in DESTINOS_QUE_EXIGEN_APROBACION and decision.aprobada:
        raise TransicionInvalidaError(
            f"la decisión {decision.id} fue una aprobación: no puede llevar a {destino}"
        )
