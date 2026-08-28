"""Inyección de dependencias (wiring)."""

from __future__ import annotations

from pathlib import Path

from agente_geoespacial.adaptadores.llm.clientes import ClienteAnthropic, ClienteDeepSeek
from agente_geoespacial.adaptadores.llm.interprete_llm import InterpreteLLM
from agente_geoespacial.adaptadores.llm.interprete_nulo import InterpreteNulo
from agente_geoespacial.adaptadores.salida.geocodificador_nominatim import (
    GeocodificadorNominatim,
    LimitadorRitmo,
)
from agente_geoespacial.adaptadores.salida.publicador_log import PublicadorLog
from agente_geoespacial.adaptadores.salida.ruteo_osrm import RuteadorOSRM
from agente_geoespacial.aplicacion.casos_uso.analizar_zonas import AnalizarZonas
from agente_geoespacial.aplicacion.casos_uso.resolver_ruta import ResolverRuta
from agente_geoespacial.aplicacion.puertos.salida import GeocodificadorPort, RuteadorPort
from agente_geoespacial.config.settings import Settings
from agente_geoespacial.dominio.entidades import GrafoVial, NodoVial, TramoVial
from agente_geoespacial.dominio.motor_rutas import MotorRutas
from agente_geoespacial.dominio.motor_zonas import MotorZonas
from agente_geoespacial.dominio.value_objects import PerfilVelocidad
from nucleo.auditoria import AuditoriaMemoria
from nucleo.geo import Punto
from nucleo.llm import ClienteGemini, ClienteVertex, ConRespaldo
from nucleo.puertos import AuditoriaPort

PROMPT_PATH = Path(__file__).parent.parent / "adaptadores" / "llm" / "prompts" / "rol_agente_5.md"


def grafo_demo() -> GrafoVial:
    """Grafo vial mínimo, solo para que el contenedor levante sin depender de red.

    En producción este grafo no se construye a mano: se carga de OpenStreetMap
    (ver ``src/agente_geoespacial/README.md``) a través de un adaptador que
    implemente ``RepositorioGrafoPort``. Este es un placeholder de tres nodos
    para desarrollo local y para que ``main.py`` pueda montar la app del agente.
    """
    nodos = {
        "N1": NodoVial(id="N1", ubicacion=Punto(lat=4.7000, lon=-74.0800)),
        "N2": NodoVial(id="N2", ubicacion=Punto(lat=4.7050, lon=-74.0750)),
        "N3": NodoVial(id="N3", ubicacion=Punto(lat=4.7100, lon=-74.0700)),
    }
    tramos = (
        TramoVial(id="T1", origen_id="N1", destino_id="N2"),
        TramoVial(id="T2", origen_id="N2", destino_id="N3"),
        TramoVial(id="T3", origen_id="N1", destino_id="N3"),
    )
    return GrafoVial(nodos=nodos, tramos=tramos)


def _construir_llm_llm(settings: Settings):
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    if settings.llm_proveedor == "vertex" and settings.vertex_proyecto:
        return InterpreteLLM(
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
        return InterpreteLLM(
            cliente=ClienteGemini(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                max_tokens=settings.gemini_max_tokens,
            ),
            rol_prompt=prompt,
        )

    if settings.llm_proveedor == "deepseek" and settings.deepseek_api_key:
        return InterpreteLLM(
            cliente=ClienteDeepSeek(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
                max_tokens=settings.deepseek_max_tokens,
                base_url=settings.deepseek_base_url,
            ),
            rol_prompt=prompt,
        )

    if settings.llm_proveedor == "anthropic" and settings.anthropic_api_key:
        return InterpreteLLM(
            cliente=ClienteAnthropic(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
            ),
            rol_prompt=prompt,
        )

    return None


def construir_llm(settings: Settings):
    """Adaptador de LLM con respaldo de reglas.

    Que el modelo se caiga no puede detener la respuesta a una emergencia: el
    LLM nunca decide, asi que su ausencia degrada la calidad de la extraccion,
    no la operacion.
    """
    principal = _construir_llm_llm(settings)
    if principal is None:
        return InterpreteNulo()
    return ConRespaldo(principal, InterpreteNulo())


def construir_ruteador(settings: Settings) -> RuteadorPort | None:
    """``None`` cuando ``settings.ruteador == "grafo"`` (por defecto): así
    ``ResolverRuta`` ni intenta red y el comportamiento es el de siempre — es lo
    que mantiene las 243 pruebas existentes verdes sin red ni cambios.
    """
    if settings.ruteador == "osrm":
        return RuteadorOSRM(url_base=settings.osrm_url_base, timeout_seg=settings.osrm_timeout_seg)
    return None


def construir_geocodificador(settings: Settings) -> GeocodificadorPort:
    return GeocodificadorNominatim(
        url_base=settings.nominatim_url_base,
        timeout_seg=settings.nominatim_timeout_seg,
        user_agent=settings.nominatim_user_agent,
        limitador=LimitadorRitmo(min_intervalo_seg=settings.nominatim_min_intervalo_seg),
    )


def construir_contenedor(
    settings: Settings | None = None,
    grafo: GrafoVial | None = None,
    auditoria: AuditoriaPort | None = None,
) -> tuple[ResolverRuta, AnalizarZonas]:
    """Sigue devolviendo un par (no un trío): ``agente_orquestador`` hace
    ``AdaptadorGeoespacial(*construido)`` esperando exactamente estos dos casos
    de uso, y no está en el alcance de este cambio tocar esa integración. El
    geocodificador (nuevo) se construye aparte con ``construir_geocodificador``
    y se pasa a ``crear_app`` como segundo argumento cuando se necesite —
    ``main.py`` sigue montando este agente sin cambios, solo que sin
    geocodificación activa (``/geocodificar`` responde 503 en ese caso).
    """
    settings = settings or Settings()
    grafo = grafo or grafo_demo()
    compartida = auditoria or AuditoriaMemoria()

    perfil = PerfilVelocidad(valores_kmh=settings.perfil_velocidad)
    motor_rutas = MotorRutas(
        grafo=grafo,
        perfil_velocidad=perfil,
        radio_conexion_km=settings.radio_conexion_km,
        max_alternativas=settings.max_alternativas,
    )
    motor_zonas = MotorZonas(tamano_celda_grados=settings.tamano_celda_grados)

    resolver_ruta = ResolverRuta(
        motor=motor_rutas,
        llm=construir_llm(settings),
        publicador=PublicadorLog(),
        auditoria=compartida,
        ruteador=construir_ruteador(settings),
    )
    analizar_zonas = AnalizarZonas(motor=motor_zonas)

    return resolver_ruta, analizar_zonas
