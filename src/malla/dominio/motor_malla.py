"""Motor de propagación: qué se hace con cada sobre que llega.

Puro y determinista, sin I/O ni reloj propio. Todo el estado que necesita —los
identificadores ya vistos— entra por parámetro, igual que en `MotorIngesta`. Eso
lo hace testeable sin mocks: la topología en triángulo, el TTL agotado y el
duplicado por tres caminos son funciones de sus argumentos.

Las cinco reglas, en orden, y el porqué de cada una:

1. **Firma inválida → descartar y registrar, nunca reenviar.** Va primero
   porque todo lo demás (deduplicar, almacenar, priorizar) sería trabajo hecho
   sobre datos que ni siquiera son del nodo que dicen ser.
2. **TTL declarado excesivo → descartar.** Un sobre con `ttl` de mil saltos es
   un intento de inundación; el límite lo pone el receptor, no el emisor.
3. **Ya visto → aceptar sin reenviar.** El mismo reporte llega por tres caminos
   en una malla densa; los tres se colapsan en uno gracias a
   `hash_idempotencia`, y solo el primero se propaga.
4. **Este nodo ya está en la ruta → no reenviar.** Anti-bucle explícito. Tres
   nodos en triángulo se saturarían entre sí en segundos sin esta regla, aun con
   deduplicación, porque el sobre volvería justo antes de registrarse.
5. **Vida agotada → descartar.** Un rumor que no ha llegado a un nodo con
   internet en ocho saltos no va a llegar; lo que corresponde es que muera y que
   el almacenar-y-reenviar local siga custodiando el original.

Sobre el TTL por defecto (8): en una red de rumor el número de saltos necesario
para cubrir la componente conexa crece como log_d(N), con d el grado medio del
nodo. Con un grado realista de 4 vecinos al alcance y una zona afectada de
~10.000 dispositivos, log_4(10000) ≈ 6.6; 8 deja margen para topologías
irregulares (calles, edificios) sin permitir que un mensaje circule
indefinidamente. Cada salto añade además latencia de segundos en un enlace de
malla: más allá de 8, el reporte llega tarde para servir de algo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from malla.dominio.firma import verificar_sobre
from malla.dominio.sobre import SobreMalla

TTL_POR_DEFECTO = 8
TTL_MAXIMO_ACEPTADO = 16

# Orden de urgencia CAP 1.2. Menor número = sale antes por un enlace estrecho.
_PESO_URGENCIA = {
    "Immediate": 0,
    "Expected": 1,
    "Future": 2,
    "Past": 3,
    "Unknown": 4,
}

# La autoridad va primero a igualdad de urgencia: su reporte es el que activa un
# despacho oficial, y suele ser el único con capacidad de confirmar los demás.
_PESO_FUENTE = {
    "autoridad": 0,
    "sensor": 1,
    "organizacion": 1,
    "voluntario": 2,
    "afectado": 2,
    "ciudadano": 3,
}
_PESO_URGENCIA_DESCONOCIDA = 5
_PESO_FUENTE_DESCONOCIDA = 4


class ResultadoRecepcion(StrEnum):
    """Qué se decidió sobre un sobre entrante."""

    ACEPTADO_Y_REENVIAR = "aceptado_y_reenviar"
    ACEPTADO_SIN_REENVIO = "aceptado_sin_reenvio"
    DUPLICADO = "duplicado"
    BUCLE = "bucle"
    TTL_AGOTADO = "ttl_agotado"
    TTL_EXCESIVO = "ttl_excesivo"
    FIRMA_INVALIDA = "firma_invalida"


# Lo que no se almacena ni se cuenta como recibido. Un duplicado sí se acepta
# (ya está almacenado); estos tres son basura o riesgo.
RESULTADOS_DESCARTE = frozenset(
    {
        ResultadoRecepcion.FIRMA_INVALIDA,
        ResultadoRecepcion.TTL_EXCESIVO,
        ResultadoRecepcion.TTL_AGOTADO,
    }
)


@dataclass(frozen=True, slots=True)
class Decision:
    """Lo que el motor resolvió, listo para que el caso de uso lo ejecute."""

    resultado: ResultadoRecepcion
    motivo: str = ""
    sobre_a_reenviar: SobreMalla | None = None

    @property
    def se_almacena(self) -> bool:
        """Solo se guarda lo legítimo y nuevo."""
        return self.resultado in (
            ResultadoRecepcion.ACEPTADO_Y_REENVIAR,
            ResultadoRecepcion.ACEPTADO_SIN_REENVIO,
        )

    @property
    def es_descarte(self) -> bool:
        return self.resultado in RESULTADOS_DESCARTE


def prioridad(sobre: SobreMalla) -> tuple[int, int, datetime]:
    """Clave de orden: urgencia, luego tipo de fuente, luego antigüedad.

    La antigüedad desempata a favor del más viejo: un reporte que lleva veinte
    minutos esperando un vecino ya perdió tiempo, y retrasarlo más solo empeora
    lo que ya está mal.
    """
    carga = sobre.carga
    urgencia = str(carga.get("urgencia", ""))
    fuente = carga.get("fuente")
    tipo_fuente = str(fuente.get("tipo", "")) if isinstance(fuente, dict) else ""
    return (
        _PESO_URGENCIA.get(urgencia, _PESO_URGENCIA_DESCONOCIDA),
        _PESO_FUENTE.get(tipo_fuente, _PESO_FUENTE_DESCONOCIDA),
        sobre.momento_origen,
    )


class MotorMalla:
    """El corazón determinista de la malla."""

    def __init__(
        self,
        id_nodo: str,
        ttl_por_defecto: int = TTL_POR_DEFECTO,
        ttl_maximo_aceptado: int = TTL_MAXIMO_ACEPTADO,
    ) -> None:
        if not id_nodo.strip():
            raise ValueError("el motor requiere el id del nodo local")
        self._id_nodo = id_nodo
        self._ttl_por_defecto = ttl_por_defecto
        self._ttl_maximo = ttl_maximo_aceptado

    @property
    def id_nodo(self) -> str:
        return self._id_nodo

    @property
    def ttl_por_defecto(self) -> int:
        return self._ttl_por_defecto

    def evaluar(self, sobre: SobreMalla, vistos: frozenset[str]) -> Decision:
        """Decide qué hacer con un sobre entrante. No toca nada de fuera."""
        if not verificar_sobre(sobre):
            return Decision(
                ResultadoRecepcion.FIRMA_INVALIDA,
                f"firma no verifica para origen {sobre.nodo_origen}",
            )

        if sobre.ttl > self._ttl_maximo:
            return Decision(
                ResultadoRecepcion.TTL_EXCESIVO,
                f"ttl={sobre.ttl} supera el máximo aceptado {self._ttl_maximo}",
            )

        if sobre.id_mensaje in vistos:
            return Decision(
                ResultadoRecepcion.DUPLICADO,
                f"id_mensaje {sobre.id_mensaje} ya conocido",
            )

        if sobre.paso_por(self._id_nodo):
            return Decision(
                ResultadoRecepcion.BUCLE,
                f"el sobre ya pasó por {self._id_nodo}: ruta={list(sobre.ruta)}",
            )

        if sobre.vida_agotada:
            return Decision(
                ResultadoRecepcion.TTL_AGOTADO,
                f"saltos={sobre.saltos} alcanzó ttl={sobre.ttl}",
            )

        avanzado = sobre.avanzar(self._id_nodo)
        if avanzado.vida_agotada:
            # Se acepta y se guarda, pero muere aquí: es el último salto.
            return Decision(
                ResultadoRecepcion.ACEPTADO_SIN_REENVIO,
                f"último salto permitido (ttl={sobre.ttl})",
            )
        return Decision(ResultadoRecepcion.ACEPTADO_Y_REENVIAR, "", avanzado)

    def ordenar_por_prioridad(self, sobres: list[SobreMalla]) -> list[SobreMalla]:
        """Ordena un lote para salir por un enlace lento. Estable y determinista."""
        return sorted(sobres, key=prioridad)

    def seleccionar_para_enlace(
        self, sobres: list[SobreMalla], capacidad: int
    ) -> list[SobreMalla]:
        """Lo que cabe en una tanda del enlace, empezando por lo más urgente.

        Un enlace de malla mueve pocos kilobytes por segundo. Si se manda todo en
        el orden en que llegó, un reporte IMMEDIATE de una autoridad puede quedar
        detrás de cincuenta reportes rutinarios y no salir nunca.
        """
        if capacidad < 1:
            return []
        return self.ordenar_por_prioridad(sobres)[:capacidad]

    def vecinos_destino(self, sobre: SobreMalla, ids_vecinos: list[str]) -> list[str]:
        """A quién reenviar: todos menos los que ya vieron el sobre.

        Devolvérselo a quien nos lo dio (*split horizon*) gasta el enlace para
        que el otro extremo lo descarte por duplicado.
        """
        return [v for v in ids_vecinos if not sobre.paso_por(v) and v != self._id_nodo]
