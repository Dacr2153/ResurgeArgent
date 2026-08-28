"""Prueba del sistema completo: los cuatro agentes reales, sin dobles.

Cada agente tiene su propia suite y todas pasaban cuando el sistema entero no
funcionaba: la ingesta rechazaba el formato que el resto emite, y los descartes
no llegaban a ninguna parte. Ese hueco solo lo ve una prueba que los conecte de
verdad, y por eso existe esta.

Todo corre sin red: cada agente cae en su adaptador nulo.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agente_geoespacial.config.contenedor import construir_contenedor as construir_geoespacial
from agente_ingesta.config.contenedor import construir_contenedor as construir_ingesta
from agente_orquestador.config.contenedor import construir_contenedor as construir_orquestador
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_verificacion.config.contenedor import construir_contenedor as construir_verificacion
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, RespuestaGeo
from nucleo.mensajes import TipoEvento
from nucleo.puertos import AuditoriaPort

DATOS = Path(__file__).resolve().parents[2] / "datos" / "reportes_demo.json"


class AdaptadorGeoespacial:
    """Une rutas y zonas en un solo interlocutor del `GeoespacialPort`."""

    def __init__(self, auditoria: AuditoriaPort) -> None:
        self._rutas, self._zonas = construir_geoespacial(auditoria=auditoria)

    async def resolver_ruta(
        self, consulta: ConsultaGeo, correlacion_id: str | None = None
    ) -> RespuestaGeo:
        return await self._rutas.ejecutar(consulta, correlacion_id=correlacion_id)

    async def zonas_afectadas(
        self, incidentes: list[IncidenteVerificado], correlacion_id: str | None = None
    ) -> dict:
        return await self._zonas.ejecutar(incidentes)


@pytest.fixture
def reportes() -> list[dict]:
    with DATOS.open(encoding="utf-8") as archivo:
        return json.load(archivo)["reportes"]


@pytest.fixture
def sistema() -> tuple:
    """El sistema entero con una sola traza compartida."""
    auditoria = AuditoriaMemoria()
    contenedor = construir_orquestador(
        ingesta=construir_ingesta(auditoria=auditoria),
        verificacion=construir_verificacion(auditoria=auditoria),
        geoespacial=AdaptadorGeoespacial(auditoria),
        auditoria=auditoria,
    )
    return contenedor, auditoria


async def test_el_lote_completo_produce_dos_incidentes(sistema, reportes):
    """Doce descripciones distintas del mismo derrumbe son un hecho, no doce."""
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})

    assert len(resultado["incidentes"]) == 2, "el derrumbe fusionado y el incendio aparte"


async def test_el_reenvio_exacto_se_descarta_y_queda_registrado(sistema, reportes):
    """Un cero en la cuenta no puede ser silencioso: hay que saber por qué."""
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})

    assert resultado["reportes_ingeridos"] == len(reportes) - 1
    descartes = resultado["reportes_descartados"]
    assert descartes["total"] == 1
    assert "reenvio_duplicado" in descartes["por_motivo"]


async def test_la_operacion_se_detiene_ante_el_gate(sistema, reportes):
    """Ningún incidente llega a ASIGNADO por su cuenta."""
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})

    assert resultado["estado_operacion"] == "pendiente_aprobacion"
    for incidente in resultado["incidentes"]:
        assert incidente["estado"] == EstadoIncidente.PENDIENTE_APROBACION
        assert incidente["requiere_firma"] is True


async def test_la_firma_aprobada_desbloquea_la_asignacion(sistema, reportes):
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})
    objetivo = resultado["incidentes"][0]["incidente_id"]

    firmada = await contenedor.registrar_decision.registrar(
        {
            "incidente_id": objetivo,
            "aprobada": True,
            "coordinador_id": "coord-ungrd-07",
            "justificacion": "Recursos disponibles",
        }
    )

    assert firmada["estado"] == EstadoIncidente.ASIGNADO


async def test_la_firma_rechazada_nunca_asigna(sistema, reportes):
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})
    objetivo = resultado["incidentes"][0]["incidente_id"]

    rechazada = await contenedor.registrar_decision.registrar(
        {
            "incidente_id": objetivo,
            "aprobada": False,
            "coordinador_id": "coord-ungrd-07",
            "justificacion": "No hay maquinaria disponible",
        }
    )

    assert rechazada["estado"] != EstadoIncidente.ASIGNADO


async def test_una_firma_sin_coordinador_se_rechaza(sistema, reportes):
    """La firma identifica a quien responde por la decisión, o no vale."""
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})
    objetivo = resultado["incidentes"][0]["incidente_id"]

    with pytest.raises(ValueError):
        await contenedor.registrar_decision.registrar(
            {
                "incidente_id": objetivo,
                "aprobada": True,
                "coordinador_id": "  ",
                "justificacion": "sin responsable",
            }
        )


async def test_la_traza_reconstruye_la_operacion_completa(sistema, reportes):
    """Un solo hilo de correlación a través de los cuatro agentes.

    Si cada agente acuñara el suyo, el log tendría todos los eventos y aun así
    sería imposible reconstruir qué pasó en una operación concreta.
    """
    contenedor, auditoria = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})

    eventos = auditoria.por_correlacion(resultado["correlacion_id"])
    agentes = {str(evento.agente) for evento in eventos}
    tipos = {evento.tipo for evento in eventos}

    assert "agente-1-orquestador" in agentes
    assert "agente-2-ingesta" in agentes
    assert TipoEvento.REPORTE_DESCARTADO in tipos
    assert TipoEvento.TAREA_DELEGADA in tipos


async def test_el_geoespacial_agrupa_los_incidentes_en_zonas(sistema, reportes):
    """El derrumbe y el incendio están a 8 km: son celdas distintas."""
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})

    celdas = resultado["zonas_afectadas"]["features"]
    assert len(celdas) == 2
    assert all(celda["geometry"]["type"] == "Polygon" for celda in celdas)


async def test_la_saga_completa_los_tres_pasos(sistema, reportes):
    contenedor, _ = sistema
    resultado = await contenedor.procesar.procesar({"reportes": reportes})

    pasos = {paso["nombre"]: paso["estado"] for paso in resultado["saga"]["pasos"]}
    assert pasos == {
        "ingesta": "completado",
        "verificacion": "completado",
        "geoespacial": "completado",
    }
    assert resultado["degradada"] is False


async def test_un_reporte_malformado_no_tumba_el_lote(sistema, reportes):
    """Un solo dato corrupto no puede costar la tanda entera en una emergencia."""
    contenedor, _ = sistema
    corrupto = {**reportes[0], "ubicacion": {"latitud": 4.6, "longitud": -74.0}}

    resultado = await contenedor.procesar.procesar({"reportes": [*reportes, corrupto]})

    assert resultado["reportes_ingeridos"] >= len(reportes) - 1
    assert resultado["reportes_descartados"]["total"] >= 1
