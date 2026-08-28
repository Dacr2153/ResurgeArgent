"""Caso de uso: alta de voluntarios."""

from __future__ import annotations

from plataforma.aplicacion.puertos.salida import RepositorioVoluntariosPort
from plataforma.dominio.entidades import EstadoVoluntario, Voluntario


class GestionarVoluntarios:
    """Registra el alta y la deja pendiente de verificación humana."""

    def __init__(self, repositorio: RepositorioVoluntariosPort) -> None:
        self._repositorio = repositorio

    async def registrar(self, datos: dict) -> Voluntario:
        """Persiste el alta. Nunca devuelve un voluntario ya habilitado.

        El estado inicial se fija aquí y no se toma del payload: si viniera de
        fuera, cualquiera podría auto-declararse verificado y saltarse el
        control que existe precisamente para proteger a los damnificados.
        """
        voluntario = Voluntario(
            nombre_completo=str(datos["nombre_completo"]).strip(),
            documento=str(datos["documento"]).strip(),
            telefono=str(datos["telefono"]).strip(),
            recurso=str(datos.get("recurso", "")).strip(),
            estado=EstadoVoluntario.EN_VERIFICACION,
        )
        await self._repositorio.guardar(voluntario)
        return voluntario

    async def listar(self) -> list[Voluntario]:
        return await self._repositorio.listar()
