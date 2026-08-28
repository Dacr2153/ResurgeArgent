"""Adaptador de entrada REST del Agente 8 (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agente_logistica.adaptadores.entrada.modelos import PlanificacionRequest
from agente_logistica.aplicacion.puertos.entrada import PlanificarLogisticaUseCase
from agente_logistica.dominio.excepciones import ErrorDominio


def crear_app(use_case: PlanificarLogisticaUseCase) -> FastAPI:
    app = FastAPI(title="Agente 8 — Planificación Logística", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/planificar")
    async def planificar(payload: PlanificacionRequest) -> dict:
        try:
            return await use_case.ejecutar(payload.model_dump())
        except (ErrorDominio, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
