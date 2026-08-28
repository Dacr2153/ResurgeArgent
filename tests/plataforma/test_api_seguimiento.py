"""El recorrido de un reporte sale del estado real de su operación."""

from __future__ import annotations

from agente_orquestador.dominio.estados import EstadoIncidente
from nucleo.esquemas import DecisionHumana
from tests.plataforma.conftest import operacion_priorizada


async def test_reporte_desconocido_es_404(client):
    assert client.get("/reportes/INC-NO-EXISTE").status_code == 404


async def test_recorrido_marca_hecho_solo_lo_ocurrido(client, operaciones):
    await operaciones.guardar(operacion_priorizada())

    cuerpo = client.get("/reportes/INC-2481").json()

    assert cuerpo["id"] == "INC-2481"
    assert cuerpo["title"] == "Incendio · Jr. Camaná 654"
    assert cuerpo["score"] == 92
    hechos = [(p["label"], p["done"]) for p in cuerpo["steps"]]
    assert hechos == [
        ("Reporte recibido", True),
        ("Verificado", True),
        ("Priorizado · CRÍTICO 92", True),
        ("Brigada asignada", False),
        ("Atendido", False),
    ]


async def test_meta_de_un_paso_pendiente_no_se_inventa(client, operaciones):
    await operaciones.guardar(operacion_priorizada())

    pasos = client.get("/reportes/INC-2481").json()["steps"]

    assert pasos[-1]["meta"] == "pendiente"
    assert "corroborado por 2 reporte(s)" in pasos[1]["meta"]


async def test_la_asignacion_genera_un_aviso_sin_leer(client, operaciones):
    operacion = operacion_priorizada()
    decision = DecisionHumana(
        incidente_id="INC-2481",
        aprobada=True,
        coordinador_id="coord-1",
        justificacion="brigada disponible",
    )
    operacion.transicionar(EstadoIncidente.ASIGNADO, decision=decision, motivo="Ana Q.")
    await operaciones.guardar(operacion)

    cuerpo = client.get("/reportes/INC-2481").json()

    assert cuerpo["unreadMessages"] == 1
    assert cuerpo["steps"][3]["done"] is True
