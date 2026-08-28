"""Cuestionario persistido y plan derivado por reglas."""

from __future__ import annotations


async def test_las_preguntas_vienen_del_repositorio(client):
    preguntas = client.get("/recuperacion/preguntas").json()

    assert [p["id"] for p in preguntas] == ["vivienda", "salud", "medios"]
    assert all(p["options"] for p in preguntas)


async def test_el_plan_se_numera_en_orden_de_plazo(client):
    pasos = client.post(
        "/recuperacion/plan",
        json={"respuestas": {"vivienda": "No, está inhabitable", "medios": "Documentos"}},
    ).json()

    assert pasos[0]["tag"] == "PASO 1 · HOY"
    assert pasos[-1]["tag"].endswith("15 DÍAS")
    assert [p["tag"].split(" ")[1] for p in pasos] == [str(i) for i in range(1, len(pasos) + 1)]


async def test_sin_respuestas_queda_solo_el_paso_base(client):
    pasos = client.post("/recuperacion/plan", json={"respuestas": {}}).json()

    assert [p["title"] for p in pasos] == ["Constancia de damnificado"]
