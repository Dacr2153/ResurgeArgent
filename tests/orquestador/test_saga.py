"""Tests de la saga: compensación en orden inverso y degradación sin excepciones."""

from __future__ import annotations

import asyncio

from agente_orquestador.dominio.saga import EstadoPaso, PasoSaga, Saga
from nucleo.auditoria import AuditoriaMemoria
from nucleo.mensajes import Agente, TipoEvento


class Diario:
    """Registra en qué orden se ejecutó y se compensó cada paso."""

    def __init__(self) -> None:
        self.ejecutados: list[str] = []
        self.compensados: list[str] = []

    def paso(self, nombre: str, falla: bool = False, **kwargs) -> PasoSaga:
        async def accion():
            self.ejecutados.append(nombre)
            if falla:
                raise RuntimeError(f"{nombre} reventó")
            return f"resultado-{nombre}"

        async def compensar():
            self.compensados.append(nombre)

        return PasoSaga(
            nombre=nombre,
            agente=Agente.INGESTA,
            accion=accion,
            accion_compensatoria=compensar,
            **kwargs,
        )


async def test_saga_feliz_ejecuta_todo_y_no_compensa():
    diario = Diario()
    auditoria = AuditoriaMemoria()
    saga = Saga("COR-1", [diario.paso("p1"), diario.paso("p2")], auditoria)

    resultado = await saga.ejecutar()

    assert resultado.exitosa and not resultado.parcial
    assert diario.ejecutados == ["p1", "p2"]
    assert diario.compensados == []
    assert resultado.resultados == {"p1": "resultado-p1", "p2": "resultado-p2"}
    assert len(auditoria.por_tipo(TipoEvento.TAREA_DELEGADA)) == 2


async def test_falla_el_paso_3_de_4_y_compensa_en_orden_inverso():
    diario = Diario()
    auditoria = AuditoriaMemoria()
    pasos = [
        diario.paso("p1"),
        diario.paso("p2"),
        diario.paso("p3", falla=True),
        diario.paso("p4"),
    ]

    resultado = await Saga("COR-1", pasos, auditoria).ejecutar()

    assert resultado.exitosa is False
    assert diario.ejecutados == ["p1", "p2", "p3"], "p4 no debe ejecutarse tras el fallo"
    assert diario.compensados == ["p2", "p1"], "la compensación va del último al primero"
    assert resultado.compensados == ("p2", "p1")
    assert resultado.fallidos == ("p3",)
    assert [p.estado for p in pasos] == [
        EstadoPaso.COMPENSADO,
        EstadoPaso.COMPENSADO,
        EstadoPaso.FALLIDO,
        EstadoPaso.PENDIENTE,
    ]
    compensaciones = auditoria.por_tipo(TipoEvento.COMPENSACION_EJECUTADA)
    assert [e.detalle["paso"] for e in compensaciones] == ["p2", "p1"]


async def test_agente_que_no_responde_produce_respuesta_parcial_sin_excepcion():
    auditoria = AuditoriaMemoria()

    async def cuelga():
        await asyncio.sleep(10)

    async def rapido():
        return "ok"

    pasos = [
        PasoSaga(nombre="rapido", agente=Agente.INGESTA, accion=rapido),
        PasoSaga(
            nombre="mudo",
            agente=Agente.GEOESPACIAL,
            accion=cuelga,
            obligatorio=False,
            timeout_s=0.01,
        ),
        PasoSaga(nombre="siguiente", agente=Agente.MATCHING, accion=rapido),
    ]

    resultado = await Saga("COR-1", pasos, auditoria).ejecutar()

    assert resultado.exitosa is True, "un paso opcional no aborta la saga"
    assert resultado.parcial is True
    assert resultado.degradada is True
    assert resultado.fallidos == ("mudo",)
    assert resultado.resultados == {"rapido": "ok", "siguiente": "ok"}
    sin_respuesta = auditoria.por_tipo(TipoEvento.AGENTE_SIN_RESPUESTA)
    assert len(sin_respuesta) == 1
    assert sin_respuesta[0].detalle["agente"] == str(Agente.GEOESPACIAL)


async def test_timeout_de_paso_obligatorio_compensa_y_aborta():
    diario = Diario()

    async def cuelga():
        await asyncio.sleep(10)

    pasos = [
        diario.paso("p1"),
        PasoSaga(
            nombre="lento",
            agente=Agente.VERIFICACION,
            accion=cuelga,
            obligatorio=True,
            timeout_s=0.01,
        ),
    ]
    resultado = await Saga("COR-1", pasos).ejecutar()

    assert resultado.exitosa is False
    assert diario.compensados == ["p1"]
    assert "sin respuesta" in pasos[1].error


async def test_un_paso_sin_compensacion_simplemente_se_salta():
    diario = Diario()
    sin_deshacer = diario.paso("p1")
    sin_deshacer.accion_compensatoria = None
    pasos = [sin_deshacer, diario.paso("p2"), diario.paso("p3", falla=True)]

    resultado = await Saga("COR-1", pasos).ejecutar()

    assert resultado.compensados == ("p2",)
    assert sin_deshacer.estado is EstadoPaso.COMPLETADO


async def test_una_compensacion_que_falla_no_detiene_a_las_demas():
    diario = Diario()

    async def compensacion_rota():
        raise RuntimeError("no se pudo deshacer")

    p1 = diario.paso("p1")
    p2 = diario.paso("p2")
    p2.accion_compensatoria = compensacion_rota
    auditoria = AuditoriaMemoria()

    resultado = await Saga("COR-1", [p1, p2, diario.paso("p3", falla=True)], auditoria).ejecutar()

    assert resultado.compensados == ("p1",)
    assert diario.compensados == ["p1"]
    errores = auditoria.por_tipo(TipoEvento.ERROR)
    assert any(e.detalle.get("fase") == "compensacion" for e in errores)
