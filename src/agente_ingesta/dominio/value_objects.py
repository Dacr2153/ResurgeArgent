"""Value objects del dominio. Sin dependencias externas más allá de ``nucleo``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MotivoDescarte(StrEnum):
    """Por qué un reporte no entró. Se audita siempre junto al descarte.

    Distinguir el motivo (en vez de un booleano "descartado") es lo que permite
    a un operador humano diferenciar, en el log de auditoría, un problema de
    calidad de datos (``FORMATO_INVALIDO``) de una decisión deliberada de
    protección del sistema bajo carga (``SATURACION_VENTANA``).
    """

    FORMATO_INVALIDO = "formato_invalido"
    TEXTO_VACIO = "texto_vacio"
    FUENTE_NO_IDENTIFICADA = "fuente_no_identificada"
    UBICACION_INVALIDA = "ubicacion_invalida"
    REENVIO_DUPLICADO = "reenvio_duplicado"
    SATURACION_VENTANA = "saturacion_ventana"


@dataclass(frozen=True, slots=True)
class ConfigVentana:
    """Parámetros de back-pressure: cuántos reportes caben por ventana de tiempo.

    El límite existe para degradar con criterio ante saturación (SRE Book,
    "Handling Overload") en vez de aceptar sin control y arriesgar el resto del
    sistema. ``segundos`` define la ventana deslizante sobre la que se cuenta.
    """

    limite: int
    segundos: float

    def __post_init__(self) -> None:
        if self.limite <= 0:
            raise ValueError("ConfigVentana.limite debe ser mayor que 0")
        if self.segundos <= 0:
            raise ValueError("ConfigVentana.segundos debe ser mayor que 0")
