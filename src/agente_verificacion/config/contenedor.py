"""Inyección de dependencias (wiring)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from agente_verificacion.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek
from agente_verificacion.adaptadores.llm.similitud_llm import SimilitudLLM
from agente_verificacion.adaptadores.llm.similitud_nula import SimilitudNula
from agente_verificacion.adaptadores.salida.publicador_log import PublicadorLog
from agente_verificacion.adaptadores.salida.repositorio_memoria import RepositorioMemoria
from agente_verificacion.aplicacion.casos_uso.verificar_reportes import VerificarReportes
from agente_verificacion.config.settings import Settings
from agente_verificacion.dominio.motor_verificacion import MotorVerificacion
from nucleo.auditoria import AuditoriaMemoria
from nucleo.llm import ClienteGemini, ClienteVertex, ConRespaldo
from nucleo.puertos import AuditoriaPort

PROMPT_PATH = Path(__file__).parent.parent / "adaptadores" / "llm" / "prompts" / "rol_agente_3.md"


def _construir_similitud_llm(settings: Settings):
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if settings.llm_proveedor == "vertex" and settings.vertex_proyecto:
        return SimilitudLLM(
            cliente=ClienteVertex(
                proyecto=settings.vertex_proyecto,
                cuenta_servicio=settings.vertex_cuenta_servicio,
                model=settings.vertex_model,
                region=settings.vertex_region,
                max_tokens=settings.vertex_max_tokens,
            ),
            rol_prompt=prompt,
        )

    if settings.llm_proveedor == "gemini" and settings.gemini_api_key:
        return SimilitudLLM(
            cliente=ClienteGemini(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                max_tokens=settings.gemini_max_tokens,
            ),
            rol_prompt=prompt,
        )

    if settings.llm_proveedor == "deepseek" and settings.deepseek_api_key:
        return SimilitudLLM(
            cliente=ClienteDeepSeek(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                max_tokens=settings.deepseek_max_tokens,
                base_url=settings.deepseek_base_url,
            ),
            rol_prompt=prompt,
        )

    if (settings.llm_proveedor in ("anthropic", "nulo")) and settings.anthropic_api_key:
        return SimilitudLLM(
            cliente=ClienteAnthropic(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
            ),
            rol_prompt=prompt,
        )

    return None


def construir_similitud(settings: Settings):
    """Adaptador de LLM con respaldo de reglas.

    Que el modelo se caiga no puede detener la respuesta a una emergencia: el
    LLM nunca decide, asi que su ausencia degrada la calidad de la extraccion,
    no la operacion.
    """
    principal = _construir_similitud_llm(settings)
    if principal is None:
        return SimilitudNula()
    return ConRespaldo(principal, SimilitudNula())


def construir_contenedor(
    settings: Settings | None = None,
    auditoria: AuditoriaPort | None = None,
) -> VerificarReportes:
    settings = settings or Settings()
    motor = MotorVerificacion(
        radio_cluster_km=settings.radio_cluster_km,
        ventana_tiempo=timedelta(hours=settings.ventana_tiempo_horas),
        umbral_fusion=settings.umbral_fusion,
        vida_media_horas=settings.vida_media_horas,
    )
    return VerificarReportes(
        motor=motor,
        similitud=construir_similitud(settings),
        publicador=PublicadorLog(),
        repositorio=RepositorioMemoria(),
        auditoria=auditoria or AuditoriaMemoria(),
    )
