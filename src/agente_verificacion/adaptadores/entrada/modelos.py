"""Modelos Pydantic del contrato de entrada del endpoint /verificacion.

Traducen el JSON de la petición HTTP a `ReporteCrudo`/`Fuente` de
`nucleo.esquemas` — los mismos tipos que usa el Orquestador al invocar este
agente en proceso. El endpoint es la puerta de entrada alternativa (HTTP) al
mismo caso de uso.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    Fuente,
    ReporteCrudo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import Punto


class UbicacionIn(BaseModel):
    lat: float
    lon: float


class FuenteIn(BaseModel):
    id: str
    tipo: TipoFuente
    nombre: str = ""
    reputacion: float = Field(default=0.5, ge=0.0, le=1.0)


class ReporteIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "texto": "Derrumbe en la vía, hay personas atrapadas",
                "fuente": {
                    "id": "c-1",
                    "tipo": "ciudadano",
                    "nombre": "Ana",
                    "reputacion": 0.5,
                },
                "canal": "sms",
                "ubicacion": {"lat": 4.6097, "lon": -74.0817},
                "categoria": "Rescue",
                "urgencia": "Immediate",
                "severidad": "Severe",
                "certeza": "Observed",
            }
        }
    )

    texto: str
    fuente: FuenteIn
    canal: Canal
    ubicacion: UbicacionIn | None = None
    categoria: Categoria = Categoria.OTHER
    urgencia: Urgencia = Urgencia.UNKNOWN
    severidad: Severidad = Severidad.UNKNOWN
    certeza: Certeza = Certeza.UNKNOWN
    personas_afectadas: int | None = None
    necesidades: list[str] = []
    id: str | None = None
    recibido_en: datetime | None = None
    ocurrido_en: datetime | None = None
    metadatos: dict = {}

    def a_reporte_crudo(self) -> ReporteCrudo:
        fuente = Fuente(
            id=self.fuente.id,
            tipo=self.fuente.tipo,
            nombre=self.fuente.nombre,
            reputacion=self.fuente.reputacion,
        )
        ubicacion = (
            Punto(lat=self.ubicacion.lat, lon=self.ubicacion.lon) if self.ubicacion else None
        )

        kwargs = dict(
            texto=self.texto,
            fuente=fuente,
            canal=self.canal,
            ubicacion=ubicacion,
            categoria=self.categoria,
            urgencia=self.urgencia,
            severidad=self.severidad,
            certeza=self.certeza,
            personas_afectadas=self.personas_afectadas,
            necesidades=tuple(self.necesidades),
            metadatos=self.metadatos,
        )
        if self.id is not None:
            kwargs["id"] = self.id
        if self.recibido_en is not None:
            kwargs["recibido_en"] = self.recibido_en
        if self.ocurrido_en is not None:
            kwargs["ocurrido_en"] = self.ocurrido_en
        return ReporteCrudo(**kwargs)


class VerificacionRequest(BaseModel):
    reportes: list[ReporteIn]
