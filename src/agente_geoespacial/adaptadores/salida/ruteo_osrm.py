"""Adaptador de ruteo contra el servidor público de OSRM (``router.project-osrm.org``).

Cumple ``RuteadorPort``: a diferencia de ``MotorRutas`` (grafo propio, sin
calles reales), este adaptador devuelve geometría que sigue calles de verdad,
porque OSRM enruta sobre la red completa de OpenStreetMap. El precio es que es
un servicio público, gratuito, sin clave y **sin SLA** — por eso nunca lanza:
cualquier falla (caída, timeout, respuesta rara) se traduce en ``None`` para
que ``ResolverRuta`` caiga al ``MotorRutas`` de respaldo sin que la petición
falle. En una demostración en vivo depender de un servicio ajeno sin plan B
es imprudente.

Limitación documentada de bloqueos
-----------------------------------
El servidor público de OSRM no acepta excluir tramos arbitrarios: la API
``exclude=`` solo funciona para clases de vía predefinidas del perfil (p. ej.
``motorway``), no para un segmento puntual como "esta cuadra está bloqueada
por un derrumbe". No hay forma de pedirle a este servicio "no pases por este
punto exacto".

Lo que hacemos en su lugar es un **desvío por waypoint**: pedimos la ruta
normal, comprobamos (con un umbral de distancia, ``_UMBRAL_INTERSECCION_KM``)
si pasa cerca del punto medio de algún tramo bloqueado, y si es así volvemos a
pedir la ruta forzando un punto intermedio desplazado perpendicularmente al
bloqueo. Esto es una **aproximación heurística**, no una garantía: OSRM sigue
libre de recalcular por donde quiera entre ese punto intermedio y los extremos,
así que puede seguir cruzando el tramo bloqueado si esa sigue siendo la vía más
corta, y el desvío puede alejarse más de lo necesario si el offset cae sobre
una zona sin vías cercanas. Es una restricción real del servicio gratuito, no
una decisión de diseño: un despliegue propio de OSRM (o un motor con soporte
nativo de exclusión, como Valhalla) sí podría excluir el tramo con certeza.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

# El entorno de este repo publica el cliente HTTP como ``httpx2`` (ver
# starlette.testclient, que hace el mismo alias) en vez del paquete ``httpx``
# habitual; el alias deja el resto del módulo idéntico a como se vería con
# ``httpx`` normal.
import httpx2 as httpx

from agente_geoespacial.dominio.entidades import ResultadoRuta, RutaAlternativa
from nucleo.esquemas import ModoTransporte
from nucleo.geo import Punto

logger = logging.getLogger("agente_geoespacial.ruteo_osrm")

URL_BASE_DEFECTO = "https://router.project-osrm.org/route/v1"
TIMEOUT_SEG_DEFECTO = 4.0

_PERFIL_OSRM: dict[ModoTransporte, str] = {
    ModoTransporte.AUTO: "driving",
    ModoTransporte.CAMION: "driving",  # OSRM público no ofrece perfil de camión.
    ModoTransporte.MOTO: "driving",
    ModoTransporte.PEATON: "foot",
}

# 50 m: suficiente para decidir que la ruta "pasa por" el tramo bloqueado sin
# ser tan angosto que un GPS con ruido nunca dispare el desvío.
_UMBRAL_INTERSECCION_KM = 0.05

# Separación del punto de desvío respecto al punto medio del tramo bloqueado,
# en grados (~110 m en latitud a esta escala). Es una heurística: ver docstring
# del módulo sobre por qué no hay garantía de evitar el tramo.
_OFFSET_DESVIO_GRADOS = 0.001


class RuteadorOSRM:
    """Ruteador contra el servidor público de OSRM. Sin clave, sin registro."""

    def __init__(
        self,
        cliente: httpx.AsyncClient | None = None,
        url_base: str = URL_BASE_DEFECTO,
        timeout_seg: float = TIMEOUT_SEG_DEFECTO,
        max_alternativas: int = 1,
    ) -> None:
        self._cliente_propio = cliente is None
        self._cliente = cliente or httpx.AsyncClient()
        self._url_base = url_base.rstrip("/")
        self._timeout_seg = timeout_seg
        self._max_alternativas = max_alternativas

    async def calcular_ruta(
        self,
        origen: Punto,
        destino: Punto,
        modo: ModoTransporte,
        segmentos_bloqueados: Sequence[tuple[Punto, Punto]] = (),
    ) -> ResultadoRuta | None:
        perfil = _PERFIL_OSRM.get(modo, "driving")

        resultado = await self._enrutar(perfil, [origen, destino])
        if resultado is None:
            return None

        if segmentos_bloqueados and _cruza_algun_bloqueo(
            resultado.geometria, segmentos_bloqueados
        ):
            punto_desvio = _punto_desvio(segmentos_bloqueados[0])
            resultado_desviado = await self._enrutar(
                perfil, [origen, punto_desvio, destino]
            )
            if resultado_desviado is not None:
                # ResultadoRuta.vias_evitadas queda vacío a propósito aquí: este
                # adaptador solo conoce coordenadas, no ids de tramo del grafo
                # interno (ver docstring de RuteadorPort). Es ResolverRuta quien
                # sabe qué ids se pidió evitar y los pone en la respuesta final.
                resultado = ResultadoRuta(
                    accesible=resultado_desviado.accesible,
                    distancia_km=resultado_desviado.distancia_km,
                    duracion_min=resultado_desviado.duracion_min,
                    geometria=resultado_desviado.geometria,
                    motivo=(
                        "desvío por waypoint: OSRM público no admite excluir "
                        "tramos arbitrarios, ver README del agente"
                    ),
                    alternativas=resultado_desviado.alternativas,
                )

        return resultado

    async def cerrar(self) -> None:
        if self._cliente_propio:
            await self._cliente.aclose()

    # ------------------------------------------------------------------ privado
    async def _enrutar(self, perfil: str, puntos: list[Punto]) -> ResultadoRuta | None:
        coordenadas = ";".join(f"{p.lon},{p.lat}" for p in puntos)
        url = f"{self._url_base}/{perfil}/{coordenadas}"
        parametros = {
            "overview": "full",
            "geometries": "geojson",
            "alternatives": "true",
        }

        try:
            respuesta = await self._cliente.get(
                url, params=parametros, timeout=self._timeout_seg
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError cubre un cuerpo que no es JSON válido. Cualquier falla
            # de este servicio público sin SLA cae al respaldo, nunca revienta
            # la resolución de la ruta.
            logger.warning("OSRM no respondió de forma utilizable: %s", exc)
            return None

        if datos.get("code") != "Ok":
            logger.warning("OSRM devolvió code=%s", datos.get("code"))
            return None

        rutas = datos.get("routes") or []
        if not rutas:
            return None

        principal, *resto = rutas
        distancia_km, duracion_min, geometria = _leer_ruta(principal)

        alternativas = tuple(
            RutaAlternativa(
                nodos=(),
                distancia_km=d,
                duracion_min=dur,
                geometria=geo,
            )
            for d, dur, geo in (_leer_ruta(r) for r in resto[: self._max_alternativas])
        )

        return ResultadoRuta(
            accesible=True,
            distancia_km=distancia_km,
            duracion_min=duracion_min,
            geometria=geometria,
            alternativas=alternativas,
        )


def _leer_ruta(ruta_osrm: dict) -> tuple[float, float, dict]:
    """OSRM da distancia en metros y duración en segundos; el resto del agente
    trabaja en km y minutos."""
    distancia_km = float(ruta_osrm["distance"]) / 1000.0
    duracion_min = float(ruta_osrm["duration"]) / 60.0
    geometria = ruta_osrm["geometry"]
    return distancia_km, duracion_min, geometria


def _cruza_algun_bloqueo(
    geometria: dict, segmentos_bloqueados: Sequence[tuple[Punto, Punto]]
) -> bool:
    coordenadas = geometria.get("coordinates") or []
    puntos_ruta = [Punto(lat=c[1], lon=c[0]) for c in coordenadas]
    if not puntos_ruta:
        return False

    for origen, destino in segmentos_bloqueados:
        medio = Punto(
            lat=(origen.lat + destino.lat) / 2.0,
            lon=(origen.lon + destino.lon) / 2.0,
        )
        if any(punto.distancia_a(medio) <= _UMBRAL_INTERSECCION_KM for punto in puntos_ruta):
            return True
    return False


def _punto_desvio(segmento_bloqueado: tuple[Punto, Punto]) -> Punto:
    """Punto intermedio desplazado perpendicularmente al tramo bloqueado.

    Heurística simple: desplaza el punto medio del segmento en la dirección
    perpendicular a su recorrido, para forzar a OSRM a pasar por un lado en vez
    del otro. No hay garantía de que el resultado evite el bloqueo (ver
    docstring del módulo).
    """
    origen, destino = segmento_bloqueado
    medio_lat = (origen.lat + destino.lat) / 2.0
    medio_lon = (origen.lon + destino.lon) / 2.0

    dlat = destino.lat - origen.lat
    dlon = destino.lon - origen.lon
    longitud = (dlat**2 + dlon**2) ** 0.5
    if longitud == 0:
        # Segmento degenerado (origen == destino): cualquier desplazamiento sirve.
        return Punto(lat=medio_lat + _OFFSET_DESVIO_GRADOS, lon=medio_lon)

    # Vector perpendicular unitario, escalado al offset.
    perp_lat = -dlon / longitud * _OFFSET_DESVIO_GRADOS
    perp_lon = dlat / longitud * _OFFSET_DESVIO_GRADOS

    lat = max(-90.0, min(90.0, medio_lat + perp_lat))
    lon = max(-180.0, min(180.0, medio_lon + perp_lon))
    return Punto(lat=lat, lon=lon)
