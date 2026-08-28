"""Persistencia de plataforma: lo escrito con una instancia se lee con otra.

Cada prueba abre un repositorio nuevo sobre el mismo archivo. Es la forma de
comprobar que sobrevive a un reinicio del proceso sin tener que reiniciar nada.
"""

from __future__ import annotations

import pytest

from nucleo.geo import Punto
from plataforma.adaptadores.salida.repositorio_sqlite import (
    RepositorioMisionesSQLite,
    RepositorioRecuperacionSQLite,
    RepositorioSincronizacionSQLite,
    RepositorioVoluntariosSQLite,
)
from plataforma.dominio.entidades import (
    EstadoVoluntario,
    ItemChecklist,
    Mision,
    PreguntaRecuperacion,
    ReporteEncolado,
    Voluntario,
)


@pytest.fixture
def ruta(tmp_path):
    return tmp_path / "plataforma.db"


async def test_un_voluntario_sobrevive_al_reinicio(ruta):
    await RepositorioVoluntariosSQLite(ruta).guardar(
        Voluntario(
            nombre_completo="Ana Quispe",
            documento="48210233",
            telefono="+51999111222",
            recurso="Brigada médica",
        )
    )

    recuperados = await RepositorioVoluntariosSQLite(ruta).listar()

    assert [v.nombre_completo for v in recuperados] == ["Ana Quispe"]
    assert recuperados[0].estado is EstadoVoluntario.EN_VERIFICACION


async def test_una_mision_sobrevive_con_ruta_y_checklist(ruta):
    await RepositorioMisionesSQLite(ruta).guardar(
        Mision(
            incidente_id="INC-2481",
            titulo="Incendio · Jr. Camaná 654",
            direccion="Jr. Camaná 654",
            ubicacion=Punto(lat=-12.0489, lon=-77.0378),
            necesidad="2 brigadistas",
            puntuacion=92,
            ruta=((-12.0464, -77.0428), (-12.0489, -77.0378)),
            checklist=(ItemChecklist("agua", "Agua · 6 L"),),
        )
    )

    recuperada = await RepositorioMisionesSQLite(ruta).obtener("INC-2481")

    assert recuperada.ubicacion == Punto(lat=-12.0489, lon=-77.0378)
    assert recuperada.ruta == ((-12.0464, -77.0428), (-12.0489, -77.0378))
    assert recuperada.checklist[0].etiqueta == "Agua · 6 L"


async def test_una_mision_cerrada_no_aparece_entre_las_abiertas(ruta):
    repositorio = RepositorioMisionesSQLite(ruta)
    await repositorio.guardar(
        Mision(
            incidente_id="INC-1",
            titulo="Cerrada",
            direccion="",
            ubicacion=Punto(lat=0.0, lon=0.0),
            abierta=False,
        )
    )

    assert await RepositorioMisionesSQLite(ruta).listar_abiertas() == []


async def test_el_cuestionario_sobrevive(ruta):
    await RepositorioRecuperacionSQLite(ruta).guardar_pregunta(
        PreguntaRecuperacion(id="vivienda", pregunta="¿Habitable?", opciones=("Sí", "No"), orden=1)
    )

    recuperadas = await RepositorioRecuperacionSQLite(ruta).listar_preguntas()

    assert recuperadas[0].opciones == ("Sí", "No")


async def test_la_cola_offline_sobrevive_y_se_vacia_una_sola_vez(ruta):
    reporte = ReporteEncolado(titulo="Reporte", meta="sin foto", puntuacion=41)
    await RepositorioSincronizacionSQLite(ruta).encolar(reporte)

    segunda = RepositorioSincronizacionSQLite(ruta)
    pendientes = await segunda.pendientes()
    await segunda.marcar_enviados(pendientes)

    assert [r.titulo for r in pendientes] == ["Reporte"]
    assert await RepositorioSincronizacionSQLite(ruta).pendientes() == []


async def test_los_pendientes_salen_por_prioridad(ruta):
    repositorio = RepositorioSincronizacionSQLite(ruta)
    await repositorio.encolar(ReporteEncolado(titulo="Menor", meta="", puntuacion=41))
    await repositorio.encolar(ReporteEncolado(titulo="Grave", meta="", puntuacion=92))

    assert [r.titulo for r in await repositorio.pendientes()] == ["Grave", "Menor"]
