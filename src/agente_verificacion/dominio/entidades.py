"""Entidades del dominio de verificación.

Este dominio no declara entidades propias de negocio: opera directamente sobre
los contratos de `nucleo.esquemas` (`ReporteCrudo` de entrada,
`IncidenteVerificado` de salida) porque esos son justamente la interfaz que
cruza la frontera con Ingesta y con el Orquestador — inventar un tipo interno
paralelo solo obligaría a traducir de un lado a otro sin ganar nada.

Este módulo se deja presente, vacío salvo este comentario, para conservar la
misma forma de paquete que `agente_matching` y como lugar natural donde meter
una entidad puramente interna si en el futuro hiciera falta una (por ejemplo,
un tipo de "cluster candidato" con metadatos propios de la agrupación).
"""

from __future__ import annotations
