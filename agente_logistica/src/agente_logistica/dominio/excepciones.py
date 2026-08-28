"""Excepciones del dominio logístico."""

from __future__ import annotations


class ErrorDominio(Exception):
    """Error base del dominio."""


class DestinoInaccesibleError(ErrorDominio):
    """No existe una ruta válida entre origen y destino."""


class VehiculoIncompatibleError(ErrorDominio):
    """Ningún vehículo es compatible con la asignación."""


class DatosInsuficientesError(ErrorDominio):
    """Faltan datos obligatorios para planificar."""
