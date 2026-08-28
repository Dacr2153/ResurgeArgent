"""Pruebas de los contratos que cruzan agentes."""

from datetime import UTC, datetime, timedelta

import pytest

from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    ConsultaGeo,
    DecisionHumana,
    Fuente,
    IncidenteVerificado,
    ReporteCrudo,
    RespuestaGeo,
    RutaAlternativa,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import Punto

CIUDADANO = Fuente(id="c-1", tipo=TipoFuente.CIUDADANO, nombre="Ana", reputacion=0.4)
AUTORIDAD = Fuente(id="a-1", tipo=TipoFuente.AUTORIDAD, nombre="UNGRD", reputacion=0.95)
SITIO = Punto(lat=4.6097, lon=-74.0817)


def _reporte(texto="Derrumbe en la vía", fuente=CIUDADANO, ubicacion=SITIO) -> ReporteCrudo:
    return ReporteCrudo(texto=texto, fuente=fuente, canal=Canal.SMS, ubicacion=ubicacion)


def test_reputacion_fuera_de_rango_se_rechaza():
    with pytest.raises(ValueError):
        Fuente(id="x", tipo=TipoFuente.CIUDADANO, reputacion=1.5)


def test_mismo_reporte_produce_el_mismo_hash():
    assert _reporte().hash_idempotencia == _reporte().hash_idempotencia


def test_el_hash_ignora_mayusculas_y_espacios():
    a = _reporte(texto="Derrumbe en la via")
    b = _reporte(texto="  DERRUMBE EN LA VIA  ")
    assert a.hash_idempotencia == b.hash_idempotencia


def test_el_hash_tolera_el_temblor_del_gps():
    # ~40 m de diferencia: el mismo reporte reenviado, no uno nuevo.
    cerca = Punto(lat=SITIO.lat + 0.0002, lon=SITIO.lon)
    assert _reporte(ubicacion=cerca).hash_idempotencia == _reporte().hash_idempotencia


def test_el_hash_distingue_ubicaciones_distintas():
    lejos = Punto(lat=SITIO.lat + 0.05, lon=SITIO.lon)
    assert _reporte(ubicacion=lejos).hash_idempotencia != _reporte().hash_idempotencia


def test_el_hash_distingue_fuentes_distintas():
    assert _reporte(fuente=AUTORIDAD).hash_idempotencia != _reporte().hash_idempotencia


def test_reporte_sin_ubicacion_sigue_teniendo_hash():
    assert len(_reporte(ubicacion=None).hash_idempotencia) == 32


def test_incidente_exige_al_menos_un_reporte_de_origen():
    with pytest.raises(ValueError):
        IncidenteVerificado(
            categoria=Categoria.GEO,
            severidad=Severidad.SEVERE,
            urgencia=Urgencia.IMMEDIATE,
            ubicacion=SITIO,
            confianza=0.9,
            reportes_origen=(),
        )


def test_confianza_fuera_de_rango_se_rechaza():
    with pytest.raises(ValueError):
        IncidenteVerificado(
            categoria=Categoria.GEO,
            severidad=Severidad.SEVERE,
            urgencia=Urgencia.IMMEDIATE,
            ubicacion=SITIO,
            confianza=1.4,
            reportes_origen=("r-1",),
        )


def test_incidente_serializa_con_los_nombres_del_contrato():
    incidente = IncidenteVerificado(
        categoria=Categoria.GEO,
        severidad=Severidad.SEVERE,
        urgencia=Urgencia.IMMEDIATE,
        ubicacion=SITIO,
        confianza=0.923456,
        reportes_origen=("r-1", "r-2"),
    )
    d = incidente.a_dict()
    assert d["verified_incident_id"] == incidente.id
    assert d["confidence_score"] == 0.9235
    assert d["source_reports"] == ["r-1", "r-2"]
    assert d["location"]["type"] == "Point"
    assert incidente.corroboraciones == 2


def test_incidente_caduca():
    ahora = datetime.now(UTC)
    incidente = IncidenteVerificado(
        categoria=Categoria.FIRE,
        severidad=Severidad.MODERATE,
        urgencia=Urgencia.EXPECTED,
        ubicacion=SITIO,
        confianza=0.6,
        reportes_origen=("r-1",),
        vence_en=ahora - timedelta(hours=1),
    )
    assert not incidente.esta_vigente(ahora)


def test_incidente_sin_vencimiento_siempre_vigente():
    incidente = IncidenteVerificado(
        categoria=Categoria.FIRE,
        severidad=Severidad.MODERATE,
        urgencia=Urgencia.EXPECTED,
        ubicacion=SITIO,
        confianza=0.6,
        reportes_origen=("r-1",),
    )
    assert incidente.esta_vigente()


def test_decision_humana_exige_coordinador():
    with pytest.raises(ValueError):
        DecisionHumana(
            incidente_id="i-1", aprobada=True, coordinador_id="  ", justificacion="ok"
        )


def test_rechazo_sin_justificacion_se_rechaza():
    with pytest.raises(ValueError):
        DecisionHumana(
            incidente_id="i-1", aprobada=False, coordinador_id="coord-1", justificacion=""
        )


def test_aprobacion_no_exige_justificacion():
    decision = DecisionHumana(
        incidente_id="i-1", aprobada=True, coordinador_id="coord-1", justificacion=""
    )
    assert decision.a_dict()["aprobada"] is True


def test_consulta_y_respuesta_geo_serializan_geojson():
    consulta = ConsultaGeo(origen=SITIO, destino=Punto(lat=4.65, lon=-74.05))
    assert consulta.a_dict()["origen"]["type"] == "Point"
    respuesta = RespuestaGeo(
        consulta_id=consulta.id,
        accesible=True,
        distancia_km=5.4321,
        geometria={"type": "LineString", "coordinates": [[-74.08, 4.60], [-74.05, 4.65]]},
    )
    assert respuesta.a_dict()["distancia_km"] == 5.432


def test_reporte_serializa_certeza_cap():
    reporte = ReporteCrudo(
        texto="Humo denso",
        fuente=AUTORIDAD,
        canal=Canal.RADIO,
        ubicacion=SITIO,
        certeza=Certeza.OBSERVED,
    )
    assert reporte.a_dict()["certeza"] == "Observed"


def test_respuesta_geo_sin_alternativas_por_defecto():
    respuesta = RespuestaGeo(consulta_id="c-1", accesible=True)
    assert respuesta.alternativas == ()
    assert respuesta.a_dict()["alternativas"] == []


def test_respuesta_geo_serializa_alternativas():
    alterna = RutaAlternativa(
        distancia_km=7.6543,
        duracion_min=14.2,
        geometria={"type": "LineString", "coordinates": [[-74.08, 4.60], [-74.03, 4.66]]},
        vias_evitadas=("T3",),
    )
    respuesta = RespuestaGeo(
        consulta_id="c-1", accesible=True, distancia_km=5.0, alternativas=(alterna,)
    )
    d = respuesta.a_dict()
    assert len(d["alternativas"]) == 1
    assert d["alternativas"][0]["distancia_km"] == 7.654
    assert d["alternativas"][0]["vias_evitadas"] == ["T3"]
