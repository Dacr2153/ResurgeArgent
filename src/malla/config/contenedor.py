"""Inyección de dependencias del nodo de malla (wiring)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from malla.adaptadores.salida.almacen_sqlite import AlmacenSQLite
from malla.adaptadores.salida.nube_http import NubeHTTP
from malla.adaptadores.salida.transporte_http import TransporteHTTP
from malla.aplicacion.casos_uso.originar_reporte import OriginarReporte
from malla.aplicacion.casos_uso.recibir_sobre import RecibirSobre
from malla.aplicacion.casos_uso.sincronizar_con_nube import SincronizarConNube
from malla.aplicacion.puertos.salida import AlmacenSobresPort, NubePort, TransportePort
from malla.config.settings import Settings
from malla.dominio.firma import IdentidadNodo, cargar_o_crear_identidad
from malla.dominio.motor_malla import MotorMalla
from malla.dominio.vecino import Vecino
from nucleo.auditoria import AuditoriaJSONL
from nucleo.puertos import AuditoriaPort


class SinNube:
    """Nube para un nodo sin salida a internet.

    No es un caso degradado: es el estado normal de casi todos los nodos de la
    malla, y por eso tiene una implementación explícita en vez de un `None` que
    haya que comprobar en cada llamada.
    """

    async def disponible(self) -> bool:
        return False

    async def subir(self, sobres: list) -> list[str]:
        return []


@dataclass(frozen=True, slots=True)
class Contenedor:
    """Todo lo que necesita el adaptador REST, ya cableado."""

    identidad: IdentidadNodo
    motor: MotorMalla
    almacen: AlmacenSobresPort
    transporte: TransportePort
    nube: NubePort
    auditoria: AuditoriaPort
    recibir: RecibirSobre
    originar: OriginarReporte
    sincronizar: SincronizarConNube


def _vecino_desde_url(url: str, capacidad: int) -> Vecino:
    """Vecino provisional a partir de su URL.

    El identificador real se resuelve preguntándole al vecino (`GET /nodo`); el
    derivado de la URL solo sirve hasta ese momento.
    """
    provisional = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return Vecino(id_nodo=provisional, direccion=url, capacidad_lote=capacidad)


def construir_contenedor(
    settings: Settings | None = None,
    almacen: AlmacenSobresPort | None = None,
    transporte: TransportePort | None = None,
    nube: NubePort | None = None,
    auditoria: AuditoriaPort | None = None,
) -> Contenedor:
    """Cablea un nodo completo. Los argumentos permiten sustituir adaptadores en tests."""
    settings = settings or Settings()

    identidad = cargar_o_crear_identidad(settings.ruta_identidad)
    motor = MotorMalla(
        id_nodo=identidad.id_nodo,
        ttl_por_defecto=settings.ttl_por_defecto,
        ttl_maximo_aceptado=settings.ttl_maximo_aceptado,
    )
    almacen = almacen or AlmacenSQLite(settings.ruta_almacen)
    transporte = transporte or TransporteHTTP(
        [_vecino_desde_url(url, settings.capacidad_lote) for url in settings.lista_vecinos],
        sondear=settings.sondear_vecinos,
    )
    nube = nube or (
        NubeHTTP(settings.url_nube, settings.ruta_subida_nube) if settings.url_nube else SinNube()
    )
    auditoria = auditoria or AuditoriaJSONL(settings.ruta_auditoria)

    return Contenedor(
        identidad=identidad,
        motor=motor,
        almacen=almacen,
        transporte=transporte,
        nube=nube,
        auditoria=auditoria,
        recibir=RecibirSobre(motor, almacen, transporte, auditoria),
        originar=OriginarReporte(identidad, motor, almacen, transporte, auditoria),
        sincronizar=SincronizarConNube(
            identidad,
            motor,
            almacen,
            nube,
            transporte,
            auditoria,
            tamano_lote=settings.tamano_lote_nube,
        ),
    )
