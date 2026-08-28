"""Dominio del Agente 2: el motor puro de ingesta y sus tipos de apoyo."""

from __future__ import annotations

from agente_ingesta.dominio.entidades import Descarte, ResultadoIngesta
from agente_ingesta.dominio.excepciones import ErrorDominio, LoteInvalidoError
from agente_ingesta.dominio.motor_ingesta import MotorIngesta
from agente_ingesta.dominio.value_objects import ConfigVentana, MotivoDescarte

__all__ = [
    "ConfigVentana",
    "Descarte",
    "ErrorDominio",
    "LoteInvalidoError",
    "MotivoDescarte",
    "MotorIngesta",
    "ResultadoIngesta",
]
