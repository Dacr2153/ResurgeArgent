"""Tests del orquestador LLM del Agente 8 con un cliente falso."""

import pytest

from agente_logistica.adaptadores.llm.orquestador_llm import OrquestadorLLM


class FakeCliente:
    def __init__(self, respuesta: str):
        self._respuesta = respuesta
        self.llamadas: list[tuple[str, str]] = []

    async def completar(self, system: str, user: str) -> str:
        self.llamadas.append((system, user))
        return self._respuesta


PLAN = {"plan_id": "PLAN_001", "operaciones": []}


@pytest.mark.asyncio
async def test_normalizar_con_json_valido():
    cliente = FakeCliente('{"asignaciones": []}')
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.normalizar({"x": 1})

    assert resultado == {"asignaciones": []}
    assert cliente.llamadas[0][0] == "prompt"


@pytest.mark.asyncio
async def test_normalizar_extrae_json_con_fences_markdown():
    cliente = FakeCliente('```json\n{"vehiculos": []}\n```')
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.normalizar({})

    assert resultado == {"vehiculos": []}


@pytest.mark.asyncio
async def test_normalizar_falla_a_passthrough_si_no_es_json():
    crudo = {"asignaciones": [{"id": "A001"}]}
    cliente = FakeCliente("lo siento, no puedo responder en JSON")
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.normalizar(crudo)

    assert resultado is crudo


@pytest.mark.asyncio
async def test_explicar_enriquece_el_plan():
    cliente = FakeCliente('{"operaciones": [], "justificaciones": ["ok"], "supuestos": []}')
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.explicar(PLAN, {})

    assert resultado["justificaciones"] == ["ok"]
    assert "operaciones" in resultado


@pytest.mark.asyncio
async def test_explicar_falla_a_passthrough_si_no_es_json():
    cliente = FakeCliente("no es json")
    orquestador = OrquestadorLLM(cliente, "prompt")

    resultado = await orquestador.explicar(PLAN, {})

    assert resultado["operaciones"] == []
    assert resultado["supuestos"] == []
    assert resultado["justificaciones"] == []
