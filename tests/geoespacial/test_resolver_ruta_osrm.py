"""Tests de ResolverRuta con un RuteadorPort configurado.

Separado de test_resolver_ruta.py (que no debe tocarse) porque cubre un
comportamiento nuevo: la elección de motor y la caída a respaldo. Usa dobles
del ``RuteadorPort``, no del cliente HTTP — esa parte ya se prueba en
test_ruteo_osrm.py.
"""

from __future__ import annotations

import pytest

from agente_geoespacial.adaptadores.llm.interprete_nulo import InterpreteNulo
from agente_geoespacial.aplicacion.casos_uso.resolver_ruta import (
    MOTOR_GRAFO,
    MOTOR_OSRM,
    ResolverRuta,
)
from agente_geoespacial.dominio.entidades import GrafoVial, NodoVial, ResultadoRuta, TramoVial
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import ConsultaGeo
from nucleo.geo import Punto
from nucleo.mensajes import TipoEvento


def _grafo() -> GrafoVial:
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7050, lon=-74.0800)),
        "N3": NodoVial(id="N3", ubicacion=Punto(lat=4.7050, lon=-74.0700)),
    }
    tramos = (
        TramoVial(id="T1", origen_id="N1", destino_id="N2"),
        TramoVial(id="T2", origen_id="N2", destino_id="N3"),
        TramoVial(id="T3", origen_id="N1", destino_id="N3"),
    )
    return GrafoVial(nodos=nodos, tramos=tramos)


class FakePublicador:
    def __init__(self):
        self.publicados = []

    async def publicar(self, evento):
        self.publicados.append(evento)


class RuteadorFalso:
    """Doble de RuteadorPort: devuelve lo que se le configure, sin red."""

    def __init__(self, resultado: ResultadoRuta | None, lanza: Exception | None = None):
        self._resultado = resultado
        self._lanza = lanza
        self.llamadas = 0
        self.ultimo_segmentos_bloqueados = None

    async def calcular_ruta(self, origen, destino, modo, segmentos_bloqueados=()):
        self.llamadas += 1
        self.ultimo_segmentos_bloqueados = segmentos_bloqueados
        if self._lanza is not None:
            raise self._lanza
        return self._resultado


def _construir(ruteador=None):
    grafo = _grafo()
    motor = MotorRutas(grafo)
    llm = InterpreteNulo()
    publicador = FakePublicador()
    auditoria = AuditoriaMemoria()
    caso = ResolverRuta(
        motor=motor, llm=llm, publicador=publicador, auditoria=auditoria, ruteador=ruteador
    )
    return caso, grafo, publicador, auditoria


@pytest.mark.asyncio
async def test_sin_ruteador_usa_el_grafo_como_siempre():
    caso, grafo, _, auditoria = _construir(ruteador=None)
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta)

    assert respuesta.accesible is True
    eventos = [e for e in auditoria.eventos if e.tipo == TipoEvento.RUTA_CALCULADA]
    assert eventos[0].detalle["motor_resolucion"] == MOTOR_GRAFO


@pytest.mark.asyncio
async def test_con_ruteador_disponible_usa_osrm():
    resultado_osrm = ResultadoRuta(
        accesible=True,
        distancia_km=1.5,
        duracion_min=3.0,
        geometria={"type": "LineString", "coordinates": [[-74.08, 4.70], [-74.07, 4.71]]},
    )
    ruteador = RuteadorFalso(resultado_osrm)
    caso, grafo, _, auditoria = _construir(ruteador=ruteador)
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta)

    assert ruteador.llamadas == 1
    assert respuesta.distancia_km == pytest.approx(1.5)
    assert respuesta.geometria["coordinates"] == [[-74.08, 4.70], [-74.07, 4.71]]
    eventos = [e for e in auditoria.eventos if e.tipo == TipoEvento.RUTA_CALCULADA]
    assert eventos[0].detalle["motor_resolucion"] == MOTOR_OSRM


@pytest.mark.asyncio
async def test_osrm_devuelve_none_cae_al_grafo_de_respaldo():
    ruteador = RuteadorFalso(resultado=None)
    caso, grafo, _, auditoria = _construir(ruteador=ruteador)
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta)

    assert respuesta.accesible is True  # el grafo propio sí resuelve esta consulta
    assert "respaldo" in respuesta.motivo
    eventos = [e for e in auditoria.eventos if e.tipo == TipoEvento.RUTA_CALCULADA]
    assert eventos[0].detalle["motor_resolucion"] == MOTOR_GRAFO


@pytest.mark.asyncio
async def test_osrm_lanza_excepcion_cae_al_grafo_de_respaldo_sin_reventar():
    """Un servicio público sin SLA no puede tumbar la petición ni con un bug
    del propio adaptador: si algo se escapa como excepción, ResolverRuta lo
    atrapa igual que un None."""
    ruteador = RuteadorFalso(resultado=None, lanza=RuntimeError("algo salió mal en el adaptador"))
    caso, grafo, _, _ = _construir(ruteador=ruteador)
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta)

    assert respuesta.accesible is True


@pytest.mark.asyncio
async def test_bloqueos_se_traducen_a_segmentos_de_coordenadas_para_el_ruteador():
    ruteador = RuteadorFalso(
        ResultadoRuta(
            accesible=True,
            distancia_km=1.0,
            duracion_min=2.0,
            geometria={"type": "LineString", "coordinates": []},
        )
    )
    caso, grafo, _, _ = _construir(ruteador=ruteador)
    consulta = ConsultaGeo(
        origen=grafo.nodos["N1"].ubicacion,
        destino=grafo.nodos["N3"].ubicacion,
        evitar_zonas=("T3",),
    )

    await caso.ejecutar(consulta)

    assert ruteador.ultimo_segmentos_bloqueados == [
        (grafo.nodos["N1"].ubicacion, grafo.nodos["N3"].ubicacion)
    ]


@pytest.mark.asyncio
async def test_vias_evitadas_en_la_respuesta_son_las_pedidas_no_las_del_ruteador():
    """El ruteador OSRM no conoce ids de tramo (solo coordenadas), así que su
    ResultadoRuta.vias_evitadas siempre viene vacío. La respuesta final debe
    igual reportar qué se pidió evitar."""
    ruteador = RuteadorFalso(
        ResultadoRuta(
            accesible=True,
            distancia_km=1.0,
            duracion_min=2.0,
            geometria={"type": "LineString", "coordinates": []},
            vias_evitadas=(),
        )
    )
    caso, grafo, _, _ = _construir(ruteador=ruteador)
    consulta = ConsultaGeo(
        origen=grafo.nodos["N1"].ubicacion,
        destino=grafo.nodos["N3"].ubicacion,
        evitar_zonas=("T3",),
    )

    respuesta = await caso.ejecutar(consulta)

    assert respuesta.vias_evitadas == ("T3",)
