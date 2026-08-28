"""Orquestador LLM genérico: implementa ``LLMOrquestadorPort`` usando un ``ClienteLLM``.

La lógica de normalización/justificación es independiente del proveedor; solo
depende de ``cliente.completar(system, user)``. Si la respuesta no es JSON válido,
degrada de forma segura al passthrough.
"""

from __future__ import annotations

import json
import re

from agente_matching.adaptadores.llm.clientes import ClienteLLM
from agente_matching.aplicacion.puertos.salida import LLMOrquestadorPort


class OrquestadorLLM(LLMOrquestadorPort):
    def __init__(self, cliente: ClienteLLM, rol_prompt: str):
        self._cliente = cliente
        self._rol_prompt = rol_prompt

    async def normalizar(self, json_crudo: dict) -> dict:
        contenido = await self._cliente.completar(
            self._rol_prompt,
            "Normaliza y completa este JSON de entrada:\n"
            f"{json.dumps(json_crudo, ensure_ascii=False)}",
        )
        normalizado = self._extraer_json(contenido)
        return normalizado if isinstance(normalizado, dict) else json_crudo

    async def justificar(self, resultado_motor: dict, contexto: dict) -> dict:
        contenido = await self._cliente.completar(
            self._rol_prompt,
            "Añade 'justificaciones' y 'supuestos' legibles a este resultado.\n"
            f"Resultado del motor:\n{json.dumps(resultado_motor, ensure_ascii=False)}\n"
            f"Contexto normalizado:\n{json.dumps(contexto, ensure_ascii=False)}",
        )
        enriquecido = self._extraer_json(contenido)
        if isinstance(enriquecido, dict) and "asignaciones" in enriquecido:
            return enriquecido
        return {**resultado_motor, "supuestos": [], "justificaciones": []}

    @staticmethod
    def _extraer_json(texto: str):
        texto = texto.strip()
        m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.DOTALL)
        if m:
            texto = m.group(1).strip()
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            inicio = texto.find("{")
            fin = texto.rfind("}")
            if inicio != -1 and fin > inicio:
                try:
                    return json.loads(texto[inicio : fin + 1])
                except json.JSONDecodeError:
                    return None
            return None
