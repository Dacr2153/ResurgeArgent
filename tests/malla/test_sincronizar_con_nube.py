"""El nodo con salida a internet sube el lote de todos y devuelve acuses."""

from __future__ import annotations

from malla.aplicacion.casos_uso.sincronizar_con_nube import SincronizarConNube
from malla.dominio.sobre import CARGA_ACUSE
from nucleo.esquemas import TipoFuente, Urgencia
from tests.malla.conftest import NubeFalsa, construir_nodo, enlazar, reporte


def _sincronizador(nodo, nube, tamano_lote: int = 50) -> SincronizarConNube:
    return SincronizarConNube(
        nodo.identidad,
        nodo.motor,
        nodo.almacen,
        nube,
        nodo.transporte,
        nodo.auditoria,
        tamano_lote=tamano_lote,
    )


async def test_la_pasarela_sube_el_lote_de_los_demas():
    """Dos nodos sin señal, uno con ella: sus reportes acaban en la nube."""
    pasarela, sin_senal_1, sin_senal_2 = construir_nodo(), construir_nodo(), construir_nodo()
    enlazar(pasarela, sin_senal_1, sin_senal_2)

    sobre_1, _ = await sin_senal_1.originar.originar(reporte(texto="hay gente bajo el escombro"))
    sobre_2, _ = await sin_senal_2.originar.originar(reporte(texto="fuga de gas en la esquina"))

    nube = NubeFalsa(hay_salida=True)
    resultado = await _sincronizador(pasarela, nube).sincronizar()

    assert resultado.hubo_salida is True
    assert set(nube.recibidos) == {sobre_1.id_mensaje, sobre_2.id_mensaje}
    assert await pasarela.almacen.pendientes() == []


async def test_sin_salida_no_sube_nada_pero_drena_hacia_los_vecinos():
    aislado, vecino = construir_nodo(), construir_nodo()
    enlazar(aislado, vecino)
    sobre, _ = await aislado.originar.originar(reporte())
    await vecino.almacen.marcar_entregados([sobre.id_mensaje])  # el vecino ya lo tenía

    nube = NubeFalsa(hay_salida=False)
    resultado = await _sincronizador(aislado, nube).sincronizar()

    assert resultado.hubo_salida is False
    assert nube.recibidos == []
    # El sobre sigue guardado: sin nube no se pierde nada.
    assert len(await aislado.almacen.pendientes()) == 1


async def test_el_acuse_llega_a_los_vecinos_y_libera_sus_pendientes():
    """Lo que ya está a salvo deja de ocupar el enlace de los demás."""
    pasarela, vecino = construir_nodo(), construir_nodo()
    enlazar(pasarela, vecino)
    sobre, _ = await vecino.originar.originar(reporte())
    assert len(await vecino.almacen.pendientes()) == 1

    nube = NubeFalsa(hay_salida=True)
    resultado = await _sincronizador(pasarela, nube).sincronizar()

    assert resultado.propagados == 1
    # El reporte deja de estar pendiente, y el propio acuse tampoco se acumula:
    # es trafico interno de la malla, no algo que haya que subir.
    assert await vecino.almacen.pendientes() == []
    assert sobre.id_mensaje in await vecino.almacen.ids_vistos()


async def test_lo_urgente_sube_primero_si_el_lote_no_cabe_entero():
    pasarela = construir_nodo()
    rutinario, _ = await pasarela.originar.originar(
        reporte(texto="arbol caido sin heridos", urgencia=Urgencia.FUTURE)
    )
    urgente, _ = await pasarela.originar.originar(
        reporte(
            texto="edificio colapsado con personas dentro",
            urgencia=Urgencia.IMMEDIATE,
            tipo_fuente=TipoFuente.AUTORIDAD,
            fuente_id="bomberos-1",
        )
    )

    nube = NubeFalsa(hay_salida=True)
    await _sincronizador(pasarela, nube, tamano_lote=2).sincronizar()

    assert nube.recibidos[0] == urgente.id_mensaje
    assert nube.recibidos[1] == rutinario.id_mensaje


async def test_lo_que_la_nube_rechaza_sigue_pendiente():
    pasarela = construir_nodo()
    aceptado, _ = await pasarela.originar.originar(reporte(texto="incendio en el mercado"))
    rechazado, _ = await pasarela.originar.originar(reporte(texto="via bloqueada por lodo"))

    nube = NubeFalsa(hay_salida=True, rechaza={rechazado.id_mensaje})
    resultado = await _sincronizador(pasarela, nube).sincronizar()

    assert resultado.subidos == (aceptado.id_mensaje,)
    pendientes = await pasarela.almacen.pendientes()
    assert [s.id_mensaje for s in pendientes] == [rechazado.id_mensaje]


async def test_sin_nada_pendiente_la_sincronizacion_es_inocua():
    pasarela = construir_nodo()
    nube = NubeFalsa(hay_salida=True)
    resultado = await _sincronizador(pasarela, nube).sincronizar()
    assert resultado.total == 0
    assert nube.recibidos == []


async def test_los_acuses_no_se_suben_a_la_nube():
    """Un acuse es tráfico interno de la malla; la nube ya sabe lo que tiene."""
    pasarela, vecino = construir_nodo(), construir_nodo()
    enlazar(pasarela, vecino)
    await vecino.originar.originar(reporte())

    nube = NubeFalsa(hay_salida=True)
    sincronizador = _sincronizador(pasarela, nube)
    await sincronizador.sincronizar()
    await sincronizador.sincronizar()

    acuses = [
        s
        for s in (await pasarela.almacen.listar_desde(0, 100))
        if s.sobre.tipo_carga == CARGA_ACUSE
    ]
    assert acuses
    assert all(a.sobre.id_mensaje not in nube.recibidos for a in acuses)
