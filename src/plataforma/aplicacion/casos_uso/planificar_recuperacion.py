"""Caso de uso: cuestionario de recuperación y derivación del plan."""

from __future__ import annotations

from plataforma.aplicacion.puertos.salida import RepositorioRecuperacionPort
from plataforma.dominio.entidades import PasoPlan, PreguntaRecuperacion
from plataforma.dominio.reglas_recuperacion import CUESTIONARIO, derivar_plan


class PlanificarRecuperacion:
    """Sirve el cuestionario persistido y aplica las reglas sobre las respuestas."""

    def __init__(
        self,
        repositorio: RepositorioRecuperacionPort,
        cuestionario_base: tuple[PreguntaRecuperacion, ...] = CUESTIONARIO,
    ) -> None:
        self._repositorio = repositorio
        self._base = cuestionario_base

    async def preguntas(self) -> list[PreguntaRecuperacion]:
        """Cuestionario persistido, sembrado la primera vez que se pide.

        La siembra es perezosa y no ocurre en el wiring por dos razones: el
        cableado es síncrono y abrir un bucle de eventos allí para escribir en
        disco es frágil, y un cuestionario vacío no es un estado válido del
        sistema —sin preguntas no hay plan—. Solo se siembra si no hay ninguna,
        así que editar el cuestionario en base de datos no se pisa al arrancar.
        """
        guardadas = await self._repositorio.listar_preguntas()
        if guardadas:
            return guardadas
        for pregunta in self._base:
            await self._repositorio.guardar_pregunta(pregunta)
        return await self._repositorio.listar_preguntas()

    async def plan(self, respuestas: dict[str, str]) -> list[PasoPlan]:
        """Deriva la hoja de ruta. No toca el repositorio: es función pura.

        Se expone igualmente como caso de uso para que la API no dependa del
        módulo de reglas: el día que un plan haya que guardarlo o firmarlo, el
        cambio queda dentro de esta clase.
        """
        return derivar_plan(respuestas)
