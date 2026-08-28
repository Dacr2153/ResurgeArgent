"""Adaptadores de auditoría compartidos.

`AuditoriaJSONL` escribe una línea por evento: formato append-only, legible con
`tail -f` durante una emergencia y trivial de cargar después para el análisis
post-operación. `AuditoriaMemoria` sirve a los tests. `AuditoriaSQLite` existe
porque el JSONL no se consulta: contar los descartes de una correlación obliga a
releer el archivo entero, y el tablero del coordinador lo pide en cada refresco.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento


class AuditoriaMemoria:
    """Acumula eventos en memoria. Para tests y modo offline."""

    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    async def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(evento)

    def por_tipo(self, tipo: str) -> list[EventoAuditoria]:
        return [e for e in self.eventos if str(e.tipo) == tipo]

    def por_correlacion(self, correlacion_id: str) -> list[EventoAuditoria]:
        return [e for e in self.eventos if e.correlacion_id == correlacion_id]


class AuditoriaJSONL:
    """Escribe cada evento como una línea JSON en un archivo append-only."""

    def __init__(self, ruta: Path | str) -> None:
        self._ruta = Path(ruta)
        self._ruta.parent.mkdir(parents=True, exist_ok=True)

    async def registrar(self, evento: EventoAuditoria) -> None:
        linea = json.dumps(evento.a_dict(), ensure_ascii=False)
        with self._ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")

    def leer(self) -> list[dict]:
        if not self._ruta.exists():
            return []
        with self._ruta.open(encoding="utf-8") as archivo:
            return [json.loads(linea) for linea in archivo if linea.strip()]


#: Esquema de la traza en SQLite. `correlacion_id` y `tipo` van indexados porque
#: son las dos únicas formas en que el sistema relee la auditoría: reconstruir una
#: operación completa y contar descartes de ingesta.
ESQUEMA_AUDITORIA = """
CREATE TABLE IF NOT EXISTS eventos_auditoria (
    id              TEXT PRIMARY KEY,
    tipo            TEXT NOT NULL,
    agente          TEXT NOT NULL,
    correlacion_id  TEXT NOT NULL,
    momento         TEXT NOT NULL,
    detalle         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auditoria_correlacion
    ON eventos_auditoria (correlacion_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_tipo
    ON eventos_auditoria (tipo);
"""


class AuditoriaSQLite:
    """Traza persistida en SQLite: sobrevive al reinicio del proceso.

    Misma interfaz que `AuditoriaMemoria` (`registrar`, `por_tipo`,
    `por_correlacion`) porque el Orquestador usa las dos lecturas para contar
    descartes de ingesta, y `leer()` como `AuditoriaJSONL` para volcar la traza.

    La escritura es lo único asíncrono. `sqlite3` es una librería síncrona y
    bloqueante: llamarla directamente desde una corrutina congelaría el bucle de
    eventos justo cuando hay varios agentes delegando en paralelo, así que la
    inserción se delega a un hilo con `asyncio.to_thread`. Las lecturas se dejan
    síncronas a propósito: el Orquestador las invoca desde código síncrono
    (`ProcesarEmergencia._descartes`) y volverlas async rompería ese contrato.

    Se abre una conexión por operación en vez de reutilizar una. Un objeto
    `sqlite3.Connection` está atado al hilo que lo creó, y `asyncio.to_thread`
    usa un hilo distinto cada vez: compartir la conexión daría
    `ProgrammingError`. Abrir es barato frente al coste de la escritura a disco.
    """

    def __init__(self, ruta: Path | str) -> None:
        self._ruta = Path(ruta)
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.executescript(ESQUEMA_AUDITORIA)
            conexion.commit()

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        """Conexión de un solo uso, siempre cerrada.

        El gestor de contexto nativo de `sqlite3.Connection` confirma la
        transacción pero no cierra el descriptor; con una conexión por operación
        eso acabaría agotando los descriptores del proceso.
        """
        conexion = sqlite3.connect(self._ruta)
        try:
            yield conexion
        finally:
            conexion.close()

    async def registrar(self, evento: EventoAuditoria) -> None:
        await asyncio.to_thread(self._insertar, evento)

    def _insertar(self, evento: EventoAuditoria) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT OR REPLACE INTO eventos_auditoria "
                "(id, tipo, agente, correlacion_id, momento, detalle) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    evento.id,
                    str(evento.tipo),
                    str(evento.agente),
                    evento.correlacion_id,
                    evento.momento.isoformat(),
                    json.dumps(evento.detalle, ensure_ascii=False),
                ),
            )
            conexion.commit()

    def por_tipo(self, tipo: str) -> list[EventoAuditoria]:
        return self._consultar("WHERE tipo = ?", (tipo,))

    def por_correlacion(self, correlacion_id: str) -> list[EventoAuditoria]:
        return self._consultar("WHERE correlacion_id = ?", (correlacion_id,))

    def leer(self) -> list[dict]:
        """Traza completa como dicts, en el mismo formato que `AuditoriaJSONL`."""
        return [e.a_dict() for e in self._consultar("", ())]

    def _consultar(self, filtro: str, parametros: tuple) -> list[EventoAuditoria]:
        # `rowid` ordena por inserción real. Ordenar por `momento` empataría los
        # eventos que un mismo paso emite dentro del mismo microsegundo y la
        # traza dejaría de leerse en el orden en que ocurrió.
        consulta = (
            "SELECT id, tipo, agente, correlacion_id, momento, detalle "
            f"FROM eventos_auditoria {filtro} ORDER BY rowid"
        )
        with self._conexion() as conexion:
            filas = conexion.execute(consulta, parametros).fetchall()
        return [_evento_desde_fila(fila) for fila in filas]


def _evento_desde_fila(fila: tuple) -> EventoAuditoria:
    """Rehidrata un evento. Los enums se reconstruyen: el resto del sistema
    compara con `TipoEvento.X`, no con cadenas sueltas."""
    id_, tipo, agente, correlacion_id, momento, detalle = fila
    return EventoAuditoria(
        id=id_,
        tipo=TipoEvento(tipo),
        agente=Agente(agente),
        correlacion_id=correlacion_id,
        momento=datetime.fromisoformat(momento),
        detalle=json.loads(detalle),
    )
