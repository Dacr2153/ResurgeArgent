"""Configuración del Agente 8 (variables de entorno y parámetros)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTE8_", env_file=".env", extra="ignore")

    # Pesos de la función de costo de ruta.
    alfa: float = 0.5
    beta: float = 0.5
    gamma: float = 0.0
    delta: float = 0.0

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
        return {
            "alfa": self.alfa,
            "beta": self.beta,
            "gamma": self.gamma,
            "delta": self.delta,
        }
