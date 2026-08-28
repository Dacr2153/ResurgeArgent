"""Extractor LLM: implementa ``ExtractorPort`` usando un ``ClienteLLM``.

Si la respuesta del modelo no es JSON válido, degrada de forma segura a "sin
campos inferidos" (dict vacío): el motor de dominio sigue funcionando con lo
que ya traía el reporte original, en vez de reventar por una respuesta mal
formada del LLM. Esa degradación es la aplicación concreta de la regla "el LLM
nunca decide": si el LLM falla, el sistema no se detiene, solo pierde el
enriquecimiento de ese reporte.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agente_ingesta.adaptadores.llm.clientes import ClienteLLM
from agente_ingesta.aplicacion.puertos.salida import ExtractorPort


class ExtractorLLM(ExtractorPort):
    def __init__(self, cliente: ClienteLLM, rol_prompt: str) -> None:
        self._cliente = cliente
        self._rol_prompt = rol_prompt

    async def extraer(self, texto: str, contexto: dict[str, Any]) -> dict[str, Any]:
        contenido = await self._cliente.completar(
            self._rol_prompt,
            "Extrae los campos estructurados de este reporte.\n"
            f"Contexto: {json.dumps(contexto, ensure_ascii=False)}\n"
            f"Texto: {texto}",
        )
        extraido = self._extraer_json(contenido)
        return extraido if isinstance(extraido, dict) else {}

    @staticmethod
    def _extraer_json(texto: str) -> Any:
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
