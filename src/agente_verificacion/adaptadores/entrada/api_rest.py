"""Adaptador de entrada REST (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agente_verificacion.adaptadores.entrada.modelos import VerificacionRequest
from agente_verificacion.aplicacion.puertos.entrada import VerificarReportesUseCase
from agente_verificacion.dominio.excepciones import ErrorDominio


def crear_app(use_case: VerificarReportesUseCase) -> FastAPI:
    app = FastAPI(title="Agente 3 — Verificación", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/verificacion")
    async def verificacion(payload: VerificacionRequest) -> dict:
        try:
            reportes = [r.a_reporte_crudo() for r in payload.reportes]
            incidentes = await use_case.verificar(reportes)
        except (ErrorDominio, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"incidentes": [i.a_dict() for i in incidentes]}

    return app
