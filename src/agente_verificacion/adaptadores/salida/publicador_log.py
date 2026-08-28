"""Publicador a log: cumple PublicadorPort sin broker externo."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("agente_verificacion.publicador")


class PublicadorLog:
    async def publicar(self, evento: dict) -> None:
        logger.info("Publicando incidentes verificados: %s", json.dumps(evento, ensure_ascii=False))
