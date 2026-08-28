"""Almacén persistente de sobres en SQLite.

Sin esto no hay almacenar-y-reenviar que valga: si los pendientes viven en
memoria, cerrar la aplicación —o que el sistema la mate por falta de batería,
que es lo que pasa de verdad en una emergencia— borra los reportes que todavía
no habían encontrado un vecino con internet.

SQLite y no un archivo JSON porque la restricción de unicidad sobre
`id_mensaje` es exactamente la deduplicación que la malla necesita, y la da el
motor de base de datos en vez de un `if` que se puede colar entre dos hilos.

El acceso es síncrono dentro de métodos `async`. Es deliberado: son escrituras
de microsegundos contra un archivo local, y meter un pool asíncrono aquí añade
una dependencia y una clase de fallos a cambio de nada medible.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from malla.aplicacion.puertos.salida import RegistroSobre
from malla.dominio.sobre import SobreMalla

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sobres (
    secuencia   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_mensaje  TEXT NOT NULL UNIQUE,
    tipo_carga  TEXT NOT NULL,
    entregado   INTEGER NOT NULL DEFAULT 0,
    documento   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sobres_entregado ON sobres (entregado);
"""


class AlmacenSQLite:
    """Persistencia local de la malla."""

    def __init__(self, ruta: Path | str) -> None:
        self._ruta = Path(ruta)
        if str(self._ruta) != ":memory:":
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._conexion = sqlite3.connect(str(self._ruta), check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row
        self._conexion.executescript(ESQUEMA)
        self._conexion.commit()

    def cerrar(self) -> None:
        self._conexion.close()

    async def guardar(self, sobre: SobreMalla) -> bool:
        """Inserta el sobre. `False` si el `id_mensaje` ya existía.

        El `INSERT OR IGNORE` es la deduplicación: dos copias del mismo reporte
        llegando a la vez por dos enlaces no producen dos filas.
        """
        cursor = self._conexion.execute(
            "INSERT OR IGNORE INTO sobres (id_mensaje, tipo_carga, documento) VALUES (?, ?, ?)",
            (
                sobre.id_mensaje,
                sobre.tipo_carga,
                json.dumps(sobre.a_dict(), ensure_ascii=False),
            ),
        )
        self._conexion.commit()
        return cursor.rowcount > 0

    async def ids_vistos(self) -> frozenset[str]:
        filas = self._conexion.execute("SELECT id_mensaje FROM sobres").fetchall()
        return frozenset(fila["id_mensaje"] for fila in filas)

    async def pendientes(self, limite: int | None = None) -> list[SobreMalla]:
        consulta = "SELECT documento FROM sobres WHERE entregado = 0 ORDER BY secuencia"
        parametros: tuple = ()
        if limite is not None:
            consulta += " LIMIT ?"
            parametros = (limite,)
        filas = self._conexion.execute(consulta, parametros).fetchall()
        return [SobreMalla.desde_dict(json.loads(fila["documento"])) for fila in filas]

    async def listar_desde(self, secuencia: int, limite: int) -> list[RegistroSobre]:
        filas = self._conexion.execute(
            "SELECT secuencia, entregado, documento FROM sobres "
            "WHERE secuencia > ? ORDER BY secuencia LIMIT ?",
            (secuencia, limite),
        ).fetchall()
        return [
            RegistroSobre(
                secuencia=fila["secuencia"],
                sobre=SobreMalla.desde_dict(json.loads(fila["documento"])),
                entregado=bool(fila["entregado"]),
            )
            for fila in filas
        ]

    async def marcar_entregados(self, ids: list[str]) -> int:
        if not ids:
            return 0
        marcadores = ",".join("?" for _ in ids)
        cursor = self._conexion.execute(
            f"UPDATE sobres SET entregado = 1 WHERE id_mensaje IN ({marcadores})",
            tuple(ids),
        )
        self._conexion.commit()
        return cursor.rowcount

    async def ultima_secuencia(self) -> int:
        fila = self._conexion.execute("SELECT MAX(secuencia) AS s FROM sobres").fetchone()
        return int(fila["s"] or 0)

    async def contar_pendientes(self) -> int:
        fila = self._conexion.execute(
            "SELECT COUNT(*) AS n FROM sobres WHERE entregado = 0"
        ).fetchone()
        return int(fila["n"])
