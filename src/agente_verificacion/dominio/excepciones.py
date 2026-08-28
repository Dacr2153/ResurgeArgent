"""Excepciones del dominio de verificación."""

from __future__ import annotations


class ErrorDominio(Exception):
    """Error base del dominio de verificación."""


class VectorAcuerdoInvalidoError(ErrorDominio):
    """Un `VectorAcuerdo` recibió una similitud fuera de [0,1]."""
