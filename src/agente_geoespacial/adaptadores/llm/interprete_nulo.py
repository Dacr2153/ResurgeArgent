"""Intérprete nulo: extrae vías bloqueadas por palabras clave, sin red ni API key.

Es el que corre en tests y en modo offline. Cumple ``LLMInterpretePort`` con
reglas simples y deterministas en vez de un modelo de lenguaje: reconoce un
puñado de palabras que delatan bloqueo y exige que el reporte marque
explícitamente el tramo (``via:T2`` o ``tramo:T2``), porque sin comprensión de
lenguaje no puede inferir "la calle 13" a partir de un id de tramo interno.
"""

from __future__ import annotations

import re

PALABRAS_CLAVE_BLOQUEO = (
    "bloquead",
    "tapad",
    "derrumb",
    "cerrad",
    "obstruid",
    "colapsad",
    "inundad",
    "cortad",
    "impasable",
    "intransitable",
    "no se puede pasar",
    "no hay paso",
    "se llevó el puente",
    "se cayó el puente",
)

_PATRON_ID = re.compile(r"(?:via|tramo)[:=]([\w-]+)", flags=re.IGNORECASE)


class InterpreteNulo:
    async def interpretar(self, reportes_texto: list[str]) -> list[str]:
        ids: list[str] = []
        for reporte in reportes_texto:
            texto = reporte.lower()
            if not any(clave in texto for clave in PALABRAS_CLAVE_BLOQUEO):
                continue
            ids.extend(_PATRON_ID.findall(reporte))

        # Sin duplicados, conservando el orden de aparición (útil para auditoría).
        vistos: set[str] = set()
        resultado: list[str] = []
        for id_tramo in ids:
            if id_tramo not in vistos:
                vistos.add(id_tramo)
                resultado.append(id_tramo)
        return resultado
