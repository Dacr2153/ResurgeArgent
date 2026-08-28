"""Configuración del Agente 7 (variables de entorno y parámetros)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTE7_", env_file=".env", extra="ignore")

    w1: float = 1.0
    w2: float = 1.0
    w3: float = 100.0
    w4: float = 1.0

    capacidad_uniforme: float = 10.0
    factor_escala: int = 100

    llm_proveedor: str = "nulo"  # nulo | anthropic | deepseek

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_max_tokens: int = 2000

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_max_tokens: int = 2000

    @property
    def pesos(self) -> dict[str, float]:
        return {"w1": self.w1, "w2": self.w2, "w3": self.w3, "w4": self.w4}
