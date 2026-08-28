"""Repositorio de operaciones en SQLite: el mismo puerto, pero con memoria larga.

El repositorio en memoria pierde todo al reiniciar el proceso. En una emergencia
eso significa que un incidente firmado por el coordinador desaparece si el
servicio se cae, y con él la evidencia de quién autorizó qué. Este adaptador
guarda cada operación completa —estado, historial, firma y triage— para que un
reinicio no borre nada.

Diferencia de semántica frente a `RepositorioOperacionesMemoria`, y es
deliberada: allí `obtener` devuelve la entidad viva y aquí devuelve una copia
rehidratada. Quien mute lo obtenido debe volver a llamar a `guardar`, que es lo
que ya hace `RegistrarDecisionHumana`.

`sqlite3` es síncrono y bloqueante: usarlo directamente desde una corrutina
congelaría el bucle de eventos mientras el disco responde. Toda operación va
envuelta en `asyncio.to_thread`. Y como un `sqlite3.Connection` queda atado al
hilo que lo abrió, se abre una conexión por operación en lugar de compartir una:
`to_thread` no garantiza el mismo hilo dos veces.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from agente_orquestador.dominio.entidades import Operacion, RegistroTransicion
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.value_objects import PuntuacionTriage
from nucleo.esquemas import DecisionHumana

#: `puntuacion` y `posicion_triage` se sacan del documento a columnas propias
#: para poder ordenar la cola del coordinador en SQL, sin rehidratar el lote
#: entero solo para compararlo.
ESQUEMA_OPERACIONES = """
CREATE TABLE IF NOT EXISTS operaciones (
    incidente_id    TEXT PRIMARY KEY,
    correlacion_id  TEXT NOT NULL,
    estado          TEXT NOT NULL,
    puntuacion      REAL,
    posicion_triage INTEGER,
    documento       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operaciones_correlacion
    ON operaciones (correlacion_id);
"""


class RepositorioOperacionesSQLite:
    """Cumple `RepositorioOperacionesPort` contra un archivo SQLite."""

    def __init__(self, ruta: Path | str) -> None:
        self._ruta = Path(ruta)
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.executescript(ESQUEMA_OPERACIONES)
            conexion.commit()

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        """Conexión de un solo uso, siempre cerrada.

        El gestor de contexto nativo de `sqlite3.Connection` confirma pero no
        cierra; con una conexión por operación eso agotaría los descriptores.
        """
        conexion = sqlite3.connect(self._ruta)
        try:
            yield conexion
        finally:
            conexion.close()

    # ------------------------------------------------------------------ puerto
    async def guardar(self, operacion: Operacion) -> None:
        await asyncio.to_thread(self._guardar, operacion)

    async def obtener(self, incidente_id: str) -> Operacion | None:
        return await asyncio.to_thread(self._obtener, incidente_id)

    async def por_correlacion(self, correlacion_id: str) -> list[Operacion]:
        return await asyncio.to_thread(self._por_correlacion, correlacion_id)

    async def listar(self) -> list[Operacion]:
        """Todas las operaciones, en orden de triage (posición 1 primero).

        Las que aún no pasaron por el triage van al final: no tienen posición y
        ponerlas arriba desplazaría a incidentes ya priorizados.
        """
        return await asyncio.to_thread(self._listar)

    # ------------------------------------------------------------------ interno
    def _guardar(self, operacion: Operacion) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT OR REPLACE INTO operaciones "
                "(incidente_id, correlacion_id, estado, puntuacion, posicion_triage, documento) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    operacion.incidente_id,
                    operacion.correlacion_id,
                    str(operacion.estado),
                    operacion.puntuacion.puntuacion if operacion.puntuacion else None,
                    operacion.puntuacion.posicion if operacion.puntuacion else None,
                    json.dumps(serializar(operacion), ensure_ascii=False),
                ),
            )
            conexion.commit()

    def _obtener(self, incidente_id: str) -> Operacion | None:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT documento FROM operaciones WHERE incidente_id = ?",
                (incidente_id,),
            ).fetchone()
        return deserializar(json.loads(fila[0])) if fila else None

    def _por_correlacion(self, correlacion_id: str) -> list[Operacion]:
        return self._consultar(
            "WHERE correlacion_id = ? ORDER BY rowid", (correlacion_id,)
        )

    def _listar(self) -> list[Operacion]:
        return self._consultar(
            "ORDER BY posicion_triage IS NULL, posicion_triage, rowid", ()
        )

    def _consultar(self, filtro: str, parametros: tuple) -> list[Operacion]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                f"SELECT documento FROM operaciones {filtro}", parametros
            ).fetchall()
        return [deserializar(json.loads(fila[0])) for fila in filas]


def serializar(operacion: Operacion) -> dict[str, Any]:
    """Vuelca la operación sin pérdida.

    No se reutiliza `Operacion.a_dict()`: esa vista es para el coordinador y
    redondea la puntuación de triage y omite `limite_visitas`. Rehidratar desde
    ella daría una operación parecida pero no la misma, y el orden de la cola
    podría cambiar tras un reinicio.
    """
    return {
        "incidente_id": operacion.incidente_id,
        "correlacion_id": operacion.correlacion_id,
        "estado": str(operacion.estado),
        "limite_visitas": operacion.limite_visitas,
        "visitas": {str(estado): veces for estado, veces in operacion.visitas.items()},
        "historial": [
            {
                "origen": str(r.origen),
                "solicitado": str(r.solicitado),
                "estado": str(r.estado),
                "aplicada": r.aplicada,
                "motivo": r.motivo,
                "momento": r.momento.isoformat(),
                "decision_id": r.decision_id,
            }
            for r in operacion.historial
        ],
        "decision": _serializar_decision(operacion.decision),
        "puntuacion": _serializar_puntuacion(operacion.puntuacion),
        "datos": operacion.datos,
    }


def deserializar(documento: dict[str, Any]) -> Operacion:
    """Reconstruye la operación tal cual se guardó."""
    return Operacion(
        incidente_id=documento["incidente_id"],
        correlacion_id=documento["correlacion_id"],
        estado=EstadoIncidente(documento["estado"]),
        limite_visitas=int(documento["limite_visitas"]),
        historial=[
            RegistroTransicion(
                origen=EstadoIncidente(r["origen"]),
                solicitado=EstadoIncidente(r["solicitado"]),
                estado=EstadoIncidente(r["estado"]),
                aplicada=bool(r["aplicada"]),
                motivo=r["motivo"],
                momento=datetime.fromisoformat(r["momento"]),
                decision_id=r["decision_id"],
            )
            for r in documento["historial"]
        ],
        visitas=Counter(
            {EstadoIncidente(k): v for k, v in documento["visitas"].items()}
        ),
        decision=_decision_desde(documento["decision"]),
        puntuacion=_puntuacion_desde(documento["puntuacion"]),
        datos=documento["datos"],
    )


def _serializar_decision(decision: DecisionHumana | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "id": decision.id,
        "incidente_id": decision.incidente_id,
        "aprobada": decision.aprobada,
        "coordinador_id": decision.coordinador_id,
        "justificacion": decision.justificacion,
        "momento": decision.momento.isoformat(),
    }


def _decision_desde(bruto: dict[str, Any] | None) -> DecisionHumana | None:
    if bruto is None:
        return None
    return DecisionHumana(
        id=bruto["id"],
        incidente_id=bruto["incidente_id"],
        aprobada=bruto["aprobada"],
        coordinador_id=bruto["coordinador_id"],
        justificacion=bruto["justificacion"],
        momento=datetime.fromisoformat(bruto["momento"]),
    )


def _serializar_puntuacion(puntuacion: PuntuacionTriage | None) -> dict[str, Any] | None:
    if puntuacion is None:
        return None
    return {
        "incidente_id": puntuacion.incidente_id,
        "puntuacion": puntuacion.puntuacion,
        "componentes": puntuacion.componentes,
        "posicion": puntuacion.posicion,
    }


def _puntuacion_desde(bruto: dict[str, Any] | None) -> PuntuacionTriage | None:
    if bruto is None:
        return None
    return PuntuacionTriage(
        incidente_id=bruto["incidente_id"],
        puntuacion=bruto["puntuacion"],
        componentes=bruto["componentes"],
        posicion=bruto["posicion"],
    )
