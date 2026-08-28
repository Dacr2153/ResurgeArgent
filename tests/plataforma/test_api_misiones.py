"""Misiones: filtrado por distancia real y detalle."""

from __future__ import annotations

from tests.plataforma.conftest import MISION, MISION_LEJOS


async def test_apertura_y_detalle(client):
    assert client.post("/misiones", json=MISION).status_code == 201

    cuerpo = client.get("/misiones/INC-2481").json()

    assert cuerpo["incidentId"] == "INC-2481"
    assert cuerpo["address"] == "Jr. Camaná 654"
    assert cuerpo["checklist"] == [{"key": "agua", "label": "Agua · 6 L"}]
    assert cuerpo["etaMinutes"] > 0


async def test_mision_inexistente_es_404(client):
    assert client.get("/misiones/INC-NADA").status_code == 404


async def test_el_radio_recorta_por_distancia_real(client):
    client.post("/misiones", json=MISION)
    client.post("/misiones", json=MISION_LEJOS)

    cercanas = client.get("/misiones", params={"radio_km": 1.0}).json()
    todas = client.get("/misiones", params={"radio_km": 10.0}).json()

    assert [m["id"] for m in cercanas] == ["INC-2481"]
    assert {m["id"] for m in todas} == {"INC-2481", "INC-2488"}


async def test_sin_radio_devuelve_todo_ordenado_por_prioridad(client):
    client.post("/misiones", json=MISION_LEJOS)
    client.post("/misiones", json=MISION)

    misiones = client.get("/misiones").json()

    assert [m["score"] for m in misiones] == [92, 38]


async def test_la_distancia_se_mide_desde_el_punto_pedido(client):
    client.post("/misiones", json=MISION)

    desde_base = client.get("/misiones").json()[0]["distanceKm"]
    encima = client.get(
        "/misiones", params={"lat": MISION["lat"], "lon": MISION["lon"]}
    ).json()[0]["distanceKm"]

    assert desde_base > 0.0
    assert encima == 0.0


async def test_coordenada_invalida_es_422(client):
    assert client.get("/misiones", params={"lat": 999.0, "lon": 0.0}).status_code == 422
