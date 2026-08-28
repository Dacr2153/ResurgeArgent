"""Construcción de eventos de auditoría de la malla.

`nucleo.mensajes` no tiene un `Agente.MALLA` ni tipos de evento propios de la
red, y esos contratos se cambian con PR aparte porque los comparten los cuatro
agentes. Mientras tanto la malla se declara como parte de la ingesta —es
literalmente el camino por el que un reporte entra al sistema— y marca su
procedencia en `detalle["componente"]`, para que el log siga siendo filtrable
sin tocar el núcleo.
"""

from __future__ import annotations

from typing import Any

from malla.dominio.sobre import SobreMalla
from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento

COMPONENTE = "malla-p2p"


def evento(
    tipo: TipoEvento,
    correlacion_id: str,
    detalle: dict[str, Any],
) -> EventoAuditoria:
    return EventoAuditoria(
        tipo=tipo,
        agente=Agente.INGESTA,
        correlacion_id=correlacion_id,
        detalle={"componente": COMPONENTE, **detalle},
    )


def resumen_sobre(sobre: SobreMalla) -> dict[str, Any]:
    """Lo mínimo para reconstruir el camino de un sobre sin copiar la carga."""
    return {
        "id_mensaje": sobre.id_mensaje,
        "nodo_origen": sobre.nodo_origen,
        "tipo_carga": sobre.tipo_carga,
        "saltos": sobre.saltos,
        "ttl": sobre.ttl,
        "ruta": list(sobre.ruta),
    }
