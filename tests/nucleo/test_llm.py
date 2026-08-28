"""Pruebas del cliente de Gemini, con respuestas reales capturadas de la API.

Ninguna sale a la red: gastar créditos en una suite de pruebas es tirar el
presupuesto de la demostración.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from nucleo.llm import ClienteGemini, ErrorLLM, RespuestaTruncadaError

# Respuesta real de gemini-3.6-flash a un prompt trivial.
RESPUESTA_OK = {
    "candidates": [
        {
            "content": {"parts": [{"text": '{"ok": true}'}], "role": "model"},
            "finishReason": "STOP",
        }
    ],
    "usageMetadata": {"promptTokenCount": 21, "totalTokenCount": 249},
}

# Respuesta real cuando el modelo agota el presupuesto razonando: sin `parts`.
RESPUESTA_TRUNCADA = {
    "candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model"}}],
    "usageMetadata": {"totalTokenCount": 82},
}

RESPUESTA_BLOQUEADA: dict = {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}


class RespuestaFalsa:
    def __init__(self, datos: dict) -> None:
        self._datos = datos

    def read(self) -> bytes:
        return json.dumps(self._datos).encode("utf-8")

    def __enter__(self) -> RespuestaFalsa:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _con_respuesta(monkeypatch, datos: dict) -> list[dict]:
    """Sustituye la llamada HTTP y devuelve la lista de cuerpos enviados."""
    enviados: list[dict] = []

    def falso_urlopen(peticion, timeout=None):  # noqa: ANN001, ARG001
        enviados.append(json.loads(peticion.data))
        return RespuestaFalsa(datos)

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    return enviados


def test_la_clave_vacia_se_rechaza_al_construir():
    """Mejor fallar al arrancar que en mitad de una emergencia."""
    with pytest.raises(ValueError):
        ClienteGemini(api_key="")


async def test_devuelve_el_texto_del_modelo(monkeypatch):
    _con_respuesta(monkeypatch, RESPUESTA_OK)
    cliente = ClienteGemini(api_key="clave-de-prueba")

    assert await cliente.completar("system", "user") == '{"ok": true}'


async def test_envia_system_y_user_por_separado(monkeypatch):
    """Gemini separa la instrucción de sistema del turno del usuario."""
    enviados = _con_respuesta(monkeypatch, RESPUESTA_OK)
    cliente = ClienteGemini(api_key="clave-de-prueba", max_tokens=1234)

    await cliente.completar("eres un extractor", "derrumbe en la via")

    cuerpo = enviados[0]
    assert cuerpo["systemInstruction"]["parts"][0]["text"] == "eres un extractor"
    assert cuerpo["contents"][0]["parts"][0]["text"] == "derrumbe en la via"
    assert cuerpo["generationConfig"]["maxOutputTokens"] == 1234
    assert cuerpo["generationConfig"]["temperature"] == 0.0


async def test_el_presupuesto_agotado_se_distingue_del_resto(monkeypatch):
    """Sin `parts` y con MAX_TOKENS: el modelo razonó hasta quedarse sin cupo.

    Tiene arreglo conocido —subir max_tokens—, así que no puede confundirse con
    un fallo del servicio: reintentar solo gastaría créditos sin obtener nada.
    """
    _con_respuesta(monkeypatch, RESPUESTA_TRUNCADA)
    cliente = ClienteGemini(api_key="clave-de-prueba", max_tokens=64)

    with pytest.raises(RespuestaTruncadaError):
        await cliente.completar("system", "user")


async def test_una_respuesta_bloqueada_es_error_claro(monkeypatch):
    _con_respuesta(monkeypatch, RESPUESTA_BLOQUEADA)
    cliente = ClienteGemini(api_key="clave-de-prueba")

    with pytest.raises(ErrorLLM, match="SAFETY"):
        await cliente.completar("system", "user")


async def test_un_modelo_retirado_da_error_legible(monkeypatch):
    """Los modelos gemini-2.5 dejaron de servirse a claves nuevas."""

    def falso_urlopen(peticion, timeout=None):  # noqa: ANN001, ARG001
        cuerpo = json.dumps(
            {"error": {"code": 404, "message": "This model is no longer available"}}
        ).encode()
        raise urllib.error.HTTPError(
            url="https://x", code=404, msg="Not Found", hdrs=None, fp=_Cuerpo(cuerpo)
        )

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    cliente = ClienteGemini(api_key="clave-de-prueba", model="gemini-2.5-flash")

    with pytest.raises(ErrorLLM, match="404"):
        await cliente.completar("system", "user")


async def test_el_servicio_caido_da_error_de_dominio(monkeypatch):
    def falso_urlopen(peticion, timeout=None):  # noqa: ANN001, ARG001
        raise urllib.error.URLError("sin conexión")

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    cliente = ClienteGemini(api_key="clave-de-prueba")

    with pytest.raises(ErrorLLM, match="no respondió"):
        await cliente.completar("system", "user")


def test_el_identificador_del_modelo_queda_para_la_traza():
    cliente = ClienteGemini(api_key="clave-de-prueba", model="gemini-3.6-flash")

    assert cliente.identificador_modelo == "gemini:gemini-3.6-flash"


class _Cuerpo:
    """Sustituto mínimo del cuerpo de un HTTPError."""

    def __init__(self, datos: bytes) -> None:
        self._datos = datos

    def read(self) -> bytes:
        return self._datos

    def close(self) -> None:
        return None
