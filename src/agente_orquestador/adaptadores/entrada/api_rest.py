"""Adaptador de entrada REST (FastAPI) del Agente 1.

El mapeo de errores no es decorativo. `DecisionHumanaRequeridaError` responde 428
(Precondition Required) porque es exactamente eso: falta una precondición que el
cliente puede satisfacer firmando. Un 400 genérico haría creer que la petición
estaba mal formada, cuando lo que falta es una persona.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from agente_orquestador.adaptadores.entrada.modelos import (
    DecisionHumanaRequest,
    EmergenciaRequest,
)
from agente_orquestador.config.contenedor import Contenedor
from agente_orquestador.dominio.entidades import Operacion
from agente_orquestador.dominio.excepciones import (
    DecisionHumanaRequeridaError,
    DecisionRechazadaError,
    ErrorDominio,
    IncidenteDesconocidoError,
    TransicionInvalidaError,
)

#: Radio operativo por defecto de un coordinador de zona, en kilómetros. Es el
#: mismo que asume el frontend para el alcance "zona".
RADIO_ZONA_KM = 3.0


def _en_zona(operacion: Operacion, radio_km: float) -> bool:
    """¿Cae la operación dentro del radio del coordinador de zona?

    La distancia sale de la ruta que calculó el agente geoespacial, que es la
    única medida real que tiene la operación. Sin ruta no hay distancia, y una
    operación sin distancia se deja fuera del alcance de zona: incluirla sería
    afirmar que está cerca sin saberlo, y el coordinador de zona la despacharía
    sin poder llegar.
    """
    ruta = operacion.datos.get("ruta")
    if not isinstance(ruta, dict):
        return False
    distancia = ruta.get("distancia_km")
    return distancia is not None and float(distancia) <= radio_km


def crear_app(contenedor: Contenedor) -> FastAPI:
    app = FastAPI(title="Agente 1 — Orquestador", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/emergencias")
    async def procesar_emergencia(payload: EmergenciaRequest) -> dict:
        try:
            return await contenedor.procesar.procesar(payload.model_dump())
        except (ErrorDominio, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/decisiones")
    async def registrar_decision(payload: DecisionHumanaRequest) -> dict:
        try:
            return await contenedor.registrar_decision.registrar(payload.model_dump())
        except IncidenteDesconocidoError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DecisionHumanaRequeridaError as exc:
            raise HTTPException(status_code=428, detail=str(exc)) from exc
        except (DecisionRechazadaError, TransicionInvalidaError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ErrorDominio, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/operaciones")
    async def listar_operaciones(
        alcance: str = Query("general", pattern="^(zona|general)$"),
        radio_km: float = Query(RADIO_ZONA_KM, gt=0.0),
    ) -> dict:
        """Cola completa del tablero del coordinador, en orden de triage.

        `alcance` es el filtro RBAC: un coordinador de zona no ve el
        departamento entero, ve lo que le toca despachar. Se resuelve con la
        distancia real que dejó el agente geoespacial en la operación.
        """
        operaciones = await contenedor.repositorio.listar()
        if alcance == "zona":
            operaciones = [o for o in operaciones if _en_zona(o, radio_km)]
        return {
            "alcance": alcance,
            "radio_km": radio_km,
            "total": len(operaciones),
            "operaciones": [o.a_dict() for o in operaciones],
        }

    @app.get("/operaciones/{incidente_id}")
    async def obtener_operacion(incidente_id: str) -> dict:
        operacion = await contenedor.repositorio.obtener(incidente_id)
        if operacion is None:
            raise HTTPException(status_code=404, detail=f"incidente desconocido: {incidente_id}")
        return operacion.a_dict()

    @app.get("/auditoria/{correlacion_id}")
    async def obtener_auditoria(correlacion_id: str) -> dict:
        """Traza completa de una operación. Es la vista que responde el 'por qué'."""
        eventos = contenedor.eventos_de(correlacion_id)
        return {"correlacion_id": correlacion_id, "eventos": eventos}

    return app
