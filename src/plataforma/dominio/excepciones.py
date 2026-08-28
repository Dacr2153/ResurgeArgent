"""Excepciones del dominio de plataforma."""

from __future__ import annotations


class ErrorPlataforma(Exception):
    """Raíz de los errores propios de plataforma."""


class RecursoDesconocidoError(ErrorPlataforma):
    """Se pidió algo que no existe: un reporte, una misión."""
