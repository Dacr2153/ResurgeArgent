"""Dobles de prueba de los agentes 2, 3 y 5, y constructores de datos.

Los agentes reales se construyen en ramas paralelas: aquí solo existen sus
protocolos. Cada doble tiene una variante que falla y una que tarda, porque la
resiliencia del Orquestador no se puede probar con agentes que siempre responden.
"""

from __future__ import annotations

import asyncio

from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    ConsultaGeo,
    Fuente,
    IncidenteVerificado,
    ReporteCrudo,
    RespuestaGeo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import Punto

BOGOTA = Punto(lat=4.7110, lon=-74.0721)


def hacer_reporte(texto: str = "colapso estructural", **kwargs) -> ReporteCrudo:
    base = {
        "texto": texto,
        "fuente": Fuente(id="F1", tipo=TipoFuente.CIUDADANO, nombre="anónimo"),
        "canal": Canal.SMS,
        "ubicacion": BOGOTA,
        "categoria": Categoria.RESCUE,
        "urgencia": Urgencia.IMMEDIATE,
        "severidad": Severidad.SEVERE,
        "certeza": Certeza.LIKELY,
    }
    base.update(kwargs)
    return ReporteCrudo(**base)


def hacer_incidente(
    id_: str = "INC-1",
    severidad: Severidad = Severidad.SEVERE,
    urgencia: Urgencia = Urgencia.IMMEDIATE,
    confianza: float = 0.8,
    personas: int | None = 10,
    **kwargs,
) -> IncidenteVerificado:
    base = {
        "id": id_,
        "categoria": Categoria.RESCUE,
        "severidad": severidad,
        "urgencia": urgencia,
        "ubicacion": BOGOTA,
        "confianza": confianza,
        "reportes_origen": ("R-1",),
        "personas_afectadas": personas,
        "resumen": f"incidente {id_}",
    }
    base.update(kwargs)
    return IncidenteVerificado(**base)


# --------------------------------------------------------------------- ingesta
class IngestaFake:
    def __init__(self, reportes: list[ReporteCrudo] | None = None) -> None:
        self.reportes = reportes if reportes is not None else [hacer_reporte()]
        self.llamadas = 0

    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]:
        self.llamadas += 1
        return list(self.reportes)


class IngestaQueFalla:
    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]:
        raise RuntimeError("la cola de ingesta no responde")


class IngestaQueTarda:
    def __init__(self, demora_s: float = 1.0) -> None:
        self.demora_s = demora_s

    async def ingerir(self, entrada: dict) -> list[ReporteCrudo]:
        await asyncio.sleep(self.demora_s)
        return [hacer_reporte()]


# ---------------------------------------------------------------- verificación
class VerificacionFake:
    def __init__(self, incidentes: list[IncidenteVerificado] | None = None) -> None:
        self.incidentes = incidentes if incidentes is not None else [hacer_incidente()]
        self.recibidos: list[ReporteCrudo] = []

    async def verificar(self, reportes: list[ReporteCrudo]) -> list[IncidenteVerificado]:
        self.recibidos = list(reportes)
        return list(self.incidentes)


class VerificacionQueFalla:
    async def verificar(self, reportes: list[ReporteCrudo]) -> list[IncidenteVerificado]:
        raise RuntimeError("el agente de verificación cayó")


# ----------------------------------------------------------------- geoespacial
class GeoespacialFake:
    def __init__(self) -> None:
        self.rutas_pedidas = 0

    async def resolver_ruta(self, consulta: ConsultaGeo) -> RespuestaGeo:
        self.rutas_pedidas += 1
        return RespuestaGeo(
            consulta_id=consulta.id,
            accesible=True,
            distancia_km=3.2,
            duracion_min=11.0,
            geometria={"type": "LineString", "coordinates": [[-74.07, 4.71], [-74.06, 4.72]]},
        )

    async def zonas_afectadas(self, incidentes: list[IncidenteVerificado]) -> dict:
        return {"zonas": [i.id for i in incidentes]}


class GeoespacialMudo:
    """Nunca responde: sirve para provocar el timeout del paso opcional."""

    def __init__(self, demora_s: float = 5.0) -> None:
        self.demora_s = demora_s

    async def resolver_ruta(self, consulta: ConsultaGeo) -> RespuestaGeo:
        await asyncio.sleep(self.demora_s)
        raise AssertionError("no debería llegar aquí")

    async def zonas_afectadas(self, incidentes: list[IncidenteVerificado]) -> dict:
        await asyncio.sleep(self.demora_s)
        raise AssertionError("no debería llegar aquí")
