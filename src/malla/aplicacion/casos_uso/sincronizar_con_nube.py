"""Caso de uso: el nodo con salida a internet sube el lote de todos.

Es el punto de toda la malla. Los reportes saltan de teléfono en teléfono sin
sentido propio hasta que alguno tiene señal; ese sube el lote acumulado al
Orquestador y devuelve acuses a la red, para que los demás dejen de arrastrar lo
que ya está a salvo.

El acuse viaja como un sobre más: firmado por este nodo, con el mismo TTL, la
misma deduplicación y el mismo anti-bucle. No hace falta un segundo protocolo
para propagarlo, y así el acuse hereda gratis todas las garantías del primero.
"""

from __future__ import annotations

from dataclasses import dataclass

from malla.aplicacion.casos_uso.difusion import drenar_pendientes
from malla.aplicacion.eventos import evento
from malla.aplicacion.puertos.salida import AlmacenSobresPort, NubePort, TransportePort
from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from malla.dominio.motor_malla import MotorMalla
from malla.dominio.sobre import CARGA_ACUSE, SobreMalla
from nucleo.mensajes import TipoEvento, ahora
from nucleo.puertos import AuditoriaPort

# Cuántos sobres se suben por tanda. La subida ocurre por un enlace igual de
# frágil que el resto: mejor varios lotes cortos que uno largo que se corta a la
# mitad y deja sin acusar todo lo que ya había llegado.
TAMANO_LOTE = 50


@dataclass(frozen=True, slots=True)
class ResultadoSincronizacion:
    subidos: tuple[str, ...] = ()
    acusados: int = 0
    hubo_salida: bool = True
    propagados: int = 0

    @property
    def total(self) -> int:
        return len(self.subidos)


class SincronizarConNube:
    """Pasarela entre la malla y el sistema central."""

    def __init__(
        self,
        identidad: IdentidadNodo,
        motor: MotorMalla,
        almacen: AlmacenSobresPort,
        nube: NubePort,
        transporte: TransportePort,
        auditoria: AuditoriaPort,
        tamano_lote: int = TAMANO_LOTE,
    ) -> None:
        self._identidad = identidad
        self._motor = motor
        self._almacen = almacen
        self._nube = nube
        self._transporte = transporte
        self._auditoria = auditoria
        self._tamano_lote = tamano_lote

    async def sincronizar(self) -> ResultadoSincronizacion:
        if not await self._nube.disponible():
            # Sin salida no hay nada que hacer contra la nube, pero sí contra los
            # vecinos: se aprovecha el barrido para drenar pendientes hacia ellos,
            # que es como el lote acaba llegando a un nodo que sí tenga señal.
            pendientes = await self._almacen.pendientes()
            difusion = await drenar_pendientes(self._motor, self._transporte, pendientes)
            return ResultadoSincronizacion(hubo_salida=False, propagados=difusion.alcanzados)

        pendientes = await self._almacen.pendientes(limite=self._tamano_lote)
        pendientes = [s for s in pendientes if s.tipo_carga != CARGA_ACUSE]
        if not pendientes:
            return ResultadoSincronizacion()

        # Prioridad también aquí: si la señal se cae a mitad de la subida, que lo
        # que alcanzó a salir sea lo urgente.
        lote = self._motor.ordenar_por_prioridad(pendientes)
        aceptados = await self._nube.subir(lote)
        acusados = await self._almacen.marcar_entregados(aceptados)

        await self._auditoria.registrar(
            evento(
                TipoEvento.TAREA_DELEGADA,
                self._identidad.id_nodo,
                {
                    "accion": "sincronizacion_nube",
                    "enviados": len(lote),
                    "aceptados": len(aceptados),
                    "acusados": acusados,
                },
            )
        )

        propagados = 0
        if aceptados:
            propagados = await self._propagar_acuse(list(aceptados))

        return ResultadoSincronizacion(
            subidos=tuple(aceptados),
            acusados=acusados,
            hubo_salida=True,
            propagados=propagados,
        )

    async def _propagar_acuse(self, ids: list[str]) -> int:
        """Difunde un sobre de acuse con los ids que la nube ya tiene.

        Lleva `momento` e `id del nodo pasarela` dentro de la carga para que dos
        acuses distintos no colapsen en el mismo `id_mensaje`: sin eso, el acuse
        de la segunda sincronización se descartaría como duplicado del primero.
        """
        carga = {
            "ids_acusados": sorted(ids),
            "nodo_pasarela": self._identidad.id_nodo,
            "momento": ahora().isoformat(),
        }
        acuse: SobreMalla = crear_sobre_firmado(
            self._identidad,
            carga,
            ttl=self._motor.ttl_por_defecto,
            tipo_carga=CARGA_ACUSE,
        )
        await self._almacen.guardar(acuse)
        await self._almacen.marcar_entregados([acuse.id_mensaje])
        difusion = await drenar_pendientes(self._motor, self._transporte, [acuse])
        return difusion.alcanzados
