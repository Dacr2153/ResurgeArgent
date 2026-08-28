"""Adaptador de entrada REST (FastAPI)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from agente_geoespacial.adaptadores.entrada.modelos import (
    ConsultaRutaIn,
    DireccionIn,
    IncidenteIn,
    ZonasRequest,
)
from agente_geoespacial.aplicacion.casos_uso.analizar_zonas import AnalizarZonas
from agente_geoespacial.aplicacion.casos_uso.resolver_ruta import ResolverRuta
from agente_geoespacial.aplicacion.puertos.salida import GeocodificadorPort
from agente_geoespacial.dominio.excepciones import NodoDesconocidoError
from nucleo.esquemas import Categoria, ConsultaGeo, IncidenteVerificado, Severidad, Urgencia
from nucleo.geo import GeometriaInvalidaError, Punto


def crear_app(
    use_cases: tuple[ResolverRuta, AnalizarZonas],
    geocodificador: GeocodificadorPort | None = None,
) -> FastAPI:
    # ``geocodificador`` es un parámetro aparte, no un tercer elemento de
    # ``use_cases``, a propósito: ``construir_contenedor()`` sigue devolviendo
    # exactamente el par que espera ``agente_orquestador`` (que hace
    # ``AdaptadorGeoespacial(*construido)``), así que no se puede cambiar su
    # forma. Con ``geocodificador=None`` (el caso cuando alguien llama
    # ``crear_app(construir_contenedor())`` como antes, incluido ``main.py``),
    # ``/geocodificar`` responde 503 en vez de fallar al construir la app.
    resolver_ruta, analizar_zonas = use_cases

    app = FastAPI(title="Agente 5 — Geoespacial y Movilidad", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.post("/rutas")
    async def rutas(payload: ConsultaRutaIn) -> dict:
        try:
            consulta = ConsultaGeo(
                origen=Punto(lat=payload.origen.lat, lon=payload.origen.lon),
                destino=Punto(lat=payload.destino.lat, lon=payload.destino.lon),
                modo=payload.modo,
                evitar_zonas=tuple(payload.evitar_zonas),
            )
        except GeometriaInvalidaError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            respuesta = await resolver_ruta.ejecutar(
                consulta, reportes_bloqueo=payload.reportes_bloqueo
            )
        except NodoDesconocidoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # respuesta.alternativas ya viaja en el contrato (nucleo.esquemas.RespuestaGeo):
        # no hace falta una vía aparte para exponer el plan B.
        return respuesta.a_dict()

    @app.post("/zonas")
    async def zonas(payload: ZonasRequest) -> dict:
        try:
            incidentes = [_a_incidente(i) for i in payload.incidentes]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return await analizar_zonas.ejecutar(incidentes)

    @app.post("/geocodificar")
    async def geocodificar(payload: DireccionIn) -> dict:
        """Convierte una dirección escrita a mano en punto, para el formulario
        de reporte del frontend. Devuelve ``{"punto": null}`` (no un error) si
        Nominatim no encontró nada o no respondió: es una consulta que puede
        legítimamente no tener resultado, no una falla del sistema."""
        if geocodificador is None:
            raise HTTPException(
                status_code=503, detail="geocodificador no configurado en este contenedor"
            )
        punto = await geocodificador.geocodificar(payload.direccion)
        return {"punto": punto.a_geojson() if punto is not None else None}

    return app


def _a_incidente(entrada: IncidenteIn) -> IncidenteVerificado:
    kwargs = dict(
        categoria=Categoria(entrada.categoria),
        severidad=Severidad(entrada.severidad),
        urgencia=Urgencia(entrada.urgencia),
        ubicacion=Punto(lat=entrada.ubicacion.lat, lon=entrada.ubicacion.lon),
        confianza=entrada.confianza,
        reportes_origen=tuple(entrada.reportes_origen),
        resumen=entrada.resumen,
    )
    if entrada.id:
        kwargs["id"] = entrada.id
    return IncidenteVerificado(**kwargs)
