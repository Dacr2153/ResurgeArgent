"""Adaptador de entrada REST del nodo de malla (FastAPI).

Este es el "enchufe" del nodo: lo que un vecino de red local usa para dejarle un
sobre, lo que un vecino usa para llevarse lo que no tiene, y lo que la interfaz
usa para saber si este teléfono es el que tiene salida a internet.

Un sobre rechazado por firma inválida responde 202, no 4xx. Es deliberado: el
vecino que lo entregó normalmente no es el atacante, sino otro nodo honesto que
retransmitió lo que le llegó. Devolverle un error le haría reintentar en bucle
un sobre que nunca va a ser aceptado. El rechazo queda en la auditoría, que es
donde sirve de algo, y en el propio cuerpo de la respuesta.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from malla.adaptadores.entrada.modelos import ReporteRequest, SobreRequest
from malla.adaptadores.entrada.senalizacion import RegistroSenalizacion, montar_senalizacion
from malla.config.contenedor import Contenedor
from malla.dominio.excepciones import ErrorMalla, SobreInvalidoError
from malla.dominio.sobre import SobreMalla
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
from nucleo.geo import GeometriaInvalidaError, Punto

LIMITE_PAGINA = 200


def _a_reporte(payload: ReporteRequest) -> ReporteCrudo:
    """Convierte la petición en el contrato del núcleo.

    Se usa `ReporteCrudo` y no un tipo propio para que el `hash_idempotencia`
    que identifica el sobre en toda la malla sea exactamente el mismo que
    calculará Ingesta cuando el reporte llegue a la nube.
    """
    fuente = payload.fuente
    ubicacion = None
    if payload.ubicacion:
        ubicacion = Punto.desde_geojson(payload.ubicacion)
    return ReporteCrudo(
        texto=payload.texto,
        fuente=Fuente(
            id=str(fuente.get("id", "desconocido")),
            tipo=TipoFuente(str(fuente.get("tipo", "ciudadano"))),
            nombre=str(fuente.get("nombre", "")),
            reputacion=float(fuente.get("reputacion", 0.5)),
        ),
        canal=Canal(payload.canal),
        ubicacion=ubicacion,
        categoria=Categoria(payload.categoria),
        urgencia=Urgencia(payload.urgencia),
        severidad=Severidad(payload.severidad),
        certeza=Certeza(payload.certeza),
        personas_afectadas=payload.personas_afectadas,
        necesidades=tuple(payload.necesidades),
    )


def crear_app(contenedor: Contenedor) -> FastAPI:
    app = FastAPI(title="Malla P2P — Red de emergencia", version="0.1.0")
    registro = RegistroSenalizacion()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/nodo")
    async def nodo() -> dict:
        """Identidad pública y estado. Es también el sondeo que usan los vecinos."""
        vecinos = await contenedor.transporte.vecinos()
        return {
            "id_nodo": contenedor.identidad.id_nodo,
            "clave_publica": contenedor.identidad.clave_publica,
            "ttl_por_defecto": contenedor.motor.ttl_por_defecto,
            "vecinos": [
                {"id_nodo": v.id_nodo, "direccion": v.direccion, "capacidad_lote": v.capacidad_lote}
                for v in vecinos
            ],
            "pendientes": len(await contenedor.almacen.pendientes()),
            "ultima_secuencia": await contenedor.almacen.ultima_secuencia(),
            "salida_internet": await contenedor.nube.disponible(),
        }

    @app.post("/sobres", status_code=202)
    async def recibir_sobre(payload: SobreRequest) -> dict:
        """Recibe un sobre de un vecino."""
        try:
            decision = await contenedor.recibir.recibir_dict(payload.model_dump())
        except SobreInvalidoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ErrorMalla as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "id_mensaje": payload.id_mensaje,
            "resultado": str(decision.resultado),
            "motivo": decision.motivo,
            "reenviado": decision.sobre_a_reenviar is not None,
        }

    @app.get("/sobres")
    async def listar_sobres(
        desde: int = Query(0, ge=0),
        limite: int = Query(LIMITE_PAGINA, ge=1, le=LIMITE_PAGINA),
    ) -> dict:
        """Lo que este nodo tiene después de una secuencia dada.

        Es el modo "tirar" de la sincronización: un vecino que estuvo apagado
        pregunta por lo que le falta en vez de esperar a que alguien se lo empuje.
        """
        registros = await contenedor.almacen.listar_desde(desde, limite)
        return {
            "desde": desde,
            "siguiente": registros[-1].secuencia if registros else desde,
            "sobres": [r.sobre.a_dict() for r in registros],
        }

    @app.post("/reportes", status_code=201)
    async def originar_reporte(payload: ReporteRequest) -> dict:
        """Origina un reporte en este teléfono: lo firma y lo suelta a la malla."""
        try:
            reporte = _a_reporte(payload)
        except (GeometriaInvalidaError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        sobre, difusion = await contenedor.originar.originar(reporte, ttl=payload.ttl)
        return {
            "sobre": sobre.a_dict(),
            "vecinos_alcanzados": difusion.alcanzados,
            "vecinos_fallidos": list(difusion.fallidos),
        }

    @app.post("/sincronizar")
    async def sincronizar() -> dict:
        """Fuerza la subida del lote acumulado a la nube."""
        resultado = await contenedor.sincronizar.sincronizar()
        return {
            "hubo_salida": resultado.hubo_salida,
            "subidos": list(resultado.subidos),
            "total": resultado.total,
            "acusados": resultado.acusados,
            "propagados": resultado.propagados,
        }

    montar_senalizacion(app, registro)
    return app


def crear_sobre_desde_request(payload: SobreRequest) -> SobreMalla:
    """Utilidad para tests y clientes: pasa del modelo REST al sobre del dominio."""
    return SobreMalla.desde_dict(payload.model_dump())
