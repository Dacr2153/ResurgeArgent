"""Fixtures de las pruebas de plataforma.

El contenedor se construye siempre con `Settings` explícitos y con un
repositorio de operaciones inyectado: sin eso las pruebas leerían la
configuración del entorno y dejarían de ser reproducibles en otra máquina.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agente_orquestador.adaptadores.salida.repositorio_memoria import (
    RepositorioOperacionesMemoria,
)
from agente_orquestador.dominio.entidades import Operacion
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.value_objects import PuntuacionTriage
from plataforma.adaptadores.entrada.api_rest import crear_app
from plataforma.config.contenedor import construir_contenedor
from plataforma.config.settings import Settings

#: Plaza de Armas de Lima: la base de operaciones que usan las pruebas.
BASE_LAT = -12.0464
BASE_LON = -77.0428


def operacion_priorizada(incidente_id: str = "INC-2481") -> Operacion:
    """Operación llevada hasta PENDIENTE_APROBACION, como la deja el Agente 1."""
    operacion = Operacion(incidente_id=incidente_id, correlacion_id="COR-1")
    operacion.datos["titulo"] = "Incendio · Jr. Camaná 654"
    operacion.transicionar(EstadoIncidente.VERIFICADO, motivo="corroborado por 2 reporte(s)")
    operacion.transicionar(EstadoIncidente.LOCALIZADO, motivo="ruta resuelta (2.4 km)")
    operacion.datos["ruta"] = {"distancia_km": 2.4}
    operacion.puntuacion = PuntuacionTriage(
        incidente_id=incidente_id, puntuacion=0.92, posicion=1
    )
    operacion.transicionar(EstadoIncidente.PRIORIZADO, motivo="posición 1 del lote")
    operacion.transicionar(EstadoIncidente.PENDIENTE_APROBACION, motivo="a la espera de firma")
    return operacion


@pytest.fixture
def operaciones() -> RepositorioOperacionesMemoria:
    return RepositorioOperacionesMemoria()


@pytest.fixture
def contenedor(operaciones):
    return construir_contenedor(
        settings=Settings(ruta_sqlite="", base_lat=BASE_LAT, base_lon=BASE_LON),
        repositorio_operaciones=operaciones,
    )


@pytest.fixture
def client(contenedor) -> TestClient:
    return TestClient(crear_app(contenedor))


MISION = {
    "incidente_id": "INC-2481",
    "titulo": "Incendio · Jr. Camaná 654",
    "direccion": "Jr. Camaná 654",
    "lat": -12.0489,
    "lon": -77.0378,
    "necesidad": "2 brigadistas",
    "puntuacion": 92,
    "modo": "a pie",
    "ruta": [[-12.0464, -77.0428], [-12.0489, -77.0378]],
    "checklist": [{"clave": "agua", "etiqueta": "Agua · 6 L"}],
}

#: Segunda misión, deliberadamente lejos de la base: es la que debe caer fuera
#: del radio corto y dentro del largo.
MISION_LEJOS = {
    "incidente_id": "INC-2488",
    "titulo": "Árbol caído · Jesús María",
    "direccion": "Av. Salaverry",
    "lat": -12.0741,
    "lon": -77.0451,
    "necesidad": "cuadrilla",
    "puntuacion": 38,
    "modo": "vehiculo",
}
