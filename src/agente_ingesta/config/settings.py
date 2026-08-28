"""Configuración del Agente 2 (variables de entorno y parámetros)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from agente_ingesta.dominio.value_objects import ConfigVentana


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTE2_", env_file=".env", extra="ignore")

    # Back-pressure: cuántos reportes se aceptan por ventana deslizante. El
    # valor por defecto es generoso a propósito (modo normal); se baja en
    # despliegue si el resto del sistema no soporta la carga.
    limite_ventana: int = 500
    ventana_segundos: float = 60.0

    llm_proveedor: str = "nulo"  # nulo | vertex | gemini | anthropic | deepseek

    vertex_proyecto: str = ""
    vertex_cuenta_servicio: str = ""
    vertex_model: str = "gemini-2.5-pro"
    vertex_region: str = "us-central1"
    vertex_max_tokens: int = 2000

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_max_tokens: int = 2000

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    anthropic_max_tokens: int = 1000

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_max_tokens: int = 1000

    @property
    def config_ventana(self) -> ConfigVentana:
        return ConfigVentana(limite=self.limite_ventana, segundos=self.ventana_segundos)
