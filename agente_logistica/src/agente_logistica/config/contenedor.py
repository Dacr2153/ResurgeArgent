"""Inyección de dependencias del Agente 8."""

from __future__ import annotations

from pathlib import Path

from agente_logistica.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek
from agente_logistica.adaptadores.llm.orquestador_llm import OrquestadorLLM
from agente_logistica.adaptadores.llm.orquestador_nulo import OrquestadorNulo
from agente_logistica.adaptadores.salida.geographic_provider_memoria import (
    GeographicProviderMemoria,
)
from agente_logistica.adaptadores.salida.publicador_log import PublicadorLog
from agente_logistica.aplicacion.casos_uso.planificar_logistica import PlanificarLogistica
from agente_logistica.config.settings import Settings
from agente_logistica.dominio.motor_logistica import MotorLogistica

PROMPT_PATH = Path(__file__).parent.parent / "adaptadores" / "llm" / "prompts" / "rol_agente_8.md"


def construir_llm(settings: Settings):
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if settings.llm_proveedor == "deepseek" and settings.deepseek_api_key:
        return OrquestadorLLM(
            cliente=ClienteDeepSeek(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                max_tokens=settings.deepseek_max_tokens,
                base_url=settings.deepseek_base_url,
            ),
            rol_prompt=prompt,
        )

    if (settings.llm_proveedor in ("anthropic", "nulo")) and settings.anthropic_api_key:
        return OrquestadorLLM(
            cliente=ClienteAnthropic(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
            ),
            rol_prompt=prompt,
        )

    return OrquestadorNulo()


def construir_contenedor(settings: Settings | None = None) -> PlanificarLogistica:
    settings = settings or Settings()
    return PlanificarLogistica(
        planner=MotorLogistica(settings.pesos),
        geo=GeographicProviderMemoria(),
        llm=construir_llm(settings),
        publicador=PublicadorLog(),
    )
