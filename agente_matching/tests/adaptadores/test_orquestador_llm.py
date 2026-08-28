"""Tests del orquestador LLM genérico con un cliente falso."""

import pytest

from agente_matching.adaptadores.llm.orquestador_llm import OrquestadorLLM


class FakeCliente:
    def __init__(self, respuesta: str):
        self._respuesta = respuesta
        self.llamadas: list[tuple[str, str]] = []

    async def completar(self, system: str, user: str) -> str:
        self.llamadas.append((system, user))
        return self._respuesta


RESULTADO = {"asignaciones": [], "no_cubierto": [], "resumen": {}}


@pytest.mark.asyncio
async def test_normalizar_con_json_valido():
    cliente = FakeCliente('{"necesidades": []}')
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.normalizar({"x": 1})

    assert resultado == {"necesidades": []}
    assert cliente.llamadas[0][0] == "prompt"


@pytest.mark.asyncio
async def test_normalizar_extrae_json_con_fences_markdown():
    cliente = FakeCliente('```json\n{"recursos": []}\n```')
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.normalizar({})

    assert resultado == {"recursos": []}


@pytest.mark.asyncio
async def test_normalizar_falla_a_passthrough_si_no_es_json():
    crudo = {"necesidades": [{"id": "N1"}]}
    cliente = FakeCliente("lo siento, no puedo responder en JSON")
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.normalizar(crudo)

    assert resultado is crudo


@pytest.mark.asyncio
async def test_justificar_enriquece_el_resultado():
    cliente = FakeCliente('{"asignaciones": [], "justificaciones": ["ok"], "supuestos": []}')
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.justificar(RESULTADO, {})

    assert resultado["justificaciones"] == ["ok"]
    assert "asignaciones" in resultado


@pytest.mark.asyncio
async def test_justificar_falla_a_passthrough_si_no_es_json():
    cliente = FakeCliente("no es json")
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.justificar(RESULTADO, {})

    assert resultado["asignaciones"] == []
    assert resultado["supuestos"] == []
    assert resultado["justificaciones"] == []
