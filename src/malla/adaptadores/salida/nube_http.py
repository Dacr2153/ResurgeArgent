"""Salida a internet: subir el lote acumulado al Orquestador.

Solo el nodo que tiene señal usa esto. Los demás lo tienen configurado igual y
`disponible()` les responde que no, que es justamente lo que hace que el sobre
siga saltando en vez de quedarse esperando una conexión que no existe.
"""

from __future__ import annotations

import asyncio
import urllib.error

from malla.adaptadores.salida.transporte_http import peticion_get, peticion_post
from malla.dominio.sobre import SobreMalla

TIMEOUT_SEGUNDOS = 10.0


class NubeHTTP:
    """Cliente del Orquestador."""

    def __init__(
        self,
        url_base: str,
        ruta_subida: str = "/emergencias",
        timeout: float = TIMEOUT_SEGUNDOS,
    ) -> None:
        self._base = url_base.rstrip("/")
        self._ruta = ruta_subida
        self._timeout = timeout

    async def disponible(self) -> bool:
        """Un `/health` que responde es la definición operativa de "hay salida"."""
        try:
            estado, _ = await asyncio.to_thread(peticion_get, f"{self._base}/health", self._timeout)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError):
            return False
        return 200 <= estado < 300

    async def subir(self, sobres: list[SobreMalla]) -> list[str]:
        """Sube las cargas y devuelve los ids que la nube aceptó.

        Se sube sobre a sobre y no en bloque: si la conexión se corta a la mitad,
        lo que ya subió queda acusado y no se reenvía. Un lote atómico obligaría
        a repetirlo entero con una señal que apenas aguanta.
        """
        aceptados: list[str] = []
        for sobre in sobres:
            try:
                estado, _ = await asyncio.to_thread(
                    peticion_post,
                    f"{self._base}{self._ruta}",
                    self._cuerpo(sobre),
                    self._timeout,
                )
            except (urllib.error.URLError, OSError, ValueError, TimeoutError):
                break  # se cayó la señal: lo que falta queda pendiente
            if 200 <= estado < 300:
                aceptados.append(sobre.id_mensaje)
        return aceptados

    def _cuerpo(self, sobre: SobreMalla) -> dict:
        """La carga se manda con su procedencia de malla.

        El Orquestador necesita saber que el reporte llegó por la malla y por qué
        ruta: es información de auditoría que no se puede reconstruir después.
        """
        return {
            **sobre.carga,
            "malla": {
                "id_mensaje": sobre.id_mensaje,
                "nodo_origen": sobre.nodo_origen,
                "saltos": sobre.saltos,
                "ruta": list(sobre.ruta),
            },
        }
