"""Caso de uso: misiones abiertas y su detalle."""

from __future__ import annotations

from nucleo.geo import Punto
from plataforma.aplicacion.puertos.salida import RepositorioMisionesPort
from plataforma.dominio.entidades import ItemChecklist, Mision
from plataforma.dominio.excepciones import RecursoDesconocidoError


class GestionarMisiones:
    """Filtra por distancia real y ordena por prioridad."""

    def __init__(self, repositorio: RepositorioMisionesPort, limite: int = 5) -> None:
        self._repositorio = repositorio
        self._limite = limite

    async def abrir(self, datos: dict) -> Mision:
        """Da de alta una misión sobre un incidente ya priorizado.

        Es la vía por la que el coordinador convierte un incidente en un encargo
        tomable; sin ella la lista de misiones no podría existir sin datos de
        ejemplo, que es justo lo que este paquete viene a eliminar.
        """
        mision = Mision(
            incidente_id=str(datos["incidente_id"]),
            titulo=str(datos["titulo"]),
            direccion=str(datos.get("direccion", "")),
            ubicacion=Punto(lat=float(datos["lat"]), lon=float(datos["lon"])),
            necesidad=str(datos.get("necesidad", "")),
            puntuacion=int(datos.get("puntuacion", 0)),
            modo=str(datos.get("modo", "a pie")),
            ruta=tuple((float(a), float(b)) for a, b in datos.get("ruta", ())),
            checklist=tuple(
                ItemChecklist(clave=str(i["clave"]), etiqueta=str(i["etiqueta"]))
                for i in datos.get("checklist", ())
            ),
        )
        await self._repositorio.guardar(mision)
        return mision

    async def listar(self, referencia: Punto, radio_km: float | None = None) -> list[Mision]:
        """Misiones abiertas dentro del radio, de mayor a menor prioridad.

        El radio se aplica con distancia Haversine sobre coordenadas reales, no
        con una caja de latitud/longitud: cerca del ecuador ambas coinciden, pero
        en latitudes altas la caja incluiría misiones a las que no se llega.

        El recorte a `limite` es lo último: primero se ordena por prioridad, para
        que el corte deje fuera lo menos urgente y no lo que llegó más tarde.
        """
        misiones = await self._repositorio.listar_abiertas()
        if radio_km is not None:
            misiones = [m for m in misiones if m.distancia_km(referencia) <= radio_km]
        misiones.sort(key=lambda m: (-m.puntuacion, m.distancia_km(referencia)))
        return misiones[: self._limite]

    async def detalle(self, incidente_id: str) -> Mision:
        mision = await self._repositorio.obtener(incidente_id)
        if mision is None:
            raise RecursoDesconocidoError(f"no hay misión para el incidente {incidente_id}")
        return mision
