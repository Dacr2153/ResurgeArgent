"""Orquestador LLM nulo del Agente 8 (passthrough, para desarrollo y tests)."""

from __future__ import annotations


class OrquestadorNulo:
    async def normalizar(self, json_crudo: dict) -> dict:
        return json_crudo

    async def explicar(self, plan: dict, contexto: dict) -> dict:
        final = dict(plan)
        final.setdefault("supuestos", [])
        final.setdefault("justificaciones", [])
        return final
