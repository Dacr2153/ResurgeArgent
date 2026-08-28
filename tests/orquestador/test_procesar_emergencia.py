"""Tests del caso de uso completo con dobles de los puertos de `nucleo`."""

from __future__ import annotations

import pytest

from agente_orquestador.adaptadores.llm.resumidor_nulo import ResumidorNulo
from agente_orquestador.adaptadores.salida.publicador_log import PublicadorLog
from agente_orquestador.adaptadores.salida.repositorio_memoria import (
    RepositorioOperacionesMemoria,
)
from agente_orquestador.aplicacion.casos_uso.procesar_emergencia import ProcesarEmergencia
from agente_orquestador.aplicacion.casos_uso.registrar_decision_humana import (
    RegistrarDecisionHumana,
)
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.excepciones import (
    IncidenteDesconocidoError,
    TransicionInvalidaError,
)
from agente_orquestador.dominio.motor_triage import MotorTriage
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import Severidad, Urgencia
from nucleo.mensajes import TipoEvento
from tests.orquestador.dobles import (
    BOGOTA,
    GeoespacialFake,
    GeoespacialMudo,
    IngestaFake,
    IngestaQueFalla,
    VerificacionFake,
    VerificacionQueFalla,
    hacer_incidente,
    hacer_reporte,
)


def construir(ingesta=None, verificacion=None, geoespacial=None, origen=BOGOTA, **kwargs):
    auditoria = AuditoriaMemoria()
    repositorio = RepositorioOperacionesMemoria()
    caso = ProcesarEmergencia(
        ingesta=ingesta or IngestaFake(),
        verificacion=verificacion or VerificacionFake(),
        geoespacial=geoespacial or GeoespacialFake(),
        motor=MotorTriage(),
        resumidor=ResumidorNulo(),
        repositorio=repositorio,
        publicador=PublicadorLog(),
        auditoria=auditoria,
        origen_despacho=origen,
        **kwargs,
    )
    return caso, repositorio, auditoria


async def test_flujo_completo_termina_en_pendiente_aprobacion():
    caso, repositorio, auditoria = construir()

    salida = await caso.procesar({"entrada": {"texto": "hay gente atrapada"}})

    assert salida["estado_operacion"] == "pendiente_aprobacion"
    assert salida["degradada"] is False
    assert len(salida["incidentes"]) == 1
    incidente = salida["incidentes"][0]
    assert incidente["estado"] == str(EstadoIncidente.PENDIENTE_APROBACION)
    assert incidente["requiere_firma"] is True
    assert incidente["triage"]["posicion"] == 1
    assert salida["resumen_situacion"]

    operacion = await repositorio.obtener("INC-1")
    assert operacion is not None
    assert operacion.estado is EstadoIncidente.PENDIENTE_APROBACION


async def test_nunca_llega_a_asignado_por_su_cuenta():
    caso, _, _ = construir()
    salida = await caso.procesar({"entrada": {}})
    estados = {i["estado"] for i in salida["incidentes"]}
    assert str(EstadoIncidente.ASIGNADO) not in estados


async def test_el_correlacion_id_hila_todos_los_eventos():
    caso, _, auditoria = construir()

    salida = await caso.procesar({"correlacion_id": "COR-XYZ", "entrada": {}})

    assert salida["correlacion_id"] == "COR-XYZ"
    eventos = auditoria.por_correlacion("COR-XYZ")
    assert len(eventos) == len(auditoria.eventos)
    tipos = {str(e.tipo) for e in eventos}
    assert str(TipoEvento.TRANSICION_ESTADO) in tipos
    assert str(TipoEvento.TAREA_DELEGADA) in tipos


async def test_la_secuencia_de_estados_queda_reconstruible_desde_el_log():
    caso, _, auditoria = construir()
    await caso.procesar({"correlacion_id": "COR-1", "entrada": {}})

    transiciones = [
        e.detalle["estado"] for e in auditoria.por_tipo(TipoEvento.TRANSICION_ESTADO)
    ]
    assert transiciones == [
        str(EstadoIncidente.VERIFICADO),
        str(EstadoIncidente.LOCALIZADO),
        str(EstadoIncidente.PRIORIZADO),
        str(EstadoIncidente.PENDIENTE_APROBACION),
    ]


async def test_el_orden_del_lote_es_el_del_triage():
    incidentes = [
        hacer_incidente("INC-leve", Severidad.MINOR, Urgencia.FUTURE, 0.9, 1),
        hacer_incidente("INC-grave", Severidad.EXTREME, Urgencia.IMMEDIATE, 0.9, 80),
    ]
    caso, _, _ = construir(verificacion=VerificacionFake(incidentes))

    salida = await caso.procesar({"entrada": {}})

    assert [i["incidente_id"] for i in salida["incidentes"]] == ["INC-grave", "INC-leve"]


async def test_agente_geoespacial_mudo_da_respuesta_parcial_sin_excepcion():
    caso, _, auditoria = construir(geoespacial=GeoespacialMudo(demora_s=5), timeout_geo_s=0.01)

    salida = await caso.procesar({"entrada": {}})

    assert salida["degradada"] is True
    assert salida["saga"]["fallidos"] == ["geoespacial"]
    assert salida["estado_operacion"] == "pendiente_aprobacion"
    assert salida["rutas"] == []
    assert salida["incidentes"][0]["datos"]["geo_degradado"] is True
    assert auditoria.por_tipo(TipoEvento.AGENTE_SIN_RESPUESTA)
    assert "no respondieron" in salida["resumen_situacion"]


async def test_fallo_de_verificacion_compensa_la_ingesta():
    caso, _, auditoria = construir(verificacion=VerificacionQueFalla())

    salida = await caso.procesar({"entrada": {}})

    assert salida["saga"]["exitosa"] is False
    assert salida["saga"]["compensados"] == ["ingesta"]
    assert salida["incidentes"] == []
    assert salida["estado_operacion"] == "abortada"
    assert auditoria.por_tipo(TipoEvento.COMPENSACION_EJECUTADA)


async def test_fallo_de_ingesta_no_lanza():
    caso, _, _ = construir(ingesta=IngestaQueFalla())

    salida = await caso.procesar({"entrada": {}})

    assert salida["saga"]["fallidos"] == ["ingesta"]
    assert salida["incidentes"] == []


async def test_se_piden_rutas_solo_con_origen_de_despacho():
    geo = GeoespacialFake()
    caso, _, _ = construir(geoespacial=geo, origen=None)

    salida = await caso.procesar({"entrada": {}})

    assert geo.rutas_pedidas == 0
    assert salida["rutas"] == []
    assert salida["zonas_afectadas"] == {"zonas": ["INC-1"]}


async def test_la_ingesta_recibe_la_carga_cruda():
    verificacion = VerificacionFake()
    ingesta = IngestaFake([hacer_reporte("techo colapsado")])
    caso, _, _ = construir(ingesta=ingesta, verificacion=verificacion)

    await caso.procesar({"entrada": {"canal": "sms", "texto": "x"}})

    assert ingesta.llamadas == 1
    assert [r.texto for r in verificacion.recibidos] == ["techo colapsado"]


# ------------------------------------------------- gate humano de punta a punta
async def test_la_firma_aprobada_asigna_el_incidente():
    caso, repositorio, auditoria = construir()
    await caso.procesar({"entrada": {}})
    registrar = RegistrarDecisionHumana(repositorio, auditoria, PublicadorLog())

    salida = await registrar.registrar(
        {
            "incidente_id": "INC-1",
            "aprobada": True,
            "coordinador_id": "COORD-7",
            "justificacion": "hay ambulancia disponible",
        }
    )

    assert salida["estado"] == str(EstadoIncidente.ASIGNADO)
    assert salida["decision"]["coordinador_id"] == "COORD-7"
    assert auditoria.por_tipo(TipoEvento.DECISION_HUMANA_REGISTRADA)


async def test_la_firma_rechazada_descarta_y_nunca_asigna():
    caso, repositorio, auditoria = construir()
    await caso.procesar({"entrada": {}})
    registrar = RegistrarDecisionHumana(repositorio, auditoria, PublicadorLog())

    salida = await registrar.registrar(
        {
            "incidente_id": "INC-1",
            "aprobada": False,
            "coordinador_id": "COORD-7",
            "justificacion": "duplicado de INC-0",
        }
    )

    assert salida["estado"] == str(EstadoIncidente.DESCARTADO)
    operacion = await repositorio.obtener("INC-1")
    assert operacion.estado is not EstadoIncidente.ASIGNADO


async def test_la_firma_rechazada_puede_suspender_en_vez_de_descartar():
    caso, repositorio, auditoria = construir()
    await caso.procesar({"entrada": {}})
    registrar = RegistrarDecisionHumana(repositorio, auditoria, PublicadorLog())

    salida = await registrar.registrar(
        {
            "incidente_id": "INC-1",
            "aprobada": False,
            "coordinador_id": "COORD-7",
            "justificacion": "faltan datos, se pide confirmación",
            "suspender": True,
        }
    )

    assert salida["estado"] == str(EstadoIncidente.SUSPENDIDO)


async def test_no_se_puede_volver_a_firmar_lo_ya_asignado():
    """La firma se consume: ASIGNADO ya no acepta otra aprobación."""
    caso, repositorio, auditoria = construir()
    await caso.procesar({"entrada": {}})
    registrar = RegistrarDecisionHumana(repositorio, auditoria, PublicadorLog())
    firma = {
        "incidente_id": "INC-1",
        "aprobada": True,
        "coordinador_id": "COORD-7",
        "justificacion": "ok",
    }
    await registrar.registrar(firma)

    with pytest.raises(TransicionInvalidaError):
        await registrar.registrar(firma)


async def test_firmar_un_incidente_desconocido_falla():
    _, repositorio, auditoria = construir()
    registrar = RegistrarDecisionHumana(repositorio, auditoria, PublicadorLog())

    with pytest.raises(IncidenteDesconocidoError):
        await registrar.registrar(
            {
                "incidente_id": "INC-404",
                "aprobada": True,
                "coordinador_id": "C",
                "justificacion": "",
            }
        )
