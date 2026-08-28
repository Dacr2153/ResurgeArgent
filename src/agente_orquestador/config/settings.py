"""Configuración del Agente 1 (variables de entorno con prefijo AGENTE1_).

Los timeouts están separados por agente porque no cuesta lo mismo cada cosa: la
ingesta es normalización local y debe ser rápida; la verificación cruza reportes
entre sí y puede tardar; el cálculo de rutas es el más caro de los tres y es
además el único que puede fallar sin abortar la operación.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from agente_orquestador.dominio.value_objects import PesosTriage


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTE1_", env_file=".env", extra="ignore")

    # Resiliencia
    timeout_ingesta_s: float = 3.0
    timeout_verificacion_s: float = 5.0
    timeout_geo_s: float = 8.0
    limite_visitas_estado: int = 3
    rutas_por_lote: int = 5

    # Triage. Sobrescribir estos pesos cambia a quién se atiende primero: se hace
    # con conocimiento de causa, no por conveniencia de un despliegue.
    peso_severidad: float = 0.45
    peso_urgencia: float = 0.35
    peso_personas: float = 0.20

    # Base de operaciones desde la que se calculan las rutas. Sin ella no se piden
    # rutas: una ruta sin origen real es un número inventado.
    origen_lat: float | None = None
    origen_lon: float | None = None

    # Auditoría. Vacío = solo en memoria; con ruta se escribe JSONL append-only.
    ruta_auditoria: str = ""

    # Persistencia. Vacío = todo en memoria, que es el modo por defecto y el que
    # usan las pruebas. Con una ruta de archivo, operaciones y auditoría pasan a
    # SQLite y sobreviven al reinicio del proceso. `ruta_auditoria` tiene
    # prioridad sobre esta para la traza: quien pide JSONL explícitamente lo
    # quiere para poder seguirlo con `tail -f`.
    ruta_sqlite: str = ""

    # LLM. Solo redacta el parte de situación; por defecto no hay red.
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
    anthropic_max_tokens: int = 1200

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_max_tokens: int = 1200

    @property
    def pesos_triage(self) -> PesosTriage:
        return PesosTriage(
            severidad=self.peso_severidad,
            urgencia=self.peso_urgencia,
            personas=self.peso_personas,
        )
