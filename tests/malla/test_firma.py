"""Firma Ed25519: lo que impide que un retransmisor reescriba una emergencia."""

from __future__ import annotations

from dataclasses import replace

import pytest

from malla.dominio.excepciones import IdentidadInvalidaError
from malla.dominio.firma import (
    IdentidadNodo,
    cargar_o_crear_identidad,
    crear_sobre_firmado,
    verificar_firma,
    verificar_sobre,
)
from tests.malla.conftest import reporte


def test_firma_valida_verifica():
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte().a_dict())
    assert verificar_sobre(sobre) is True


def test_firma_de_otra_clave_no_verifica():
    identidad = IdentidadNodo.generar()
    intrusa = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte().a_dict())
    falsificado = replace(sobre, firma=intrusa.firmar(sobre.contenido_firmado))
    assert verificar_sobre(falsificado) is False


def test_retransmisor_que_altera_la_ubicacion_es_rechazado():
    """El ataque que motiva todo esto: mover la emergencia a otro barrio."""
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte(lat=4.6097, lon=-74.0817).a_dict())

    carga_alterada = dict(sobre.carga)
    carga_alterada["ubicacion"] = {"type": "Point", "coordinates": [-75.5, 6.2]}
    alterado = replace(sobre, carga=carga_alterada)

    assert verificar_sobre(alterado) is False


def test_retransmisor_que_infla_victimas_es_rechazado():
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte().a_dict())
    carga = dict(sobre.carga) | {"personas_afectadas": 900}
    assert verificar_sobre(replace(sobre, carga=carga)) is False


def test_retransmisor_no_puede_inflar_el_ttl():
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte().a_dict(), ttl=8)
    assert verificar_sobre(replace(sobre, ttl=999)) is False


def test_retransmitir_no_invalida_la_firma():
    """Saltos y ruta cambian en cada salto y por eso quedan fuera de la firma."""
    identidad = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(identidad, reporte().a_dict())
    tres_saltos = sobre.avanzar("nodo-a").avanzar("nodo-b").avanzar("nodo-c")
    assert tres_saltos.saltos == 3
    assert verificar_sobre(tres_saltos) is True


def test_suplantar_el_id_de_origen_es_rechazado():
    """La clave pública tiene que corresponder al nodo_origen declarado."""
    intrusa = IdentidadNodo.generar()
    sobre = crear_sobre_firmado(intrusa, reporte().a_dict())
    suplantado = replace(sobre, nodo_origen="autoridad-oficial")
    assert verificar_sobre(suplantado) is False


def test_firma_basura_no_lanza():
    assert verificar_firma("no-es-hex", "tampoco", b"contenido") is False


def test_identidad_persiste_entre_arranques(tmp_path):
    ruta = tmp_path / "malla" / "identidad.key"
    primera = cargar_o_crear_identidad(ruta)
    segunda = cargar_o_crear_identidad(ruta)
    assert primera.id_nodo == segunda.id_nodo
    assert primera.clave_publica == segunda.clave_publica
    assert ruta.stat().st_mode & 0o777 == 0o600


def test_identidad_corrupta_falla_explicitamente(tmp_path):
    ruta = tmp_path / "identidad.key"
    ruta.write_text("esto no es una clave", encoding="utf-8")
    with pytest.raises(IdentidadInvalidaError):
        cargar_o_crear_identidad(ruta)


def test_id_de_nodo_se_deriva_de_la_clave():
    identidad = IdentidadNodo.generar()
    reconstruida = IdentidadNodo._desde_privada(identidad._privada)
    assert reconstruida.id_nodo == identidad.id_nodo
