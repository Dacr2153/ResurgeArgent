"""Tests del caso de uso con dobles de prueba (fakes) de los puertos."""

import pytest

from agente_ingesta.aplicacion.casos_uso.ingerir_reportes import IngerirReportes
from agente_ingesta.dominio import ConfigVentana, MotorIngesta
from agente_ingesta.dominio.excepciones import LoteInvalidoError
from nucleo.auditoria import AuditoriaMemoria
from nucleo.mensajes import TipoEvento


class FakeExtractor:
    def __init__(self, extraido=None):
        self._extraido = extraido or {"categoria": "Fire", "urgencia": "Immediate"}
        self.llamadas = 0

    async def extraer(self, texto, contexto):
        self.llamadas += 1
        return dict(self._extraido)


class FakePublicador:
    def __init__(self):
        self.publicados = []

    async def publicar(self, evento):
        self.publicados.append(evento)


class FakeRepositorio:
    def __init__(self):
        self.guardados = []

    async def guardar(self, reportes):
        self.guardados.append(reportes)


def construir_caso_uso(limite=100, segundos=60.0, extraido=None):
    motor = MotorIngesta(ConfigVentana(limite=limite, segundos=segundos))
    extractor = FakeExtractor(extraido)
    auditoria = AuditoriaMemoria()
    publicador = FakePublicador()
    repositorio = FakeRepositorio()
    caso = IngerirReportes(motor, extractor, auditoria, publicador, repositorio)
    return caso, extractor, auditoria, publicador, repositorio


def reporte_texto(fuente_id="f1", texto="hay un incendio grande", canal="sms"):
    return {"fuente": {"id": fuente_id, "tipo": "ciudadano"}, "canal": canal, "texto": texto}


def reporte_sensor(fuente_id="sensor-1"):
    return {
        "fuente": {"id": fuente_id, "tipo": "sensor"},
        "canal": "sensor",
        "datos_sensor": {
            "descripcion": "Nivel de río sobre umbral",
            "categoria": "Geo",
            "severidad": "Severe",
            "ubicacion": {"lat": 4.6, "lon": -74.08},
        },
    }


@pytest.mark.asyncio
async def test_lote_vacio_no_publica_ni_guarda():
    caso, extractor, auditoria, publicador, repo = construir_caso_uso()
    aceptados = await caso.ingerir({"reportes": []})
    assert aceptados == []
    assert publicador.publicados == []
    assert repo.guardados == []
    assert extractor.llamadas == 0


@pytest.mark.asyncio
async def test_entrada_sin_clave_reportes_lanza_lote_invalido():
    caso, *_ = construir_caso_uso()
    with pytest.raises(LoteInvalidoError):
        await caso.ingerir({})


@pytest.mark.asyncio
async def test_entrada_no_es_dict_lanza_lote_invalido():
    caso, *_ = construir_caso_uso()
    with pytest.raises(LoteInvalidoError):
        await caso.ingerir(["no", "es", "un", "dict"])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_reporte_de_texto_libre_invoca_al_extractor():
    caso, extractor, *_ = construir_caso_uso()
    aceptados = await caso.ingerir({"reportes": [reporte_texto()]})
    assert extractor.llamadas == 1
    assert len(aceptados) == 1
    assert str(aceptados[0].categoria) == "Fire"


@pytest.mark.asyncio
async def test_reporte_de_sensor_no_invoca_al_extractor():
    caso, extractor, *_ = construir_caso_uso()
    aceptados = await caso.ingerir({"reportes": [reporte_sensor()]})
    assert extractor.llamadas == 0
    assert len(aceptados) == 1
    assert str(aceptados[0].severidad) == "Severe"
    assert aceptados[0].ubicacion is not None


@pytest.mark.asyncio
async def test_campo_explicito_del_reporte_gana_sobre_lo_inferido():
    caso, extractor, *_ = construir_caso_uso(extraido={"categoria": "Fire"})
    lote = [{**reporte_texto(), "categoria": "Rescue"}]
    aceptados = await caso.ingerir({"reportes": lote})
    assert str(aceptados[0].categoria) == "Rescue"


@pytest.mark.asyncio
async def test_auditoria_registra_recibido_y_descartado():
    caso, _, auditoria, *_ = construir_caso_uso()
    lote = [reporte_texto(fuente_id="f1"), {"fuente": {}, "canal": "sms", "texto": ""}]
    aceptados = await caso.ingerir({"reportes": lote})

    assert len(aceptados) == 1
    assert len(auditoria.por_tipo(str(TipoEvento.REPORTE_RECIBIDO))) == 1
    assert len(auditoria.por_tipo(str(TipoEvento.REPORTE_DESCARTADO))) == 1


@pytest.mark.asyncio
async def test_publica_y_guarda_solo_cuando_hay_aceptados():
    caso, *_, publicador, repo = construir_caso_uso()
    aceptados = await caso.ingerir({"reportes": [{"fuente": {}, "canal": "sms", "texto": ""}]})
    assert aceptados == []
    assert publicador.publicados == []
    assert repo.guardados == []


@pytest.mark.asyncio
async def test_correlacion_id_se_conserva_en_la_auditoria():
    caso, _, auditoria, *_ = construir_caso_uso()
    await caso.ingerir({"correlacion_id": "op-123", "reportes": [reporte_texto()]})
    eventos = auditoria.por_correlacion("op-123")
    assert len(eventos) == 1


@pytest.mark.asyncio
async def test_backpressure_persiste_entre_llamadas():
    caso, *_ = construir_caso_uso(limite=1)
    primero = await caso.ingerir({"reportes": [reporte_texto(fuente_id="f1", texto="uno")]})
    segundo = await caso.ingerir({"reportes": [reporte_texto(fuente_id="f2", texto="dos")]})
    assert len(primero) == 1
    assert len(segundo) == 0
