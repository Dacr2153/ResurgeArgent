"""Saga de orquestación: pasos delegados con compensación en orden inverso.

El Orquestador no ejecuta trabajo, lo delega. Una delegación puede fallar a mitad
de camino y dejar el sistema con medio compromiso hecho: reportes consumidos que
nadie verificó, recursos reservados para un incidente que se cayó. La saga es la
respuesta a eso: cada paso declara cómo se deshace, y si un paso obligatorio
falla, se deshacen en orden inverso los que ya se habían completado.

Dos modos de fallo, deliberadamente distintos:

- **Paso obligatorio** (`obligatorio=True`): si falla, la saga aborta y compensa.
  Sin verificación no hay incidente que priorizar; seguir sería inventar.
- **Paso opcional** (`obligatorio=False`): si falla, se marca FALLIDO, se registra
  y la saga continúa. Es la degradación: sin rutas del agente geoespacial todavía
  se puede priorizar por coordenadas propias, y un coordinador prefiere una lista
  sin rutas a no tener lista.

En ningún caso se propaga la excepción hacia arriba. Una emergencia no se detiene
porque un microservicio no respondió; el resultado dice qué falló y sigue.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from nucleo.mensajes import Agente, EventoAuditoria, TipoEvento
from nucleo.puertos import AuditoriaPort

#: Timeout por defecto de un paso, en segundos. Cinco segundos es el punto en el
#: que un coordinador humano ya percibe el sistema como colgado; más allá de eso
#: vale más una respuesta parcial que una respuesta completa tardía.
TIMEOUT_PASO_S = 5.0

#: Timeout de una compensación. Más corto que el del paso: deshacer es una
#: operación local y barata, y si tampoco responde no queremos encadenar esperas
#: mientras la operación entera está bloqueada.
TIMEOUT_COMPENSACION_S = 3.0


class EstadoPaso(StrEnum):
    """Ciclo de vida de un paso de la saga."""

    PENDIENTE = "pendiente"
    EN_EJECUCION = "en_ejecucion"
    COMPLETADO = "completado"
    FALLIDO = "fallido"
    COMPENSADO = "compensado"


@dataclass
class PasoSaga:
    """Un paso delegado a otro agente, con su acción de deshacer."""

    nombre: str
    agente: Agente
    accion: Callable[[], Awaitable[Any]]
    accion_compensatoria: Callable[[], Awaitable[None]] | None = None
    obligatorio: bool = True
    timeout_s: float = TIMEOUT_PASO_S
    estado: EstadoPaso = EstadoPaso.PENDIENTE
    resultado: Any = None
    error: str = ""

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "agente": str(self.agente),
            "estado": str(self.estado),
            "obligatorio": self.obligatorio,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class ResultadoSaga:
    """Qué pasó con la saga completa. Es lo único que ve el caso de uso."""

    exitosa: bool
    parcial: bool
    resultados: dict[str, Any] = field(default_factory=dict)
    pasos: tuple[PasoSaga, ...] = ()
    fallidos: tuple[str, ...] = ()
    compensados: tuple[str, ...] = ()

    @property
    def degradada(self) -> bool:
        """Hubo fallos pero se pudo seguir: el resultado no está completo."""
        return self.exitosa and self.parcial

    def a_dict(self) -> dict[str, Any]:
        return {
            "exitosa": self.exitosa,
            "parcial": self.parcial,
            "degradada": self.degradada,
            "pasos": [p.a_dict() for p in self.pasos],
            "fallidos": list(self.fallidos),
            "compensados": list(self.compensados),
        }


class Saga:
    """Ejecuta pasos en orden y compensa hacia atrás si uno obligatorio falla."""

    def __init__(
        self,
        correlacion_id: str,
        pasos: list[PasoSaga],
        auditoria: AuditoriaPort | None = None,
        agente: Agente = Agente.ORQUESTADOR,
    ) -> None:
        self._correlacion_id = correlacion_id
        self._pasos = pasos
        self._auditoria = auditoria
        self._agente = agente

    @property
    def pasos(self) -> tuple[PasoSaga, ...]:
        return tuple(self._pasos)

    async def ejecutar(self) -> ResultadoSaga:
        """Corre la saga entera. No lanza: todo fallo se devuelve descrito."""
        resultados: dict[str, Any] = {}
        completados: list[PasoSaga] = []
        fallidos: list[str] = []
        compensados: tuple[str, ...] = ()
        abortada = False

        for paso in self._pasos:
            paso.estado = EstadoPaso.EN_EJECUCION
            await self._auditar(
                TipoEvento.TAREA_DELEGADA,
                {"paso": paso.nombre, "agente": str(paso.agente), "timeout_s": paso.timeout_s},
            )

            ok = await self._ejecutar_paso(paso)
            if ok:
                resultados[paso.nombre] = paso.resultado
                completados.append(paso)
                continue

            fallidos.append(paso.nombre)
            if paso.obligatorio:
                abortada = True
                break

        if abortada:
            compensados = await self._compensar(completados)

        return ResultadoSaga(
            exitosa=not abortada,
            parcial=bool(fallidos),
            resultados=resultados,
            pasos=tuple(self._pasos),
            fallidos=tuple(fallidos),
            compensados=compensados,
        )

    # ------------------------------------------------------------------ interno
    async def _ejecutar_paso(self, paso: PasoSaga) -> bool:
        """Ejecuta un paso con timeout. Devuelve si salió bien; nunca lanza."""
        try:
            paso.resultado = await asyncio.wait_for(paso.accion(), timeout=paso.timeout_s)
        except (TimeoutError, asyncio.TimeoutError):
            paso.estado = EstadoPaso.FALLIDO
            paso.error = f"sin respuesta en {paso.timeout_s}s"
            await self._auditar(
                TipoEvento.AGENTE_SIN_RESPUESTA,
                {"paso": paso.nombre, "agente": str(paso.agente), "timeout_s": paso.timeout_s},
            )
            return False
        except Exception as exc:  # noqa: BLE001 - un agente roto no tumba la operación
            paso.estado = EstadoPaso.FALLIDO
            paso.error = f"{type(exc).__name__}: {exc}"
            await self._auditar(
                TipoEvento.ERROR,
                {"paso": paso.nombre, "agente": str(paso.agente), "error": paso.error},
            )
            return False

        paso.estado = EstadoPaso.COMPLETADO
        return True

    async def _compensar(self, completados: list[PasoSaga]) -> tuple[str, ...]:
        """Deshace los pasos completados, del último al primero.

        El orden inverso no es estético: el paso N pudo apoyarse en el estado que
        dejó el N-1, así que deshacer primero el N-1 dejaría al N compensando
        sobre un mundo que ya cambió.
        """
        compensados: list[str] = []
        for paso in reversed(completados):
            if paso.accion_compensatoria is None:
                continue
            try:
                await asyncio.wait_for(
                    paso.accion_compensatoria(), timeout=TIMEOUT_COMPENSACION_S
                )
            except Exception as exc:  # noqa: BLE001 - una compensación fallida se audita
                await self._auditar(
                    TipoEvento.ERROR,
                    {
                        "paso": paso.nombre,
                        "fase": "compensacion",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
                continue
            paso.estado = EstadoPaso.COMPENSADO
            compensados.append(paso.nombre)
            await self._auditar(
                TipoEvento.COMPENSACION_EJECUTADA,
                {"paso": paso.nombre, "agente": str(paso.agente)},
            )
        return tuple(compensados)

    async def _auditar(self, tipo: TipoEvento, detalle: dict[str, Any]) -> None:
        if self._auditoria is None:
            return
        await self._auditoria.registrar(
            EventoAuditoria(
                tipo=tipo,
                agente=self._agente,
                correlacion_id=self._correlacion_id,
                detalle=detalle,
            )
        )
