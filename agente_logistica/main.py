"""Punto de entrada del Agente 8: arma el contenedor y levanta la API REST."""

from __future__ import annotations

import uvicorn

from agente_logistica.adaptadores.entrada.api_rest import crear_app
from agente_logistica.config.contenedor import construir_contenedor

app = crear_app(construir_contenedor())


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
