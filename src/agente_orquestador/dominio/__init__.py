"""Dominio del Orquestador: estados, triage y saga. Sin dependencias de framework."""

from agente_orquestador.dominio.entidades import (
    LIMITE_VISITAS_POR_ESTADO,
    Operacion,
    RegistroTransicion,
)
from agente_orquestador.dominio.estados import (
    ESTADOS_TERMINALES,
    TRANSICIONES_AUTOMATICAS,
    TRANSICIONES_CON_DECISION_HUMANA,
    EstadoIncidente,
    transiciones_posibles,
    validar_transicion,
)
from agente_orquestador.dominio.excepciones import (
    DecisionHumanaRequeridaError,
    DecisionNoCorrespondeError,
    DecisionRechazadaError,
    ErrorDominio,
    IncidenteDesconocidoError,
    SinIncidentesError,
    TransicionInvalidaError,
)
from agente_orquestador.dominio.motor_triage import MotorTriage
from agente_orquestador.dominio.saga import (
    EstadoPaso,
    PasoSaga,
    ResultadoSaga,
    Saga,
)
from agente_orquestador.dominio.value_objects import PesosTriage, PuntuacionTriage

__all__ = [
    "ESTADOS_TERMINALES",
    "LIMITE_VISITAS_POR_ESTADO",
    "TRANSICIONES_AUTOMATICAS",
    "TRANSICIONES_CON_DECISION_HUMANA",
    "DecisionHumanaRequeridaError",
    "DecisionNoCorrespondeError",
    "DecisionRechazadaError",
    "ErrorDominio",
    "EstadoIncidente",
    "EstadoPaso",
    "IncidenteDesconocidoError",
    "MotorTriage",
    "Operacion",
    "PasoSaga",
    "PesosTriage",
    "PuntuacionTriage",
    "RegistroTransicion",
    "ResultadoSaga",
    "Saga",
    "SinIncidentesError",
    "TransicionInvalidaError",
    "transiciones_posibles",
    "validar_transicion",
]
