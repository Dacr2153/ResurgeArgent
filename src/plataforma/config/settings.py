"""Configuración de plataforma (variables de entorno con prefijo PLATAFORMA_)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLATAFORMA_", env_file=".env", extra="ignore")

    # Persistencia. Vacío = memoria, que es lo que usan las pruebas. Con una ruta
    # de archivo, voluntarios, misiones, cuestionario y cola offline sobreviven al
    # reinicio, que es el único modo en que la cola offline tiene sentido.
    ruta_sqlite: str = ""

    # Base de operaciones: punto de referencia por defecto de toda distancia. Si
    # no se declara, cualquier filtro por radio mediría desde un origen inventado
    # y devolvería misiones inalcanzables.
    base_lat: float = 0.0
    base_lon: float = 0.0

    # Cuántas misiones se devuelven como máximo. Un voluntario no elige entre
    # cuarenta: elige entre las que puede atender ahora.
    misiones_por_lote: int = 5
