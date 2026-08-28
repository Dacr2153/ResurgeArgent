"""Publicador a log: cumple PublicadorPort sin broker externo."""

from __future__ import annotations

import json
import logging

registro = logging.getLogger("agente_orquestador.publicador")


class PublicadorLog:
    async def publicar(self, evento: dict) -> None:
        registro.info("Estado de la operación: %s", json.dumps(evento, ensure_ascii=False))
