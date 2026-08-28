"""Contratos de datos que cruzan las fronteras entre agentes.

Estos son los únicos tipos que un agente puede recibir de otro. Cada agente es
libre de tener sus propias entidades internas, pero en la frontera se habla este
lenguaje. Cambiar algo aquí rompe a los cuatro, así que se cambia con PR aparte.

Las taxonomías (`Categoria`, `Urgencia`, `Severidad`, `Certeza`) son literalmente
las de CAP 1.2 (OASIS), el estándar internacional de alertas de emergencia. No se
inventan valores propios: usarlas es lo que hace el sistema interoperable con
sistemas oficiales de alerta.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from nucleo.geo import Punto
from nucleo.mensajes import Agente, ahora, nuevo_id


class Categoria(StrEnum):
    """Categoría del evento. CAP 1.2, elemento <category>."""

    GEO = "Geo"
    MET = "Met"
    SAFETY = "Safety"
    SECURITY = "Security"
    RESCUE = "Rescue"
    FIRE = "Fire"
    HEALTH = "Health"
    ENV = "Env"
    TRANSPORT = "Transport"
    INFRA = "Infra"
    CBRNE = "CBRNE"
    OTHER = "Other"


class Urgencia(StrEnum):
    """Cuánto margen hay para responder. CAP 1.2, elemento <urgency>."""

    IMMEDIATE = "Immediate"
    EXPECTED = "Expected"
    FUTURE = "Future"
    PAST = "Past"
    UNKNOWN = "Unknown"


class Severidad(StrEnum):
    """Magnitud del daño. CAP 1.2, elemento <severity>."""

    EXTREME = "Extreme"
    SEVERE = "Severe"
    MODERATE = "Moderate"
    MINOR = "Minor"
    UNKNOWN = "Unknown"


class Certeza(StrEnum):
    """Confianza en que el evento ocurrió. CAP 1.2, elemento <certainty>."""

    OBSERVED = "Observed"
    LIKELY = "Likely"
    POSSIBLE = "Possible"
    UNLIKELY = "Unlikely"
    UNKNOWN = "Unknown"


class Canal(StrEnum):
    """Por dónde entró el reporte.

    SMS y USSD no son opcionales: en un desastre real la red de datos cae, y la
    nota de priorización del proyecto marca la baja conectividad como requisito
    de la ingesta, no como detalle.
    """

    APP = "app"
    WEB = "web"
    SMS = "sms"
    USSD = "ussd"
    WHATSAPP = "whatsapp"
    LLAMADA = "llamada"
    RADIO = "radio"
    SENSOR = "sensor"
    API_OFICIAL = "api_oficial"


class TipoFuente(StrEnum):
    """Quién reporta. Determina el peso base de credibilidad en Verificación."""

    CIUDADANO = "ciudadano"
    AFECTADO = "afectado"
    VOLUNTARIO = "voluntario"
    ORGANIZACION = "organizacion"
    AUTORIDAD = "autoridad"
    SENSOR = "sensor"


@dataclass(frozen=True, slots=True)
class Fuente:
    """Origen de un reporte, con su reputación conocida."""

    id: str
    tipo: TipoFuente
    nombre: str = ""
    reputacion: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.reputacion <= 1.0:
            raise ValueError(f"reputacion debe estar en [0,1]: {self.reputacion}")


@dataclass(frozen=True, slots=True)
class ReporteCrudo:
    """Salida del Agente de Ingesta: un reporte normalizado, aún sin verificar.

    'Crudo' significa que nadie ha juzgado todavía si es cierto, duplicado o viejo.
    Ingesta solo garantiza que está bien formado y que no entró dos veces.
    """

    texto: str
    fuente: Fuente
    canal: Canal
    ubicacion: Punto | None = None
    categoria: Categoria = Categoria.OTHER
    urgencia: Urgencia = Urgencia.UNKNOWN
    severidad: Severidad = Severidad.UNKNOWN
    certeza: Certeza = Certeza.UNKNOWN
    personas_afectadas: int | None = None
    necesidades: tuple[str, ...] = ()
    id: str = field(default_factory=nuevo_id)
    recibido_en: datetime = field(default_factory=ahora)
    ocurrido_en: datetime | None = None
    metadatos: dict[str, Any] = field(default_factory=dict)

    @property
    def hash_idempotencia(self) -> str:
        """Huella para descartar reenvíos del mismo reporte.

        Se calcula sobre fuente + texto + ubicación redondeada a ~100 m. El
        redondeo es deliberado: el GPS de un teléfono oscila entre envíos, y sin
        él el mismo reporte reenviado entraría como dos.
        """
        if self.ubicacion is None:
            geo = "sin-ubicacion"
        else:
            geo = f"{self.ubicacion.lat:.3f},{self.ubicacion.lon:.3f}"
        semilla = f"{self.fuente.id}|{self.texto.strip().lower()}|{geo}"
        return hashlib.sha256(semilla.encode("utf-8")).hexdigest()[:32]

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "texto": self.texto,
            "fuente": {
                "id": self.fuente.id,
                "tipo": str(self.fuente.tipo),
                "nombre": self.fuente.nombre,
                "reputacion": self.fuente.reputacion,
            },
            "canal": str(self.canal),
            "ubicacion": self.ubicacion.a_geojson() if self.ubicacion else None,
            "categoria": str(self.categoria),
            "urgencia": str(self.urgencia),
            "severidad": str(self.severidad),
            "certeza": str(self.certeza),
            "personas_afectadas": self.personas_afectadas,
            "necesidades": list(self.necesidades),
            "recibido_en": self.recibido_en.isoformat(),
            "ocurrido_en": self.ocurrido_en.isoformat() if self.ocurrido_en else None,
            "hash_idempotencia": self.hash_idempotencia,
            "metadatos": self.metadatos,
        }


@dataclass(frozen=True, slots=True)
class IncidenteVerificado:
    """Salida del Agente de Verificación: varios reportes colapsados en un hecho.

    `source_reports` es lo que hace auditable la fusión: permite reconstruir qué
    reportes originales sostienen este incidente y con qué confianza.
    """

    categoria: Categoria
    severidad: Severidad
    urgencia: Urgencia
    ubicacion: Punto
    confianza: float
    reportes_origen: tuple[str, ...]
    resumen: str = ""
    personas_afectadas: int | None = None
    necesidades: tuple[str, ...] = ()
    id: str = field(default_factory=nuevo_id)
    verificado_en: datetime = field(default_factory=ahora)
    vence_en: datetime | None = None
    metadatos: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confianza <= 1.0:
            raise ValueError(f"confianza debe estar en [0,1]: {self.confianza}")
        if not self.reportes_origen:
            raise ValueError("un incidente verificado requiere al menos un reporte de origen")

    @property
    def corroboraciones(self) -> int:
        """Cuántos reportes independientes sostienen el incidente."""
        return len(self.reportes_origen)

    def esta_vigente(self, momento: datetime | None = None) -> bool:
        """Un incidente caducado no debe seguir consumiendo recursos."""
        if self.vence_en is None:
            return True
        return (momento or ahora()) < self.vence_en

    def a_dict(self) -> dict[str, Any]:
        return {
            "verified_incident_id": self.id,
            "category": str(self.categoria),
            "severity": str(self.severidad),
            "urgency": str(self.urgencia),
            "location": self.ubicacion.a_geojson(),
            "confidence_score": round(self.confianza, 4),
            "source_reports": list(self.reportes_origen),
            "resumen": self.resumen,
            "personas_afectadas": self.personas_afectadas,
            "necesidades": list(self.necesidades),
            "verificado_en": self.verificado_en.isoformat(),
            "vence_en": self.vence_en.isoformat() if self.vence_en else None,
            "metadatos": self.metadatos,
        }


class ModoTransporte(StrEnum):
    AUTO = "auto"
    CAMION = "camion"
    MOTO = "moto"
    PEATON = "peaton"


@dataclass(frozen=True, slots=True)
class ConsultaGeo:
    """Petición del Orquestador al Agente Geoespacial."""

    origen: Punto
    destino: Punto
    modo: ModoTransporte = ModoTransporte.AUTO
    evitar_zonas: tuple[str, ...] = ()
    id: str = field(default_factory=nuevo_id)

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "origen": self.origen.a_geojson(),
            "destino": self.destino.a_geojson(),
            "modo": str(self.modo),
            "evitar_zonas": list(self.evitar_zonas),
        }


@dataclass(frozen=True, slots=True)
class RespuestaGeo:
    """Respuesta del Agente Geoespacial. La geometría va en GeoJSON estricto."""

    consulta_id: str
    accesible: bool
    distancia_km: float = 0.0
    duracion_min: float = 0.0
    geometria: dict[str, Any] = field(default_factory=dict)
    vias_evitadas: tuple[str, ...] = ()
    motivo: str = ""

    def a_dict(self) -> dict[str, Any]:
        return {
            "consulta_id": self.consulta_id,
            "accesible": self.accesible,
            "distancia_km": round(self.distancia_km, 3),
            "duracion_min": round(self.duracion_min, 2),
            "geometria": self.geometria,
            "vias_evitadas": list(self.vias_evitadas),
            "motivo": self.motivo,
        }


@dataclass(frozen=True, slots=True)
class DecisionHumana:
    """Firma del coordinador que autoriza una asignación.

    Existe porque un sistema que despacha rescates sin firma humana no lo adopta
    ninguna entidad: es el gate que el Orquestador exige para pasar de
    PENDIENTE_APROBACION a ASIGNADO.
    """

    incidente_id: str
    aprobada: bool
    coordinador_id: str
    justificacion: str
    id: str = field(default_factory=nuevo_id)
    momento: datetime = field(default_factory=ahora)

    def __post_init__(self) -> None:
        if not self.coordinador_id.strip():
            raise ValueError("una decisión humana requiere identificar al coordinador")
        if not self.aprobada and not self.justificacion.strip():
            raise ValueError("un rechazo debe justificarse")

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incidente_id": self.incidente_id,
            "aprobada": self.aprobada,
            "coordinador_id": self.coordinador_id,
            "justificacion": self.justificacion,
            "momento": self.momento.isoformat(),
            "firmante": str(Agente.HUMANO),
        }
