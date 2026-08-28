"""Derivación del recorrido: bandas, escalado y avisos."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from plataforma.dominio.entidades import EstadoOperacion, HitoOperacion
from plataforma.dominio.seguimiento import banda, derivar_recorrido, escalar


@pytest.mark.parametrize(
    ("puntuacion", "esperada"),
    [(92, "CRÍTICO"), (80, "CRÍTICO"), (79, "ALTO"), (60, "ALTO"), (59, "MEDIO"), (0, "MEDIO")],
)
def test_bandas(puntuacion, esperada):
    assert banda(puntuacion) == esperada


def test_escalar_sin_triage_es_cero():
    assert escalar(None) == 0


def test_escalar_satura_en_cien():
    assert escalar(1.4) == 100


def test_una_transicion_no_aplicada_no_marca_el_paso():
    # Una transición desviada a SUSPENDIDO por ciclo queda registrada pero con
    # `aplicada=False`: contarla diría al ciudadano que hubo brigada asignada.
    estado = EstadoOperacion(
        incidente_id="INC-1",
        estado="suspendido",
        titulo="Rescate",
        puntuacion=0.5,
        hitos=(
            HitoOperacion(
                estado="asignado",
                momento=datetime(2026, 8, 28, 14, 7, tzinfo=UTC),
                motivo="intento",
                aplicada=False,
            ),
        ),
    )

    recorrido = derivar_recorrido(estado)

    assert recorrido.pasos[3].hecho is False
    assert recorrido.mensajes_sin_leer == 0


def test_se_conserva_la_primera_vez_que_se_alcanzo_un_estado():
    estado = EstadoOperacion(
        incidente_id="INC-1",
        estado="priorizado",
        titulo="Rescate",
        puntuacion=0.7,
        hitos=(
            HitoOperacion("priorizado", datetime(2026, 8, 28, 14, 3, tzinfo=UTC), "primera", True),
            HitoOperacion("priorizado", datetime(2026, 8, 28, 15, 9, tzinfo=UTC), "retriage", True),
        ),
    )

    assert "14:03 · primera" == derivar_recorrido(estado).pasos[2].meta
