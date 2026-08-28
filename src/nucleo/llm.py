"""Cliente de Gemini, compartido por los cuatro agentes.

Vive en el núcleo, y no repetido en cada agente, porque es infraestructura sin
criterio propio: no decide nada, solo habla con un servicio. Los cuatro agentes
lo consumen a través de su `ClienteLLM`, que es el contrato que cada uno declara.

Sin SDK ni dependencias nuevas: la API de Gemini es HTTP con JSON, y este repo ya
resuelve así en `check_keys.py`. Se usa `urllib` de la biblioteca estándar dentro
de `asyncio.to_thread`, porque la llamada es bloqueante y el resto del sistema es
asíncrono: hacerla en el hilo del bucle de eventos congelaría al Orquestador
mientras espera al modelo.

Tres cosas aprendidas contra la API real, y que este cliente contempla:

1. Los modelos `gemini-2.5-*` ya no se sirven a claves nuevas. El modelo por
   defecto es `gemini-3.6-flash`.
2. Los modelos de la generación 3 gastan tokens **razonando** antes de responder.
   Con un presupuesto corto agotan el límite pensando y devuelven una respuesta
   sin `parts`, con `finishReason: MAX_TOKENS`. Un cliente que asuma
   `parts[0].text` revienta justo ahí, y con datos reales es lo que más pasa.
3. Un prompt trivial costó 249 tokens. El coste está en el razonamiento, no en
   el texto devuelto, así que el presupuesto no puede ajustarse a ojo por el
   tamaño de la respuesta esperada.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODELO_POR_DEFECTO = "gemini-3.6-flash"
TIMEOUT_S = 60.0

# Codigos que significan "vuelve a intentarlo", no "esto esta mal". El 503 lo
# devuelve Gemini cuando el modelo esta saturado, y es frecuente en horas punta;
# el 429 es la cuota por minuto. Rendirse al primero desperdicia una peticion
# que habria funcionado un segundo despues.
# El 429 NO se reintenta: en el nivel gratuito significa cuota agotada, y
# reintentar solo consume mas peticiones del mismo cupo. Se aprendio gastando el
# cupo diario de un proyecto con tres reintentos por llamada.
CODIGOS_TRANSITORIOS = frozenset({500, 502, 503, 504})
REINTENTOS = 2
ESPERA_BASE_S = 2.0

# Peticiones por minuto que se permite el cliente. El nivel gratuito es estrecho
# y una rafaga agota el cupo antes de que nadie lo note.
MIN_SEGUNDOS_ENTRE_LLAMADAS = 4.0


class ErrorLLM(RuntimeError):
    """El modelo no devolvió una respuesta utilizable."""


class RespuestaTruncadaError(ErrorLLM):
    """El modelo agotó el presupuesto de tokens antes de responder.

    Se distingue del resto de errores porque tiene arreglo conocido: subir
    `max_tokens`. Confundirla con un fallo del servicio lleva a reintentar en
    vano y a gastar créditos sin obtener nada.
    """


class ClienteGemini:
    """Habla con la API de Gemini y devuelve texto plano."""

    def __init__(
        self,
        api_key: str,
        model: str = MODELO_POR_DEFECTO,
        max_tokens: int = 2000,
        temperatura: float = 0.0,
        timeout_s: float = TIMEOUT_S,
    ) -> None:
        if not api_key:
            raise ValueError("ClienteGemini requiere una API key")
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperatura = temperatura
        self._timeout_s = timeout_s
        # Consumo acumulado. Con credito limitado, no poder ver el gasto es
        # descubrirlo cuando ya se agoto.
        self.llamadas = 0
        self.tokens_totales = 0
        self._ultimo_envio = 0.0

    @property
    def identificador_modelo(self) -> str:
        """Para la traza de auditoría: qué modelo produjo cada salida."""
        return f"gemini:{self._model}"

    async def completar(self, system: str, user: str) -> str:
        return await asyncio.to_thread(self._completar_bloqueante, system, user)

    def _completar_bloqueante(self, system: str, user: str) -> str:
        cuerpo: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self._temperatura,
                "maxOutputTokens": self._max_tokens,
                "responseMimeType": "application/json",
            },
        }
        url = f"{BASE}/models/{self._model}:generateContent?key={self._api_key}"
        self._esperar_turno()
        datos = self._pedir_con_reintentos(url, cuerpo)

        uso = datos.get("usageMetadata", {})
        self.llamadas += 1
        self.tokens_totales += int(uso.get("totalTokenCount", 0) or 0)
        return self._extraer_texto(datos)

    def _esperar_turno(self) -> None:
        """Separa las llamadas para no agotar el cupo con una rafaga."""
        desde_la_ultima = time.monotonic() - self._ultimo_envio
        if self._ultimo_envio and desde_la_ultima < MIN_SEGUNDOS_ENTRE_LLAMADAS:
            time.sleep(MIN_SEGUNDOS_ENTRE_LLAMADAS - desde_la_ultima)
        self._ultimo_envio = time.monotonic()

    def _pedir_con_reintentos(self, url: str, cuerpo: dict[str, Any]) -> dict[str, Any]:
        """Una saturacion temporal no puede costar el reporte de una emergencia."""
        ultimo = ""
        for intento in range(REINTENTOS):
            peticion = urllib.request.Request(
                url,
                data=json.dumps(cuerpo).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(peticion, timeout=self._timeout_s) as respuesta:
                    return dict(json.loads(respuesta.read()))
            except urllib.error.HTTPError as error:
                ultimo = f"HTTP {error.code}: {self._mensaje_de_error(error)}"
                if error.code not in CODIGOS_TRANSITORIOS or intento == REINTENTOS - 1:
                    raise ErrorLLM(f"Gemini respondió {ultimo}") from error
            except (urllib.error.URLError, TimeoutError) as error:
                ultimo = str(error)
                if intento == REINTENTOS - 1:
                    raise ErrorLLM(f"Gemini no respondió: {ultimo}") from error
            time.sleep(ESPERA_BASE_S * (2**intento))
        raise ErrorLLM(f"Gemini no respondió tras {REINTENTOS} intentos: {ultimo}")

    @staticmethod
    def _mensaje_de_error(error: urllib.error.HTTPError) -> str:
        try:
            return str(json.loads(error.read()).get("error", {}).get("message", ""))[:200]
        except Exception:  # noqa: BLE001 - el cuerpo del error puede no ser JSON
            return "sin detalle"

    @staticmethod
    def _extraer_texto(datos: dict[str, Any]) -> str:
        candidatos = datos.get("candidates") or []
        if not candidatos:
            bloqueo = datos.get("promptFeedback", {}).get("blockReason")
            raise ErrorLLM(f"Gemini no devolvió candidatos (bloqueo: {bloqueo})")

        candidato = candidatos[0]
        partes = candidato.get("content", {}).get("parts")
        if not partes:
            razon = candidato.get("finishReason", "desconocida")
            if razon == "MAX_TOKENS":
                raise RespuestaTruncadaError(
                    "el modelo agotó el presupuesto de tokens razonando y no llegó a "
                    "responder; sube max_tokens"
                )
            raise ErrorLLM(f"Gemini devolvió una respuesta vacía (finishReason: {razon})")

        return str(partes[0].get("text", "")).strip()


def clave_gemini() -> str:
    """Lee la clave del entorno. Cadena vacía si no está, para caer al modo nulo."""
    return os.environ.get("GEMINI_API_KEY", "").strip()


class ConRespaldo:
    """Delega en el adaptador de LLM y cae al de reglas si el modelo falla.

    Es la contrapartida de la regla que sostiene el diseño: si el LLM nunca
    decide, entonces que el LLM se caiga no puede detener la respuesta a una
    emergencia. Degrada la calidad de la extracción, no la operación.

    Funciona con cualquier pareja de adaptadores porque reenvía el método que le
    pidan: cada agente nombra el suyo distinto (`extraer`, `comparar`,
    `interpretar`, `resumir`) y no hay una interfaz común que compartan.
    """

    def __init__(self, principal: Any, respaldo: Any) -> None:
        self._principal = principal
        self._respaldo = respaldo
        self.degradaciones = 0

    def __getattr__(self, nombre: str) -> Any:
        principal = getattr(self._principal, nombre)
        if not callable(principal):
            return principal

        async def envoltura(*args: Any, **kwargs: Any) -> Any:
            try:
                return await principal(*args, **kwargs)
            except ErrorLLM:
                self.degradaciones += 1
                return await getattr(self._respaldo, nombre)(*args, **kwargs)

        return envoltura


# --------------------------------------------------------------------- Vertex

VERTEX_MODELO_POR_DEFECTO = "gemini-2.5-pro"
VERTEX_REGION_POR_DEFECTO = "us-central1"
# Un token de acceso dura una hora; se renueva antes para no apurar el margen.
VIGENCIA_TOKEN_S = 50 * 60


class ClienteVertex:
    """Gemini a través de Vertex AI, con cuenta de servicio.

    Es un cliente aparte del de AI Studio porque cambian las dos cosas que
    importan: el endpoint lleva proyecto y región, y la autenticación es un token
    OAuth en la cabecera en vez de una clave en la URL. El cuerpo de la petición y
    la forma de la respuesta sí son idénticos, así que el parseo se reutiliza.

    La ruta de Vertex es la que da acceso al nivel de pago: la API de AI Studio
    sirve por cupo gratuito aunque el proyecto tenga facturación vinculada, y ese
    cupo se agota en un puñado de peticiones.

    El token se pide a `gcloud` en vez de usar `google-auth` para no añadir una
    dependencia por algo que la máquina ya tiene resuelto y autenticado.
    """

    def __init__(
        self,
        proyecto: str,
        cuenta_servicio: str = "",
        model: str = VERTEX_MODELO_POR_DEFECTO,
        region: str = VERTEX_REGION_POR_DEFECTO,
        max_tokens: int = 2000,
        temperatura: float = 0.0,
        timeout_s: float = TIMEOUT_S,
    ) -> None:
        if not proyecto:
            raise ValueError("ClienteVertex requiere el id del proyecto")
        self._proyecto = proyecto
        self._cuenta = cuenta_servicio
        self._model = model
        self._region = region
        self._max_tokens = max_tokens
        self._temperatura = temperatura
        self._timeout_s = timeout_s
        self._token = ""
        self._token_hasta = 0.0
        self.llamadas = 0
        self.tokens_totales = 0

    @property
    def identificador_modelo(self) -> str:
        return f"vertex:{self._model}"

    async def completar(self, system: str, user: str) -> str:
        return await asyncio.to_thread(self._completar_bloqueante, system, user)

    def _url(self) -> str:
        host = (
            "aiplatform.googleapis.com"
            if self._region == "global"
            else f"{self._region}-aiplatform.googleapis.com"
        )
        return (
            f"https://{host}/v1/projects/{self._proyecto}/locations/{self._region}"
            f"/publishers/google/models/{self._model}:generateContent"
        )

    def _token_de_acceso(self) -> str:
        if self._token and time.monotonic() < self._token_hasta:
            return self._token
        orden = ["gcloud", "auth", "print-access-token"]
        if self._cuenta:
            orden.append(f"--account={self._cuenta}")
        try:
            salida = subprocess.run(  # noqa: S603 - orden fija, sin entrada del usuario
                orden, capture_output=True, text=True, timeout=60, check=True
            )
        except (subprocess.SubprocessError, OSError) as error:
            raise ErrorLLM(f"no se pudo obtener el token de Vertex: {error}") from error
        self._token = salida.stdout.strip()
        if not self._token:
            raise ErrorLLM("gcloud devolvió un token vacío")
        self._token_hasta = time.monotonic() + VIGENCIA_TOKEN_S
        return self._token

    def _completar_bloqueante(self, system: str, user: str) -> str:
        cuerpo: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self._temperatura,
                "maxOutputTokens": self._max_tokens,
                "responseMimeType": "application/json",
            },
        }
        token = self._token_de_acceso()
        ultimo = ""
        for intento in range(REINTENTOS):
            peticion = urllib.request.Request(
                self._url(),
                data=json.dumps(cuerpo).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            try:
                with urllib.request.urlopen(peticion, timeout=self._timeout_s) as respuesta:
                    datos = json.loads(respuesta.read())
                uso = datos.get("usageMetadata", {})
                self.llamadas += 1
                self.tokens_totales += int(uso.get("totalTokenCount", 0) or 0)
                return ClienteGemini._extraer_texto(datos)
            except urllib.error.HTTPError as error:
                ultimo = f"HTTP {error.code}: {ClienteGemini._mensaje_de_error(error)}"
                if error.code not in CODIGOS_TRANSITORIOS or intento == REINTENTOS - 1:
                    raise ErrorLLM(f"Vertex respondió {ultimo}") from error
            except (urllib.error.URLError, TimeoutError) as error:
                ultimo = str(error)
                if intento == REINTENTOS - 1:
                    raise ErrorLLM(f"Vertex no respondió: {ultimo}") from error
            time.sleep(ESPERA_BASE_S * (2**intento))
        raise ErrorLLM(f"Vertex no respondió tras {REINTENTOS} intentos: {ultimo}")
