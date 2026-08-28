"""Entidades de los dominios de plataforma.

Aquí no hay agentes ni LLM: son los cuatro dominios que el sistema necesita para
funcionar de punta a punta y que nadie más cubre —voluntarios, misiones,
recuperación y cola de sincronización—. Todo es determinista y persistible.

Las entidades son inmutables y el estado que cambia se modela como una entidad
nueva (`ReporteEncolado.marcar_enviado`). Un reporte encolado sin red es
evidencia de que alguien pidió ayuda y no había cobertura: mutarlo en sitio
borraría el momento en que se encoló, que es justo lo que hay que poder auditar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from nucleo.geo import Punto, haversine
from nucleo.mensajes import ahora, nuevo_id

#: Velocidad media por modo de desplazamiento, en km/h. Son valores urbanos de
#: emergencia, no de tráfico normal: el ETA que ve un voluntario tiene que ser
#: pesimista, porque llegar tarde a una hora anunciada es peor que anunciar más.
VELOCIDAD_KMH: dict[str, float] = {
    "a pie": 4.5,
    "bicicleta": 12.0,
    "moto": 25.0,
    "vehiculo": 20.0,
}

#: Velocidad de reserva para un modo no catalogado. Se usa la del peatón porque
#: es la única que nunca sobreestima.
VELOCIDAD_POR_DEFECTO = 4.5


class EstadoVoluntario(StrEnum):
    """Un voluntario no opera hasta que alguien verifica quién es.

    El registro no habilita: habilita la verificación. Un sistema que despacha a
    desconocidos a casas de damnificados es un riesgo, no una ayuda.
    """

    EN_VERIFICACION = "en_verificacion"
    VERIFICADO = "verificado"
    RECHAZADO = "rechazado"


class Horizonte(StrEnum):
    """Plazo de un paso del plan de recuperación.

    El orden de declaración es el orden en que se le presentan al damnificado:
    primero lo que puede hacer hoy. Un plan que empieza por el trámite de 15 días
    se lee como una espera, no como una salida.
    """

    HOY = "HOY"
    H72 = "72 H"
    D15 = "15 DÍAS"


@dataclass(frozen=True, slots=True)
class Voluntario:
    """Persona que se ofrece con un recurso concreto."""

    nombre_completo: str
    documento: str
    telefono: str
    recurso: str
    id: str = field(default_factory=nuevo_id)
    estado: EstadoVoluntario = EstadoVoluntario.EN_VERIFICACION
    registrado_en: datetime = field(default_factory=ahora)

    def __post_init__(self) -> None:
        if not self.nombre_completo.strip():
            raise ValueError("el voluntario requiere un nombre")
        if not self.documento.strip():
            raise ValueError("el voluntario requiere un documento de identidad")
        if not self.telefono.strip():
            raise ValueError("el voluntario requiere un teléfono de contacto")


@dataclass(frozen=True, slots=True)
class ItemChecklist:
    """Elemento que el voluntario debe llevar o confirmar antes de salir."""

    clave: str
    etiqueta: str


@dataclass(frozen=True, slots=True)
class Mision:
    """Encargo abierto sobre un incidente, listo para que alguien lo tome."""

    incidente_id: str
    titulo: str
    direccion: str
    ubicacion: Punto
    necesidad: str = ""
    puntuacion: int = 0
    modo: str = "a pie"
    ruta: tuple[tuple[float, float], ...] = ()
    checklist: tuple[ItemChecklist, ...] = ()
    abierta: bool = True
    creada_en: datetime = field(default_factory=ahora)

    def distancia_km(self, desde: Punto) -> float:
        """Distancia real sobre la superficie terrestre, no en línea de cuadrícula."""
        return haversine(desde.lat, desde.lon, self.ubicacion.lat, self.ubicacion.lon)

    def eta_min(self, desde: Punto) -> int:
        """Minutos estimados de llegada según el modo declarado.

        Se redondea hacia arriba: un ETA de 8,2 minutos anunciado como 8 llega
        tarde siempre, y el voluntario pierde la confianza en el número.
        """
        velocidad = VELOCIDAD_KMH.get(self.modo, VELOCIDAD_POR_DEFECTO)
        return int(math.ceil(self.distancia_km(desde) / velocidad * 60.0))

    def antiguedad_min(self, momento: datetime | None = None) -> int:
        """Minutos transcurridos desde que se abrió la misión."""
        transcurrido = (momento or ahora()) - self.creada_en
        return max(0, int(transcurrido.total_seconds() // 60))


@dataclass(frozen=True, slots=True)
class PreguntaRecuperacion:
    """Pregunta del cuestionario de recuperación, con sus opciones cerradas.

    Las opciones son cerradas porque las reglas del plan se disparan sobre ellas:
    una respuesta libre no sería derivable de forma determinista y el plan
    dejaría de ser explicable.
    """

    id: str
    pregunta: str
    opciones: tuple[str, ...]
    orden: int = 0


@dataclass(frozen=True, slots=True)
class PasoPlan:
    """Un paso de la hoja de ruta de recuperación."""

    horizonte: Horizonte
    titulo: str
    cuerpo: str


@dataclass(frozen=True, slots=True)
class ReporteEncolado:
    """Reporte que se creó sin red y espera a poder salir."""

    titulo: str
    meta: str
    puntuacion: int = 0
    id: str = field(default_factory=nuevo_id)
    encolado_en: datetime = field(default_factory=ahora)
    enviado_en: datetime | None = None
    carga: dict[str, Any] = field(default_factory=dict)

    @property
    def pendiente(self) -> bool:
        return self.enviado_en is None

    def marcar_enviado(self, momento: datetime | None = None) -> ReporteEncolado:
        """Devuelve la misma entrada ya enviada, conservando cuándo se encoló."""
        return ReporteEncolado(
            titulo=self.titulo,
            meta=self.meta,
            puntuacion=self.puntuacion,
            id=self.id,
            encolado_en=self.encolado_en,
            enviado_en=momento or ahora(),
            carga=self.carga,
        )


@dataclass(frozen=True, slots=True)
class HitoOperacion:
    """Una transición ya ocurrida en la operación del Orquestador."""

    estado: str
    momento: datetime
    motivo: str
    aplicada: bool


@dataclass(frozen=True, slots=True)
class EstadoOperacion:
    """Foto neutral de una operación del Orquestador.

    Plataforma no importa las entidades del Orquestador: recibe esta proyección.
    Así el recorrido que ve el ciudadano se deriva de datos, no de la máquina de
    estados de otro agente, y un cambio interno del Orquestador no obliga a tocar
    este dominio.
    """

    incidente_id: str
    estado: str
    titulo: str
    puntuacion: float | None = None
    hitos: tuple[HitoOperacion, ...] = ()


@dataclass(frozen=True, slots=True)
class PasoSeguimiento:
    """Un peldaño del recorrido que ve quien reportó."""

    etiqueta: str
    meta: str
    hecho: bool


@dataclass(frozen=True, slots=True)
class ReporteSeguimiento:
    """Estado de un reporte tal y como se le muestra a quien lo envió."""

    id: str
    titulo: str
    puntuacion: int
    pasos: tuple[PasoSeguimiento, ...]
    mensajes_sin_leer: int
