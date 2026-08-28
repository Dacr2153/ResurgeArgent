"""Adaptadores de auditoría compartidos.

`AuditoriaJSONL` escribe una línea por evento: formato append-only, legible con
`tail -f` durante una emergencia y trivial de cargar después para el análisis
post-operación. `AuditoriaMemoria` sirve a los tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from nucleo.mensajes import EventoAuditoria


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
