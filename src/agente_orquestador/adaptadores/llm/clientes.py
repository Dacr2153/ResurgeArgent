"""Clientes LLM concretos detrás de una interfaz común (``ClienteLLM``).

Cada cliente envuelve un SDK y expone un único ``completar(system, user) -> str``.
Los imports son perezosos para no obligar a instalar ambos SDK. Ningún cliente se
construye si no hay API key: el modo por defecto del agente es sin red.
"""

from __future__ import annotations

from typing import Protocol


class ClienteLLM(Protocol):
    async def completar(self, system: str, user: str) -> str:
        """Devuelve el texto de la respuesta del modelo."""
        ...


class ClienteAnthropic:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        from anthropic import AsyncAnthropic

        self._cliente = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def completar(self, system: str, user: str) -> str:
        respuesta = await self._cliente.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return respuesta.content[0].text


class ClienteDeepSeek:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        base_url: str = "https://api.deepseek.com",
    ):
        from openai import AsyncOpenAI

        self._cliente = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._max_tokens = max_tokens

    async def completar(self, system: str, user: str) -> str:
        respuesta = await self._cliente.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return respuesta.choices[0].message.content
