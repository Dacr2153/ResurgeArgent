"""Modelos Pydantic del contrato de entrada del endpoint /matching."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UbicacionIn(BaseModel):
    lat: float
    lon: float


class NecesidadIn(BaseModel):
    id: str
    zona_id: str = ""
    tipo: str
    cantidad_requerida: float = Field(ge=0)
    prioridad: int = Field(default=1, ge=1)
    ubicacion: UbicacionIn


class RecursoIn(BaseModel):
    id: str
    lugar_id: str = ""
    tipo: str
    cantidad_disponible: float = Field(ge=0)
    ubicacion: UbicacionIn


class EmpresaIn(BaseModel):
    id: str
    nombre: str = ""
    ubicacion: UbicacionIn
    num_vehiculos: int = Field(ge=0)
    num_en_transito: int = Field(default=0, ge=0)
    zonas_cobertura: list[str] | None = None


class AsignacionFijaIn(BaseModel):
    empresa_id: str
    recurso_id: str
    necesidad_id: str
    cantidad: float = Field(ge=0)


class MatchingRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "necesidades": [
                    {
                        "id": "N1",
                        "zona_id": "Z-A",
                        "tipo": "agua",
                        "cantidad_requerida": 100.0,
                        "prioridad": 3,
                        "ubicacion": {"lat": 4.711, "lon": -74.072},
                    }
                ],
                "recursos": [
                    {
                        "id": "R1",
                        "lugar_id": "Z-B",
                        "tipo": "agua",
                        "cantidad_disponible": 150.0,
                        "ubicacion": {"lat": 4.6, "lon": -74.08},
                    }
                ],
                "empresas": [
                    {
                        "id": "A",
                        "nombre": "Empresa A",
                        "ubicacion": {"lat": 4.65, "lon": -74.09},
                        "num_vehiculos": 4,
                        "num_en_transito": 1,
                    },
                    {
                        "id": "B",
                        "nombre": "Empresa B",
                        "ubicacion": {"lat": 4.65, "lon": -74.09},
                        "num_vehiculos": 4,
                        "num_en_transito": 0,
                    },
                    {
                        "id": "C",
                        "nombre": "Empresa C",
                        "ubicacion": {"lat": 4.65, "lon": -74.09},
                        "num_vehiculos": 4,
                        "num_en_transito": 0,
                    },
                ],
                "asignaciones_fijas": [],
            }
        }
    )

    necesidades: list[NecesidadIn]
    recursos: list[RecursoIn]
    empresas: list[EmpresaIn]
    asignaciones_fijas: list[AsignacionFijaIn] = []
