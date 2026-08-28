"""Publicador a log: cumple ``PublicadorPort`` sin broker externo."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("agente_ingesta.publicador")


class PublicadorLog:
    async def publicar(self, evento: dict[str, Any]) -> None:
        logger.info("Lote de ingesta procesado: %s", json.dumps(evento, ensure_ascii=False))
