"""Puertos de salida (protocolos)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from agente_geoespacial.dominio.entidades import GrafoVial, ResultadoRuta
from nucleo.esquemas import ModoTransporte
from nucleo.geo import Punto


class LLMInterpretePort(Protocol):
    async def interpretar(self, reportes_texto: list[str]) -> list[str]:
        """Lee reportes en español y devuelve los ids de tramo vial bloqueados.

        Solo interpreta lenguaje natural. No decide la ruta ni descarta un tramo
        por su cuenta: esa decisión es del dominio (``MotorRutas``).
        """
        ...


class RepositorioGrafoPort(Protocol):
    async def obtener_grafo(self) -> GrafoVial:
        """Entrega el grafo vial vigente."""
        ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict) -> None:
        """Publica un resultado (cola, log, etc.)."""
        ...


class RuteadorPort(Protocol):
    async def calcular_ruta(
        self,
        origen: Punto,
        destino: Punto,
        modo: ModoTransporte,
        segmentos_bloqueados: Sequence[tuple[Punto, Punto]] = (),
    ) -> ResultadoRuta | None:
        """Calcula una ruta con geometría real de calles, o ``None`` si no pudo.

        ``None`` es la señal de "no hay respuesta confiable" (caída, timeout,
        respuesta vacía o inválida) — nunca una excepción: un servicio público
        sin SLA no puede tumbar la resolución de una ruta de emergencia. Quien
        implemente este puerto (p. ej. ``RuteadorOSRM``) es responsable de
        atrapar sus propios errores de red y devolver ``None`` en su lugar.

        ``segmentos_bloqueados`` son pares (origen, destino) en coordenadas —no
        ids de tramo del grafo interno, que el ruteador externo no conoce— para
        que el adaptador pueda decidir cómo evitarlos sobre la geometría que
        reciba del servicio.
        """
        ...


class GeocodificadorPort(Protocol):
    async def geocodificar(self, direccion: str) -> Punto | None:
        """Convierte una dirección en texto libre a coordenadas, o ``None`` si
        el servicio no encontró nada (o no respondió)."""
        ...
