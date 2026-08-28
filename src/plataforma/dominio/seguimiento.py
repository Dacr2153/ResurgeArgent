"""Derivación del recorrido que ve quien reportó una emergencia.

El recorrido no es una lista fija con texto bonito: cada peldaño se marca hecho
solo si existe una transición realmente aplicada a ese estado en la operación del
Orquestador, y su detalle sale del motivo que quedó registrado en el historial.
Es la misma evidencia que lee el post-mortem, mostrada en lenguaje de ciudadano.
"""

from __future__ import annotations

from plataforma.dominio.entidades import (
    EstadoOperacion,
    HitoOperacion,
    PasoSeguimiento,
    ReporteSeguimiento,
)

#: Peldaños del recorrido, en orden, y el estado de la operación que los cumple.
#: Son cinco y no diez porque cada uno responde una pregunta que el ciudadano se
#: hace de verdad: ¿llegó?, ¿me creyeron?, ¿qué lugar tengo?, ¿va alguien?,
#: ¿terminó? Los estados intermedios del Orquestador no le dicen nada.
RECORRIDO: tuple[tuple[str, str], ...] = (
    ("Reporte recibido", "recibido"),
    ("Verificado", "verificado"),
    ("Priorizado", "priorizado"),
    ("Brigada asignada", "asignado"),
    ("Atendido", "resuelto"),
)

#: Estados cuya llegada genera un aviso para quien reportó. Solo los que cambian
#: lo que esa persona debe hacer o esperar; el resto es ruido de tramitación.
ESTADOS_NOTIFICABLES = frozenset({"asignado", "en_ejecucion", "resuelto", "suspendido"})

#: Umbrales de las bandas de prioridad. Son los mismos que usa el tablero del
#: coordinador: si el ciudadano y el coordinador vieran bandas distintas para el
#: mismo incidente, ninguna de las dos sería creíble.
UMBRAL_CRITICO = 80
UMBRAL_ALTO = 60

META_PENDIENTE = "pendiente"


def banda(puntuacion: int) -> str:
    """Banda de prioridad de una puntuación de triage ya escalada a 0-100."""
    if puntuacion >= UMBRAL_CRITICO:
        return "CRÍTICO"
    if puntuacion >= UMBRAL_ALTO:
        return "ALTO"
    return "MEDIO"


def escalar(puntuacion: float | None) -> int:
    """Lleva la puntuación de triage, que vive en [0,1], a la escala 0-100.

    El frontend y el coordinador razonan en enteros ("CRÍTICO 92"): mostrar
    0.9231 obligaría a cada pantalla a repetir esta conversión, y bastaría con
    que una la hiciera distinta para que dos vistas discreparan del mismo caso.
    """
    if puntuacion is None:
        return 0
    return max(0, min(100, round(puntuacion * 100)))


def derivar_recorrido(estado: EstadoOperacion) -> ReporteSeguimiento:
    """Traduce una operación a los pasos que ve quien reportó."""
    puntuacion = escalar(estado.puntuacion)
    aplicados = _primer_hito_por_estado(estado.hitos)

    pasos: list[PasoSeguimiento] = []
    for etiqueta, estado_esperado in RECORRIDO:
        hito = aplicados.get(estado_esperado)
        # RECIBIDO no genera transición: es el estado con el que nace la
        # operación. Que la operación exista ya prueba que el reporte llegó.
        hecho = hito is not None or estado_esperado == "recibido"
        pasos.append(
            PasoSeguimiento(
                etiqueta=_etiqueta(etiqueta, estado_esperado, puntuacion),
                meta=_meta(hito),
                hecho=hecho,
            )
        )

    return ReporteSeguimiento(
        id=estado.incidente_id,
        titulo=estado.titulo,
        puntuacion=puntuacion,
        pasos=tuple(pasos),
        mensajes_sin_leer=contar_avisos(estado.hitos),
    )


def contar_avisos(hitos: tuple[HitoOperacion, ...]) -> int:
    """Cuántas transiciones aplicadas merecen un aviso al ciudadano."""
    return sum(1 for h in hitos if h.aplicada and h.estado in ESTADOS_NOTIFICABLES)


def _primer_hito_por_estado(hitos: tuple[HitoOperacion, ...]) -> dict[str, HitoOperacion]:
    """Primera entrada aplicada a cada estado.

    La primera y no la última: si un incidente reentra a un estado tras una
    suspensión, la fecha que le importa a quien reportó es cuándo ocurrió por
    primera vez, no cuándo el sistema lo reconfirmó.
    """
    primeros: dict[str, HitoOperacion] = {}
    for hito in hitos:
        if hito.aplicada and hito.estado not in primeros:
            primeros[hito.estado] = hito
    return primeros


def _etiqueta(base: str, estado_esperado: str, puntuacion: int) -> str:
    if estado_esperado == "priorizado" and puntuacion:
        return f"{base} · {banda(puntuacion)} {puntuacion}"
    return base


def _meta(hito: HitoOperacion | None) -> str:
    if hito is None:
        return META_PENDIENTE
    hora = hito.momento.strftime("%H:%M")
    return f"{hora} · {hito.motivo}" if hito.motivo else hora
