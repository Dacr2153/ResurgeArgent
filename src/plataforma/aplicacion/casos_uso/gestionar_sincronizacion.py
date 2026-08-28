"""Caso de uso: cola de reportes creados sin red."""

from __future__ import annotations

from plataforma.aplicacion.puertos.salida import RepositorioSincronizacionPort
from plataforma.dominio.entidades import ReporteEncolado


class GestionarSincronizacion:
    """Encola lo que no pudo salir y lo vacía cuando vuelve la cobertura."""

    def __init__(self, repositorio: RepositorioSincronizacionPort) -> None:
        self._repositorio = repositorio

    async def encolar(self, datos: dict) -> ReporteEncolado:
        reporte = ReporteEncolado(
            titulo=str(datos["titulo"]),
            meta=str(datos.get("meta", "")),
            puntuacion=int(datos.get("puntuacion", 0)),
            carga=dict(datos.get("carga", {})),
        )
        await self._repositorio.encolar(reporte)
        return reporte

    async def pendientes(self) -> list[ReporteEncolado]:
        return await self._repositorio.pendientes()

    async def vaciar(self) -> int:
        """Marca como enviados los pendientes y devuelve cuántos salieron.

        Se marcan, no se borran: un reporte que llegó tarde porque no había red
        sigue siendo evidencia de dónde falló la cobertura durante el desastre.
        """
        pendientes = await self._repositorio.pendientes()
        if not pendientes:
            return 0
        await self._repositorio.marcar_enviados(pendientes)
        return len(pendientes)
