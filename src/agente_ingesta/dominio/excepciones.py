"""Excepciones del dominio."""

from __future__ import annotations


class ErrorDominio(Exception):
    """Error base del dominio."""


class LoteInvalidoError(ErrorDominio):
    """La entrada no tiene la forma mínima de un lote de ingesta."""
