"""Puertos de salida de plataforma (protocolos, como en el resto del repo).

Un puerto por dominio, y no un repositorio único: voluntarios, misiones,
recuperación y cola offline se guardan juntos hoy por comodidad de despliegue,
pero no comparten ciclo de vida. Separarlos deja abierto mover la cola offline a
otro almacén sin arrastrar a los demás.
"""

from __future__ import annotations

from typing import Protocol

from plataforma.dominio.entidades import (
    EstadoOperacion,
    Mision,
    PreguntaRecuperacion,
    ReporteEncolado,
    Voluntario,
)


class ConsultaOperacionesPort(Protocol):
    """Lectura del estado de una operación abierta en el Orquestador.

    Solo lectura y solo proyectada: plataforma informa del recorrido, nunca
    mueve un incidente de estado. Eso es competencia del Orquestador y de la
    firma del coordinador.
    """

    async def obtener(self, incidente_id: str) -> EstadoOperacion | None: ...


class RepositorioVoluntariosPort(Protocol):
    async def guardar(self, voluntario: Voluntario) -> None: ...

    async def obtener(self, voluntario_id: str) -> Voluntario | None: ...

    async def listar(self) -> list[Voluntario]: ...


class RepositorioMisionesPort(Protocol):
    async def guardar(self, mision: Mision) -> None: ...

    async def obtener(self, incidente_id: str) -> Mision | None: ...

    async def listar_abiertas(self) -> list[Mision]: ...


class RepositorioRecuperacionPort(Protocol):
    async def guardar_pregunta(self, pregunta: PreguntaRecuperacion) -> None: ...

    async def listar_preguntas(self) -> list[PreguntaRecuperacion]: ...


class RepositorioSincronizacionPort(Protocol):
    async def encolar(self, reporte: ReporteEncolado) -> None: ...

    async def pendientes(self) -> list[ReporteEncolado]: ...

    async def marcar_enviados(self, reportes: list[ReporteEncolado]) -> None: ...
