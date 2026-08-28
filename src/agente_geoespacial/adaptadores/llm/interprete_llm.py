"""Intérprete LLM real: implementa ``LLMInterpretePort`` delegando en un ``ClienteLLM``.

Lee reportes en español libre ("no se puede pasar por la calle 13, el río se
llevó el puente") y devuelve una lista de ids de tramo bloqueados. Si la
respuesta no es JSON parseable, degrada de forma segura a "ningún bloqueo
detectado" en vez de propagar el error: un LLM que falla no puede tumbar el
cálculo de rutas, solo puede hacer que se calcule sin la información que no
logró extraer.
"""

from __future__ import annotations

import json
import re

from agente_geoespacial.adaptadores.llm.clientes import ClienteLLM
from agente_geoespacial.aplicacion.puertos.salida import LLMInterpretePort


class InterpreteLLM(LLMInterpretePort):
    def __init__(self, cliente: ClienteLLM, rol_prompt: str):
        self._cliente = cliente
        self._rol_prompt = rol_prompt

    async def interpretar(self, reportes_texto: list[str]) -> list[str]:
        if not reportes_texto:
            return []

        contenido = await self._cliente.completar(
            self._rol_prompt,
            "Reportes:\n" + "\n".join(f"- {reporte}" for reporte in reportes_texto),
        )
        return self._extraer_lista(contenido)

    @staticmethod
    def _extraer_lista(texto: str) -> list[str]:
        texto = texto.strip()
        bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, re.DOTALL)
        if bloque:
            texto = bloque.group(1).strip()

        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            inicio, fin = texto.find("["), texto.rfind("]")
            if inicio == -1 or fin <= inicio:
                return []
            try:
                datos = json.loads(texto[inicio : fin + 1])
            except json.JSONDecodeError:
                return []

        if isinstance(datos, dict):
            datos = datos.get("vias_bloqueadas", [])
        if not isinstance(datos, list):
            return []
        return [str(item) for item in datos]
