"""Excepciones del dominio."""

from __future__ import annotations


class ErrorDominio(Exception):
    """Error base del dominio."""


class SinDemandaError(ErrorDominio):
    """No hay necesidades para matchear."""


class RecursoIncompatibleError(ErrorDominio):
    """Un recurso no es compatible con una necesidad."""


class CapacidadInsuficienteError(ErrorDominio):
    """La cantidad reservada supera la capacidad disponible."""
