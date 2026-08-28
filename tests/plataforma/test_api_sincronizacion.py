"""Cola de reportes creados sin cobertura."""

from __future__ import annotations

REPORTE = {
    "titulo": "Reporte · Incendio Jr. Camaná",
    "meta": "con foto · 1.2 MB",
    "puntuacion": 92,
}
SEGUNDO = {**REPORTE, "titulo": "Reporte · Techo dañado", "puntuacion": 41}


async def test_la_cola_arranca_vacia(client):
    assert client.get("/sincronizacion").json() == []


async def test_encolar_y_vaciar(client):
    client.post("/sincronizacion/reportes", json=REPORTE)
    client.post("/sincronizacion/reportes", json=SEGUNDO)

    pendientes = client.get("/sincronizacion").json()
    vaciado = client.post("/sincronizacion").json()

    assert [r["score"] for r in pendientes] == [92, 41]
    assert vaciado == {"sent": 2}
    assert client.get("/sincronizacion").json() == []


async def test_vaciar_una_cola_vacia_no_falla(client):
    assert client.post("/sincronizacion").json() == {"sent": 0}
