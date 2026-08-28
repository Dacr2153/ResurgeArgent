"""Adaptador de lectura contra el repositorio de operaciones del Orquestador.

Traduce la `Operacion` del Orquestador a la proyección neutra que consume el
dominio de plataforma. La traducción vive aquí y no en el dominio a propósito: es
el único punto del paquete que conoce la forma interna de otro agente, y así un
cambio en su máquina de estados se absorbe en un archivo.

En un despliegue con `ruta_sqlite` compartida, el repositorio que se inyecta
apunta al mismo archivo que escribe el Orquestador: por eso el seguimiento
funciona aunque plataforma corra en otro proceso.
"""

from __future__ import annotations

from agente_orquestador.aplicacion.puertos.salida import RepositorioOperacionesPort
from agente_orquestador.dominio.entidades import Operacion
from plataforma.dominio.entidades import EstadoOperacion, HitoOperacion


class OperacionesDelOrquestador:
    """Cumple `ConsultaOperacionesPort` leyendo el repositorio del Agente 1."""

    def __init__(self, repositorio: RepositorioOperacionesPort) -> None:
        self._repositorio = repositorio

    async def obtener(self, incidente_id: str) -> EstadoOperacion | None:
        operacion = await self._repositorio.obtener(incidente_id)
        return proyectar(operacion) if operacion is not None else None


def proyectar(operacion: Operacion) -> EstadoOperacion:
    """Reduce la operación a lo que plataforma necesita mostrar."""
    return EstadoOperacion(
        incidente_id=operacion.incidente_id,
        estado=str(operacion.estado),
        titulo=titulo_de(operacion),
        puntuacion=operacion.puntuacion.puntuacion if operacion.puntuacion else None,
        hitos=tuple(
            HitoOperacion(
                estado=str(registro.estado),
                momento=registro.momento,
                motivo=registro.motivo,
                aplicada=registro.aplicada,
            )
            for registro in operacion.historial
        ),
    )


def titulo_de(operacion: Operacion) -> str:
    """Título legible del incidente.

    El Orquestador no guarda un título: guarda el resumen que dejó el agente de
    verificación en `datos`. Cuando no hay ninguno se cae al identificador, que
    es feo pero cierto; inventar un título haría que dos pantallas llamaran
    distinto al mismo incidente.
    """
    for clave in ("titulo", "resumen"):
        valor = operacion.datos.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return f"Reporte {operacion.incidente_id}"
