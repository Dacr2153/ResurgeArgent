"""Publicador a log del Agente 8."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("agente_logistica.publicador")


class PublicadorLog:
    async def publicar(self, evento: dict) -> None:
        logger.info("Publicando plan logístico: %s", json.dumps(evento, ensure_ascii=False))
