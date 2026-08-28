"""Difusión: mandar un sobre a los vecinos que aún no lo tienen.

Se comparte entre `recibir_sobre`, `originar_reporte` y `sincronizar_con_nube`
porque los tres hacen exactamente lo mismo al final: elegir destinatarios,
respetar el ancho del enlace y no pelearse con un vecino caído.

Que un envío falle no es un error del sistema: en un desastre los vecinos
aparecen y desaparecen. El sobre ya está en el almacén local, así que el fallo
solo significa "todavía no"; el siguiente barrido lo reintenta. Eso es
almacenar-y-reenviar.
"""

from __future__ import annotations

from dataclasses import dataclass

from malla.aplicacion.puertos.salida import TransportePort
from malla.dominio.motor_malla import MotorMalla
from malla.dominio.sobre import SobreMalla


@dataclass(frozen=True, slots=True)
class ResultadoDifusion:
    entregados: tuple[str, ...] = ()
    fallidos: tuple[str, ...] = ()
    omitidos: tuple[str, ...] = ()

    @property
    def alcanzados(self) -> int:
        return len(self.entregados)


async def difundir(
    motor: MotorMalla,
    transporte: TransportePort,
    sobre: SobreMalla,
) -> ResultadoDifusion:
    """Manda un sobre a todos los vecinos que no lo hayan visto ya."""
    vecinos = await transporte.vecinos()
    destinos = set(motor.vecinos_destino(sobre, [v.id_nodo for v in vecinos]))

    entregados: list[str] = []
    fallidos: list[str] = []
    omitidos: list[str] = []

    for vecino in vecinos:
        if vecino.id_nodo not in destinos:
            omitidos.append(vecino.id_nodo)
            continue
        try:
            ok = await transporte.enviar(sobre, vecino)
        except Exception:  # noqa: BLE001 - un vecino caído no puede tumbar al nodo
            ok = False
        (entregados if ok else fallidos).append(vecino.id_nodo)

    return ResultadoDifusion(tuple(entregados), tuple(fallidos), tuple(omitidos))


async def drenar_pendientes(
    motor: MotorMalla,
    transporte: TransportePort,
    pendientes: list[SobreMalla],
) -> ResultadoDifusion:
    """Reintenta lo acumulado cuando aparece un vecino.

    Cada vecino recibe solo lo que cabe en su enlace, y lo más urgente primero:
    si el encuentro dura diez segundos, que esos diez segundos se gasten en los
    reportes IMMEDIATE y no en los rutinarios que llegaron antes.
    """
    vecinos = await transporte.vecinos()
    entregados: list[str] = []
    fallidos: list[str] = []

    for vecino in vecinos:
        candidatos = [s for s in pendientes if not s.paso_por(vecino.id_nodo)]
        for sobre in motor.seleccionar_para_enlace(candidatos, vecino.capacidad_lote):
            try:
                ok = await transporte.enviar(sobre, vecino)
            except Exception:  # noqa: BLE001
                ok = False
            (entregados if ok else fallidos).append(sobre.id_mensaje)

    return ResultadoDifusion(tuple(entregados), tuple(fallidos))
