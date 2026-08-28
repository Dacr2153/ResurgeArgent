"""Orquestador LLM nulo: passthrough, para desarrollo y tests sin API key."""

from __future__ import annotations


class OrquestadorNulo:
    async def normalizar(self, json_crudo: dict) -> dict:
        return json_crudo

    async def justificar(self, resultado_motor: dict, contexto: dict) -> dict:
        final = dict(resultado_motor)
        final.setdefault("supuestos", [])
        final.setdefault("justificaciones", [])
        return final
