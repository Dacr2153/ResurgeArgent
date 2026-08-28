"""Pruebas del sobre de mensajes y la auditoría."""

import json

from nucleo.auditoria import AuditoriaJSONL, AuditoriaMemoria
from nucleo.mensajes import (
    Agente,
    EventoAuditoria,
    Mensaje,
    Performativa,
    TipoEvento,
    nuevo_id,
)


def _cfp() -> Mensaje:
    return Mensaje(
        emisor=Agente.ORQUESTADOR,
        receptor=Agente.GEOESPACIAL,
        performativa=Performativa.CFP,
        contenido={"incidente": "i-1"},
        correlacion_id="corr-1",
    )


def test_responder_conserva_el_hilo_de_correlacion():
    respuesta = _cfp().responder(Performativa.PROPOSE, {"eta_min": 12})
    assert respuesta.correlacion_id == "corr-1"


def test_responder_invierte_emisor_y_receptor():
    original = _cfp()
    respuesta = original.responder(Performativa.PROPOSE, {})
    assert respuesta.emisor == original.receptor
    assert respuesta.receptor == original.emisor


def test_responder_encadena_con_responde_a():
    original = _cfp()
    assert original.responder(Performativa.REFUSE, {}).responde_a == original.id


def test_cada_mensaje_tiene_id_unico():
    assert _cfp().id != _cfp().id


def test_mensaje_serializa_performativa_fipa():
    d = _cfp().a_dict()
    assert d["performativa"] == "cfp"
    assert d["emisor"] == "agente-1-orquestador"
    assert d["version"] == "1.0"


async def test_auditoria_memoria_filtra_por_tipo_y_correlacion():
    auditoria = AuditoriaMemoria()
    await auditoria.registrar(
        EventoAuditoria(
            tipo=TipoEvento.REPORTE_RECIBIDO,
            agente=Agente.INGESTA,
            correlacion_id="corr-1",
            detalle={},
        )
    )
    await auditoria.registrar(
        EventoAuditoria(
            tipo=TipoEvento.TRANSICION_ESTADO,
            agente=Agente.ORQUESTADOR,
            correlacion_id="corr-2",
            detalle={},
        )
    )
    assert len(auditoria.eventos) == 2
    assert len(auditoria.por_tipo("reporte_recibido")) == 1
    assert len(auditoria.por_correlacion("corr-2")) == 1


async def test_auditoria_jsonl_escribe_una_linea_por_evento(tmp_path):
    ruta = tmp_path / "cache" / "auditoria.jsonl"
    auditoria = AuditoriaJSONL(ruta)
    for n in range(3):
        await auditoria.registrar(
            EventoAuditoria(
                tipo=TipoEvento.REPORTE_RECIBIDO,
                agente=Agente.INGESTA,
                correlacion_id=nuevo_id(),
                detalle={"n": n},
            )
        )
    lineas = ruta.read_text(encoding="utf-8").strip().split("\n")
    assert len(lineas) == 3
    assert json.loads(lineas[0])["tipo"] == "reporte_recibido"
    assert auditoria.leer()[2]["detalle"]["n"] == 2


async def test_auditoria_jsonl_es_append_only(tmp_path):
    ruta = tmp_path / "auditoria.jsonl"
    primera = AuditoriaJSONL(ruta)
    await primera.registrar(
        EventoAuditoria(
            tipo=TipoEvento.ERROR, agente=Agente.INGESTA, correlacion_id="c", detalle={}
        )
    )
    segunda = AuditoriaJSONL(ruta)
    await segunda.registrar(
        EventoAuditoria(
            tipo=TipoEvento.ERROR, agente=Agente.INGESTA, correlacion_id="c", detalle={}
        )
    )
    assert len(segunda.leer()) == 2


def test_auditoria_jsonl_vacia_devuelve_lista_vacia(tmp_path):
    assert AuditoriaJSONL(tmp_path / "no-existe.jsonl").leer() == []
