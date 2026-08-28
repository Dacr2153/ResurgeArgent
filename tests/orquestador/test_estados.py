"""Tests de la máquina de estados y del gate humano.

El gate es la garantía central del sistema: sin firma no hay despacho. Estos
tests existen para que romperlo sea imposible sin que falle la suite.
"""

from __future__ import annotations

import pytest

from agente_orquestador.dominio.entidades import Operacion
from agente_orquestador.dominio.estados import (
    ESTADOS_TERMINALES,
    TRANSICIONES_AUTOMATICAS,
    EstadoIncidente,
    transiciones_posibles,
    validar_transicion,
)
from agente_orquestador.dominio.excepciones import (
    DecisionHumanaRequeridaError,
    DecisionNoCorrespondeError,
    DecisionRechazadaError,
    TransicionInvalidaError,
)
from nucleo.esquemas import DecisionHumana


def aprobacion(incidente_id: str = "INC-1") -> DecisionHumana:
    return DecisionHumana(
        incidente_id=incidente_id,
        aprobada=True,
        coordinador_id="COORD-7",
        justificacion="recursos disponibles y ruta accesible",
    )


def rechazo(incidente_id: str = "INC-1") -> DecisionHumana:
    return DecisionHumana(
        incidente_id=incidente_id,
        aprobada=False,
        coordinador_id="COORD-7",
        justificacion="reporte duplicado del incidente INC-0",
    )


def operacion_pendiente(incidente_id: str = "INC-1") -> Operacion:
    op = Operacion(incidente_id=incidente_id, correlacion_id="COR-1")
    op.transicionar(EstadoIncidente.VERIFICADO)
    op.transicionar(EstadoIncidente.LOCALIZADO)
    op.transicionar(EstadoIncidente.PRIORIZADO)
    op.transicionar(EstadoIncidente.PENDIENTE_APROBACION)
    return op


# ------------------------------------------------------------------ el gate
def test_sin_decision_no_se_llega_a_asignado():
    with pytest.raises(DecisionHumanaRequeridaError):
        validar_transicion(EstadoIncidente.PENDIENTE_APROBACION, EstadoIncidente.ASIGNADO)


def test_operacion_sin_decision_no_se_asigna():
    op = operacion_pendiente()
    with pytest.raises(DecisionHumanaRequeridaError):
        op.transicionar(EstadoIncidente.ASIGNADO)
    assert op.estado is EstadoIncidente.PENDIENTE_APROBACION


def test_con_decision_firmada_y_aprobada_se_asigna():
    op = operacion_pendiente()
    registro = op.transicionar(EstadoIncidente.ASIGNADO, decision=aprobacion())
    assert op.estado is EstadoIncidente.ASIGNADO
    assert registro.aplicada is True
    assert registro.decision_id == op.decision.id


def test_decision_rechazada_nunca_lleva_a_asignado():
    op = operacion_pendiente()
    with pytest.raises(DecisionRechazadaError):
        op.transicionar(EstadoIncidente.ASIGNADO, decision=rechazo())
    assert op.estado is EstadoIncidente.PENDIENTE_APROBACION


def test_decision_rechazada_descarta_o_suspende():
    descartada = operacion_pendiente()
    descartada.transicionar(EstadoIncidente.DESCARTADO, decision=rechazo())
    assert descartada.estado is EstadoIncidente.DESCARTADO

    suspendida = operacion_pendiente()
    suspendida.transicionar(EstadoIncidente.SUSPENDIDO, decision=rechazo())
    assert suspendida.estado is EstadoIncidente.SUSPENDIDO


def test_ningun_estado_llega_a_asignado_de_forma_automatica():
    for origen, destinos in TRANSICIONES_AUTOMATICAS.items():
        assert EstadoIncidente.ASIGNADO not in destinos, origen


def test_una_aprobacion_no_puede_descartar():
    op = operacion_pendiente()
    with pytest.raises(TransicionInvalidaError):
        op.transicionar(EstadoIncidente.DESCARTADO, decision=aprobacion())


def test_decision_de_otro_incidente_se_rechaza():
    op = operacion_pendiente("INC-1")
    with pytest.raises(DecisionNoCorrespondeError):
        op.transicionar(EstadoIncidente.ASIGNADO, decision=aprobacion("INC-999"))


# ------------------------------------------------------- estructura del grafo
def test_transicion_nula_no_permitida():
    with pytest.raises(TransicionInvalidaError):
        validar_transicion(EstadoIncidente.RECIBIDO, EstadoIncidente.RECIBIDO)


def test_no_se_salta_la_verificacion():
    with pytest.raises(TransicionInvalidaError):
        validar_transicion(EstadoIncidente.RECIBIDO, EstadoIncidente.PRIORIZADO)


def test_los_estados_terminales_no_tienen_salida():
    for terminal in ESTADOS_TERMINALES:
        assert transiciones_posibles(terminal) == frozenset()


def test_flujo_feliz_completo():
    op = operacion_pendiente()
    op.transicionar(EstadoIncidente.ASIGNADO, decision=aprobacion())
    op.transicionar(EstadoIncidente.EN_EJECUCION)
    op.transicionar(EstadoIncidente.RESUELTO)
    assert op.terminada
    recorrido = [r.estado for r in op.historial]
    assert recorrido == [
        EstadoIncidente.VERIFICADO,
        EstadoIncidente.LOCALIZADO,
        EstadoIncidente.PRIORIZADO,
        EstadoIncidente.PENDIENTE_APROBACION,
        EstadoIncidente.ASIGNADO,
        EstadoIncidente.EN_EJECUCION,
        EstadoIncidente.RESUELTO,
    ]


# ------------------------------------------------------------ ciclos
def test_ciclo_repetido_acaba_en_suspendido():
    op = Operacion(incidente_id="INC-1", correlacion_id="COR-1", limite_visitas=3)
    op.transicionar(EstadoIncidente.VERIFICADO)
    op.transicionar(EstadoIncidente.LOCALIZADO)

    # Cada vuelta: PRIORIZADO -> PENDIENTE_APROBACION -> SUSPENDIDO -> PRIORIZADO
    for _ in range(3):
        op.transicionar(EstadoIncidente.PRIORIZADO)
        if op.estado is EstadoIncidente.SUSPENDIDO:
            break
        op.transicionar(EstadoIncidente.PENDIENTE_APROBACION)
        op.transicionar(EstadoIncidente.SUSPENDIDO, motivo="el coordinador no respondió")

    assert op.estado is EstadoIncidente.SUSPENDIDO
    assert op.visitas[EstadoIncidente.PRIORIZADO] == 3

    # La cuarta entrada a PRIORIZADO ya no se aplica: se desvía a SUSPENDIDO.
    registro = op.transicionar(EstadoIncidente.PRIORIZADO)
    assert registro.aplicada is False
    assert registro.estado is EstadoIncidente.SUSPENDIDO
    assert "ciclo detectado" in registro.motivo
    assert op.estado is EstadoIncidente.SUSPENDIDO


def test_suspender_no_cuenta_como_ciclo():
    op = Operacion(incidente_id="INC-1", correlacion_id="COR-1", limite_visitas=2)
    for _ in range(5):
        if op.estado is not EstadoIncidente.SUSPENDIDO:
            op.transicionar(EstadoIncidente.SUSPENDIDO)
        op.transicionar(EstadoIncidente.PRIORIZADO)
    assert op.estado is EstadoIncidente.SUSPENDIDO
