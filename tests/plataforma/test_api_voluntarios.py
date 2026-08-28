"""Alta de voluntarios: persiste y nunca habilita por sí sola."""

from __future__ import annotations

ALTA = {
    "nombre_completo": "Ana Quispe",
    "documento": "48210233",
    "telefono": "+51999111222",
    "recurso": "Brigada médica",
}


async def test_registro_queda_en_verificacion(client):
    respuesta = client.post("/voluntarios", json=ALTA)

    assert respuesta.status_code == 201
    assert respuesta.json()["status"] == "en_verificacion"


async def test_el_alta_se_persiste(client, contenedor):
    client.post("/voluntarios", json=ALTA)

    guardados = await contenedor.voluntarios.listar()

    assert [v.nombre_completo for v in guardados] == ["Ana Quispe"]


async def test_acepta_el_contrato_camelcase_del_frontend(client):
    respuesta = client.post(
        "/voluntarios",
        json={
            "fullName": "Luis Rojas",
            "document": "10203040",
            "phone": "+51988777666",
            "resource": "Transporte",
        },
    )

    assert respuesta.status_code == 201


async def test_alta_sin_telefono_es_422(client):
    assert client.post("/voluntarios", json={**ALTA, "telefono": ""}).status_code == 422
