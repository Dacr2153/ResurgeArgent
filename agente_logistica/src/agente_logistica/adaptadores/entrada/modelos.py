"""Modelos Pydantic del contrato de entrada del endpoint /planificar."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PuntoIn(BaseModel):
    id: str
    latitud: float
    longitud: float


class AsignacionIn(BaseModel):
    id: str
    necesidad_id: str
    recurso_id: str
    tipo: str = ""
    origen: PuntoIn
    destino: PuntoIn
    cantidad: float = Field(ge=0)
    unidad: str = ""
    prioridad: int = Field(default=1, ge=1)


class UbicacionIn(BaseModel):
    latitud: float
    longitud: float


class VehiculoIn(BaseModel):
    id: str
    tipo: str = ""
    capacidad: float = Field(gt=0)
    unidad_capacidad: str = ""
    ubicacion: UbicacionIn
    disponible: bool = True
    restricciones: list[str] = []


class RestriccionIn(BaseModel):
    tipo: str = "VIA_BLOQUEADA"
    via_id: str


class AristaIn(BaseModel):
    origen: str
    destino: str
    distancia: float = Field(ge=0)
    tiempo: float = Field(ge=0)
    estado: str = "DISPONIBLE"
    via_id: str = ""
    riesgo: float = Field(default=0.0, ge=0)


class NodoIn(BaseModel):
    id: str


class MapaIn(BaseModel):
    nodos: list[NodoIn] = []
    aristas: list[AristaIn] = []


class PlanificacionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "asignaciones": [
                    {
                        "id": "A001",
                        "necesidad_id": "N001",
                        "recurso_id": "R001",
                        "tipo": "agua",
                        "origen": {"id": "CENTRO_01", "latitud": 4.610, "longitud": -74.080},
                        "destino": {"id": "REFUGIO_03", "latitud": 4.650, "longitud": -74.060},
                        "cantidad": 500.0,
                        "unidad": "litros",
                        "prioridad": 10,
                    }
                ],
                "vehiculos": [
                    {
                        "id": "V001",
                        "tipo": "camion",
                        "capacidad": 1000.0,
                        "unidad_capacidad": "litros",
                        "ubicacion": {"latitud": 4.600, "longitud": -74.090},
                        "disponible": True,
                    }
                ],
                "restricciones": [{"tipo": "VIA_BLOQUEADA", "via_id": "VIA_023"}],
                "mapa": {
                    "nodos": [
                        {"id": "CENTRO_01"},
                        {"id": "NODO_X"},
                        {"id": "REFUGIO_03"},
                    ],
                    "aristas": [
                        {
                            "origen": "CENTRO_01",
                            "destino": "NODO_X",
                            "distancia": 2.5,
                            "tiempo": 5,
                            "estado": "DISPONIBLE",
                            "via_id": "VIA_001",
                        },
                        {
                            "origen": "NODO_X",
                            "destino": "REFUGIO_03",
                            "distancia": 9.9,
                            "tiempo": 23,
                            "estado": "DISPONIBLE",
                            "via_id": "VIA_023",
                        },
                    ],
                },
            }
        }
    )

    asignaciones: list[AsignacionIn]
    vehiculos: list[VehiculoIn]
    restricciones: list[RestriccionIn] = []
    mapa: MapaIn = MapaIn()
