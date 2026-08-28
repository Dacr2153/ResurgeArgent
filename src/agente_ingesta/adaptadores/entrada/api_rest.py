"""Adaptador de entrada REST (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agente_ingesta.adaptadores.entrada.modelos import IngestaRequest
from agente_ingesta.aplicacion.puertos.entrada import IngerirReportesUseCase
from agente_ingesta.dominio.excepciones import ErrorDominio, LoteInvalidoError


def crear_app(use_case: IngerirReportesUseCase) -> FastAPI:
    app = FastAPI(title="Agente 2 — Ingesta de Información", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/ingesta")
    async def ingesta(payload: IngestaRequest) -> dict:
        try:
            aceptados = await use_case.ingerir(payload.model_dump())
        except LoteInvalidoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (ErrorDominio, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "aceptados": len(aceptados),
            "reportes": [reporte.a_dict() for reporte in aceptados],
        }

    return app
