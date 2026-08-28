"""Tests de los clientes LLM concretos, sustituyendo los SDK por módulos falsos."""

import sys
import types
from types import SimpleNamespace

import pytest

from agente_logistica.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek


@pytest.mark.asyncio
async def test_cliente_anthropic(monkeypatch):
    captured = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(text="hola-anthropic")])

    class FakeAsyncAnthropic:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        messages = FakeMessages()

    mod = types.ModuleType("anthropic")
    mod.AsyncAnthropic = FakeAsyncAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", mod)

    cliente = ClienteAnthropic(api_key="k", model="m", max_tokens=10)
    salida = await cliente.completar("sys", "usr")

    assert salida == "hola-anthropic"
    assert captured["init"]["api_key"] == "k"
    assert captured["model"] == "m"
    assert captured["system"] == "sys"
    assert captured["messages"] == [{"role": "user", "content": "usr"}]


@pytest.mark.asyncio
async def test_cliente_deepseek(monkeypatch):
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="hola-deepseek"))]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        chat = FakeChat()

    mod = types.ModuleType("openai")
    mod.AsyncOpenAI = FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", mod)

    cliente = ClienteDeepSeek(api_key="k", model="deepseek-chat", max_tokens=20)
    salida = await cliente.completar("sys", "usr")

    assert salida == "hola-deepseek"
    assert captured["init"]["api_key"] == "k"
    assert captured["init"]["base_url"] == "https://api.deepseek.com"
    assert captured["model"] == "deepseek-chat"
    assert captured["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
