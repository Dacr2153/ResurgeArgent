"""Configuración del Agente 5 (variables de entorno y parámetros)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from nucleo.esquemas import ModoTransporte


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTE5_", env_file=".env", extra="ignore")

    tamano_celda_grados: float = 0.01
    radio_conexion_km: float = 5.0
    max_alternativas: int = 1

    velocidad_auto_kmh: float = 40.0
    velocidad_camion_kmh: float = 30.0
    velocidad_moto_kmh: float = 45.0
    velocidad_peaton_kmh: float = 5.0

    llm_proveedor: str = "nulo"  # nulo | anthropic | deepseek

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_max_tokens: int = 1000

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_max_tokens: int = 1000

    @property
    def perfil_velocidad(self) -> dict[ModoTransporte, float]:
        return {
            ModoTransporte.AUTO: self.velocidad_auto_kmh,
            ModoTransporte.CAMION: self.velocidad_camion_kmh,
            ModoTransporte.MOTO: self.velocidad_moto_kmh,
            ModoTransporte.PEATON: self.velocidad_peaton_kmh,
        }
