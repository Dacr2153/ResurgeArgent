"""Adaptador de entrada REST (FastAPI) de plataforma.

Se monta bajo `/plataforma`. Todo lo que responde sale de datos persistidos o de
reglas deterministas: ningún endpoint devuelve ejemplos.

El punto de referencia de las distancias (`lat`/`lon`) es opcional en cada
petición y cae a la base de operaciones configurada. Es deliberado: un voluntario
consulta desde donde está, y un coordinador desde el puesto de mando; forzar
siempre las coordenadas del cliente rompería la segunda vista, y no aceptarlas
nunca haría inútil el filtro por radio.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from nucleo.geo import GeometriaInvalidaError, Punto
from plataforma.adaptadores.entrada import presentadores
from plataforma.adaptadores.entrada.modelos import (
    EncolarRequest,
    MisionRequest,
    PlanRequest,
    VoluntarioRequest,
)
from plataforma.config.contenedor import Contenedor
from plataforma.dominio.excepciones import RecursoDesconocidoError


def crear_app(contenedor: Contenedor) -> FastAPI:
    app = FastAPI(title="Plataforma — Voluntarios, misiones y recuperación", version="0.1.0")

    def referencia(lat: float | None, lon: float | None) -> Punto:
        if lat is None or lon is None:
            return contenedor.base_operaciones
        try:
            return Punto(lat=lat, lon=lon)
        except GeometriaInvalidaError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/reportes/{incidente_id}")
    async def seguimiento(incidente_id: str) -> dict:
        """Recorrido real de un reporte, derivado del estado de su operación."""
        try:
            reporte = await contenedor.seguimiento.consultar(incidente_id)
        except RecursoDesconocidoError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return presentadores.seguimiento(reporte)

    @app.post("/voluntarios", status_code=201)
    async def registrar_voluntario(payload: VoluntarioRequest) -> dict:
        """Alta de voluntario. Queda en verificación: registrarse no habilita."""
        try:
            voluntario = await contenedor.voluntarios.registrar(
                payload.model_dump(by_alias=False)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": voluntario.id, "status": str(voluntario.estado)}

    @app.post("/misiones", status_code=201)
    async def abrir_mision(payload: MisionRequest) -> dict:
        mision = await contenedor.misiones.abrir(payload.model_dump())
        return presentadores.mision_detalle(mision, contenedor.base_operaciones)

    @app.get("/misiones")
    async def listar_misiones(
        radio_km: float | None = Query(default=None, gt=0.0),
        lat: float | None = Query(default=None),
        lon: float | None = Query(default=None),
    ) -> list[dict]:
        """Misiones abiertas dentro del radio, ordenadas por prioridad."""
        punto = referencia(lat, lon)
        misiones = await contenedor.misiones.listar(punto, radio_km)
        return [presentadores.mision_listada(m, punto) for m in misiones]

    @app.get("/misiones/{incidente_id}")
    async def detalle_mision(
        incidente_id: str,
        lat: float | None = Query(default=None),
        lon: float | None = Query(default=None),
    ) -> dict:
        punto = referencia(lat, lon)
        try:
            mision = await contenedor.misiones.detalle(incidente_id)
        except RecursoDesconocidoError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return presentadores.mision_detalle(mision, punto)

    @app.get("/recuperacion/preguntas")
    async def preguntas_recuperacion() -> list[dict]:
        preguntas = await contenedor.recuperacion.preguntas()
        return [presentadores.pregunta(p) for p in preguntas]

    @app.post("/recuperacion/plan")
    async def plan_recuperacion(payload: PlanRequest) -> list[dict]:
        """Hoja de ruta derivada por reglas sobre las respuestas."""
        pasos = await contenedor.recuperacion.plan(payload.respuestas)
        return presentadores.plan(pasos)

    @app.get("/sincronizacion")
    async def cola_pendiente() -> list[dict]:
        pendientes = await contenedor.sincronizacion.pendientes()
        return [presentadores.encolado(r) for r in pendientes]

    @app.post("/sincronizacion")
    async def vaciar_cola() -> dict:
        """Marca como enviados los reportes que esperaban cobertura."""
        return {"sent": await contenedor.sincronizacion.vaciar()}

    @app.post("/sincronizacion/reportes", status_code=201)
    async def encolar_reporte(payload: EncolarRequest) -> dict:
        reporte = await contenedor.sincronizacion.encolar(payload.model_dump())
        return presentadores.encolado(reporte)

    return app
