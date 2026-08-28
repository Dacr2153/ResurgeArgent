"""Señalización mínima para que dos navegadores se presenten por WebRTC.

Por qué existe algo tan pequeño: WebRTC conecta dos navegadores **directamente**,
pero no puede empezar solo. Antes de hablar entre ellos tienen que intercambiar
una oferta SDP, una respuesta y los candidatos ICE, y ese saludo inicial necesita
un intermediario. Después de él la conversación ya no pasa por aquí.

Esa es también la limitación honesta de la malla en navegador: hace falta que
alguien —un nodo con salida, un servidor de barrio, el propio portátil de un
voluntario— sostenga este punto de encuentro. Sin infraestructura ninguna, dos
navegadores no se encuentran; dos aplicaciones nativas con Bluetooth sí.

El registro vive en memoria y los buzones se vacían al leerse: es un punto de
encuentro, no un almacén. Lo que hay que conservar son los sobres, y de eso se
encarga el almacén persistente.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, FastAPI

from malla.adaptadores.entrada.modelos import AnuncioRequest, SenalRequest

# Un par que lleva dos minutos sin anunciarse se da por ido. En una emergencia
# la gente se mueve: mantener pares fantasma solo hace que los demás gasten
# intentos de conexión contra nadie.
VIGENCIA_SEGUNDOS = 120.0


@dataclass
class RegistroSenalizacion:
    """Quién está presente y qué señales tiene esperando."""

    presentes: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict)
    buzones: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))

    def anunciar(self, id_nodo: str, descripcion: dict[str, Any], momento: float) -> None:
        self.presentes[id_nodo] = (momento, descripcion)

    def pares(self, excluir: str, momento: float) -> list[dict[str, Any]]:
        vigentes = []
        for id_nodo, (visto, descripcion) in list(self.presentes.items()):
            if momento - visto > VIGENCIA_SEGUNDOS:
                self.presentes.pop(id_nodo, None)
                continue
            if id_nodo == excluir:
                continue
            vigentes.append({"id_nodo": id_nodo, "descripcion": descripcion})
        return vigentes

    def encolar(self, senal: dict[str, Any]) -> None:
        self.buzones[str(senal["destino"])].append(senal)

    def vaciar(self, destino: str) -> list[dict[str, Any]]:
        senales = self.buzones.get(destino, [])
        self.buzones[destino] = []
        return senales


def crear_router_senalizacion(registro: RegistroSenalizacion) -> APIRouter:
    router = APIRouter(prefix="/senalizacion", tags=["senalizacion"])

    @router.post("/anuncios")
    async def anunciar(payload: AnuncioRequest) -> dict:
        """"Estoy aquí": el par se registra para que otros lo encuentren."""
        registro.anunciar(payload.id_nodo, payload.descripcion, time.monotonic())
        return {"id_nodo": payload.id_nodo, "estado": "anunciado"}

    @router.get("/pares")
    async def pares(excluir: str = "") -> dict:
        """Con quién se puede intentar una conexión directa ahora mismo."""
        return {"pares": registro.pares(excluir, time.monotonic())}

    @router.post("/senales")
    async def enviar_senal(payload: SenalRequest) -> dict:
        """Deja una oferta, respuesta o candidato ICE en el buzón del destinatario."""
        registro.encolar(payload.model_dump())
        return {"estado": "encolada", "destino": payload.destino}

    @router.get("/senales")
    async def recoger_senales(destino: str) -> dict:
        """Recoge y vacía el buzón. Se lee una vez: no es un histórico."""
        return {"destino": destino, "senales": registro.vaciar(destino)}

    return router


def montar_senalizacion(app: FastAPI, registro: RegistroSenalizacion) -> None:
    app.include_router(crear_router_senalizacion(registro))
