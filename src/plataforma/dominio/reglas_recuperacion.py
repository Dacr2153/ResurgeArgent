"""Reglas del plan de recuperación: de respuestas a hoja de ruta.

Es una tabla de reglas, no un texto redactado. Cada regla dice "si la respuesta a
esta pregunta es esta opción, entonces este paso entra en el plan", y el plan
final es la unión de los pasos disparados. Se hace así por tres razones:

- **Es auditable.** Ante un reclamo se puede señalar la regla exacta que puso (o
  no puso) un trámite en la hoja de ruta de una familia.
- **Es testeable.** Cada regla se prueba por separado con una sola respuesta.
- **No necesita LLM.** Un modelo generativo redactaría planes distintos para dos
  familias en la misma situación, y eso, en ayuda estatal, es discriminación.

Un paso puede ser disparado por varias reglas (una vivienda inhabitable y dos
heridos comparten el bono). Se deduplica por título conservando la primera
aparición: repetir un trámite en la lista hace creer que son dos.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from plataforma.dominio.entidades import Horizonte, PasoPlan, PreguntaRecuperacion

#: Cuestionario base. Vive en el dominio porque cada pregunta existe solo para
#: disparar reglas: añadir una que no dispare nada sería pedir un dato que no se
#: usa, y en una emergencia no se le piden datos inútiles a un damnificado.
CUESTIONARIO: tuple[PreguntaRecuperacion, ...] = (
    PreguntaRecuperacion(
        id="vivienda",
        pregunta="¿Tu vivienda quedó habitable?",
        opciones=("Sí, con daños menores", "Parcialmente", "No, está inhabitable"),
        orden=1,
    ),
    PreguntaRecuperacion(
        id="salud",
        pregunta="¿Alguien de tu familia necesita atención médica continua?",
        opciones=("No", "Sí, una persona", "Sí, dos o más"),
        orden=2,
    ),
    PreguntaRecuperacion(
        id="medios",
        pregunta="¿Perdiste documentos o medios de trabajo?",
        opciones=("Ninguno", "Documentos", "Medios de trabajo"),
        orden=3,
    ),
)


@dataclass(frozen=True, slots=True)
class Regla:
    """Una condición sobre una respuesta y el paso que activa."""

    pregunta_id: str
    opcion: str
    paso: PasoPlan


#: Paso que entra siempre. La constancia de damnificado es la llave de todo lo
#: demás: sin ella ningún otro trámite del Estado admite la solicitud, así que no
#: depende de ninguna respuesta.
PASO_BASE = PasoPlan(
    horizonte=Horizonte.HOY,
    titulo="Constancia de damnificado",
    cuerpo=(
        "Preséntate en el módulo municipal con el identificador de tu reporte y "
        "tu documento de identidad. Es el requisito de todos los demás trámites."
    ),
)

#: Tabla de reglas. El orden importa solo para desempatar dentro de un mismo
#: horizonte: los pasos se presentan agrupados por plazo.
REGLAS: tuple[Regla, ...] = (
    Regla(
        "vivienda",
        "No, está inhabitable",
        PasoPlan(
            Horizonte.HOY,
            "Albergue temporal",
            "Solicita cupo en el albergue asignado a tu zona antes de que anochezca. "
            "No vuelvas a la vivienda hasta la evaluación estructural.",
        ),
    ),
    Regla(
        "vivienda",
        "No, está inhabitable",
        PasoPlan(
            Horizonte.H72,
            "Evaluación estructural",
            "Un ingeniero de Defensa Civil debe certificar la vivienda antes de "
            "que alguien vuelva a habitarla.",
        ),
    ),
    Regla(
        "vivienda",
        "No, está inhabitable",
        PasoPlan(
            Horizonte.D15,
            "Bono de reconstrucción",
            "Solicítalo adjuntando la constancia de damnificado y el informe "
            "estructural.",
        ),
    ),
    Regla(
        "vivienda",
        "Parcialmente",
        PasoPlan(
            Horizonte.H72,
            "Evaluación estructural",
            "Un ingeniero de Defensa Civil debe certificar la vivienda antes de "
            "que alguien vuelva a habitarla.",
        ),
    ),
    Regla(
        "vivienda",
        "Sí, con daños menores",
        PasoPlan(
            Horizonte.D15,
            "Kit de reparaciones menores",
            "Retíralo en el módulo municipal presentando la constancia. Cubre "
            "materiales de cierre y techado provisional.",
        ),
    ),
    Regla(
        "salud",
        "Sí, una persona",
        PasoPlan(
            Horizonte.H72,
            "Continuidad de atención médica",
            "Registra a la persona en el puesto de salud de campaña para no "
            "interrumpir su tratamiento.",
        ),
    ),
    Regla(
        "salud",
        "Sí, dos o más",
        PasoPlan(
            Horizonte.HOY,
            "Visita de brigada médica domiciliaria",
            "Con dos o más personas dependientes el traslado es el riesgo: se "
            "solicita que la brigada acuda al domicilio o al albergue.",
        ),
    ),
    Regla(
        "salud",
        "Sí, dos o más",
        PasoPlan(
            Horizonte.H72,
            "Continuidad de atención médica",
            "Registra a las personas en el puesto de salud de campaña para no "
            "interrumpir sus tratamientos.",
        ),
    ),
    Regla(
        "medios",
        "Documentos",
        PasoPlan(
            Horizonte.D15,
            "Reposición de documentos",
            "La reposición por desastre es gratuita durante la emergencia. "
            "Tramítala antes de que venza el plazo excepcional.",
        ),
    ),
    Regla(
        "medios",
        "Medios de trabajo",
        PasoPlan(
            Horizonte.D15,
            "Bono de reactivación productiva",
            "Declara las herramientas o el vehículo perdidos: el bono repone el "
            "medio de sustento, no la vivienda.",
        ),
    ),
)


def derivar_plan(respuestas: dict[str, str]) -> list[PasoPlan]:
    """Aplica la tabla de reglas y devuelve la hoja de ruta ordenada por plazo.

    Las respuestas se comparan normalizadas (sin tildes, sin mayúsculas, sin
    espacios de sobra) porque llegan de un formulario y de una cola offline, y
    una tilde perdida en el transporte no puede dejar a alguien sin su albergue.
    """
    elegidas = {clave: _normalizar(valor) for clave, valor in respuestas.items()}

    pasos = [PASO_BASE]
    for regla in REGLAS:
        if elegidas.get(regla.pregunta_id) == _normalizar(regla.opcion):
            pasos.append(regla.paso)

    return _ordenar(_deduplicar(pasos))


def _deduplicar(pasos: list[PasoPlan]) -> list[PasoPlan]:
    vistos: set[str] = set()
    unicos: list[PasoPlan] = []
    for paso in pasos:
        if paso.titulo in vistos:
            continue
        vistos.add(paso.titulo)
        unicos.append(paso)
    return unicos


def _ordenar(pasos: list[PasoPlan]) -> list[PasoPlan]:
    """Agrupa por horizonte conservando el orden de disparo dentro de cada uno."""
    orden = {horizonte: indice for indice, horizonte in enumerate(Horizonte)}
    return sorted(pasos, key=lambda paso: orden[paso.horizonte])


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").strip().casefold()
