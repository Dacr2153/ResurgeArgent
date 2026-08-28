"""Transporte por HTTP en la red local.

Es el único transporte que se puede demostrar hoy sin aplicación nativa: dos o
más procesos en puertos distintos, o varias máquinas en el mismo Wi-Fi, hablando
`POST /sobres` entre sí. Sirve para probar la lógica de malla completa —flooding,
deduplicación, TTL, almacenar-y-reenviar— sobre una capa que existe.

No es la malla real. La malla real es Bluetooth o Wi-Fi Direct entre teléfonos
sin infraestructura, y eso exige un envoltorio nativo; cuando exista, será otro
adaptador que cumpla este mismo puerto y el dominio no se entera.

Se usa `urllib` de la biblioteca estándar en un hilo aparte en vez de un cliente
HTTP asíncrono: el repositorio no tiene `httpx` instalado y añadir una
dependencia para tres peticiones no se justifica.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import replace

from malla.dominio.sobre import SobreMalla
from malla.dominio.vecino import Vecino

TIMEOUT_SEGUNDOS = 3.0


def peticion_post(url: str, cuerpo: dict, timeout: float) -> tuple[int, dict]:
    datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    peticion = urllib.request.Request(  # noqa: S310 - URL de vecino configurada localmente
        url,
        data=datos,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:  # noqa: S310
        crudo = respuesta.read().decode("utf-8") or "{}"
        return respuesta.status, json.loads(crudo)


def peticion_get(url: str, timeout: float) -> tuple[int, dict]:
    peticion = urllib.request.Request(url, method="GET")  # noqa: S310
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:  # noqa: S310
        crudo = respuesta.read().decode("utf-8") or "{}"
        return respuesta.status, json.loads(crudo)


class TransporteHTTP:
    """Vecinos alcanzables por HTTP en la red local."""

    def __init__(
        self,
        vecinos_configurados: list[Vecino] | None = None,
        timeout: float = TIMEOUT_SEGUNDOS,
        sondear: bool = True,
    ) -> None:
        self._vecinos = list(vecinos_configurados or [])
        self._timeout = timeout
        self._sondear = sondear

    async def enviar(self, sobre: SobreMalla, vecino: Vecino) -> bool:
        """Entrega un sobre. Cualquier fallo de red es `False`, no una excepción.

        Un vecino que se apagó, se alejó o se quedó sin batería es el caso normal
        en una malla, no una condición de error: el sobre sigue pendiente y se
        reintenta en el siguiente barrido.
        """
        url = f"{vecino.direccion.rstrip('/')}/sobres"
        try:
            estado, _ = await asyncio.to_thread(peticion_post, url, sobre.a_dict(), self._timeout)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False
        return 200 <= estado < 300

    async def vecinos(self) -> list[Vecino]:
        """Los vecinos configurados que responden ahora mismo.

        Sondear en cada barrido evita gastar el enlace mandando sobres a un nodo
        que ya no está; si el sondeo se desactiva, se asume que todos están.
        """
        if not self._sondear:
            return list(self._vecinos)

        vivos: list[Vecino] = []
        for vecino in self._vecinos:
            id_real = await self._identificar(vecino)
            if id_real is None:
                continue
            # El id que devuelve el propio nodo sustituye al provisional derivado
            # de la URL: sin el id real, el anti-bucle no puede saber que un sobre
            # ya pasó por ese vecino y se lo devolvería una y otra vez.
            vivos.append(vecino if id_real == vecino.id_nodo else replace(vecino, id_nodo=id_real))
        return vivos

    async def _identificar(self, vecino: Vecino) -> str | None:
        """Pregunta al vecino quién es. `None` si no responde."""
        url = f"{vecino.direccion.rstrip('/')}/nodo"
        try:
            estado, cuerpo = await asyncio.to_thread(peticion_get, url, self._timeout)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return None
        if not 200 <= estado < 300:
            return None
        id_nodo = cuerpo.get("id_nodo")
        return str(id_nodo) if id_nodo else vecino.id_nodo

    def agregar_vecino(self, vecino: Vecino) -> None:
        if all(v.id_nodo != vecino.id_nodo for v in self._vecinos):
            self._vecinos.append(vecino)

    @property
    def configurados(self) -> list[Vecino]:
        return list(self._vecinos)
