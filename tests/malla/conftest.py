"""Utilidades compartidas por las pruebas de malla. Ninguna toca la red."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from malla.adaptadores.salida.almacen_memoria import AlmacenMemoria
from malla.aplicacion.casos_uso.originar_reporte import OriginarReporte
from malla.aplicacion.casos_uso.recibir_sobre import RecibirSobre
from malla.dominio.firma import IdentidadNodo
from malla.dominio.motor_malla import MotorMalla
from malla.dominio.sobre import SobreMalla
from malla.dominio.vecino import Vecino
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import Canal, Categoria, Fuente, ReporteCrudo, TipoFuente, Urgencia
from nucleo.geo import Punto


class TransporteFalso:
    """Transporte en memoria: entrega instantánea a nodos del mismo proceso.

    Cumple `TransportePort` sin heredar nada, que es justo lo que el diseño
    persigue: el dominio no distingue esto de un enlace Bluetooth real.
    """

    def __init__(self) -> None:
        self._destinos: dict[str, RecibirSobre] = {}
        self._capacidades: dict[str, int] = {}
        self.caidos: set[str] = set()
        self.enviados: list[tuple[str, str]] = []

    def conectar(self, id_nodo: str, receptor: RecibirSobre, capacidad_lote: int = 20) -> None:
        self._destinos[id_nodo] = receptor
        self._capacidades[id_nodo] = capacidad_lote

    async def vecinos(self) -> list[Vecino]:
        return [
            Vecino(
                id_nodo=id_nodo,
                direccion=f"memoria://{id_nodo}",
                capacidad_lote=self._capacidades[id_nodo],
            )
            for id_nodo in self._destinos
            if id_nodo not in self.caidos
        ]

    async def enviar(self, sobre: SobreMalla, vecino: Vecino) -> bool:
        self.enviados.append((vecino.id_nodo, sobre.id_mensaje))
        if vecino.id_nodo in self.caidos:
            return False
        receptor = self._destinos.get(vecino.id_nodo)
        if receptor is None:
            return False
        await receptor.recibir(sobre)
        return True


class TransporteMudo:
    """Nodo aislado: no alcanza a nadie. El caso normal de los primeros minutos."""

    async def vecinos(self) -> list[Vecino]:
        return []

    async def enviar(self, sobre: SobreMalla, vecino: Vecino) -> bool:
        return False


@dataclass
class NubeFalsa:
    """Nube que acepta todo, o que no está. Sin red."""

    hay_salida: bool = True
    recibidos: list[str] = field(default_factory=list)
    rechaza: set[str] = field(default_factory=set)

    async def disponible(self) -> bool:
        return self.hay_salida

    async def subir(self, sobres: list[SobreMalla]) -> list[str]:
        aceptados = []
        for sobre in sobres:
            if sobre.id_mensaje in self.rechaza:
                continue
            self.recibidos.append(sobre.id_mensaje)
            aceptados.append(sobre.id_mensaje)
        return aceptados


@dataclass
class Nodo:
    """Un nodo completo montado en memoria."""

    identidad: IdentidadNodo
    motor: MotorMalla
    almacen: AlmacenMemoria
    transporte: TransporteFalso
    auditoria: AuditoriaMemoria
    recibir: RecibirSobre
    originar: OriginarReporte

    @property
    def id(self) -> str:
        return self.identidad.id_nodo


def construir_nodo(ttl_por_defecto: int = 8) -> Nodo:
    identidad = IdentidadNodo.generar()
    motor = MotorMalla(identidad.id_nodo, ttl_por_defecto=ttl_por_defecto)
    almacen = AlmacenMemoria()
    transporte = TransporteFalso()
    auditoria = AuditoriaMemoria()
    recibir = RecibirSobre(motor, almacen, transporte, auditoria)
    originar = OriginarReporte(identidad, motor, almacen, transporte, auditoria)
    return Nodo(identidad, motor, almacen, transporte, auditoria, recibir, originar)


def enlazar(*nodos: Nodo) -> None:
    """Conecta todos los nodos entre sí (topología completa)."""
    for nodo in nodos:
        for otro in nodos:
            if otro.id != nodo.id:
                nodo.transporte.conectar(otro.id, otro.recibir)


def reporte(
    texto: str = "Se cayó el puente peatonal, hay gente atrapada",
    fuente_id: str = "ciudadano-1",
    tipo_fuente: TipoFuente = TipoFuente.CIUDADANO,
    urgencia: Urgencia = Urgencia.IMMEDIATE,
    lat: float = 4.6097,
    lon: float = -74.0817,
) -> ReporteCrudo:
    return ReporteCrudo(
        texto=texto,
        fuente=Fuente(id=fuente_id, tipo=tipo_fuente),
        canal=Canal.APP,
        ubicacion=Punto(lat=lat, lon=lon),
        categoria=Categoria.RESCUE,
        urgencia=urgencia,
    )


@pytest.fixture
def nodo() -> Nodo:
    return construir_nodo()
