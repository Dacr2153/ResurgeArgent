"""Puertos de salida de la malla (protocolos, no clases base).

`TransportePort` es la decisión de diseño central de este módulo. El dominio no
sabe si el sobre viaja por HTTP en la red local, por WebRTC entre navegadores,
por Bluetooth LE o por Wi-Fi Direct: solo sabe pedir "manda esto a este vecino"
y "dime a quién alcanzas". Eso importa porque el navegador **no puede** hablar
Bluetooth, y la malla real algún día lo va a necesitar desde un envoltorio
nativo. Cuando llegue ese día se escribe un adaptador nuevo y no se toca ni una
línea del motor de propagación.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from malla.dominio.sobre import SobreMalla
from malla.dominio.vecino import Vecino


@dataclass(frozen=True, slots=True)
class RegistroSobre:
    """Un sobre tal como quedó en el almacén local.

    `secuencia` es un contador local monótono, no un reloj: en un desastre los
    relojes de los teléfonos van desincronizados, y un vecino que pregunta "qué
    tienes desde X" necesita una referencia que no dependa de la hora de nadie.
    """

    secuencia: int
    sobre: SobreMalla
    entregado: bool = False


class TransportePort(Protocol):
    """Cómo salen los sobres de este nodo hacia los vecinos."""

    async def enviar(self, sobre: SobreMalla, vecino: Vecino) -> bool:
        """Entrega un sobre a un vecino. `False` si el enlace falló."""
        ...

    async def vecinos(self) -> list[Vecino]:
        """Quién está al alcance ahora mismo."""
        ...


class AlmacenSobresPort(Protocol):
    """Persistencia local de la malla. Debe sobrevivir al cierre de la app."""

    async def guardar(self, sobre: SobreMalla) -> bool:
        """Guarda un sobre nuevo. `False` si el id ya estaba."""
        ...

    async def ids_vistos(self) -> frozenset[str]:
        """Todos los `id_mensaje` conocidos, entregados o no."""
        ...

    async def pendientes(self, limite: int | None = None) -> list[SobreMalla]:
        """Lo que todavía no llegó a la nube."""
        ...

    async def listar_desde(self, secuencia: int, limite: int) -> list[RegistroSobre]:
        """Lo almacenado después de una secuencia dada, para que un vecino sincronice."""
        ...

    async def marcar_entregados(self, ids: list[str]) -> int:
        """Marca como entregados los sobres cuya subida a la nube fue acusada."""
        ...

    async def ultima_secuencia(self) -> int: ...


class NubePort(Protocol):
    """La salida a internet: el Orquestador al otro lado del enlace."""

    async def disponible(self) -> bool:
        """Si este nodo tiene salida ahora mismo. Es lo que lo convierte en pasarela."""
        ...

    async def subir(self, sobres: list[SobreMalla]) -> list[str]:
        """Sube el lote y devuelve los `id_mensaje` efectivamente aceptados."""
        ...
