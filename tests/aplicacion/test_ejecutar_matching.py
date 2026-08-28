"""Tests del caso de uso con dobles de prueba (fakes) de los puertos."""

import pytest

from agente_matching.aplicacion.casos_uso.ejecutar_matching import EjecutarMatching
from agente_matching.dominio import MotorMatching


class FakeLLM:
    def __init__(self, normalizado=None):
        self._normalizado = normalizado
        self.normalizar_llamadas = 0
        self.justificar_llamadas = 0

    async def normalizar(self, crudo):
        self.normalizar_llamadas += 1
        return self._normalizado if self._normalizado is not None else crudo

    async def justificar(self, resultado, contexto):
        self.justificar_llamadas += 1
        return {**resultado, "supuestos": [], "justificaciones": ["ok"]}


class FakePublicador:
    def __init__(self):
        self.publicados = []

    async def publicar(self, evento):
        self.publicados.append(evento)


class FakeRepositorio:
    def __init__(self):
        self.guardados = []

    async def guardar(self, resultado):
        self.guardados.append(resultado)


ENTRADA = {
    "necesidades": [
        {
            "id": "N1",
            "zona_id": "Z-A",
            "tipo": "agua",
            "cantidad_requerida": 100.0,
            "prioridad": 3,
            "ubicacion": {"lat": 4.7110, "lon": -74.0721},
        }
    ],
    "recursos": [
        {
            "id": "R1",
            "lugar_id": "Z-B",
            "tipo": "agua",
            "cantidad_disponible": 150.0,
            "ubicacion": {"lat": 4.6000, "lon": -74.0800},
        }
    ],
    "empresas": [
        {
            "id": "E1",
            "nombre": "Empresa A",
            "ubicacion": {"lat": 4.6500, "lon": -74.0900},
            "zonas_cobertura": None,
            "num_vehiculos": 20,
            "num_en_transito": 1,
        }
    ],
    "asignaciones_fijas": [
        {"empresa_id": "E1", "recurso_id": "R1", "necesidad_id": "N1", "cantidad": 10.0}
    ],
}


def construir_caso_uso():
    motor = MotorMatching(pesos={"w1": 1.0, "w2": 1.0, "w3": 100.0, "w4": 1.0})
    llm = FakeLLM()
    publicador = FakePublicador()
    repo = FakeRepositorio()
    return EjecutarMatching(motor, llm, publicador, repo), llm, publicador, repo


@pytest.mark.asyncio
async def test_flujo_completo():
    caso, llm, publicador, repo = construir_caso_uso()
    resultado = await caso.ejecutar(ENTRADA)

    assert llm.normalizar_llamadas == 1
    assert llm.justificar_llamadas == 1
    assert len(publicador.publicados) == 1
    assert len(repo.guardados) == 1

    assert "asignaciones" in resultado
    assert "no_cubierto" in resultado
    assert "resumen" in resultado
    assert "justificaciones" in resultado
    assert resultado["resumen"]["demanda_cubierta"] == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_publica_el_resultado_final_justificado():
    caso, llm, publicador, _ = construir_caso_uso()
    resultado = await caso.ejecutar(ENTRADA)

    publicado = publicador.publicados[-1]
    assert publicado is resultado
    assert publicado["justificaciones"] == ["ok"]
