"""Cada regla del plan de recuperación, probada por separado.

Son pruebas de una tabla, no de un texto: lo que se verifica es qué respuesta
dispara qué trámite, que es lo que alguien podría reclamar.
"""

from __future__ import annotations

import pytest

from plataforma.dominio.entidades import Horizonte
from plataforma.dominio.reglas_recuperacion import PASO_BASE, derivar_plan


def titulos(respuestas: dict[str, str]) -> list[str]:
    return [paso.titulo for paso in derivar_plan(respuestas)]


def test_el_paso_base_entra_siempre():
    assert titulos({}) == [PASO_BASE.titulo]


def test_respuesta_desconocida_no_dispara_nada():
    assert titulos({"vivienda": "no contesto"}) == [PASO_BASE.titulo]


@pytest.mark.parametrize(
    ("respuesta", "esperado"),
    [
        ("No, está inhabitable", "Albergue temporal"),
        ("No, está inhabitable", "Evaluación estructural"),
        ("No, está inhabitable", "Bono de reconstrucción"),
        ("Parcialmente", "Evaluación estructural"),
        ("Sí, con daños menores", "Kit de reparaciones menores"),
    ],
)
def test_reglas_de_vivienda(respuesta, esperado):
    assert esperado in titulos({"vivienda": respuesta})


@pytest.mark.parametrize(
    ("respuesta", "esperado"),
    [
        ("Sí, una persona", "Continuidad de atención médica"),
        ("Sí, dos o más", "Continuidad de atención médica"),
        ("Sí, dos o más", "Visita de brigada médica domiciliaria"),
    ],
)
def test_reglas_de_salud(respuesta, esperado):
    assert esperado in titulos({"salud": respuesta})


def test_sin_necesidad_medica_no_hay_pasos_de_salud():
    assert titulos({"salud": "No"}) == [PASO_BASE.titulo]


@pytest.mark.parametrize(
    ("respuesta", "esperado"),
    [
        ("Documentos", "Reposición de documentos"),
        ("Medios de trabajo", "Bono de reactivación productiva"),
    ],
)
def test_reglas_de_medios(respuesta, esperado):
    assert esperado in titulos({"medios": respuesta})


def test_un_paso_disparado_dos_veces_aparece_una_sola():
    plan = titulos({"vivienda": "No, está inhabitable", "salud": "Sí, dos o más"})

    assert plan.count("Continuidad de atención médica") == 1


def test_el_plan_va_ordenado_por_plazo():
    plan = derivar_plan(
        {"vivienda": "No, está inhabitable", "salud": "Sí, dos o más", "medios": "Documentos"}
    )
    orden = [list(Horizonte).index(paso.horizonte) for paso in plan]

    assert orden == sorted(orden)


def test_las_tildes_perdidas_en_el_transporte_no_dejan_a_nadie_sin_plan():
    con_tilde = titulos({"vivienda": "No, está inhabitable"})
    sin_tilde = titulos({"vivienda": "no, esta INHABITABLE  "})

    assert con_tilde == sin_tilde
