"""Adaptador REST del nodo de malla.

Ninguna prueba sale a la red: el `TestClient` habla con la app en el mismo
proceso, y tanto el transporte como la nube son dobles en memoria. El adaptador
`TransporteHTTP` y `NubeHTTP` no se instancian aquí a propósito.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from malla.adaptadores.entrada.api_rest import crear_app
from malla.config.contenedor import construir_contenedor
from malla.config.settings import Settings
from malla.dominio.firma import IdentidadNodo, crear_sobre_firmado
from tests.malla.conftest import NubeFalsa, TransporteMudo, reporte

REPORTE_JSON = {
    "texto": "Se cayo el puente peatonal, hay gente atrapada",
    "fuente": {"id": "ciudadano-1", "tipo": "ciudadano"},
    "canal": "app",
    "ubicacion": {"type": "Point", "coordinates": [-74.0817, 4.6097]},
    "categoria": "Rescue",
    "urgencia": "Immediate",
}


def _contenedor(tmp_path, hay_salida: bool = True):
    settings = Settings(
        ruta_identidad=str(tmp_path / "identidad.key"),
        ruta_almacen=str(tmp_path / "sobres.sqlite3"),
        ruta_auditoria=str(tmp_path / "auditoria.jsonl"),
    )
    return construir_contenedor(
        settings,
        transporte=TransporteMudo(),
        nube=NubeFalsa(hay_salida=hay_salida),
    )


@pytest.fixture
def contenedor(tmp_path):
    return _contenedor(tmp_path)


@pytest.fixture
def client(contenedor):
    return TestClient(crear_app(contenedor))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_nodo_expone_identidad_y_estado(client, contenedor):
    cuerpo = client.get("/nodo").json()

    assert cuerpo["id_nodo"] == contenedor.identidad.id_nodo
    assert cuerpo["clave_publica"] == contenedor.identidad.clave_publica
    assert cuerpo["vecinos"] == []
    assert cuerpo["pendientes"] == 0
    assert cuerpo["salida_internet"] is True
    assert cuerpo["ttl_por_defecto"] == 8


def test_originar_reporte_devuelve_el_sobre_firmado(client, contenedor):
    respuesta = client.post("/reportes", json=REPORTE_JSON)

    assert respuesta.status_code == 201
    sobre = respuesta.json()["sobre"]
    assert sobre["nodo_origen"] == contenedor.identidad.id_nodo
    assert sobre["saltos"] == 0
    assert len(sobre["firma"]) == 128  # Ed25519: 64 bytes en hexadecimal
    assert client.get("/nodo").json()["pendientes"] == 1


def test_reporte_con_geometria_invalida_es_422(client):
    malo = REPORTE_JSON | {"ubicacion": {"type": "LineString", "coordinates": []}}
    assert client.post("/reportes", json=malo).status_code == 422


def test_recibir_sobre_valido_de_un_vecino(client):
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())

    respuesta = client.post("/sobres", json=sobre.a_dict())

    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert cuerpo["resultado"] == "aceptado_y_reenviar"
    assert cuerpo["id_mensaje"] == sobre.id_mensaje
    assert client.get("/nodo").json()["pendientes"] == 1


def test_sobre_con_firma_invalida_se_rechaza_y_no_se_almacena(client):
    """202 y no 4xx: quien lo entrega suele ser un nodo honesto, no el atacante.

    Devolverle un error le haria reintentar en bucle un sobre que nunca va a ser
    aceptado. El rechazo queda en el cuerpo de la respuesta y en la auditoria.
    """
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    alterado = replace(sobre, carga=dict(sobre.carga) | {"personas_afectadas": 900})

    respuesta = client.post("/sobres", json=alterado.a_dict())

    assert respuesta.status_code == 202
    assert respuesta.json()["resultado"] == "firma_invalida"
    assert respuesta.json()["reenviado"] is False
    assert client.get("/nodo").json()["pendientes"] == 0


def test_sobre_duplicado_no_se_reenvia(client):
    sobre = crear_sobre_firmado(IdentidadNodo.generar(), reporte().a_dict())
    client.post("/sobres", json=sobre.a_dict())

    # El mismo reporte vuelve por otro camino, con otra ruta y otro numero de saltos.
    otra_ruta = sobre.avanzar("vecino-lejano").avanzar("otro-vecino")
    respuesta = client.post("/sobres", json=otra_ruta.a_dict())

    assert respuesta.status_code == 202
    assert respuesta.json()["resultado"] == "duplicado"
    assert respuesta.json()["reenviado"] is False
    assert client.get("/nodo").json()["pendientes"] == 1


def test_sobre_mal_formado_es_422(client):
    assert client.post("/sobres", json={"id_mensaje": "x"}).status_code == 422


def test_un_vecino_se_lleva_lo_que_no_tiene(client):
    for texto in ("incendio en el mercado", "via bloqueada por lodo"):
        client.post("/reportes", json=REPORTE_JSON | {"texto": texto})

    todos = client.get("/sobres?desde=0").json()
    assert len(todos["sobres"]) == 2

    primera = client.get("/sobres?desde=0&limite=1").json()
    assert len(primera["sobres"]) == 1

    resto = client.get(f"/sobres?desde={primera['siguiente']}").json()
    assert len(resto["sobres"]) == 1
    assert resto["sobres"][0]["id_mensaje"] != primera["sobres"][0]["id_mensaje"]

    # Un vecino ya al dia no se lleva nada.
    assert client.get(f"/sobres?desde={resto['siguiente']}").json()["sobres"] == []


def test_sincronizar_sube_el_lote(client, contenedor):
    client.post("/reportes", json=REPORTE_JSON)

    cuerpo = client.post("/sincronizar").json()

    assert cuerpo["hubo_salida"] is True
    assert cuerpo["total"] == 1
    assert contenedor.nube.recibidos == cuerpo["subidos"]
    assert client.get("/nodo").json()["pendientes"] == 0


def test_sincronizar_sin_salida_no_sube_nada(tmp_path):
    contenedor = _contenedor(tmp_path, hay_salida=False)
    client = TestClient(crear_app(contenedor))
    client.post("/reportes", json=REPORTE_JSON)

    cuerpo = client.post("/sincronizar").json()

    assert cuerpo["hubo_salida"] is False
    assert cuerpo["total"] == 0
    assert contenedor.nube.recibidos == []
    # El reporte sigue guardado: sin nube no se pierde nada.
    assert client.get("/nodo").json()["pendientes"] == 1
    assert client.get("/nodo").json()["salida_internet"] is False


def test_senalizacion_permite_que_dos_pares_se_encuentren(client):
    client.post("/senalizacion/anuncios", json={"id_nodo": "nav-a", "descripcion": {}})
    client.post("/senalizacion/anuncios", json={"id_nodo": "nav-b", "descripcion": {}})

    pares = client.get("/senalizacion/pares?excluir=nav-a").json()["pares"]
    assert [p["id_nodo"] for p in pares] == ["nav-b"]

    client.post(
        "/senalizacion/senales",
        json={
            "remitente": "nav-a",
            "destino": "nav-b",
            "tipo": "oferta",
            "datos": {"sdp": "v=0"},
        },
    )

    buzon = client.get("/senalizacion/senales?destino=nav-b").json()["senales"]
    assert buzon[0]["tipo"] == "oferta"
    # El buzon se vacia al leerse: es un punto de encuentro, no un historico.
    assert client.get("/senalizacion/senales?destino=nav-b").json()["senales"] == []
