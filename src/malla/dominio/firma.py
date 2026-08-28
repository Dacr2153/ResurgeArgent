"""Identidad del nodo y firma Ed25519 de los sobres.

Por qué se firma, y por qué solo en origen: un reporte de emergencia atraviesa
los teléfonos de desconocidos antes de llegar a alguien con internet. Un nodo
malicioso en medio del camino podría mover la ubicación de un derrumbe a otro
barrio, inflar el número de víctimas o inventar un incidente entero. La firma
del **originador** es lo único que lo impide: quien retransmite puede negarse a
reenviar, pero no puede alterar el contenido sin invalidar la firma, y no puede
falsificar una firma ajena sin la clave privada, que nunca sale del teléfono.

Los retransmisores no firman. Firmar en cada salto encarecería el reenvío
(varios milisegundos y bytes por salto) sin aportar nada: la propiedad que hace
falta es "esto es lo que dijo el origen", no "esto pasó por aquí". La ruta ya
queda registrada en el sobre para diagnóstico, sin pretensión criptográfica.

Ed25519 y no RSA: firmas de 64 bytes y claves de 32, verificación rápida en
hardware modesto. En un enlace de malla el tamaño del sobre es el presupuesto.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from malla.dominio.excepciones import IdentidadInvalidaError
from malla.dominio.sobre import CARGA_REPORTE, SobreMalla, derivar_id_mensaje
from nucleo.mensajes import ahora

TTL_POR_DEFECTO = 8


def _id_desde_clave(clave_publica_hex: str) -> str:
    """El id del nodo se deriva de su clave pública.

    Así un nodo no puede presentarse con el identificador de otro: cambiar el id
    exige cambiar la clave, y con ella la capacidad de firmar como el original.
    """
    return hashlib.sha256(bytes.fromhex(clave_publica_hex)).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class IdentidadNodo:
    """Par de claves del nodo. La privada nunca se serializa hacia la red."""

    id_nodo: str
    clave_publica: str
    _privada: Ed25519PrivateKey

    @classmethod
    def generar(cls) -> IdentidadNodo:
        privada = Ed25519PrivateKey.generate()
        return cls._desde_privada(privada)

    @classmethod
    def _desde_privada(cls, privada: Ed25519PrivateKey) -> IdentidadNodo:
        publica_hex = (
            privada.public_key()
            .public_bytes(Encoding.Raw, PublicFormat.Raw)
            .hex()
        )
        return cls(
            id_nodo=_id_desde_clave(publica_hex),
            clave_publica=publica_hex,
            _privada=privada,
        )

    def firmar(self, contenido: bytes) -> str:
        return self._privada.sign(contenido).hex()

    def bytes_privados(self) -> bytes:
        return self._privada.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def cargar_o_crear_identidad(ruta: Path | str) -> IdentidadNodo:
    """Identidad persistente del nodo, generada la primera vez que arranca.

    Debe sobrevivir a los reinicios: si el nodo cambiara de clave en cada
    arranque, todos los sobres que ya circulan con su firma quedarían huérfanos
    y su reputación como origen se perdería en cada cierre de la aplicación.

    El archivo se guarda con permisos 0600. Es una clave privada, no un caché.
    """
    ruta = Path(ruta)
    if ruta.exists():
        crudo = ruta.read_text(encoding="utf-8").strip()
        try:
            privada = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(crudo))
        except (ValueError, TypeError) as exc:
            raise IdentidadInvalidaError(f"identidad ilegible en {ruta}: {exc}") from exc
        return IdentidadNodo._desde_privada(privada)

    identidad = IdentidadNodo.generar()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(identidad.bytes_privados().hex(), encoding="utf-8")
    ruta.chmod(0o600)
    return identidad


def verificar_firma(clave_publica_hex: str, firma_hex: str, contenido: bytes) -> bool:
    """Verifica una firma Ed25519. Nunca lanza: una firma basura es un `False`.

    Los bytes llegan de la red, así que cualquier campo puede venir corrupto o
    manipulado a propósito. Que una excepción de parseo tumbe el nodo sería una
    denegación de servicio trivial de provocar.
    """
    try:
        publica = Ed25519PublicKey.from_public_bytes(bytes.fromhex(clave_publica_hex))
        publica.verify(bytes.fromhex(firma_hex), contenido)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def verificar_sobre(sobre: SobreMalla) -> bool:
    """Cierto si el sobre viene íntegro del nodo que dice haberlo originado.

    Comprueba también que la clave pública corresponda al `nodo_origen`
    declarado: sin eso, un atacante podría firmar con su propia clave y poner el
    identificador de otro nodo en el sobre.
    """
    if _id_desde_clave_segura(sobre.clave_publica_origen) != sobre.nodo_origen:
        return False
    return verificar_firma(sobre.clave_publica_origen, sobre.firma, sobre.contenido_firmado)


def _id_desde_clave_segura(clave_publica_hex: str) -> str | None:
    try:
        return _id_desde_clave(clave_publica_hex)
    except ValueError:
        return None


def crear_sobre_firmado(
    identidad: IdentidadNodo,
    carga: dict[str, Any],
    ttl: int = TTL_POR_DEFECTO,
    tipo_carga: str = CARGA_REPORTE,
    momento: datetime | None = None,
) -> SobreMalla:
    """Envuelve una carga en un sobre firmado por este nodo.

    Se construye primero sin firma para poder calcular `contenido_firmado` con
    los valores definitivos, y luego se sustituye. La firma cubre exactamente lo
    que se va a transmitir, no una aproximación.
    """
    sobre = SobreMalla(
        carga=carga,
        nodo_origen=identidad.id_nodo,
        clave_publica_origen=identidad.clave_publica,
        firma="",
        id_mensaje=derivar_id_mensaje(carga),
        ttl=ttl,
        momento_origen=momento or ahora(),
        tipo_carga=tipo_carga,
    )
    return replace(sobre, firma=identidad.firmar(sobre.contenido_firmado))
