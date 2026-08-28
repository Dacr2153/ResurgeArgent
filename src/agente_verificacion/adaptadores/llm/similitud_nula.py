"""Similitud textual nula: léxica (Jaccard sobre tokens), sin red ni API key.

Imita a `agente_matching.adaptadores.llm.orquestador_nulo.OrquestadorNulo`: es
el adaptador que permite que todo el sistema corra y pase los tests sin
depender de un proveedor externo. No entiende sinónimos ni paráfrasis ("se cayó
el puente" vs "colapsó la estructura sobre el río" comparten pocas palabras),
así que es deliberadamente más conservador que `SimilitudLLM` — el motor
compensa esa debilidad con las señales deterministas (ubicación, categoría,
tiempo), que es justo el diseño que hace que el sistema no dependa del LLM
para funcionar.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-záéíóúñü0-9]+")


def _tokens(texto: str) -> set[str]:
    return set(_TOKEN_RE.findall(texto.lower()))


class SimilitudNula:
    async def comparar(
        self, pares: list[tuple[str, str, str, str]]
    ) -> dict[tuple[str, str], float]:
        resultado: dict[tuple[str, str], float] = {}
        for id_a, id_b, texto_a, texto_b in pares:
            tokens_a, tokens_b = _tokens(texto_a), _tokens(texto_b)
            if not tokens_a and not tokens_b:
                score = 0.0
            else:
                interseccion = len(tokens_a & tokens_b)
                union = len(tokens_a | tokens_b) or 1
                score = interseccion / union
            resultado[(id_a, id_b)] = score
        return resultado
