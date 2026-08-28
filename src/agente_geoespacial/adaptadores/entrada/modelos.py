"""Modelos Pydantic del contrato de entrada de los endpoints REST."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from nucleo.esquemas import ModoTransporte


class PuntoIn(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class ConsultaRutaIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "origen": {"lat": 4.7000, "lon": -74.0800},
                "destino": {"lat": 4.7100, "lon": -74.0700},
                "modo": "auto",
                "evitar_zonas": [],
                "reportes_bloqueo": [],
            }
        }
    )

    origen: PuntoIn
    destino: PuntoIn
    modo: ModoTransporte = ModoTransporte.AUTO
    evitar_zonas: list[str] = []
    reportes_bloqueo: list[str] = []


class IncidenteIn(BaseModel):
    """Espejo de ``nucleo.esquemas.IncidenteVerificado`` para el contrato REST."""

    id: str | None = None
    categoria: str = "Other"
    severidad: str = "Unknown"
    urgencia: str = "Unknown"
    ubicacion: PuntoIn
    confianza: float = Field(ge=0.0, le=1.0, default=0.5)
    reportes_origen: list[str] = Field(min_length=1)
    resumen: str = ""


class ZonasRequest(BaseModel):
    incidentes: list[IncidenteIn]
