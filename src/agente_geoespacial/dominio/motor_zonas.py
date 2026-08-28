"""Motor de zonas: agrupa incidentes en una rejilla geográfica, puro y determinista.

Es el mismo enfoque de indexación por celdas que usa H3 (hexágonos de tamaño
fijo), aquí implementado con un rectángulo de tamaño configurable en grados para
no traer una dependencia externa que el resto del sistema no necesita. La rejilla
es suficiente para el propósito del agente: decirle al Orquestador "estas
celdas concentran incidentes", no producir cartografía de precisión.
"""

from __future__ import annotations

import math
from collections import defaultdict

from agente_geoespacial.dominio.value_objects import CeldaId
from nucleo.esquemas import IncidenteVerificado, Severidad
from nucleo.geo import Punto, validar_geojson

TAMANO_CELDA_GRADOS_DEFECTO = 0.01

# Orden de severidad CAP 1.2 para agregar la más grave de cada celda.
_ORDEN_SEVERIDAD = {
    Severidad.EXTREME: 4,
    Severidad.SEVERE: 3,
    Severidad.MODERATE: 2,
    Severidad.MINOR: 1,
    Severidad.UNKNOWN: 0,
}


class MotorZonas:
    def __init__(self, tamano_celda_grados: float = TAMANO_CELDA_GRADOS_DEFECTO) -> None:
        if tamano_celda_grados <= 0:
            raise ValueError("tamano_celda_grados debe ser positivo")
        self._tamano = tamano_celda_grados

    def agrupar(self, incidentes: list[IncidenteVerificado]) -> dict:
        """Devuelve un FeatureCollection GeoJSON: un polígono por celda con incidentes."""
        if not incidentes:
            return {"type": "FeatureCollection", "features": []}

        por_celda: dict[CeldaId, list[IncidenteVerificado]] = defaultdict(list)
        for incidente in incidentes:
            por_celda[self._celda_de(incidente.ubicacion)].append(incidente)

        features = []
        for celda in sorted(por_celda, key=CeldaId.como_str):
            lista = por_celda[celda]
            poligono = self._poligono_celda(celda)
            validar_geojson(poligono)

            severidad_max = max(lista, key=lambda i: _ORDEN_SEVERIDAD[i.severidad]).severidad
            features.append(
                {
                    "type": "Feature",
                    "geometry": poligono,
                    "properties": {
                        "celda_id": celda.como_str(),
                        "conteo_incidentes": len(lista),
                        "severidad_agregada": str(severidad_max),
                        "incidentes_ids": [i.id for i in lista],
                    },
                }
            )

        return {"type": "FeatureCollection", "features": features}

    # ------------------------------------------------------------------ rejilla
    def _celda_de(self, punto: Punto) -> CeldaId:
        return CeldaId(
            fila=math.floor(punto.lat / self._tamano),
            columna=math.floor(punto.lon / self._tamano),
        )

    def _poligono_celda(self, celda: CeldaId) -> dict:
        lat_min = celda.fila * self._tamano
        lat_max = lat_min + self._tamano
        lon_min = celda.columna * self._tamano
        lon_max = lon_min + self._tamano
        # Anillo cerrado en sentido antihorario, coordenadas [lon, lat] (RFC 7946).
        anillo = [
            [lon_min, lat_min],
            [lon_max, lat_min],
            [lon_max, lat_max],
            [lon_min, lat_max],
            [lon_min, lat_min],
        ]
        return {"type": "Polygon", "coordinates": [anillo]}
