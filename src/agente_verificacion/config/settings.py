"""Configuración del Agente 3 (variables de entorno y parámetros)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTE3_", env_file=".env", extra="ignore")

    radio_cluster_km: float = 0.5
    ventana_tiempo_horas: float = 6.0
    umbral_fusion: float = 0.65
    vida_media_horas: float = 12.0

    llm_proveedor: str = "nulo"  # nulo | anthropic | deepseek

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_max_tokens: int = 2000

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_max_tokens: int = 2000
