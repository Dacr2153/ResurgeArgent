"""Excepciones del dominio geoespacial."""

from __future__ import annotations


class ErrorGeoespacial(Exception):
    """Error base del dominio geoespacial."""


class NodoDesconocidoError(ErrorGeoespacial):
    """El grafo vial no contiene un nodo suficientemente cerca del punto pedido.

    Distinto de "destino inalcanzable": aquí el punto ni siquiera pertenece a la
    red vial que conoce el agente (está fuera de su radio de conexión), así que
    no hay nada que calcular. Un destino real pero bloqueado por vías caídas se
    modela como ``RespuestaGeo(accesible=False, ...)``, no como esta excepción.
    """


class GrafoVialInvalidoError(ErrorGeoespacial):
    """Un tramo referencia un nodo que no existe en el grafo."""
