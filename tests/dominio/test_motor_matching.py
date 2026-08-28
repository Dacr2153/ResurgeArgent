"""Tests puros del motor de matching. Sin mocks ni I/O."""

import pytest

from agente_matching.dominio import (
    CapacidadInsuficienteError,
    Empresa,
    MotorMatching,
    Necesidad,
    Prioridad,
    Recurso,
    SinDemandaError,
    Ubicacion,
)


def u(lat=0.0, lon=0.0):
    return Ubicacion(lat, lon)


def nec(id_, tipo="agua", cant=100.0, prioridad=1, zona="Z", ubicacion=None):
    return Necesidad(
        id=id_,
        zona_id=zona,
        tipo=tipo,
        cantidad_requerida=cant,
        prioridad=Prioridad(prioridad),
        ubicacion=ubicacion or u(),
    )


def rec(id_, tipo="agua", cant=100.0, ubicacion=None, lugar="L"):
    return Recurso(
        id=id_,
        lugar_id=lugar,
        tipo=tipo,
        cantidad_disponible=cant,
        ubicacion=ubicacion or u(),
    )


def emp(id_, n=4, transito=0, zonas=None):
    return Empresa(
        id=id_,
        nombre=id_,
        ubicacion=u(),
        num_vehiculos=n,
        num_en_transito=transito,
        zonas_cobertura=zonas,
    )


def motor(pesos=None, capacidad_uniforme=10.0):
    p = {"w1": 1.0, "w2": 1.0, "w3": 100.0, "w4": 1.0}
    p.update(pesos or {})
    return MotorMatching(pesos=p, factor_escala=100, capacidad_uniforme=capacidad_uniforme)


def cubierto(resultado):
    return resultado.resumen.demanda_cubierta


def sin_cubrir(resultado):
    return resultado.resumen.demanda_sin_cubrir


def causas(resultado):
    return {nc.causa: nc.cantidad for nc in resultado.no_cubierto}


# --------------------------------------------------------------- básicos


def test_asigna_todo_cuando_hay_suficiente():
    r = motor().ejecutar([nec("N1", cant=100)], [rec("R1", cant=150)], [emp("E1", n=20)])
    assert cubierto(r) == pytest.approx(100)
    assert sin_cubrir(r) == pytest.approx(0)
    assert r.resumen.por_empresa["E1"]["asignado"] == pytest.approx(100)


def test_flota_insuficiente_genera_sin_capacidad():
    r = motor().ejecutar([nec("N1", cant=100)], [rec("R1", cant=150)], [emp("E1", n=5)])
    assert cubierto(r) == pytest.approx(50)
    assert causas(r)["sin_capacidad"] == pytest.approx(50)


def test_tipo_incompatible_genera_sin_recurso():
    r = motor().ejecutar(
        [nec("N1", tipo="agua", cant=100)], [rec("R1", tipo="comida", cant=150)], [emp("E1", n=20)]
    )
    assert cubierto(r) == pytest.approx(0)
    assert causas(r)["sin_recurso"] == pytest.approx(100)


def test_stock_insuficiente_genera_sin_recurso():
    r = motor().ejecutar([nec("N1", cant=100)], [rec("R1", cant=50)], [emp("E1", n=20)])
    assert cubierto(r) == pytest.approx(50)
    assert causas(r)["sin_recurso"] == pytest.approx(50)


def test_sin_necesidades_lanza_excepcion():
    with pytest.raises(SinDemandaError):
        motor().ejecutar([], [rec("R1")], [emp("E1")])


def test_asignacion_fija_excede_stock_lanza_excepcion():
    fijas = [{"empresa_id": "E1", "recurso_id": "R1", "necesidad_id": "N1", "cantidad": 200}]
    with pytest.raises(CapacidadInsuficienteError):
        motor().ejecutar([nec("N1", cant=100)], [rec("R1", cant=150)], [emp("E1", n=20)], fijas)


# --------------------------------------------------------------- pesos


def test_prefiere_recurso_mas_cercano():
    cerca = rec("R1", cant=100, ubicacion=u(0.0, 0.0))
    lejos = rec("R2", cant=100, ubicacion=u(0.0, 5.0))
    r = motor().ejecutar(
        [nec("N1", cant=50, ubicacion=u(0.0, 0.0))], [cerca, lejos], [emp("E1", n=20)]
    )
    asignado_cerca = sum(a.cantidad for a in r.asignaciones if a.recurso_id == "R1")
    asignado_lejos = sum(a.cantidad for a in r.asignaciones if a.recurso_id == "R2")
    assert asignado_cerca == pytest.approx(50)
    assert asignado_lejos == pytest.approx(0)


def test_prioridad_alta_atrae_recurso_escaso():
    r = motor().ejecutar(
        [nec("N1", cant=50, prioridad=1), nec("N2", cant=50, prioridad=10)],
        [rec("R1", cant=50)],
        [emp("E1", n=20)],
    )
    asignado_prioritario = sum(a.cantidad for a in r.asignaciones if a.necesidad_id == "N2")
    assert asignado_prioritario == pytest.approx(50)


def test_empresa_en_transito_es_preferida():
    r = motor().ejecutar(
        [nec("N1", cant=40)],
        [rec("R1", cant=100)],
        [emp("E1", n=4, transito=0), emp("E2", n=4, transito=4)],
    )
    assert r.resumen.por_empresa["E2"]["asignado"] == pytest.approx(40)
    assert r.resumen.por_empresa["E1"]["asignado"] == pytest.approx(0)


# --------------------------------------------------------------- capacidades


def test_total_por_empresa_no_excede_flota():
    r = motor().ejecutar(
        [nec("N1", cant=100)],
        [rec("R1", cant=200)],
        [emp("A", n=4), emp("B", n=4), emp("C", n=4)],
    )
    for empresa in ["A", "B", "C"]:
        assert r.resumen.por_empresa[empresa]["asignado"] <= 40 + 1e-6
    assert cubierto(r) == pytest.approx(100)


def test_escenario_abc_cuatro_vehiculos():
    r = motor().ejecutar(
        [nec("N1", cant=100)],
        [rec("R1", cant=200)],
        [emp("A", n=4), emp("B", n=4), emp("C", n=4)],
    )
    assert r.resumen.por_empresa["A"]["asignado"] == pytest.approx(40)
    assert r.resumen.por_empresa["B"]["asignado"] == pytest.approx(40)
    assert r.resumen.por_empresa["C"]["asignado"] == pytest.approx(20)


def test_total_por_recurso_no_excede_stock():
    r = motor().ejecutar(
        [nec("N1", cant=50), nec("N2", cant=50)],
        [rec("R1", cant=60)],
        [emp("E1", n=20)],
    )
    asignado = sum(a.cantidad for a in r.asignaciones if a.recurso_id == "R1")
    assert asignado == pytest.approx(60)


def test_cargas_parciales_un_vehiculo_dos_necesidades():
    # Un vehículo (flota 10) reparte su capacidad entre dos necesidades.
    r = motor().ejecutar(
        [nec("N1", cant=5), nec("N2", cant=5)],
        [rec("R1", cant=100)],
        [emp("E1", n=1)],
    )
    assert cubierto(r) == pytest.approx(10)
    assert r.resumen.por_empresa["E1"]["asignado"] == pytest.approx(10)


# --------------------------------------------------------------- fijas


def test_asignaciones_fijas_se_respetan():
    fijas = [{"empresa_id": "E1", "recurso_id": "R1", "necesidad_id": "N1", "cantidad": 30}]
    r = motor().ejecutar([nec("N1", cant=100)], [rec("R1", cant=150)], [emp("E1", n=20)], fijas)
    fijas_en_resultado = [a for a in r.asignaciones if a.cantidad == pytest.approx(30)]
    assert len(fijas_en_resultado) == 1
    assert cubierto(r) == pytest.approx(100)


# --------------------------------------------------------------- cobertura


def test_zona_fuera_cobertura_no_atribuible():
    r = motor().ejecutar(
        [nec("N1", zona="Z2", cant=100)],
        [rec("R1", cant=100)],
        [emp("E1", n=20, zonas=frozenset({"Z1"}))],
    )
    assert len(r.asignaciones) == 0
    assert causas(r)["zona_fuera_cobertura"] == pytest.approx(100)


def test_cobertura_nula_permite_cualquier_zona():
    r = motor().ejecutar(
        [nec("N1", zona="Z2", cant=100)],
        [rec("R1", cant=100)],
        [emp("E1", n=20, zonas=None)],
    )
    assert cubierto(r) == pytest.approx(100)
