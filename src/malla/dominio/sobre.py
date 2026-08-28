"""El sobre de malla: lo que viaja de teléfono en teléfono.

En un desastre lo primero que cae son las comunicaciones. La malla asume que no
hay servidor: cada nodo reenvía a sus vecinos hasta que alguno con salida a
internet sube lo acumulado. Ese modelo de rumor (*epidemic routing*, Vahdat y
Becker 2000) necesita tres cosas del sobre y solo tres:

- un identificador **estable** del mensaje, para que el mismo reporte llegando
  por tres caminos colapse en uno;
- un límite de vida, para que el rumor no circule para siempre;
- una firma del origen, porque el sobre atraviesa teléfonos de desconocidos.

El identificador no se inventa aquí: se deriva de `ReporteCrudo.hash_idempotencia`,
que ya redondea la ubicación a ~100 m para absorber la oscilación del GPS. Que
sea la misma primitiva que usa Ingesta es lo que hace que un reporte deduplicado
en la malla siga estando deduplicado cuando llega a la nube.

El sobre es inmutable. Retransmitir no muta: produce un sobre nuevo con un salto
más (`avanzar`). Los campos que cambian al retransmitir — `saltos` y `ruta` —
quedan deliberadamente **fuera** de la firma; todo lo demás va dentro.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from malla.dominio.excepciones import SobreInvalidoError
from nucleo.mensajes import ahora

VERSION_SOBRE = "1.0"

# Tipos de carga que la malla entiende. Cualquier otro se transporta igual: la
# malla no interpreta el contenido, solo lo mueve.
CARGA_REPORTE = "reporte"
CARGA_ACUSE = "acuse"


def canonicalizar(dato: Any) -> bytes:
    """Serialización canónica y estable, para firmar y para derivar ids.

    Claves ordenadas y sin espacios: dos nodos que serialicen el mismo
    diccionario deben producir byte a byte lo mismo, o la firma fallaría por
    razones que no tienen nada que ver con el contenido.
    """
    return json.dumps(dato, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def derivar_id_mensaje(carga: dict[str, Any]) -> str:
    """Identificador del mensaje, igual en toda la red para el mismo reporte.

    Si la carga trae `hash_idempotencia` (todo `ReporteCrudo.a_dict()` lo trae),
    ese es el id. No se inventa otra huella: reutilizar la del núcleo es lo que
    garantiza que el mismo reporte por tres caminos sea un solo mensaje.
    """
    huella = carga.get("hash_idempotencia")
    if isinstance(huella, str) and huella:
        return huella
    return hashlib.sha256(canonicalizar(carga)).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class SobreMalla:
    """Un mensaje en tránsito por la malla.

    `ttl` se fija en origen y no cambia; lo que sube es `saltos`. Hacerlo así (y
    no decrementar el ttl) permite firmarlo: un retransmisor no puede inflar la
    vida del mensaje para inundar la red sin romper la firma.
    """

    carga: dict[str, Any]
    nodo_origen: str
    clave_publica_origen: str
    firma: str
    id_mensaje: str
    ttl: int
    momento_origen: datetime = field(default_factory=ahora)
    saltos: int = 0
    ruta: tuple[str, ...] = ()
    tipo_carga: str = CARGA_REPORTE
    version: str = VERSION_SOBRE

    def __post_init__(self) -> None:
        if not self.id_mensaje:
            raise SobreInvalidoError("el sobre requiere id_mensaje")
        if not self.nodo_origen.strip():
            raise SobreInvalidoError("el sobre requiere nodo_origen")
        if self.ttl < 1:
            raise SobreInvalidoError(f"ttl debe ser >= 1: {self.ttl}")
        if self.saltos < 0:
            raise SobreInvalidoError(f"saltos no puede ser negativo: {self.saltos}")

    @property
    def contenido_firmado(self) -> bytes:
        """Los bytes exactos que cubre la firma.

        Van dentro la carga, el origen, el momento, el ttl y el id. Quedan fuera
        `saltos` y `ruta` porque cambian legítimamente en cada retransmisión: si
        entraran, ningún sobre reenviado verificaría jamás.
        """
        return canonicalizar(
            {
                "version": self.version,
                "id_mensaje": self.id_mensaje,
                "tipo_carga": self.tipo_carga,
                "nodo_origen": self.nodo_origen,
                "momento_origen": self.momento_origen.isoformat(),
                "ttl": self.ttl,
                "carga": self.carga,
            }
        )

    @property
    def vida_agotada(self) -> bool:
        """Cierto cuando el sobre ya dio todos los saltos que tenía."""
        return self.saltos >= self.ttl

    def avanzar(self, id_nodo: str) -> SobreMalla:
        """Sobre equivalente con un salto más y este nodo anotado en la ruta."""
        return replace(self, saltos=self.saltos + 1, ruta=(*self.ruta, id_nodo))

    def paso_por(self, id_nodo: str) -> bool:
        """Cierto si el nodo ya retransmitió este sobre (o lo originó)."""
        return id_nodo == self.nodo_origen or id_nodo in self.ruta

    def a_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "id_mensaje": self.id_mensaje,
            "tipo_carga": self.tipo_carga,
            "nodo_origen": self.nodo_origen,
            "clave_publica_origen": self.clave_publica_origen,
            "firma": self.firma,
            "momento_origen": self.momento_origen.isoformat(),
            "ttl": self.ttl,
            "saltos": self.saltos,
            "ruta": list(self.ruta),
            "carga": self.carga,
        }

    @classmethod
    def desde_dict(cls, dato: dict[str, Any]) -> SobreMalla:
        """Reconstruye un sobre recibido por la red. No confía en el emisor."""
        try:
            return cls(
                carga=dict(dato["carga"]),
                nodo_origen=str(dato["nodo_origen"]),
                clave_publica_origen=str(dato["clave_publica_origen"]),
                firma=str(dato["firma"]),
                id_mensaje=str(dato["id_mensaje"]),
                ttl=int(dato["ttl"]),
                momento_origen=datetime.fromisoformat(str(dato["momento_origen"])),
                saltos=int(dato.get("saltos", 0)),
                ruta=tuple(str(n) for n in dato.get("ruta", ())),
                tipo_carga=str(dato.get("tipo_carga", CARGA_REPORTE)),
                version=str(dato.get("version", VERSION_SOBRE)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SobreInvalidoError(f"sobre mal formado: {exc}") from exc
