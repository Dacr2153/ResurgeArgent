"""Modelos Pydantic del contrato de entrada de la API del Orquestador."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UbicacionIn(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class EmergenciaRequest(BaseModel):
    """Disparo de una emergencia.

    `entrada` va sin esquema a propósito: es la carga cruda que consume el Agente
    de Ingesta, y el Orquestador no debe conocer su forma. Validarla aquí
    duplicaría el contrato del Agente 2 y obligaría a tocar este archivo cada vez
    que ellos añadan un canal.
    """

    model_config = ConfigDict(extra="forbid")

    entrada: dict[str, Any] = Field(default_factory=dict)
    correlacion_id: str | None = None
    origen_despacho: UbicacionIn | None = None


class DecisionHumanaRequest(BaseModel):
    """Firma del coordinador sobre un incidente en PENDIENTE_APROBACION."""

    model_config = ConfigDict(extra="forbid")

    incidente_id: str = Field(min_length=1)
    aprobada: bool
    coordinador_id: str = Field(min_length=1)
    justificacion: str = ""
    suspender: bool = False
