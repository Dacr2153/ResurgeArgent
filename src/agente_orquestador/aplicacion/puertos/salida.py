"""Puertos de salida del Orquestador (protocolos).

Los puertos hacia los otros agentes (`IngestaPort`, `VerificacionPort`,
`GeoespacialPort`, `AuditoriaPort`) no se redeclaran aquí: son contrato común y
viven en `nucleo.puertos`. Aquí solo están los puertos propios del Orquestador.
"""

from __future__ import annotations

from typing import Protocol

from agente_orquestador.dominio.entidades import Operacion


class ResumidorPort(Protocol):
    """Redacción del resumen de situación para el coordinador humano.

    Es el único punto del agente donde interviene un LLM, y es deliberadamente
    incapaz de decidir: recibe un contexto ya resuelto y devuelve texto. No
    calcula prioridades, no elige destinos y no autoriza nada.
    """

    async def resumir_situacion(self, contexto: dict) -> str:
        """Redacta en prosa el estado de la operación. Solo texto."""
        ...


class RepositorioOperacionesPort(Protocol):
    async def guardar(self, operacion: Operacion) -> None: ...

    async def obtener(self, incidente_id: str) -> Operacion | None: ...

    async def por_correlacion(self, correlacion_id: str) -> list[Operacion]: ...


class PublicadorPort(Protocol):
    async def publicar(self, evento: dict) -> None:
        """Publica el estado consolidado de la operación (cola, log, etc.)."""
        ...
