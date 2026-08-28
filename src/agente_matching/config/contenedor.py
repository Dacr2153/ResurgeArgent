"""Inyección de dependencias (wiring)."""

from __future__ import annotations

from pathlib import Path

from agente_matching.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek
from agente_matching.adaptadores.llm.orquestador_llm import OrquestadorLLM
from agente_matching.adaptadores.llm.orquestador_nulo import OrquestadorNulo
from agente_matching.adaptadores.salida.publicador_log import PublicadorLog
from agente_matching.adaptadores.salida.repositorio_memoria import RepositorioMemoria
from agente_matching.aplicacion.casos_uso.ejecutar_matching import EjecutarMatching
from agente_matching.config.settings import Settings
from agente_matching.dominio.motor_matching import MotorMatching

PROMPT_PATH = Path(__file__).parent.parent / "adaptadores" / "llm" / "prompts" / "rol_agente_7.md"


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


def construir_contenedor(settings: Settings | None = None) -> EjecutarMatching:
    settings = settings or Settings()
    motor = MotorMatching(
        pesos=settings.pesos,
        factor_escala=settings.factor_escala,
        capacidad_uniforme=settings.capacidad_uniforme,
    )
    return EjecutarMatching(
        motor=motor,
        llm=construir_llm(settings),
        publicador=PublicadorLog(),
        repositorio=RepositorioMemoria(),
    )
