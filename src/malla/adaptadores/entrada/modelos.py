"""Modelos de entrada del adaptador REST.

Se validan aquí solo la forma y los tipos. La legitimidad del sobre —firma,
TTL, bucles— la decide el motor: un modelo Pydantic no puede saber si una firma
Ed25519 verifica, y fingir que sí llevaría a aceptar sobres por parecer bien
formados.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SobreRequest(BaseModel):
    """Un sobre tal como llega de un vecino."""

    id_mensaje: str
    nodo_origen: str
    clave_publica_origen: str
    firma: str
    momento_origen: str
    ttl: int
    carga: dict[str, Any]
    saltos: int = 0
    ruta: list[str] = Field(default_factory=list)
    tipo_carga: str = "reporte"
    version: str = "1.0"


class ReporteRequest(BaseModel):
    """Un reporte originado en este teléfono, listo para firmar y difundir."""

    texto: str
    fuente: dict[str, Any]
    canal: str
    ubicacion: dict[str, Any] | None = None
    categoria: str = "Other"
    urgencia: str = "Unknown"
    severidad: str = "Unknown"
    certeza: str = "Unknown"
    personas_afectadas: int | None = None
    necesidades: list[str] = Field(default_factory=list)
    ttl: int | None = None


class AnuncioRequest(BaseModel):
    """Un navegador que se presenta en la señalización para encontrar pares."""

    id_nodo: str
    descripcion: dict[str, Any] = Field(default_factory=dict)


class SenalRequest(BaseModel):
    """Oferta, respuesta o candidato ICE dirigido a otro par."""

    remitente: str
    destino: str
    tipo: str
    datos: dict[str, Any]
