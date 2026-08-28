"""Resumidor con LLM: convierte el contexto ya resuelto en prosa para el humano.

Cumple `ResumidorPort`. No decide nada y no puede: recibe el resultado final,
devuelve texto, y el texto no vuelve a entrar en ninguna lógica. Si el modelo
falla, tarda o devuelve algo vacío, se degrada al `ResumidorNulo` — el parte se
entrega igual, redactado por plantilla.
"""

from __future__ import annotations

import json
import logging

from agente_orquestador.adaptadores.llm.clientes import ClienteLLM
from agente_orquestador.adaptadores.llm.resumidor_nulo import ResumidorNulo

registro = logging.getLogger("agente_orquestador.resumidor")

#: Campos del contexto que se le envían al modelo. La lista es explícita para no
#: filtrar al proveedor datos personales de los reportes originales.
CAMPOS_PERMITIDOS = (
    "correlacion_id",
    "estado_operacion",
    "degradada",
    "reportes_ingeridos",
    "incidentes",
    "zonas_afectadas",
)


class ResumidorLLM:
    def __init__(self, cliente: ClienteLLM, rol_prompt: str) -> None:
        self._cliente = cliente
        self._rol_prompt = rol_prompt
        self._respaldo = ResumidorNulo()

    async def resumir_situacion(self, contexto: dict) -> str:
        recortado = {k: contexto.get(k) for k in CAMPOS_PERMITIDOS if k in contexto}
        try:
            texto = await self._cliente.completar(
                self._rol_prompt,
                "Redacta el parte de situación para el coordinador humano a partir "
                f"de este estado ya resuelto:\n{json.dumps(recortado, ensure_ascii=False)}",
            )
        except Exception:  # noqa: BLE001 - el parte se entrega aunque el modelo caiga
            registro.exception("el resumidor LLM falló; se usa el resumen por plantilla")
            return await self._respaldo.resumir_situacion(contexto)

        if not texto or not texto.strip():
            return await self._respaldo.resumir_situacion(contexto)
        return texto.strip()
