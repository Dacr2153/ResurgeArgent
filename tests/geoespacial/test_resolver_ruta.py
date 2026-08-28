"""Tests del caso de uso ResolverRuta, con dobles de prueba de los puertos."""

import pytest

from agente_geoespacial.adaptadores.llm.interprete_nulo import InterpreteNulo
from agente_geoespacial.aplicacion.casos_uso.analizar_zonas import AnalizarZonas
from agente_geoespacial.aplicacion.casos_uso.resolver_ruta import ResolverRuta
from agente_geoespacial.aplicacion.casos_uso.servicio_geoespacial import ServicioGeoespacial
from agente_geoespacial.dominio.entidades import GrafoVial, NodoVial, TramoVial
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import ConsultaGeo
from nucleo.geo import Punto
from nucleo.mensajes import TipoEvento


def _grafo() -> GrafoVial:
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7050, lon=-74.0750)),
        "N3": NodoVial(id="N3", ubicacion=Punto(lat=4.7100, lon=-74.0700)),
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


class LLMQueDecide:
    """Doble que simula un LLM que intentara decidir en vez de solo interpretar.

    Se usa para probar que ResolverRuta nunca le pide al LLM más que una lista
    de ids: si el LLM devolviera algo distinto de una lista de bloqueos, el
    motor seguiría siendo quien calcula la ruta con lo que reciba.
    """

    def __init__(self, bloqueos):
        self._bloqueos = bloqueos
        self.llamadas = 0

    async def interpretar(self, reportes_texto):
        self.llamadas += 1
        return self._bloqueos


def construir_caso_uso(bloqueos=None):
    grafo = _grafo()
    motor = MotorRutas(grafo)
    llm = LLMQueDecide(bloqueos or [])
    publicador = FakePublicador()
    auditoria = AuditoriaMemoria()
    caso = ResolverRuta(motor=motor, llm=llm, publicador=publicador, auditoria=auditoria)
    return caso, grafo, llm, publicador, auditoria


@pytest.mark.asyncio
async def test_resuelve_ruta_sin_reportes_de_bloqueo():
    caso, grafo, llm, publicador, auditoria = construir_caso_uso()
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta)

    assert respuesta.accesible
    assert respuesta.vias_evitadas == ()
    assert llm.llamadas == 1
    assert len(publicador.publicados) == 1
    eventos_ruta = auditoria.por_tipo(str(TipoEvento.RUTA_CALCULADA))
    assert len(eventos_ruta) == 1
    assert auditoria.por_tipo(str(TipoEvento.VIA_BLOQUEADA)) == []


@pytest.mark.asyncio
async def test_via_bloqueada_detectada_por_el_llm_emite_evento_de_auditoria():
    caso, grafo, llm, _, auditoria = construir_caso_uso(bloqueos=["T1"])
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta, reportes_bloqueo=["la via:T1 esta bloqueada"])

    assert respuesta.accesible
    assert respuesta.vias_evitadas == ("T1",)
    eventos_bloqueo = auditoria.por_tipo(str(TipoEvento.VIA_BLOQUEADA))
    assert len(eventos_bloqueo) == 1
    assert eventos_bloqueo[0].detalle["vias_bloqueadas"] == ["T1"]


@pytest.mark.asyncio
async def test_ejecutar_detallado_expone_alternativas():
    caso, grafo, _, _, _ = construir_caso_uso()
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta, resultado = await caso.ejecutar_detallado(consulta)

    assert respuesta.accesible
    assert len(resultado.alternativas) >= 1


@pytest.mark.asyncio
async def test_interprete_nulo_extrae_via_bloqueada_por_palabra_clave():
    grafo = _grafo()
    motor = MotorRutas(grafo)
    publicador = FakePublicador()
    auditoria = AuditoriaMemoria()
    caso = ResolverRuta(
        motor=motor, llm=InterpreteNulo(), publicador=publicador, auditoria=auditoria
    )
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(
        consulta, reportes_bloqueo=["no se puede pasar, la tramo:T3 quedo tapada por el derrumbe"]
    )

    assert "T3" in respuesta.vias_evitadas


@pytest.mark.asyncio
async def test_reportes_sin_palabra_clave_no_bloquean_nada():
    grafo = _grafo()
    motor = MotorRutas(grafo)
    caso = ResolverRuta(
        motor=motor, llm=InterpreteNulo(), publicador=FakePublicador(), auditoria=AuditoriaMemoria()
    )
    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)

    respuesta = await caso.ejecutar(consulta, reportes_bloqueo=["trafico lento pero fluido"])

    assert respuesta.vias_evitadas == ()


@pytest.mark.asyncio
async def test_servicio_geoespacial_cumple_el_puerto_del_nucleo():
    grafo = _grafo()
    motor = MotorRutas(grafo)
    resolver_ruta = ResolverRuta(
        motor=motor, llm=InterpreteNulo(), publicador=FakePublicador(), auditoria=AuditoriaMemoria()
    )
    from agente_geoespacial.dominio.motor_zonas import MotorZonas

    analizar_zonas = AnalizarZonas(motor=MotorZonas())
    servicio = ServicioGeoespacial(resolver_ruta=resolver_ruta, analizar_zonas=analizar_zonas)

    consulta = ConsultaGeo(origen=grafo.nodos["N1"].ubicacion, destino=grafo.nodos["N3"].ubicacion)
    respuesta = await servicio.resolver_ruta(consulta)
    assert respuesta.accesible

    zonas = await servicio.zonas_afectadas([])
    assert zonas == {"type": "FeatureCollection", "features": []}
