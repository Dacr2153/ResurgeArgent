"""Repositorios de plataforma sobre SQLite.

Todos comparten un archivo y una `BaseSQLite` que resuelve dos problemas del
mismo origen: `sqlite3` es síncrono y sus conexiones están atadas al hilo que
las abrió.

- **Bloqueo del bucle de eventos.** Una consulta a disco desde una corrutina
  detiene todo lo demás que la API esté sirviendo. Por eso cada operación se
  ejecuta con `asyncio.to_thread`.
- **Conexión por operación.** `asyncio.to_thread` no garantiza el mismo hilo dos
  veces, y reutilizar una conexión entre hilos lanza `ProgrammingError`. Abrir
  es barato comparado con la escritura, así que se abre y se cierra cada vez.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from nucleo.geo import Punto
from plataforma.dominio.entidades import (
    EstadoVoluntario,
    ItemChecklist,
    Mision,
    PreguntaRecuperacion,
    ReporteEncolado,
    Voluntario,
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS voluntarios (
    id              TEXT PRIMARY KEY,
    nombre_completo TEXT NOT NULL,
    documento       TEXT NOT NULL,
    telefono        TEXT NOT NULL,
    recurso         TEXT NOT NULL,
    estado          TEXT NOT NULL,
    registrado_en   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS misiones (
    incidente_id TEXT PRIMARY KEY,
    titulo       TEXT NOT NULL,
    direccion    TEXT NOT NULL,
    lat          REAL NOT NULL,
    lon          REAL NOT NULL,
    necesidad    TEXT NOT NULL,
    puntuacion   INTEGER NOT NULL,
    modo         TEXT NOT NULL,
    ruta         TEXT NOT NULL,
    checklist    TEXT NOT NULL,
    abierta      INTEGER NOT NULL,
    creada_en    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preguntas_recuperacion (
    id       TEXT PRIMARY KEY,
    pregunta TEXT NOT NULL,
    opciones TEXT NOT NULL,
    orden    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cola_sincronizacion (
    id          TEXT PRIMARY KEY,
    titulo      TEXT NOT NULL,
    meta        TEXT NOT NULL,
    puntuacion  INTEGER NOT NULL,
    encolado_en TEXT NOT NULL,
    enviado_en  TEXT,
    carga       TEXT NOT NULL
);
"""


class BaseSQLite:
    """Conexión y esquema compartidos por los cuatro repositorios."""

    def __init__(self, ruta: Path | str) -> None:
        self._ruta = Path(ruta)
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.executescript(ESQUEMA)
            conexion.commit()

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        """Conexión de un solo uso, siempre cerrada.

        El gestor nativo de `sqlite3.Connection` confirma pero no cierra; con una
        conexión por operación eso agotaría los descriptores del proceso.
        """
        conexion = sqlite3.connect(self._ruta)
        try:
            yield conexion
        finally:
            conexion.close()

    def _escribir(self, consulta: str, parametros: tuple) -> None:
        with self._conexion() as conexion:
            conexion.execute(consulta, parametros)
            conexion.commit()

    def _leer(self, consulta: str, parametros: tuple = ()) -> list[tuple]:
        with self._conexion() as conexion:
            return conexion.execute(consulta, parametros).fetchall()


class RepositorioVoluntariosSQLite(BaseSQLite):
    async def guardar(self, voluntario: Voluntario) -> None:
        await asyncio.to_thread(
            self._escribir,
            "INSERT OR REPLACE INTO voluntarios "
            "(id, nombre_completo, documento, telefono, recurso, estado, registrado_en) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                voluntario.id,
                voluntario.nombre_completo,
                voluntario.documento,
                voluntario.telefono,
                voluntario.recurso,
                str(voluntario.estado),
                voluntario.registrado_en.isoformat(),
            ),
        )

    async def obtener(self, voluntario_id: str) -> Voluntario | None:
        filas = await asyncio.to_thread(
            self._leer, f"{_SELECT_VOLUNTARIO} WHERE id = ?", (voluntario_id,)
        )
        return _voluntario(filas[0]) if filas else None

    async def listar(self) -> list[Voluntario]:
        filas = await asyncio.to_thread(self._leer, f"{_SELECT_VOLUNTARIO} ORDER BY rowid")
        return [_voluntario(f) for f in filas]


class RepositorioMisionesSQLite(BaseSQLite):
    async def guardar(self, mision: Mision) -> None:
        await asyncio.to_thread(
            self._escribir,
            "INSERT OR REPLACE INTO misiones "
            "(incidente_id, titulo, direccion, lat, lon, necesidad, puntuacion, modo, "
            "ruta, checklist, abierta, creada_en) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                mision.incidente_id,
                mision.titulo,
                mision.direccion,
                mision.ubicacion.lat,
                mision.ubicacion.lon,
                mision.necesidad,
                mision.puntuacion,
                mision.modo,
                json.dumps([list(p) for p in mision.ruta]),
                json.dumps([{"clave": i.clave, "etiqueta": i.etiqueta} for i in mision.checklist]),
                int(mision.abierta),
                mision.creada_en.isoformat(),
            ),
        )

    async def obtener(self, incidente_id: str) -> Mision | None:
        filas = await asyncio.to_thread(
            self._leer, f"{_SELECT_MISION} WHERE incidente_id = ?", (incidente_id,)
        )
        return _mision(filas[0]) if filas else None

    async def listar_abiertas(self) -> list[Mision]:
        filas = await asyncio.to_thread(
            self._leer, f"{_SELECT_MISION} WHERE abierta = 1 ORDER BY rowid"
        )
        return [_mision(f) for f in filas]


class RepositorioRecuperacionSQLite(BaseSQLite):
    async def guardar_pregunta(self, pregunta: PreguntaRecuperacion) -> None:
        await asyncio.to_thread(
            self._escribir,
            "INSERT OR REPLACE INTO preguntas_recuperacion (id, pregunta, opciones, orden) "
            "VALUES (?, ?, ?, ?)",
            (
                pregunta.id,
                pregunta.pregunta,
                json.dumps(list(pregunta.opciones), ensure_ascii=False),
                pregunta.orden,
            ),
        )

    async def listar_preguntas(self) -> list[PreguntaRecuperacion]:
        filas = await asyncio.to_thread(
            self._leer,
            "SELECT id, pregunta, opciones, orden FROM preguntas_recuperacion "
            "ORDER BY orden, id",
        )
        return [
            PreguntaRecuperacion(
                id=f[0], pregunta=f[1], opciones=tuple(json.loads(f[2])), orden=f[3]
            )
            for f in filas
        ]


class RepositorioSincronizacionSQLite(BaseSQLite):
    async def encolar(self, reporte: ReporteEncolado) -> None:
        await asyncio.to_thread(self._guardar_reporte, reporte)

    def _guardar_reporte(self, reporte: ReporteEncolado) -> None:
        self._escribir(
            "INSERT OR REPLACE INTO cola_sincronizacion "
            "(id, titulo, meta, puntuacion, encolado_en, enviado_en, carga) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                reporte.id,
                reporte.titulo,
                reporte.meta,
                reporte.puntuacion,
                reporte.encolado_en.isoformat(),
                reporte.enviado_en.isoformat() if reporte.enviado_en else None,
                json.dumps(reporte.carga, ensure_ascii=False),
            ),
        )

    async def pendientes(self) -> list[ReporteEncolado]:
        filas = await asyncio.to_thread(
            self._leer,
            f"{_SELECT_COLA} WHERE enviado_en IS NULL ORDER BY puntuacion DESC, rowid",
        )
        return [_encolado(f) for f in filas]

    async def marcar_enviados(self, reportes: list[ReporteEncolado]) -> None:
        await asyncio.to_thread(
            self._marcar, [reporte.marcar_enviado() for reporte in reportes]
        )

    def _marcar(self, enviados: list[ReporteEncolado]) -> None:
        # Una sola transacción para todo el vaciado: si el proceso muere a mitad,
        # la cola queda entera y se reintenta, en vez de dejar la mitad enviada y
        # la otra mitad sin saber si salió.
        with self._conexion() as conexion:
            conexion.executemany(
                "UPDATE cola_sincronizacion SET enviado_en = ? WHERE id = ?",
                [
                    (reporte.enviado_en.isoformat() if reporte.enviado_en else None, reporte.id)
                    for reporte in enviados
                ],
            )
            conexion.commit()


_SELECT_VOLUNTARIO = (
    "SELECT id, nombre_completo, documento, telefono, recurso, estado, registrado_en "
    "FROM voluntarios"
)

_SELECT_MISION = (
    "SELECT incidente_id, titulo, direccion, lat, lon, necesidad, puntuacion, modo, "
    "ruta, checklist, abierta, creada_en FROM misiones"
)

_SELECT_COLA = (
    "SELECT id, titulo, meta, puntuacion, encolado_en, enviado_en, carga "
    "FROM cola_sincronizacion"
)


def _voluntario(fila: tuple) -> Voluntario:
    return Voluntario(
        id=fila[0],
        nombre_completo=fila[1],
        documento=fila[2],
        telefono=fila[3],
        recurso=fila[4],
        estado=EstadoVoluntario(fila[5]),
        registrado_en=datetime.fromisoformat(fila[6]),
    )


def _mision(fila: tuple) -> Mision:
    return Mision(
        incidente_id=fila[0],
        titulo=fila[1],
        direccion=fila[2],
        ubicacion=Punto(lat=fila[3], lon=fila[4]),
        necesidad=fila[5],
        puntuacion=fila[6],
        modo=fila[7],
        ruta=tuple((float(p[0]), float(p[1])) for p in json.loads(fila[8])),
        checklist=tuple(
            ItemChecklist(clave=i["clave"], etiqueta=i["etiqueta"]) for i in json.loads(fila[9])
        ),
        abierta=bool(fila[10]),
        creada_en=datetime.fromisoformat(fila[11]),
    )


def _encolado(fila: tuple) -> ReporteEncolado:
    return ReporteEncolado(
        id=fila[0],
        titulo=fila[1],
        meta=fila[2],
        puntuacion=fila[3],
        encolado_en=datetime.fromisoformat(fila[4]),
        enviado_en=datetime.fromisoformat(fila[5]) if fila[5] else None,
        carga=json.loads(fila[6]),
    )
