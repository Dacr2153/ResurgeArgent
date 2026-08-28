"""Tests del caso de uso del Agente 8 con dobles de prueba."""

import pytest

from agente_logistica.adaptadores.salida.geographic_provider_memoria import (
    GeographicProviderMemoria,
)
from agente_logistica.aplicacion.casos_uso.planificar_logistica import PlanificarLogistica
from agente_logistica.dominio import MotorLogistica


class FakeLLM:
    def __init__(self):
        self.normalizar_llamadas = 0
        self.explicar_llamadas = 0

    async def normalizar(self, crudo):
        self.normalizar_llamadas += 1
        return crudo

    async def explicar(self, plan, contexto):
        self.explicar_llamadas += 1
        return {**plan, "supuestos": [], "justificaciones": ["ok"]}


class FakePublicador:
    def __init__(self):
        self.publicados = []

    async def publicar(self, evento):
        self.publicados.append(evento)


ENTRADA = {
    "asignaciones": [
        {
            "id": "A001",
            "necesidad_id": "N001",
            "recurso_id": "R001",
            "tipo": "agua",
            "origen": {"id": "A", "latitud": 4.61, "longitud": -74.08},
            "destino": {"id": "C", "latitud": 4.65, "longitud": -74.06},
            "cantidad": 500.0,
            "unidad": "litros",
            "prioridad": 10,
        }
    ],
    "vehiculos": [
        {
            "id": "V1",
            "tipo": "camion",
            "capacidad": 1000.0,
            "unidad_capacidad": "litros",
            "ubicacion": {"latitud": 4.60, "longitud": -74.09},
            "disponible": True,
        }
    ],
    "restricciones": [],
    "mapa": {
        "nodos": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
        "aristas": [
            {
                "origen": "A",
                "destino": "B",
                "distancia": 2.0,
                "tiempo": 10.0,
                "estado": "DISPONIBLE",
                "via_id": "V1",
            },
            {
                "origen": "B",
                "destino": "C",
                "distancia": 3.0,
                "tiempo": 15.0,
                "estado": "DISPONIBLE",
                "via_id": "V2",
            },
        ],
    },
}


def construir_caso_uso():
    motor = MotorLogistica({"alfa": 0.5, "beta": 0.5, "gamma": 0.0, "delta": 0.0})
    llm = FakeLLM()
    publicador = FakePublicador()
    caso = PlanificarLogistica(motor, GeographicProviderMemoria(), llm, publicador)
    return caso, llm, publicador


@pytest.mark.asyncio
async def test_flujo_completo():
    caso, llm, publicador = construir_caso_uso()
    resultado = await caso.ejecutar(ENTRADA)

    assert llm.normalizar_llamadas == 1
    assert llm.explicar_llamadas == 1
    assert len(publicador.publicados) == 1

    assert resultado["plan_id"] == "PLAN_001"
    assert resultado["estado"] == "PLANIFICADA"
    assert len(resultado["operaciones"]) == 1

    op = resultado["operaciones"][0]
    assert op["vehiculo_id"] == "V1"
    assert op["viajes"] == 1
    assert op["ruta"]["nodos"] == ["A", "B", "C"]
    assert op["ruta"]["distancia"] == pytest.approx(5.0)
    assert op["estado"] == "PLANIFICADA"
    assert resultado["justificaciones"] == ["ok"]


@pytest.mark.asyncio
async def test_asignacion_no_enrutable_se_bloquea():
    caso, _, _ = construir_caso_uso()
    entrada = {
        **ENTRADA,
        "asignaciones": [
            {
                "id": "A002",
                "necesidad_id": "N002",
                "recurso_id": "R002",
                "tipo": "agua",
                "origen": {"id": "X", "latitud": 1.0, "longitud": 1.0},
                "destino": {"id": "Y", "latitud": 2.0, "longitud": 2.0},
                "cantidad": 10.0,
                "unidad": "litros",
                "prioridad": 1,
            }
        ],
    }
    resultado = await caso.ejecutar(entrada)
    op = resultado["operaciones"][0]
    assert op["estado"] == "BLOQUEADA"
    assert op["motivo"] == "DESTINO_INACCESIBLE"
