"""Tests del motor de rutas: puro, determinista, sin I/O."""

import pytest

from agente_geoespacial.dominio.entidades import GrafoVial, NodoVial, TramoVial
from agente_geoespacial.dominio.excepciones import NodoDesconocidoError
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from agente_geoespacial.dominio.value_objects import PERFIL_VELOCIDAD_DEFECTO, PerfilVelocidad
from nucleo.esquemas import ConsultaGeo, ModoTransporte
from nucleo.geo import Punto, validar_geojson


def _grafo_lineal() -> GrafoVial:
    """N1 - N2 - N3 en línea, más un desvío directo N1-N3 más largo (vía T4)."""
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7050, lon=-74.0750)),
        "N3": NodoVial(id="N3", ubicacion=Punto(lat=4.7100, lon=-74.0700)),
        "N4": NodoVial(id="N4", ubicacion=Punto(lat=4.6800, lon=-74.0900)),
    }
    tramos = (
        TramoVial(id="T1", origen_id="N1", destino_id="N2"),
        TramoVial(id="T2", origen_id="N2", destino_id="N3"),
        # Desvío más largo: pasa por N4, para tener una alternativa real.
        TramoVial(id="T3", origen_id="N1", destino_id="N4"),
        TramoVial(id="T4", origen_id="N4", destino_id="N3"),
    )
    return GrafoVial(nodos=nodos, tramos=tramos)


def _grafo_sin_alternativa() -> GrafoVial:
    """N1 - N2 - N3 en línea única, sin ningún desvío posible."""
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7050, lon=-74.0750)),
        "N3": NodoVial(id="N3", ubicacion=Punto(lat=4.7100, lon=-74.0700)),
    }
    tramos = (
        TramoVial(id="T1", origen_id="N1", destino_id="N2"),
        TramoVial(id="T2", origen_id="N2", destino_id="N3"),
    )
    return GrafoVial(nodos=nodos, tramos=tramos)


def _consulta(origen: str, destino: str, grafo: GrafoVial, modo=ModoTransporte.AUTO) -> ConsultaGeo:
    return ConsultaGeo(
        origen=grafo.nodos[origen].ubicacion,
        destino=grafo.nodos[destino].ubicacion,
        modo=modo,
    )


def test_ruta_directa_sin_bloqueos():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo)
    resultado = motor.calcular_ruta(_consulta("N1", "N3", grafo))

    assert resultado.accesible
    assert resultado.distancia_km > 0
    assert resultado.duracion_min > 0
    assert resultado.vias_evitadas == ()
    assert resultado.motivo == ""


def test_geometria_es_linestring_geojson_valido_en_orden_lon_lat():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo)
    resultado = motor.calcular_ruta(_consulta("N1", "N3", grafo))

    geometria = resultado.geometria
    validar_geojson(geometria)
    assert geometria["type"] == "LineString"

    primer_punto = geometria["coordinates"][0]
    nodo_origen = grafo.nodos["N1"].ubicacion
    # [lon, lat], no [lat, lon]: la inversión es la fuente de error más común.
    assert primer_punto == [nodo_origen.lon, nodo_origen.lat]


def test_origen_igual_a_destino_devuelve_ruta_vacia_accesible():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo)
    resultado = motor.calcular_ruta(_consulta("N1", "N1", grafo))

    assert resultado.accesible
    assert resultado.distancia_km == 0.0
    assert resultado.duracion_min == 0.0
    validar_geojson(resultado.geometria)


def test_via_bloqueada_fuerza_desvio_mas_largo_y_distinto():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo)

    directa = motor.calcular_ruta(_consulta("N1", "N3", grafo))
    desviada = motor.calcular_ruta(_consulta("N1", "N3", grafo), vias_bloqueadas=["T2"])

    assert directa.accesible
    assert desviada.accesible
    assert desviada.vias_evitadas == ("T2",)
    # La ruta desviada debe ser una ruta distinta y estrictamente más larga.
    assert desviada.geometria != directa.geometria
    assert desviada.distancia_km > directa.distancia_km


def test_destino_inaccesible_no_lanza_excepcion_sino_respuesta_informativa():
    grafo = _grafo_sin_alternativa()
    motor = MotorRutas(grafo)

    resultado = motor.calcular_ruta(_consulta("N1", "N3", grafo), vias_bloqueadas=["T1"])

    assert resultado.accesible is False
    assert resultado.distancia_km == 0.0
    assert resultado.motivo != ""
    assert resultado.vias_evitadas == ("T1",)


def test_nodo_fuera_del_grafo_lanza_nodo_desconocido():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo, radio_conexion_km=1.0)

    consulta = ConsultaGeo(
        origen=Punto(lat=-33.45, lon=-70.66),  # Santiago de Chile: fuera de la red
        destino=grafo.nodos["N3"].ubicacion,
    )
    with pytest.raises(NodoDesconocidoError):
        motor.calcular_ruta(consulta)


def test_grafo_sin_nodos_lanza_nodo_desconocido():
    grafo_vacio = GrafoVial(nodos={}, tramos=())
    motor = MotorRutas(grafo_vacio)

    consulta = ConsultaGeo(origen=Punto(lat=4.7, lon=-74.08), destino=Punto(lat=4.71, lon=-74.07))
    with pytest.raises(NodoDesconocidoError):
        motor.calcular_ruta(consulta)


def test_ofrece_al_menos_una_ruta_alternativa_cuando_existe():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo)
    resultado = motor.calcular_ruta(_consulta("N1", "N3", grafo))

    assert len(resultado.alternativas) >= 1
    alternativa = resultado.alternativas[0]
    # La alternativa es una ruta distinta a la principal, y al ser la principal
    # la óptima, la alternativa no puede ser más corta.
    assert alternativa.nodos != ("N1", "N2", "N3")
    assert alternativa.distancia_km >= resultado.distancia_km
    validar_geojson(alternativa.geometria)


def test_sin_alternativa_devuelve_tupla_vacia():
    grafo = _grafo_sin_alternativa()
    motor = MotorRutas(grafo)
    resultado = motor.calcular_ruta(_consulta("N1", "N3", grafo))

    assert resultado.alternativas == ()


def test_lista_de_bloqueos_vacia_no_cambia_el_resultado():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo)

    con_lista_vacia = motor.calcular_ruta(_consulta("N1", "N3", grafo), vias_bloqueadas=[])
    sin_argumento = motor.calcular_ruta(_consulta("N1", "N3", grafo))

    assert con_lista_vacia.distancia_km == pytest.approx(sin_argumento.distancia_km)


def test_modo_transporte_afecta_la_duracion_no_la_distancia():
    grafo = _grafo_lineal()
    motor = MotorRutas(grafo, perfil_velocidad=PERFIL_VELOCIDAD_DEFECTO)

    en_auto = motor.calcular_ruta(_consulta("N1", "N3", grafo, modo=ModoTransporte.AUTO))
    a_pie = motor.calcular_ruta(_consulta("N1", "N3", grafo, modo=ModoTransporte.PEATON))

    assert en_auto.distancia_km == pytest.approx(a_pie.distancia_km)
    assert a_pie.duracion_min > en_auto.duracion_min


def test_perfil_velocidad_rechaza_valores_no_positivos():
    with pytest.raises(ValueError):
        PerfilVelocidad(valores_kmh={ModoTransporte.AUTO: 0.0})
