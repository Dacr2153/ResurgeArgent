"""Inyección de dependencias (wiring) de plataforma.

Dos decisiones que no son obvias:

1. **El repositorio de operaciones se toma del Orquestador, no se duplica.** El
   seguimiento de un reporte tiene que decir lo que dice la operación real; una
   copia propia divergiría a la primera firma del coordinador. Con
   `AGENTE1_RUTA_SQLITE` apuntando al mismo archivo, funciona incluso si
   plataforma corre en otro proceso.

2. **El cuestionario no se siembra aquí.** El wiring es síncrono y abrir un
   bucle de eventos para escribir en disco durante el arranque es frágil; la
   siembra la hace `PlanificarRecuperacion` la primera vez que alguien pide las
   preguntas.
"""

from __future__ import annotations

from dataclasses import dataclass

from agente_orquestador.aplicacion.puertos.salida import RepositorioOperacionesPort
from agente_orquestador.config.contenedor import construir_repositorio
from agente_orquestador.config.settings import Settings as SettingsOrquestador
from nucleo.geo import Punto
from plataforma.adaptadores.salida.operaciones_orquestador import OperacionesDelOrquestador
from plataforma.adaptadores.salida.repositorio_memoria import (
    RepositorioMisionesMemoria,
    RepositorioRecuperacionMemoria,
    RepositorioSincronizacionMemoria,
    RepositorioVoluntariosMemoria,
)
from plataforma.adaptadores.salida.repositorio_sqlite import (
    RepositorioMisionesSQLite,
    RepositorioRecuperacionSQLite,
    RepositorioSincronizacionSQLite,
    RepositorioVoluntariosSQLite,
)
from plataforma.aplicacion.casos_uso.consultar_seguimiento import ConsultarSeguimiento
from plataforma.aplicacion.casos_uso.gestionar_misiones import GestionarMisiones
from plataforma.aplicacion.casos_uso.gestionar_sincronizacion import GestionarSincronizacion
from plataforma.aplicacion.casos_uso.gestionar_voluntarios import GestionarVoluntarios
from plataforma.aplicacion.casos_uso.planificar_recuperacion import PlanificarRecuperacion
from plataforma.config.settings import Settings


@dataclass
class Contenedor:
    """Todo lo que la capa de entrada necesita, ya cableado."""

    seguimiento: ConsultarSeguimiento
    voluntarios: GestionarVoluntarios
    misiones: GestionarMisiones
    recuperacion: PlanificarRecuperacion
    sincronizacion: GestionarSincronizacion
    base_operaciones: Punto


def construir_contenedor(
    settings: Settings | None = None,
    repositorio_operaciones: RepositorioOperacionesPort | None = None,
) -> Contenedor:
    settings = settings or Settings()

    if settings.ruta_sqlite:
        ruta = settings.ruta_sqlite
        voluntarios = RepositorioVoluntariosSQLite(ruta)
        misiones = RepositorioMisionesSQLite(ruta)
        recuperacion = RepositorioRecuperacionSQLite(ruta)
        sincronizacion = RepositorioSincronizacionSQLite(ruta)
    else:
        voluntarios = RepositorioVoluntariosMemoria()
        misiones = RepositorioMisionesMemoria()
        recuperacion = RepositorioRecuperacionMemoria()
        sincronizacion = RepositorioSincronizacionMemoria()

    operaciones = repositorio_operaciones or construir_repositorio(SettingsOrquestador())

    return Contenedor(
        seguimiento=ConsultarSeguimiento(OperacionesDelOrquestador(operaciones)),
        voluntarios=GestionarVoluntarios(voluntarios),
        misiones=GestionarMisiones(misiones, limite=settings.misiones_por_lote),
        recuperacion=PlanificarRecuperacion(recuperacion),
        sincronizacion=GestionarSincronizacion(sincronizacion),
        base_operaciones=Punto(lat=settings.base_lat, lon=settings.base_lon),
    )
