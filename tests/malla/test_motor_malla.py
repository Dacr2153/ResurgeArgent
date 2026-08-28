"""Motor de propagación: anti-bucle, TTL, deduplicación y prioridad."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from malla.dominio.motor_malla import MotorMalla, ResultadoRecepcion, prioridad
from malla.dominio.sobre import SobreMalla
from nucleo.esquemas import TipoFuente, Urgencia
from nucleo.mensajes import ahora
from tests.malla.conftest import reporte

SIN_VISTOS = frozenset()


def _sobre(ttl: int = 8, texto: str = "derrumbe en la via") -> SobreMalla:
    return crear_sobre_firmado(IdentidadNodo.generar(), reporte(texto=texto).a_dict(), ttl=ttl)


def test_sobre_legitimo_se_acepta_y_se_reenvia():
    motor = MotorMalla("nodo-local")
    decision = motor.evaluar(_sobre(), SIN_VISTOS)
    assert decision.resultado is ResultadoRecepcion.ACEPTADO_Y_REENVIAR
    assert decision.sobre_a_reenviar.saltos == 1
    assert decision.sobre_a_reenviar.ruta == ("nodo-local",)


def test_firma_invalida_se_descarta_y_nunca_se_reenvia():
    motor = MotorMalla("nodo-local")
    alterado = replace(_sobre(), carga={"texto": "mentira"})
    decision = motor.evaluar(alterado, SIN_VISTOS)
    assert decision.resultado is ResultadoRecepcion.FIRMA_INVALIDA
    assert decision.sobre_a_reenviar is None
    assert decision.se_almacena is False
    assert decision.es_descarte is True


def test_duplicado_no_se_reenvia():
    motor = MotorMalla("nodo-local")
    sobre = _sobre()
    decision = motor.evaluar(sobre, frozenset({sobre.id_mensaje}))
    assert decision.resultado is ResultadoRecepcion.DUPLICADO
    assert decision.sobre_a_reenviar is None


def test_anti_bucle_en_triangulo():
    """A -> B -> C -> A: al volver a A el sobre muere, aunque A no lo tuviera visto."""
    motor_a = MotorMalla("A")
    sobre = _sobre()
    dando_la_vuelta = sobre.avanzar("A").avanzar("B").avanzar("C")
    decision = motor_a.evaluar(dando_la_vuelta, SIN_VISTOS)
    assert decision.resultado is ResultadoRecepcion.BUCLE
    assert decision.sobre_a_reenviar is None


def test_el_originador_no_acepta_su_propio_sobre_de_vuelta():
    identidad = IdentidadNodo.generar()
    motor = MotorMalla(identidad.id_nodo)
    sobre = crear_sobre_firmado(identidad, reporte().a_dict()).avanzar("otro")
    assert motor.evaluar(sobre, SIN_VISTOS).resultado is ResultadoRecepcion.BUCLE


def test_ttl_agotado_se_descarta():
    motor = MotorMalla("nodo-local")
    sobre = _sobre(ttl=2)
    agotado = replace(sobre, saltos=2, ruta=("x", "y"))
    decision = motor.evaluar(agotado, SIN_VISTOS)
    assert decision.resultado is ResultadoRecepcion.TTL_AGOTADO
    assert decision.se_almacena is False


def test_ultimo_salto_se_acepta_pero_no_se_reenvia():
    motor = MotorMalla("nodo-local")
    sobre = replace(_sobre(ttl=2), saltos=1, ruta=("x",))
    decision = motor.evaluar(sobre, SIN_VISTOS)
    assert decision.resultado is ResultadoRecepcion.ACEPTADO_SIN_REENVIO
    assert decision.se_almacena is True
    assert decision.sobre_a_reenviar is None


def test_ttl_inflado_por_encima_del_maximo_se_rechaza():
    """El límite lo pone el receptor: un ttl enorme es un intento de inundación."""
    motor = MotorMalla("nodo-local", ttl_maximo_aceptado=16)
    decision = motor.evaluar(_sobre(ttl=500), SIN_VISTOS)
    assert decision.resultado is ResultadoRecepcion.TTL_EXCESIVO


def test_un_sobre_muere_tras_ttl_saltos_en_cadena():
    """Ocho nodos en fila: el noveno ya no lo reenvía."""
    sobre = _sobre(ttl=8)
    reenvios = 0
    for indice in range(20):
        motor = MotorMalla(f"nodo-{indice}")
        decision = motor.evaluar(sobre, SIN_VISTOS)
        if decision.sobre_a_reenviar is None:
            break
        sobre = decision.sobre_a_reenviar
        reenvios += 1
    assert reenvios == 7  # el octavo salto es el último y ya no propaga
    assert sobre.saltos == 7


def test_prioridad_inmediato_antes_que_futuro():
    urgente = _sobre_con(Urgencia.IMMEDIATE, TipoFuente.CIUDADANO, "incendio")
    rutinario = _sobre_con(Urgencia.FUTURE, TipoFuente.CIUDADANO, "arbol caido")
    assert prioridad(urgente) < prioridad(rutinario)


def test_prioridad_autoridad_desempata():
    autoridad = _sobre_con(Urgencia.IMMEDIATE, TipoFuente.AUTORIDAD, "colapso edificio")
    ciudadano = _sobre_con(Urgencia.IMMEDIATE, TipoFuente.CIUDADANO, "colapso muro")
    assert prioridad(autoridad) < prioridad(ciudadano)


def test_enlace_estrecho_saca_primero_lo_urgente_y_lo_oficial():
    motor = MotorMalla("nodo-local")
    autoridad = _sobre_con(Urgencia.IMMEDIATE, TipoFuente.AUTORIDAD, "gas escapando")
    urgente = _sobre_con(Urgencia.IMMEDIATE, TipoFuente.CIUDADANO, "gente atrapada")
    rutinarios = [
        _sobre_con(Urgencia.FUTURE, TipoFuente.CIUDADANO, f"rutinario {i}") for i in range(10)
    ]

    # El enlace solo aguanta dos, y los rutinarios llegaron primero.
    elegidos = motor.seleccionar_para_enlace([*rutinarios, urgente, autoridad], capacidad=2)

    assert [s.id_mensaje for s in elegidos] == [autoridad.id_mensaje, urgente.id_mensaje]


def test_a_igual_urgencia_y_fuente_sale_primero_el_mas_viejo():
    motor = MotorMalla("nodo-local")
    viejo = _sobre_con(Urgencia.IMMEDIATE, TipoFuente.CIUDADANO, "primero")
    nuevo = replace(
        _sobre_con(Urgencia.IMMEDIATE, TipoFuente.CIUDADANO, "segundo"),
        momento_origen=ahora() + timedelta(minutes=20),
    )
    assert motor.ordenar_por_prioridad([nuevo, viejo])[0].id_mensaje == viejo.id_mensaje


def test_capacidad_cero_no_manda_nada():
    motor = MotorMalla("nodo-local")
    assert motor.seleccionar_para_enlace([_sobre()], capacidad=0) == []


def test_vecinos_destino_excluye_a_quien_ya_lo_vio():
    motor = MotorMalla("nodo-local")
    sobre = _sobre().avanzar("B")
    destinos = motor.vecinos_destino(sobre, ["B", "C", "nodo-local"])
    assert destinos == ["C"]


def _sobre_con(urgencia: Urgencia, tipo_fuente: TipoFuente, texto: str) -> SobreMalla:
    return crear_sobre_firmado(
        IdentidadNodo.generar(),
        reporte(texto=texto, urgencia=urgencia, tipo_fuente=tipo_fuente).a_dict(),
    )
