"""Punto de entrada del sistema: monta la API de cada agente disponible.

El montaje es por descubrimiento a propósito. Los agentes se construyen en ramas
paralelas, y si cada una tuviera que editar este archivo para registrarse, las
cuatro chocarían aquí en cada merge. En vez de eso, cada agente expone
`crear_app()` y `construir_contenedor()` en las rutas de siempre, y este archivo
monta lo que encuentre e ignora lo que aún no existe.
"""

from __future__ import annotations

import importlib
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

registro = logging.getLogger(__name__)

# Orígenes del frontend en desarrollo. Vite arranca en 5173 y salta a 5174 si el
# puerto está ocupado, así que ambos tienen que estar. En despliegue se declara
# el dominio real por RESURGE_ORIGENES, separado por comas.
ORIGENES_DEV = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]


def origenes_permitidos() -> list[str]:
    declarados = os.environ.get("RESURGE_ORIGENES", "").strip()
    if not declarados:
        return ORIGENES_DEV
    return [origen.strip() for origen in declarados.split(",") if origen.strip()]


# (prefijo de ruta, paquete). El orden es el del flujo del sistema.
AGENTES: list[tuple[str, str]] = [
    ("/ingesta", "agente_ingesta"),
    ("/verificacion", "agente_verificacion"),
    ("/geoespacial", "agente_geoespacial"),
    ("/matching", "agente_matching"),
    ("/orquestador", "agente_orquestador"),
    ("/plataforma", "plataforma"),
]


def _montar(paquete: str) -> FastAPI | None:
    """Construye la app de un agente, o devuelve None si aún no está construido."""
    try:
        api = importlib.import_module(f"{paquete}.adaptadores.entrada.api_rest")
        contenedor = importlib.import_module(f"{paquete}.config.contenedor")
    except ModuleNotFoundError:
        registro.info("agente no disponible todavía: %s", paquete)
        return None

    try:
        return api.crear_app(contenedor.construir_contenedor())
    except Exception:  # noqa: BLE001 - un agente roto no debe tumbar a los demás
        registro.exception("fallo al montar el agente %s", paquete)
        return None


def crear_app() -> FastAPI:
    app = FastAPI(
        title="ResurgeAgent — Sistema de Coordinación de Respuesta",
        description="Agentes de ingesta, verificación, geoespacial, matching y orquestación.",
        version="0.2.0",
    )

    # Sin esto el navegador bloquea toda peticion del frontend antes de que
    # salga: no es configuracion opcional, es lo que hace usable la API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_permitidos(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    montados: list[str] = []
    for prefijo, paquete in AGENTES:
        sub_app = _montar(paquete)
        if sub_app is not None:
            app.mount(prefijo, sub_app)
            montados.append(paquete)

    @app.get("/salud")
    def salud() -> dict:
        return {"estado": "ok", "agentes": montados}

    return app


app = crear_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
