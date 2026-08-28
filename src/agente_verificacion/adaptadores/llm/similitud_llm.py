"""Adaptador LLM: opina si dos descripciones hablan del mismo hecho.

Solo devuelve un score de similitud semántica en [0,1] por par. La decisión de
fusionar dos reportes en un incidente la toma siempre `MotorVerificacion`, vía
`VerificarReportes.verificar` — este adaptador no ve ni ubicación ni tiempo ni
categoría, y no tiene forma de fusionar nada por su cuenta aunque quisiera.
"""

from __future__ import annotations

import json
import re

from agente_verificacion.adaptadores.llm.clientes import ClienteLLM


class SimilitudLLM:
    def __init__(self, cliente: ClienteLLM, rol_prompt: str):
        self._cliente = cliente
        self._rol_prompt = rol_prompt

    async def comparar(
        self, pares: list[tuple[str, str, str, str]]
    ) -> dict[tuple[str, str], float]:
        if not pares:
            return {}

        entrada = [
            {"id_a": id_a, "id_b": id_b, "texto_a": texto_a, "texto_b": texto_b}
            for id_a, id_b, texto_a, texto_b in pares
        ]
        contenido = await self._cliente.completar(
            self._rol_prompt,
            "Evalúa si cada par de descripciones habla del mismo hecho. Responde "
            'únicamente con una lista JSON de objetos {"id_a", "id_b", "similitud"}, '
            "con similitud en [0,1].\n"
            f"Pares:\n{json.dumps(entrada, ensure_ascii=False)}",
        )
        crudo = self._extraer_json(contenido)

        resultado: dict[tuple[str, str], float] = {}
        if isinstance(crudo, list):
            for item in crudo:
                try:
                    id_a, id_b = item["id_a"], item["id_b"]
                    score = float(item["similitud"])
                except (KeyError, TypeError, ValueError):
                    continue
                resultado[(id_a, id_b)] = max(0.0, min(1.0, score))

        # Un par sin respuesta útil del LLM degrada a similitud 0.0: el motor
        # decide igual con las señales deterministas, nunca se bloquea por un
        # LLM que no respondió o respondió basura.
        for id_a, id_b, _, _ in pares:
            resultado.setdefault((id_a, id_b), 0.0)
        return resultado

    @staticmethod
    def _extraer_json(texto: str):
        texto = texto.strip()
        m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.DOTALL)
        if m:
            texto = m.group(1).strip()
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            inicio = texto.find("[")
            fin = texto.rfind("]")
            if inicio != -1 and fin > inicio:
                try:
                    return json.loads(texto[inicio : fin + 1])
                except json.JSONDecodeError:
                    return None
            return None
