"""Modelos Pydantic del contrato de entrada de la API de plataforma.

Los nombres de campo son los del frontend (`fullName`, `radio_km`…) solo donde el
frontend ya los fijó; el resto va en español como el resto del repo. Se declara
`extra="forbid"` en todos: un campo que el servidor ignora en silencio es un dato
que el usuario cree haber enviado y nadie va a leer.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VoluntarioRequest(BaseModel):
    """Alta de un voluntario. Coincide con `VolunteerSignup` del frontend."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    nombre_completo: str = Field(min_length=1, alias="fullName")
    documento: str = Field(min_length=1, alias="document")
    telefono: str = Field(min_length=1, alias="phone")
    recurso: str = Field(default="", alias="resource")


class ItemChecklistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clave: str = Field(min_length=1)
    etiqueta: str = Field(min_length=1)


class MisionRequest(BaseModel):
    """Apertura de una misión sobre un incidente ya priorizado."""

    model_config = ConfigDict(extra="forbid")

    incidente_id: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    direccion: str = ""
    necesidad: str = ""
    puntuacion: int = Field(default=0, ge=0, le=100)
    modo: str = "a pie"
    ruta: list[tuple[float, float]] = Field(default_factory=list)
    checklist: list[ItemChecklistRequest] = Field(default_factory=list)


class PlanRequest(BaseModel):
    """Respuestas del cuestionario de recuperación."""

    model_config = ConfigDict(extra="forbid")

    respuestas: dict[str, str] = Field(default_factory=dict)


class EncolarRequest(BaseModel):
    """Reporte que se creó sin cobertura y espera turno para salir."""

    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(min_length=1)
    meta: str = ""
    puntuacion: int = Field(default=0, ge=0, le=100)
    carga: dict[str, Any] = Field(default_factory=dict)
