"""Tests puros del motor logístico (routing + vehículos + viajes)."""

import pytest

from agente_logistica.dominio import (
    ESTADO_BLOQUEADA,
    ESTADO_PLANIFICADA,
    Arista,
    Asignacion,
    GrafoMovilidad,
    MotorLogistica,
    Ubicacion,
    Vehiculo,
)


def u(lat=0.0, lon=0.0):
    return Ubicacion(lat, lon)


def asignacion(id_="A001", origen="A", destino="C", cantidad=100.0, unidad="litros", prioridad=1):
    return Asignacion(
        id=id_,
        necesidad_id="N",
        recurso_id="R",
        tipo="agua",
        origen_id=origen,
        destino_id=destino,
        origen=u(),
        destino=u(),
        cantidad=cantidad,
        unidad=unidad,
        prioridad=prioridad,
    )


def vehiculo(id_="V1", capacidad=100.0, unidad="litros", disponible=True):
    return Vehiculo(
        id=id_,
        tipo="camion",
        capacidad=capacidad,
        unidad_capacidad=unidad,
        ubicacion=u(),
        disponible=disponible,
    )


def motor(pesos=None):
    p = {"alfa": 0.5, "beta": 0.5, "gamma": 0.0, "delta": 0.0}
    p.update(pesos or {})
    return MotorLogistica(p)


def grafo_lineal():
    aristas = [
        Arista("A", "B", distancia=2.0, tiempo=10.0, estado="DISPONIBLE", via_id="V1"),
        Arista("B", "C", distancia=3.0, tiempo=15.0, estado="DISPONIBLE", via_id="V2"),
    ]
    return GrafoMovilidad(nodos=("A", "B", "C"), aristas=tuple(aristas))


def grafo_diamante():
    aristas = [
        Arista("A", "B", distancia=2.0, tiempo=10.0, estado="DISPONIBLE", via_id="V1"),
        Arista("B", "C", distancia=3.0, tiempo=15.0, estado="DISPONIBLE", via_id="V2"),
        Arista("A", "D", distancia=4.0, tiempo=20.0, estado="DISPONIBLE", via_id="V3"),
        Arista("D", "C", distancia=4.0, tiempo=20.0, estado="DISPONIBLE", via_id="V4"),
    ]
    return GrafoMovilidad(nodos=("A", "B", "C", "D"), aristas=tuple(aristas))


def _unica(plan):
    assert len(plan.operaciones) == 1
    return plan.operaciones[0]


def test_ruta_simple_y_viajes_uno():
    plan = motor().planificar([asignacion()], [vehiculo()], [], grafo_lineal())
    op = _unica(plan)
    assert op.estado == ESTADO_PLANIFICADA
    assert op.vehiculo_id == "V1"
    assert op.ruta.nodos == ("A", "B", "C")
    assert op.ruta.distancia == pytest.approx(5.0)
    assert op.ruta.tiempo_estimado == pytest.approx(25.0)
    assert op.viajes == 1


def test_via_bloqueada_destino_inaccesible():
    restricciones = [{"tipo": "VIA_BLOQUEADA", "via_id": "V2"}]
    plan = motor().planificar([asignacion()], [vehiculo()], restricciones, grafo_lineal())
    op = _unica(plan)
    assert op.estado == ESTADO_BLOQUEADA
    assert op.motivo == "DESTINO_INACCESIBLE"
    assert op.ruta is None


def test_via_bloqueada_toma_ruta_alternativa():
    restricciones = [{"tipo": "VIA_BLOQUEADA", "via_id": "V1"}]
    plan = motor().planificar([asignacion()], [vehiculo()], restricciones, grafo_diamante())
    op = _unica(plan)
    assert op.estado == ESTADO_PLANIFICADA
    assert op.ruta.nodos == ("A", "D", "C")


def test_arista_con_estado_bloqueada_se_evita():
    aristas = [
        Arista("A", "B", distancia=2.0, tiempo=10.0, estado="DISPONIBLE", via_id="V1"),
        Arista("B", "C", distancia=3.0, tiempo=15.0, estado="BLOQUEADA", via_id="V2"),
    ]
    grafo = GrafoMovilidad(nodos=("A", "B", "C"), aristas=tuple(aristas))
    plan = motor().planificar([asignacion()], [vehiculo()], [], grafo)
    assert _unica(plan).estado == ESTADO_BLOQUEADA


def test_multiple_viajes_por_capacidad():
    plan = motor().planificar(
        [asignacion(cantidad=300.0)], [vehiculo(capacidad=100.0)], [], grafo_lineal()
    )
    op = _unica(plan)
    assert op.viajes == 3
    assert op.estado == ESTADO_PLANIFICADA


def test_vehiculo_incompatible_por_unidad():
    plan = motor().planificar(
        [asignacion(unidad="litros")], [vehiculo(unidad="kg")], [], grafo_lineal()
    )
    op = _unica(plan)
    assert op.estado == ESTADO_BLOQUEADA
    assert op.motivo == "SIN_VEHICULO_COMPATIBLE"


def test_vehiculo_no_disponible_se_excluye():
    plan = motor().planificar([asignacion()], [vehiculo(disponible=False)], [], grafo_lineal())
    op = _unica(plan)
    assert op.estado == ESTADO_BLOQUEADA
    assert op.motivo == "SIN_VEHICULO_COMPATIBLE"


def test_elige_vehiculo_de_menor_capacidad_suficiente():
    plan = motor().planificar(
        [asignacion(cantidad=100.0)],
        [vehiculo("V1", capacidad=100.0), vehiculo("V2", capacidad=500.0)],
        [],
        grafo_lineal(),
    )
    op = _unica(plan)
    assert op.vehiculo_id == "V1"


def test_ordena_por_prioridad():
    a1 = asignacion(id_="A001", cantidad=50.0, prioridad=1)
    a2 = asignacion(id_="A002", cantidad=50.0, prioridad=10)
    plan = motor().planificar([a1, a2], [vehiculo()], [], grafo_lineal())
    assert plan.operaciones[0].asignacion_id == "A002"
    assert plan.operaciones[1].asignacion_id == "A001"


def test_sin_ruta_no_inventa_solucion():
    plan = motor().planificar(
        [asignacion(origen="X", destino="Y")], [vehiculo()], [], grafo_lineal()
    )
    op = _unica(plan)
    assert op.estado == ESTADO_BLOQUEADA
    assert op.motivo == "DESTINO_INACCESIBLE"
