"""Tests del motor de zonas: agrupación en rejilla, puro y determinista."""

import pytest

from agente_geoespacial.dominio.motor_zonas import MotorZonas
from nucleo.esquemas import Categoria, IncidenteVerificado, Severidad, Urgencia
from nucleo.geo import Punto, validar_geojson


def _incidente(lat, lon, severidad=Severidad.MODERATE, reportes=("r1",)) -> IncidenteVerificado:
    return IncidenteVerificado(
        categoria=Categoria.INFRA,
        severidad=severidad,
        urgencia=Urgencia.EXPECTED,
        ubicacion=Punto(lat=lat, lon=lon),
        confianza=0.8,
        reportes_origen=tuple(reportes),
    )


def test_lista_vacia_devuelve_feature_collection_vacio():
    motor = MotorZonas(tamano_celda_grados=0.01)
    resultado = motor.agrupar([])

    assert resultado == {"type": "FeatureCollection", "features": []}


def test_agrupa_incidentes_cercanos_en_la_misma_celda():
    motor = MotorZonas(tamano_celda_grados=0.1)
    incidentes = [
        _incidente(4.701, -74.081),
        _incidente(4.705, -74.085),
    ]
    resultado = motor.agrupar(incidentes)

    assert len(resultado["features"]) == 1
    assert resultado["features"][0]["properties"]["conteo_incidentes"] == 2


def test_separa_incidentes_lejanos_en_celdas_distintas():
    motor = MotorZonas(tamano_celda_grados=0.01)
    incidentes = [
        _incidente(4.70, -74.08),
        _incidente(6.25, -75.56),  # Medellín: muy lejos de Bogotá
    ]
    resultado = motor.agrupar(incidentes)

    assert len(resultado["features"]) == 2
    for feature in resultado["features"]:
        assert feature["properties"]["conteo_incidentes"] == 1


def test_severidad_agregada_es_la_maxima_de_la_celda():
    motor = MotorZonas(tamano_celda_grados=0.1)
    incidentes = [
        _incidente(4.70, -74.08, severidad=Severidad.MINOR),
        _incidente(4.71, -74.07, severidad=Severidad.EXTREME),
        _incidente(4.72, -74.06, severidad=Severidad.MODERATE),
    ]
    resultado = motor.agrupar(incidentes)

    assert len(resultado["features"]) == 1
    assert resultado["features"][0]["properties"]["severidad_agregada"] == str(Severidad.EXTREME)


def test_geometria_de_cada_celda_es_poligono_geojson_valido():
    motor = MotorZonas(tamano_celda_grados=0.05)
    resultado = motor.agrupar([_incidente(4.70, -74.08)])

    feature = resultado["features"][0]
    validar_geojson(feature["geometry"])
    assert feature["geometry"]["type"] == "Polygon"

    anillo = feature["geometry"]["coordinates"][0]
    assert anillo[0] == anillo[-1]  # anillo cerrado
    # Coordenadas en orden [lon, lat]: la longitud de Bogotá es negativa y grande
    # en magnitud, la latitud es positiva y pequeña — sirve para detectar inversión.
    for lon, lat in anillo:
        assert lon < -70
        assert 0 < lat < 10


def test_incidentes_ids_quedan_en_las_propiedades_de_la_celda():
    motor = MotorZonas(tamano_celda_grados=0.1)
    incidente = _incidente(4.70, -74.08)
    resultado = motor.agrupar([incidente])

    assert resultado["features"][0]["properties"]["incidentes_ids"] == [incidente.id]


def test_tamano_celda_no_positivo_es_invalido():
    with pytest.raises(ValueError):
        MotorZonas(tamano_celda_grados=0.0)
    with pytest.raises(ValueError):
        MotorZonas(tamano_celda_grados=-0.01)
