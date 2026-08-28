"""Excepciones del dominio del Orquestador.

Todas heredan de `ErrorDominio` para que el adaptador REST pueda mapear la
familia completa sin conocer cada caso. Las que describen un fallo del gate
humano se separan del resto porque tienen respuesta HTTP distinta: pedir una
firma no es lo mismo que pedir una transición imposible.
"""

from __future__ import annotations


class ErrorDominio(Exception):
    """Error base del dominio del Orquestador."""


class TransicionInvalidaError(ErrorDominio):
    """La transición de estado solicitada no existe en la máquina de estados."""


class DecisionHumanaRequeridaError(TransicionInvalidaError):
    """La transición existe pero exige una decisión humana firmada que no llegó.

    Es la excepción que protege el paso PENDIENTE_APROBACION -> ASIGNADO: sin
    firma no se despacha, y el fallo es explícito en vez de silencioso.
    """


class DecisionRechazadaError(TransicionInvalidaError):
    """Se intentó usar una decisión rechazada para autorizar una asignación."""


class DecisionNoCorrespondeError(ErrorDominio):
    """La decisión firmada apunta a otro incidente distinto del que se transiciona."""


class IncidenteDesconocidoError(ErrorDominio):
    """No hay operación abierta para el incidente indicado."""


class SinIncidentesError(ErrorDominio):
    """No quedó ningún incidente verificado que priorizar."""
