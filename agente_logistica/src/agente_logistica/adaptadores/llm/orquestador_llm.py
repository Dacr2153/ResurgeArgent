"""Orquestador LLM del Agente 8 (normalizar + explicar) usando un ``ClienteLLM``.

Reutiliza el cliente de proveedor del Agente 7 (Anthropic/DeepSeek).
"""

from __future__ import annotations

import json
import re

from agente_logistica.adaptadores.llm.clientes import ClienteLLM
from agente_logistica.aplicacion.puertos.salida import LLMAgente8Port


class OrquestadorLLM(LLMAgente8Port):
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

    async def explicar(self, plan: dict, contexto: dict) -> dict:
        contenido = await self._cliente.completar(
            self._rol_prompt,
            "Explica este plan logístico y añade 'justificaciones' y 'supuestos'.\n"
            f"Plan:\n{json.dumps(plan, ensure_ascii=False)}\n"
            f"Contexto normalizado:\n{json.dumps(contexto, ensure_ascii=False)}",
        )
        enriquecido = self._extraer_json(contenido)
        if isinstance(enriquecido, dict) and "operaciones" in enriquecido:
            return enriquecido
        return {**plan, "supuestos": [], "justificaciones": []}

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
