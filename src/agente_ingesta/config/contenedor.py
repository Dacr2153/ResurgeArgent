"""Inyección de dependencias (wiring)."""

from __future__ import annotations

from pathlib import Path

from agente_ingesta.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek
from agente_ingesta.adaptadores.llm.extractor_llm import ExtractorLLM
from agente_ingesta.adaptadores.llm.extractor_nulo import ExtractorNulo
from agente_ingesta.adaptadores.salida.publicador_log import PublicadorLog
from agente_ingesta.adaptadores.salida.repositorio_memoria import RepositorioMemoria
from agente_ingesta.aplicacion.casos_uso.ingerir_reportes import IngerirReportes
from agente_ingesta.config.settings import Settings
from agente_ingesta.dominio.motor_ingesta import MotorIngesta
from nucleo.auditoria import AuditoriaMemoria

PROMPT_PATH = Path(__file__).parent.parent / "adaptadores" / "llm" / "prompts" / "rol_agente_2.md"


def construir_extractor(settings: Settings):
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if settings.llm_proveedor == "deepseek" and settings.deepseek_api_key:
        return ExtractorLLM(
            cliente=ClienteDeepSeek(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                max_tokens=settings.deepseek_max_tokens,
                base_url=settings.deepseek_base_url,
            ),
            rol_prompt=prompt,
        )

    if (settings.llm_proveedor in ("anthropic", "nulo")) and settings.anthropic_api_key:
        return ExtractorLLM(
            cliente=ClienteAnthropic(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
            ),
            rol_prompt=prompt,
        )

    return ExtractorNulo()


def construir_contenedor(settings: Settings | None = None) -> IngerirReportes:
    settings = settings or Settings()
    motor = MotorIngesta(config_ventana=settings.config_ventana)
    return IngerirReportes(
        motor=motor,
        extractor=construir_extractor(settings),
        auditoria=AuditoriaMemoria(),
        publicador=PublicadorLog(),
        repositorio=RepositorioMemoria(),
    )
