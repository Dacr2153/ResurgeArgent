"""Traducción de entidades a la forma que espera el frontend.

Vive en el adaptador de entrada y no en el dominio porque es contrato de una
interfaz concreta: las claves van en inglés y en camelCase porque así están
declaradas en `frontend/src/api/types.ts`, y renombrarlas obligaría a tocar todas
las pantallas. El dominio sigue hablando español.
"""

from __future__ import annotations

from typing import Any

from nucleo.geo import Punto
from plataforma.dominio.entidades import (
    Mision,
    PasoPlan,
    PreguntaRecuperacion,
    ReporteEncolado,
    ReporteSeguimiento,
)


def seguimiento(reporte: ReporteSeguimiento) -> dict[str, Any]:
    """`TrackedReport`."""
    return {
        "id": reporte.id,
        "title": reporte.titulo,
        "score": reporte.puntuacion,
        "steps": [
            {"label": paso.etiqueta, "meta": paso.meta, "done": paso.hecho}
            for paso in reporte.pasos
        ],
        "unreadMessages": reporte.mensajes_sin_leer,
    }


def mision_listada(mision: Mision, referencia: Punto) -> dict[str, Any]:
    """`Incident`: la fila de la lista de misiones abiertas."""
    return {
        "id": mision.incidente_id,
        "title": mision.titulo,
        "score": mision.puntuacion,
        "lat": mision.ubicacion.lat,
        "lng": mision.ubicacion.lon,
        "distanceKm": round(mision.distancia_km(referencia), 2),
        "need": mision.necesidad,
        "ageMinutes": mision.antiguedad_min(),
    }


def mision_detalle(mision: Mision, referencia: Punto) -> dict[str, Any]:
    """`Mission`: el detalle que ve quien va a salir."""
    return {
        "incidentId": mision.incidente_id,
        "title": mision.titulo,
        "address": mision.direccion,
        "etaMinutes": mision.eta_min(referencia),
        "distanceKm": round(mision.distancia_km(referencia), 2),
        "mode": mision.modo,
        "route": [list(punto) for punto in mision.ruta],
        "checklist": [{"key": i.clave, "label": i.etiqueta} for i in mision.checklist],
    }


def pregunta(pregunta_recuperacion: PreguntaRecuperacion) -> dict[str, Any]:
    """`RecoveryQuestion`."""
    return {
        "id": pregunta_recuperacion.id,
        "question": pregunta_recuperacion.pregunta,
        "options": list(pregunta_recuperacion.opciones),
    }


def plan(pasos: list[PasoPlan]) -> list[dict[str, Any]]:
    """`RecoveryPlanStep[]`.

    La numeración se calcula aquí, sobre la lista ya ordenada, y no se guarda en
    el paso: el mismo trámite puede ser el paso 2 de una familia y el 4 de otra,
    según qué más se les haya disparado.
    """
    return [
        {
            "tag": f"PASO {indice} · {paso.horizonte}",
            "title": paso.titulo,
            "body": paso.cuerpo,
        }
        for indice, paso in enumerate(pasos, start=1)
    ]


def encolado(reporte: ReporteEncolado) -> dict[str, Any]:
    """`QueuedSync`."""
    return {
        "id": reporte.id,
        "title": reporte.titulo,
        "meta": reporte.meta,
        "score": reporte.puntuacion,
    }
