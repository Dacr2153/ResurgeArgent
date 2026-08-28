"""Un reinicio del servicio no borra lo que la gente ya envió.

Se levantan dos aplicaciones distintas sobre el mismo archivo: la primera
escribe, la segunda lee. Es el escenario real de un despliegue que se cae en
plena emergencia y vuelve.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agente_orquestador.adaptadores.salida.repositorio_memoria import (
    RepositorioOperacionesMemoria,
)
from plataforma.adaptadores.entrada.api_rest import crear_app
from plataforma.config.contenedor import construir_contenedor
from plataforma.config.settings import Settings


@pytest.fixture
def arranque(tmp_path):
    """Fábrica de contenedores: cada llamada simula un arranque limpio."""
    ruta = str(tmp_path / "plataforma.db")

    def construir():
        return construir_contenedor(
            settings=Settings(ruta_sqlite=ruta, base_lat=-12.0464, base_lon=-77.0428),
            repositorio_operaciones=RepositorioOperacionesMemoria(),
        )

    return construir


@pytest.fixture
def cliente_nuevo(arranque):
    return lambda: TestClient(crear_app(arranque()))


async def test_el_alta_de_un_voluntario_sigue_ahi_tras_reiniciar(cliente_nuevo, arranque):
    cliente_nuevo().post(
        "/voluntarios",
        json={
            "nombre_completo": "Ana Quispe",
            "documento": "48210233",
            "telefono": "+51999111222",
            "recurso": "Brigada médica",
        },
    )

    guardados = await arranque().voluntarios.listar()

    assert [v.nombre_completo for v in guardados] == ["Ana Quispe"]


def test_una_mision_abierta_sigue_disponible_tras_reiniciar(cliente_nuevo):
    cliente_nuevo().post(
        "/misiones",
        json={
            "incidente_id": "INC-2481",
            "titulo": "Incendio · Jr. Camaná 654",
            "lat": -12.0489,
            "lon": -77.0378,
            "necesidad": "2 brigadistas",
            "puntuacion": 92,
        },
    )

    misiones = cliente_nuevo().get("/misiones", params={"radio_km": 5}).json()

    assert [m["id"] for m in misiones] == ["INC-2481"]


def test_la_cola_offline_sigue_pendiente_tras_reiniciar(cliente_nuevo):
    cliente_nuevo().post(
        "/sincronizacion/reportes",
        json={"titulo": "Reporte · Techo dañado", "meta": "sin foto", "puntuacion": 41},
    )

    despues = cliente_nuevo()

    assert [r["title"] for r in despues.get("/sincronizacion").json()] == [
        "Reporte · Techo dañado"
    ]
    assert despues.post("/sincronizacion").json() == {"sent": 1}


def test_el_cuestionario_no_se_duplica_al_reiniciar(cliente_nuevo):
    cliente_nuevo().get("/recuperacion/preguntas")

    preguntas = cliente_nuevo().get("/recuperacion/preguntas").json()

    assert [p["id"] for p in preguntas] == ["vivienda", "salud", "medios"]
