"""Adaptador que compone los dos casos de uso para cumplir ``GeoespacialPort``.

``nucleo.puertos.GeoespacialPort`` declara ``resolver_ruta`` y
``zonas_afectadas`` en un único puerto porque así lo consume el Orquestador,
pero internamente son dos capacidades independientes (rutas vs. zonas), cada
una con su propio caso de uso y su propio motor. Esta clase es solo el punto de
composición: por su forma (duck typing, sin herencia) cumple el ``Protocol``.
"""

from __future__ import annotations

from agente_geoespacial.aplicacion.casos_uso.analizar_zonas import AnalizarZonas
from agente_geoespacial.aplicacion.casos_uso.resolver_ruta import ResolverRuta
from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, RespuestaGeo


class ServicioGeoespacial:
    def __init__(self, resolver_ruta: ResolverRuta, analizar_zonas: AnalizarZonas) -> None:
        self._resolver_ruta = resolver_ruta
        self._analizar_zonas = analizar_zonas

    async def resolver_ruta(self, consulta: ConsultaGeo) -> RespuestaGeo:
        return await self._resolver_ruta.ejecutar(consulta)

    async def zonas_afectadas(self, incidentes: list[IncidenteVerificado]) -> dict:
        return await self._analizar_zonas.ejecutar(incidentes)
