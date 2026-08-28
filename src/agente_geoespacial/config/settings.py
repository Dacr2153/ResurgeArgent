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

    # "grafo" por defecto: las 243 pruebas existentes no salen a red y siguen
    # pasando sin cambios. "osrm" activa el ruteo sobre calles reales, con el
    # grafo propio como respaldo automático si OSRM no responde (ver
    # ResolverRuta._resolver).
    ruteador: str = "grafo"  # grafo | osrm
    osrm_url_base: str = "https://router.project-osrm.org/route/v1"
    osrm_timeout_seg: float = 4.0

    nominatim_url_base: str = "https://nominatim.openstreetmap.org/search"
    nominatim_timeout_seg: float = 5.0
    nominatim_user_agent: str = (
        "ResurgeAgent-Agente5-Geoespacial/0.1 (hackaton INVIMA; sin contacto publico)"
    )
    nominatim_min_intervalo_seg: float = 1.0

    @property
    def perfil_velocidad(self) -> dict[ModoTransporte, float]:
        return {
            ModoTransporte.AUTO: self.velocidad_auto_kmh,
            ModoTransporte.CAMION: self.velocidad_camion_kmh,
            ModoTransporte.MOTO: self.velocidad_moto_kmh,
            ModoTransporte.PEATON: self.velocidad_peaton_kmh,
        }
