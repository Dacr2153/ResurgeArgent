"""El sobre: identidad estable del mensaje y serialización de ida y vuelta."""

from __future__ import annotations

import pytest

from malla.dominio.excepciones import SobreInvalidoError
from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from malla.dominio.sobre import SobreMalla, derivar_id_mensaje
from tests.malla.conftest import reporte


def test_id_mensaje_es_el_hash_de_idempotencia():
    """La primitiva se reutiliza, no se reinventa."""
    r = reporte()
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), r.a_dict())
    assert sobre.id_mensaje == r.hash_idempotencia


def test_mismo_reporte_mismo_id_en_nodos_distintos():
    """Tres nodos que reciben el mismo reporte producen el mismo identificador."""
    r = reporte()
    ids = {crear_sobre_firmado(IdentidadNodo.generar(), r.a_dict()).id_mensaje for _ in range(3)}
    assert len(ids) == 1


def test_gps_oscilante_no_produce_dos_mensajes():
    """El redondeo a ~100 m del núcleo absorbe la deriva del GPS del teléfono."""
    a = reporte(lat=4.60971, lon=-74.08172)
    b = reporte(lat=4.60973, lon=-74.08174)
    assert derivar_id_mensaje(a.a_dict()) == derivar_id_mensaje(b.a_dict())


def test_carga_sin_hash_deriva_id_de_su_contenido():
    id_a = derivar_id_mensaje({"ids_acusados": ["x"], "nodo": "n1"})
    id_b = derivar_id_mensaje({"nodo": "n1", "ids_acusados": ["x"]})
    assert id_a == id_b  # el orden de las claves no cambia el id


def test_avanzar_no_muta_el_original():
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    avanzado = sobre.avanzar("nodo-x")
    assert sobre.saltos == 0
    assert avanzado.saltos == 1
    assert avanzado.ruta == ("nodo-x",)


def test_paso_por_reconoce_origen_y_ruta():
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte().a_dict()).avanzar("nodo-x")
    assert sobre.paso_por(identidad.id_nodo) is True
    assert sobre.paso_por("nodo-x") is True
    assert sobre.paso_por("nodo-y") is False


def test_serializacion_ida_y_vuelta_conserva_la_firma():
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict()).avanzar("n1")
    recuperado = SobreMalla.desde_dict(sobre.a_dict())
    assert recuperado == sobre
    assert recuperado.contenido_firmado == sobre.contenido_firmado


def test_sobre_mal_formado_falla_explicitamente():
    with pytest.raises(SobreInvalidoError):
        SobreMalla.desde_dict({"carga": {}, "nodo_origen": "n"})


def test_ttl_minimo():
    with pytest.raises(SobreInvalidoError):
        SobreMalla(
            carga={},
            nodo_origen="n",
            clave_publica_origen="",
            firma="",
            id_mensaje="abc",
            ttl=0,
        )
