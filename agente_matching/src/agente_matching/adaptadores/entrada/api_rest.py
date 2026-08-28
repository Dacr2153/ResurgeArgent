"""Adaptador de entrada REST (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agente_matching.adaptadores.entrada.modelos import MatchingRequest
from agente_matching.aplicacion.puertos.entrada import EjecutarMatchingUseCase
from agente_matching.dominio.excepciones import ErrorDominio, SinDemandaError


def crear_app(use_case: EjecutarMatchingUseCase) -> FastAPI:
    app = FastAPI(title="Agente 7 — Matching/Asignación", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/matching")
    async def matching(payload: MatchingRequest) -> dict:
        try:
            return await use_case.ejecutar(payload.model_dump())
        except SinDemandaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (ErrorDominio, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
