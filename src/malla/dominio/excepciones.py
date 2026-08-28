"""Errores del dominio de malla."""

from __future__ import annotations


class ErrorMalla(Exception):
    """Raíz de los errores del dominio de malla."""


class SobreInvalidoError(ErrorMalla):
    """El sobre está mal formado y no puede procesarse."""


class IdentidadInvalidaError(ErrorMalla):
    """La identidad criptográfica del nodo no se pudo cargar o generar."""
