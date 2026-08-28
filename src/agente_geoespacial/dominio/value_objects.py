"""Value objects del dominio geoespacial. Sin dependencias externas."""

from __future__ import annotations

from dataclasses import dataclass

from nucleo.esquemas import ModoTransporte


@dataclass(frozen=True)
class PerfilVelocidad:
    """Velocidad promedio (km/h) por modo de transporte.

    Es lo que convierte distancia en tiempo de viaje: el peso que usa el motor
    de rutas no es la distancia en sí, sino cuánto tarda recorrerla con el modo
    pedido en la consulta.
    """

    valores_kmh: dict[ModoTransporte, float]

    def __post_init__(self) -> None:
        for modo, valor in self.valores_kmh.items():
            if valor <= 0:
                raise ValueError(f"velocidad para {modo} debe ser positiva: {valor}")

    def kmh(self, modo: ModoTransporte) -> float:
        """Velocidad del modo pedido; cae a AUTO si el modo no está calibrado."""
        return self.valores_kmh.get(modo, self.valores_kmh[ModoTransporte.AUTO])


PERFIL_VELOCIDAD_DEFECTO = PerfilVelocidad(
    valores_kmh={
        ModoTransporte.AUTO: 40.0,
        ModoTransporte.CAMION: 30.0,
        ModoTransporte.MOTO: 45.0,
        ModoTransporte.PEATON: 5.0,
    }
)


@dataclass(frozen=True)
class CeldaId:
    """Identificador de una celda de la rejilla geográfica: (fila, columna).

    Es el mismo principio de indexación por celdas de H3 (hexágonos), aquí
    simplificado a un rectángulo de tamaño fijo en grados para no depender de una
    librería externa. Suficiente para agrupar incidentes por vecindad aproximada.
    """

    fila: int
    columna: int

    def como_str(self) -> str:
        return f"{self.fila}:{self.columna}"
