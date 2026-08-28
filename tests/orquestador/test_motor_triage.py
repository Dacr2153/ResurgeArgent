"""Tests del motor de triage: orden explicable y reproducible."""

from __future__ import annotations

import random

import pytest

from agente_orquestador.dominio.motor_triage import MotorTriage
from agente_orquestador.dominio.value_objects import PesosTriage, factor_personas
from nucleo.esquemas import Severidad, Urgencia
from tests.orquestador.dobles import hacer_incidente

LOTE = [
    hacer_incidente("INC-A", Severidad.EXTREME, Urgencia.IMMEDIATE, confianza=0.9, personas=50),
    hacer_incidente("INC-B", Severidad.MINOR, Urgencia.FUTURE, confianza=0.9, personas=2),
    hacer_incidente("INC-C", Severidad.SEVERE, Urgencia.EXPECTED, confianza=0.6, personas=20),
    hacer_incidente("INC-D", Severidad.MODERATE, Urgencia.IMMEDIATE, confianza=0.3, personas=5),
]


def test_orden_reproducible_sobre_el_mismo_lote():
    motor = MotorTriage()
    esperado = [p.incidente_id for p in motor.ordenar(LOTE)]

    for _ in range(20):
        barajado = list(LOTE)
        random.shuffle(barajado)
        assert [p.incidente_id for p in motor.ordenar(barajado)] == esperado


def test_el_mas_grave_y_urgente_va_primero():
    orden = [p.incidente_id for p in MotorTriage().ordenar(LOTE)]
    assert orden[0] == "INC-A"
    assert orden[-1] == "INC-B"


def test_las_posiciones_son_consecutivas_desde_uno():
    puntuaciones = MotorTriage().ordenar(LOTE)
    assert [p.posicion for p in puntuaciones] == [1, 2, 3, 4]


def test_empate_se_desempata_por_id_no_por_orden_de_llegada():
    gemelo_a = hacer_incidente("INC-Z", Severidad.SEVERE, Urgencia.EXPECTED, 0.7, 10)
    gemelo_b = hacer_incidente("INC-Y", Severidad.SEVERE, Urgencia.EXPECTED, 0.7, 10)
    motor = MotorTriage()
    assert [p.incidente_id for p in motor.ordenar([gemelo_a, gemelo_b])] == ["INC-Y", "INC-Z"]
    assert [p.incidente_id for p in motor.ordenar([gemelo_b, gemelo_a])] == ["INC-Y", "INC-Z"]


def test_la_confianza_degrada_pero_no_anula():
    """Un extremo sin corroborar sigue por encima de un menor confirmado."""
    motor = MotorTriage()
    rumor_grave = hacer_incidente("INC-1", Severidad.EXTREME, Urgencia.IMMEDIATE, 0.0, 100)
    confirmado_menor = hacer_incidente("INC-2", Severidad.MINOR, Urgencia.FUTURE, 1.0, 1)
    orden = [p.incidente_id for p in motor.ordenar([confirmado_menor, rumor_grave])]
    assert orden[0] == "INC-1"


def test_la_confianza_ordena_entre_iguales():
    motor = MotorTriage()
    fiable = hacer_incidente("INC-1", Severidad.SEVERE, Urgencia.IMMEDIATE, 0.95, 10)
    dudoso = hacer_incidente("INC-2", Severidad.SEVERE, Urgencia.IMMEDIATE, 0.20, 10)
    assert [p.incidente_id for p in motor.ordenar([dudoso, fiable])] == ["INC-1", "INC-2"]


def test_el_desglose_explica_la_puntuacion():
    puntuacion = MotorTriage().puntuar(LOTE[0])
    componentes = puntuacion.componentes
    assert set(componentes) == {
        "severidad",
        "urgencia",
        "personas",
        "base",
        "multiplicador_confianza",
    }
    esperado = componentes["base"] * componentes["multiplicador_confianza"]
    assert puntuacion.puntuacion == pytest.approx(esperado)


def test_personas_afectadas_satura_y_desconocido_no_es_cero():
    assert factor_personas(0) == 0.0
    assert factor_personas(None) > 0.0
    assert factor_personas(10) < factor_personas(100)
    assert factor_personas(100000) == 1.0


def test_los_pesos_deben_sumar_uno():
    with pytest.raises(ValueError):
        PesosTriage(severidad=0.5, urgencia=0.5, personas=0.5)


def test_lote_vacio_no_falla():
    assert MotorTriage().ordenar([]) == []
