"""Inyección de dependencias (wiring) del Agente 1.

Dos detalles que no son obvios:

1. **Los agentes delegados se descubren, no se importan.** Los agentes 2, 3 y 5
   se construyen en ramas paralelas y pueden no existir en este despliegue. Si el
   módulo no está, se inyecta un sustituto que falla limpio y la saga degrada.
   Importarlos directamente haría que el Orquestador no arrancara sin ellos.

2. **El contenedor expone los dos casos de uso y el repositorio**, porque la API
   los necesita a los tres y `main.py` solo llama a `construir_contenedor()`.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agente_orquestador.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek
from agente_orquestador.adaptadores.llm.resumidor_llm import ResumidorLLM
from agente_orquestador.adaptadores.llm.resumidor_nulo import ResumidorNulo
from agente_orquestador.adaptadores.salida.agentes_ausentes import (
    GeoespacialAusente,
    IngestaAusente,
    VerificacionAusente,
)
from agente_orquestador.adaptadores.salida.publicador_log import PublicadorLog
from agente_orquestador.adaptadores.salida.repositorio_memoria import (
    RepositorioOperacionesMemoria,
)
from agente_orquestador.aplicacion.casos_uso.procesar_emergencia import ProcesarEmergencia
from agente_orquestador.aplicacion.casos_uso.registrar_decision_humana import (
    RegistrarDecisionHumana,
)
from agente_orquestador.config.settings import Settings
from agente_orquestador.dominio.motor_triage import MotorTriage
from nucleo.auditoria import AuditoriaJSONL, AuditoriaMemoria
from nucleo.geo import Punto
from nucleo.puertos import AuditoriaPort, GeoespacialPort, IngestaPort, VerificacionPort

registro = logging.getLogger("agente_orquestador.contenedor")

PROMPT_PATH = Path(__file__).parent.parent / "adaptadores" / "llm" / "prompts" / "rol_agente_1.md"


@dataclass
class Contenedor:
    """Todo lo que la capa de entrada necesita, ya cableado."""

    procesar: ProcesarEmergencia
    registrar_decision: RegistrarDecisionHumana
    repositorio: RepositorioOperacionesMemoria
    auditoria: AuditoriaPort

    def eventos_de(self, correlacion_id: str) -> list[dict[str, Any]]:
        """Eventos de auditoría de una operación, si el adaptador sabe releerlos."""
        if isinstance(self.auditoria, AuditoriaMemoria):
            return [e.a_dict() for e in self.auditoria.por_correlacion(correlacion_id)]
        if isinstance(self.auditoria, AuditoriaJSONL):
            return [e for e in self.auditoria.leer() if e.get("correlacion_id") == correlacion_id]
        return []


def construir_resumidor(settings: Settings):
    """Devuelve el resumidor configurado; sin API key, siempre el nulo."""
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if settings.llm_proveedor == "deepseek" and settings.deepseek_api_key:
        return ResumidorLLM(
            cliente=ClienteDeepSeek(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                max_tokens=settings.deepseek_max_tokens,
                base_url=settings.deepseek_base_url,
            ),
            rol_prompt=prompt,
        )

    if settings.llm_proveedor == "anthropic" and settings.anthropic_api_key:
        return ResumidorLLM(
            cliente=ClienteAnthropic(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
            ),
            rol_prompt=prompt,
        )

    return ResumidorNulo()


def _descubrir(paquete: str, ausente: Any) -> Any:
    """Construye el contenedor del agente delegado, o devuelve el sustituto."""
    try:
        modulo = importlib.import_module(f"{paquete}.config.contenedor")
    except ModuleNotFoundError:
        registro.info("agente no disponible todavía: %s", paquete)
        return ausente
    try:
        return modulo.construir_contenedor()
    except Exception:  # noqa: BLE001 - un agente roto no impide arrancar al Orquestador
        registro.exception("fallo al construir el agente %s", paquete)
        return ausente


def construir_auditoria(settings: Settings) -> AuditoriaPort:
    if settings.ruta_auditoria:
        return AuditoriaJSONL(settings.ruta_auditoria)
    return AuditoriaMemoria()


def construir_contenedor(
    settings: Settings | None = None,
    ingesta: IngestaPort | None = None,
    verificacion: VerificacionPort | None = None,
    geoespacial: GeoespacialPort | None = None,
) -> Contenedor:
    settings = settings or Settings()

    repositorio = RepositorioOperacionesMemoria()
    publicador = PublicadorLog()
    auditoria = construir_auditoria(settings)

    origen = None
    if settings.origen_lat is not None and settings.origen_lon is not None:
        origen = Punto(lat=settings.origen_lat, lon=settings.origen_lon)

    procesar = ProcesarEmergencia(
        ingesta=ingesta or _descubrir("agente_ingesta", IngestaAusente()),
        verificacion=verificacion or _descubrir("agente_verificacion", VerificacionAusente()),
        geoespacial=geoespacial or _descubrir("agente_geoespacial", GeoespacialAusente()),
        motor=MotorTriage(settings.pesos_triage),
        resumidor=construir_resumidor(settings),
        repositorio=repositorio,
        publicador=publicador,
        auditoria=auditoria,
        origen_despacho=origen,
        timeout_ingesta_s=settings.timeout_ingesta_s,
        timeout_verificacion_s=settings.timeout_verificacion_s,
        timeout_geo_s=settings.timeout_geo_s,
        limite_visitas=settings.limite_visitas_estado,
        rutas_por_lote=settings.rutas_por_lote,
    )

    return Contenedor(
        procesar=procesar,
        registrar_decision=RegistrarDecisionHumana(repositorio, auditoria, publicador),
        repositorio=repositorio,
        auditoria=auditoria,
    )
