"""Repositorios en memoria: cumplen los puertos sin infraestructura.

Son el modo por defecto y el que usan las pruebas de los casos de uso. No
sustituyen a SQLite en un despliegue real: aquí un reinicio borra la cola de
reportes offline, que es exactamente el dato que no puede perderse.
"""

from __future__ import annotations

from plataforma.dominio.entidades import (
    Mision,
    PreguntaRecuperacion,
    ReporteEncolado,
    Voluntario,
)


class RepositorioVoluntariosMemoria:
    def __init__(self) -> None:
        self._voluntarios: dict[str, Voluntario] = {}

    async def guardar(self, voluntario: Voluntario) -> None:
        self._voluntarios[voluntario.id] = voluntario

    async def obtener(self, voluntario_id: str) -> Voluntario | None:
        return self._voluntarios.get(voluntario_id)

    async def listar(self) -> list[Voluntario]:
        return list(self._voluntarios.values())


class RepositorioMisionesMemoria:
    def __init__(self) -> None:
        self._misiones: dict[str, Mision] = {}

    async def guardar(self, mision: Mision) -> None:
        self._misiones[mision.incidente_id] = mision

    async def obtener(self, incidente_id: str) -> Mision | None:
        return self._misiones.get(incidente_id)

    async def listar_abiertas(self) -> list[Mision]:
        return [m for m in self._misiones.values() if m.abierta]


class RepositorioRecuperacionMemoria:
    def __init__(self) -> None:
        self._preguntas: dict[str, PreguntaRecuperacion] = {}

    async def guardar_pregunta(self, pregunta: PreguntaRecuperacion) -> None:
        self._preguntas[pregunta.id] = pregunta

    async def listar_preguntas(self) -> list[PreguntaRecuperacion]:
        return sorted(self._preguntas.values(), key=lambda p: (p.orden, p.id))


class RepositorioSincronizacionMemoria:
    def __init__(self) -> None:
        self._reportes: dict[str, ReporteEncolado] = {}

    async def encolar(self, reporte: ReporteEncolado) -> None:
        self._reportes[reporte.id] = reporte

    async def pendientes(self) -> list[ReporteEncolado]:
        return [r for r in self._reportes.values() if r.pendiente]

    async def marcar_enviados(self, reportes: list[ReporteEncolado]) -> None:
        for reporte in reportes:
            self._reportes[reporte.id] = reporte.marcar_enviado()
