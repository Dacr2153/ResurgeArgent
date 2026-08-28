"""Tests del caso de uso, con dobles de prueba de los puertos.

Incluye el test estrella del Agente 3: 40 reportes del mismo derrumbe, de
fuentes distintas, con texto variado y GPS ligeramente disperso, deben
colapsar en exactamente un `IncidenteVerificado` con las 40 corroboraciones y
confianza alta. Es el mayor diferenciador del proyecto: sin esto, cuarenta
reportes de un mismo derrumbe saturarían al Orquestador como si fueran
cuarenta emergencias distintas.
"""

import random

import pytest

from agente_verificacion.adaptadores.llm.similitud_nula import SimilitudNula
from agente_verificacion.aplicacion.casos_uso.verificar_reportes import VerificarReportes
from agente_verificacion.dominio.motor_verificacion import MotorVerificacion
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    Fuente,
    ReporteCrudo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import Punto
from nucleo.mensajes import TipoEvento, ahora

SITIO = Punto(lat=4.6097, lon=-74.0817)
LEJOS = Punto(lat=4.9500, lon=-74.3500)


class FakePublicador:
    def __init__(self):
        self.publicados = []

    async def publicar(self, evento):
        self.publicados.append(evento)


class FakeRepositorio:
    def __init__(self):
        self.guardados = []

    async def guardar(self, incidentes):
        self.guardados.append(incidentes)


def _fuente(id_, tipo=TipoFuente.CIUDADANO, reputacion=0.6) -> Fuente:
    return Fuente(id=id_, tipo=tipo, nombre=id_, reputacion=reputacion)


def _reporte(
    texto,
    fuente,
    ubicacion=SITIO,
    categoria=Categoria.RESCUE,
    urgencia=Urgencia.IMMEDIATE,
    severidad=Severidad.SEVERE,
    certeza=Certeza.OBSERVED,
) -> ReporteCrudo:
    return ReporteCrudo(
        texto=texto,
        fuente=fuente,
        canal=Canal.SMS,
        ubicacion=ubicacion,
        categoria=categoria,
        urgencia=urgencia,
        severidad=severidad,
        certeza=certeza,
        recibido_en=ahora(),
    )


def _construir_caso_uso(**pesos_motor):
    motor = MotorVerificacion(**pesos_motor)
    similitud = SimilitudNula()
    publicador = FakePublicador()
    repositorio = FakeRepositorio()
    auditoria = AuditoriaMemoria()
    caso = VerificarReportes(motor, similitud, publicador, repositorio, auditoria)
    return caso, publicador, repositorio, auditoria


# ------------------------------------------------------------- test estrella
# Cinco redacciones GENUINAMENTE distintas del mismo hecho, sin vocabulario
# compartido de propósito ("puente" / "estructura sobre el río" / "vía" /
# "montaña" / "paso"): es el caso que expuso el defecto original, donde la
# fusión dependía por completo de que el texto se pareciera léxicamente. Con
# SimilitudNula (Jaccard) estas frases casi no comparten tokens entre sí, así
# que si la fusión siguiera necesitando apoyo textual, este test fallaría tal
# como falló en el reporte de regresión.
FRASES_DERRUMBE = [
    "Se cayó el puente",
    "Colapsó la estructura sobre el río",
    "Derrumbe tapó la vía",
    "La montaña se vino encima de la carretera",
    "Deslizamiento bloquea el paso",
]


@pytest.mark.asyncio
async def test_cuarenta_reportes_del_mismo_derrumbe_colapsan_en_un_incidente():
    random.seed(0)
    reportes = []
    for i in range(40):
        frase = FRASES_DERRUMBE[i % len(FRASES_DERRUMBE)]
        # Dispersión de GPS de hasta ~110 m por eje: simula el temblor normal
        # del GPS de distintos teléfonos reportando el mismo punto, bien
        # dentro del radio por defecto (500 m).
        jitter_lat = random.uniform(-0.001, 0.001)
        jitter_lon = random.uniform(-0.001, 0.001)
        ubicacion = Punto(lat=SITIO.lat + jitter_lat, lon=SITIO.lon + jitter_lon)
        fuente = _fuente(f"fuente-{i}", tipo=TipoFuente.CIUDADANO, reputacion=0.6)
        reportes.append(
            _reporte(frase, fuente, ubicacion=ubicacion, categoria=Categoria.GEO)
        )

    caso, publicador, repositorio, auditoria = _construir_caso_uso()

    incidentes = await caso.verificar(reportes)

    assert len(incidentes) == 1
    incidente = incidentes[0]
    assert incidente.corroboraciones == 40
    assert set(incidente.reportes_origen) == {r.id for r in reportes}
    assert incidente.confianza > 0.9

    eventos_fusion = auditoria.por_tipo(str(TipoEvento.INCIDENTE_FUSIONADO))
    assert len(eventos_fusion) == 1
    assert len(repositorio.guardados[0]) == 1
    assert len(publicador.publicados) == 1


@pytest.mark.asyncio
async def test_caso_ambiguo_distancia_intermedia_y_texto_distinto_no_fusiona():
    # Dos reportes de la misma categoría, dentro del radio configurado pero
    # más allá de la "zona segura" (~450 m de 500 m), y con textos que no
    # comparten nada: ni la geometría sola ni el texto solo alcanzan el
    # umbral, así que legítimamente NO deben fusionarse. Este es el caso que
    # sí debe seguir dependiendo del texto (o de un LLM que confirme el
    # parecido semántico) para decidir.
    ambiguo = Punto(lat=SITIO.lat + 0.45 / 111.32, lon=SITIO.lon)
    a = _reporte(
        "Se cayó el puente",
        _fuente("f-1"),
        ubicacion=SITIO,
        categoria=Categoria.GEO,
    )
    b = _reporte(
        "Manifestación con disturbios en la plaza",
        _fuente("f-2"),
        ubicacion=ambiguo,
        categoria=Categoria.GEO,
    )

    caso, _, _, _ = _construir_caso_uso()
    incidentes = await caso.verificar([a, b])

    assert len(incidentes) == 2


# ------------------------------------------------------------- casos límite
@pytest.mark.asyncio
async def test_lote_vacio_devuelve_lista_vacia_sin_publicar():
    caso, publicador, repositorio, _ = _construir_caso_uso()

    incidentes = await caso.verificar([])

    assert incidentes == []
    assert publicador.publicados == []
    assert repositorio.guardados == []


@pytest.mark.asyncio
async def test_dos_incidentes_distintos_cercanos_en_tiempo_lejanos_en_espacio():
    a = _reporte("Incendio en un edificio del centro", _fuente("f-1"), ubicacion=SITIO)
    b = _reporte("Incendio en una bodega del norte", _fuente("f-2"), ubicacion=LEJOS)

    caso, _, _, _ = _construir_caso_uso()
    incidentes = await caso.verificar([a, b])

    assert len(incidentes) == 2


@pytest.mark.asyncio
async def test_un_solo_reporte_de_fuente_poco_confiable_da_confianza_baja():
    reporte = _reporte(
        "Creo que se cayó algo por allá, no estoy seguro",
        _fuente("f-1", tipo=TipoFuente.CIUDADANO, reputacion=0.15),
        certeza=Certeza.UNLIKELY,
    )

    caso, _, _, _ = _construir_caso_uso()
    (incidente,) = await caso.verificar([reporte])

    assert incidente.corroboraciones == 1
    assert incidente.confianza < 0.15


@pytest.mark.asyncio
async def test_verificar_cumple_el_puerto_compartido_verificacion_port():
    from nucleo.puertos import VerificacionPort

    caso, *_ = _construir_caso_uso()
    puerto: VerificacionPort = caso  # verificación estructural (typing.Protocol)
    assert callable(puerto.verificar)
