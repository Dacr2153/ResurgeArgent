"""Extractor nulo: reglas de palabras clave, sin red y sin API key.

Cumple ``ExtractorPort`` con el mismo criterio que ``orquestador_nulo.py`` en
``agente_matching``: es lo que corre en CI, en tests y en modo offline. No
pretende ser tan bueno como el LLM — solo lo bastante determinista para que el
motor de dominio tenga algo que validar sin depender de una API externa.
"""

from __future__ import annotations

import re
from typing import Any

from nucleo.esquemas import Categoria, Certeza, Severidad, Urgencia

_PALABRAS_CATEGORIA: dict[Categoria, tuple[str, ...]] = {
    Categoria.FIRE: ("incendio", "fuego", "quemando", "llamas"),
    Categoria.GEO: ("inundacion", "inundación", "deslizamiento", "terremoto", "sismo", "avalancha"),
    Categoria.MET: ("tormenta", "huracan", "huracán", "vendaval", "granizo"),
    Categoria.HEALTH: ("herido", "heridos", "enfermo", "hospital", "salud", "epidemia"),
    Categoria.RESCUE: ("atrapado", "atrapados", "rescate", "auxilio", "socorro"),
    Categoria.SECURITY: ("robo", "saqueo", "violencia", "disturbio"),
    Categoria.TRANSPORT: ("carretera", "via", "vía", "puente", "bloqueado", "bloqueada"),
    Categoria.INFRA: ("electricidad", "energia", "energía", "acueducto", "torre caida"),
}

_PALABRAS_URGENCIA: dict[Urgencia, tuple[str, ...]] = {
    Urgencia.IMMEDIATE: ("ahora", "inmediato", "urgente", "ya", "socorro", "auxilio"),
    Urgencia.EXPECTED: ("pronto", "hoy", "en camino"),
    Urgencia.FUTURE: ("mañana", "despues", "después", "proximos dias", "próximos días"),
}

_PALABRAS_SEVERIDAD: dict[Severidad, tuple[str, ...]] = {
    Severidad.EXTREME: ("muerto", "muertos", "fallecido", "fallecidos", "masivo"),
    Severidad.SEVERE: ("grave", "critico", "crítico", "colapso", "colapsado", "destruido"),
    Severidad.MODERATE: ("dañado", "danado", "afectado", "parcial"),
    Severidad.MINOR: ("leve", "menor", "sin gravedad"),
}

_PALABRAS_CERTEZA_OBSERVADA = ("estoy viendo", "lo estoy viendo", "acabo de ver", "vi ", "aquí ")

_PALABRAS_NECESIDAD = (
    "agua",
    "comida",
    "alimento",
    "medicinas",
    "medicamentos",
    "refugio",
    "abrigo",
    "rescate",
    "atencion medica",
    "atención médica",
    "electricidad",
)

_RE_PERSONAS = re.compile(r"(\d+)\s*(?:personas?|heridos?|afectados?|familias?)", re.IGNORECASE)
_RE_COORDENADAS = re.compile(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")


class ExtractorNulo:
    """Estructura texto libre en español con reglas simples, sin llamadas externas."""

    async def extraer(self, texto: str, contexto: dict[str, Any]) -> dict[str, Any]:
        minusculas = texto.lower()

        resultado: dict[str, Any] = {
            "categoria": self._buscar(minusculas, _PALABRAS_CATEGORIA, Categoria.OTHER),
            "urgencia": self._buscar(minusculas, _PALABRAS_URGENCIA, Urgencia.UNKNOWN),
            "severidad": self._buscar(minusculas, _PALABRAS_SEVERIDAD, Severidad.UNKNOWN),
            "certeza": self._certeza(minusculas),
            "necesidades": self._necesidades(minusculas),
        }

        personas = _RE_PERSONAS.search(minusculas)
        if personas:
            resultado["personas_afectadas"] = int(personas.group(1))

        ubicacion = self._ubicacion(texto)
        if ubicacion is not None:
            resultado["ubicacion"] = ubicacion

        return resultado

    @staticmethod
    def _buscar(texto: str, tabla: dict, defecto: Any) -> Any:
        for valor, palabras in tabla.items():
            if any(palabra in texto for palabra in palabras):
                return valor
        return defecto

    @staticmethod
    def _certeza(texto: str) -> Certeza:
        if any(frase in texto for frase in _PALABRAS_CERTEZA_OBSERVADA):
            return Certeza.OBSERVED
        return Certeza.LIKELY

    @staticmethod
    def _necesidades(texto: str) -> tuple[str, ...]:
        return tuple(palabra for palabra in _PALABRAS_NECESIDAD if palabra in texto)

    @staticmethod
    def _ubicacion(texto: str) -> dict[str, float] | None:
        coincidencia = _RE_COORDENADAS.search(texto)
        if coincidencia is None:
            return None
        lat, lon = float(coincidencia.group(1)), float(coincidencia.group(2))
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            return {"lat": lat, "lon": lon}
        return None
