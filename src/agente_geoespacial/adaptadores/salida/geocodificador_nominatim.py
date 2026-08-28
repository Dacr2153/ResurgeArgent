"""Geocodificación de direcciones en texto libre contra Nominatim (OpenStreetMap).

Cumple ``GeocodificadorPort``. Existe para el formulario de reporte del
frontend: alguien escribe "Calle 45 # 12-30, Bogotá" a mano y esto lo convierte
en un ``Punto`` que el resto del sistema (``ConsultaGeo.origen``/``destino``)
entiende.

Nominatim es gratuito y sin clave, pero su política de uso
(https://operations.osmfoundation.org/policies/nominatim/) **exige** dos cosas
que aquí se implementan de verdad, no como comentario:

- Un ``User-Agent`` propio que identifique la aplicación (``USER_AGENT_DEFECTO``
  abajo). Sin él, Nominatim puede rechazar la petición.
- Máximo una petición por segundo. ``LimitadorRitmo`` lo aplica esperando lo
  que haga falta antes de cada llamada — no es un límite de "buenas
  intenciones", incumplirlo hace que bloqueen la IP de origen (que en este
  caso sería la del propio despliegue, compartida por todas las peticiones de
  emergencia que pasen por este agente).
"""

from __future__ import annotations

import asyncio
import logging
import time

# Ver ruteo_osrm.py: este entorno publica el cliente HTTP como ``httpx2``.
import httpx2 as httpx

from nucleo.geo import GeometriaInvalidaError, Punto

logger = logging.getLogger("agente_geoespacial.geocodificador_nominatim")

URL_BASE_DEFECTO = "https://nominatim.openstreetmap.org/search"
TIMEOUT_SEG_DEFECTO = 5.0

# Identifica la aplicación ante Nominatim, como exige su política de uso. Un
# User-Agent genérico de librería HTTP (o ausente) es motivo de bloqueo de IP.
USER_AGENT_DEFECTO = "ResurgeAgent-Agente5-Geoespacial/0.1 (hackaton INVIMA; sin contacto publico)"

MIN_INTERVALO_SEG_DEFECTO = 1.0


class LimitadorRitmo:
    """Fuerza un intervalo mínimo entre llamadas consecutivas.

    Async-safe con un ``asyncio.Lock``: si dos corrutinas llaman a la vez, la
    segunda espera a que la primera termine de esperar, no que ambas midan el
    mismo "tiempo transcurrido" y crean que ya pueden pasar.
    """

    def __init__(self, min_intervalo_seg: float = MIN_INTERVALO_SEG_DEFECTO) -> None:
        self._min_intervalo_seg = min_intervalo_seg
        self._ultima_llamada: float | None = None
        self._lock = asyncio.Lock()

    async def esperar(self) -> None:
        async with self._lock:
            ahora = time.monotonic()
            if self._ultima_llamada is not None:
                transcurrido = ahora - self._ultima_llamada
                faltante = self._min_intervalo_seg - transcurrido
                if faltante > 0:
                    await asyncio.sleep(faltante)
            self._ultima_llamada = time.monotonic()


class GeocodificadorNominatim:
    def __init__(
        self,
        cliente: httpx.AsyncClient | None = None,
        url_base: str = URL_BASE_DEFECTO,
        timeout_seg: float = TIMEOUT_SEG_DEFECTO,
        user_agent: str = USER_AGENT_DEFECTO,
        limitador: LimitadorRitmo | None = None,
    ) -> None:
        self._cliente_propio = cliente is None
        self._cliente = cliente or httpx.AsyncClient()
        self._url_base = url_base
        self._timeout_seg = timeout_seg
        self._user_agent = user_agent
        self._limitador = limitador or LimitadorRitmo()

    async def geocodificar(self, direccion: str) -> Punto | None:
        direccion = direccion.strip()
        if not direccion:
            return None

        await self._limitador.esperar()

        try:
            respuesta = await self._cliente.get(
                self._url_base,
                params={"q": direccion, "format": "jsonv2", "limit": 1},
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout_seg,
            )
            respuesta.raise_for_status()
            resultados = respuesta.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Igual que RuteadorOSRM: cualquier falla de este servicio público
            # devuelve None en vez de propagar. El formulario del frontend
            # interpreta None como "no encontrado", no como error 500.
            logger.warning("Nominatim no respondió de forma utilizable: %s", exc)
            return None

        if not resultados:
            return None

        primero = resultados[0]
        try:
            return Punto(lat=float(primero["lat"]), lon=float(primero["lon"]))
        except (KeyError, TypeError, ValueError, GeometriaInvalidaError) as exc:
            logger.warning("Respuesta de Nominatim sin lat/lon utilizable: %s", exc)
            return None

    async def cerrar(self) -> None:
        if self._cliente_propio:
            await self._cliente.aclose()
