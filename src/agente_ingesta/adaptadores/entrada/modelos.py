"""Modelos Pydantic del contrato de entrada del endpoint /ingesta.

Deliberadamente permisivo: casi todo es opcional porque un reporte de SMS trae
mucho menos que uno de sensor, y es el motor de dominio —no este modelo— quien
decide qué falta y descarta con motivo. Validar de más aquí duplicaría esa
lógica en dos capas y las dejaría divergir con el tiempo.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UbicacionIn(BaseModel):
    lat: float
    lon: float


class FuenteIn(BaseModel):
    id: str = ""
    tipo: str = ""
    nombre: str = ""
    reputacion: float = 0.5


class ReporteEntradaIn(BaseModel):
    fuente: FuenteIn = Field(default_factory=FuenteIn)
    canal: str = ""
    texto: str | None = None
    datos_sensor: dict[str, Any] | None = None
    ubicacion: UbicacionIn | None = None
    categoria: str | None = None
    urgencia: str | None = None
    severidad: str | None = None
    certeza: str | None = None
    personas_afectadas: int | None = None
    necesidades: list[str] | None = None
    ocurrido_en: str | None = None
    metadatos: dict[str, Any] = Field(default_factory=dict)


class IngestaRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "correlacion_id": "op-2026-08-28-001",
                "reportes": [
                    {
                        "fuente": {"id": "ciudadano-123", "tipo": "ciudadano"},
                        "canal": "sms",
                        "texto": "Hay un incendio grande cerca del puente, urgente",
                    }
                ],
            }
        }
    )

    correlacion_id: str | None = None
    reportes: list[ReporteEntradaIn] = Field(default_factory=list)
