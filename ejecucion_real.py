"""Pasada completa del sistema con los agentes reales y Gemini, grabada entera.

Se ejecuta UNA vez y deja en disco todo lo que ocurrió: cada llamada al modelo
con su prompt y su respuesta, el consumo de tokens, los tiempos, los incidentes
resultantes y la traza de auditoría. Con eso se construye el informe para el
jurado, y la demostración puede repetirse en vivo o apoyarse en lo grabado si la
red del sitio falla.

Hay un tope de llamadas al modelo a propósito: el crédito es limitado, y un fallo
que provoque reintentos podría agotarlo sin que nadie se dé cuenta hasta que ya
no queda nada.

Uso:
    python ejecucion_real.py [ruta_json]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agente_geoespacial.config.contenedor import construir_contenedor as construir_geoespacial
from agente_ingesta.config.contenedor import construir_contenedor as construir_ingesta
from agente_orquestador.config.contenedor import construir_contenedor as construir_orquestador
from agente_verificacion.config.contenedor import construir_contenedor as construir_verificacion
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, RespuestaGeo
from nucleo.llm import ClienteGemini
from nucleo.puertos import AuditoriaPort

RAIZ = Path(__file__).resolve().parent
DATOS_DEMO = RAIZ / "datos" / "reportes_demo.json"
SALIDA = RAIZ / "datos" / "ejecucion_real.json"
TOPE_LLAMADAS = 120


class ErrorTope(RuntimeError):
    """Se alcanzó el tope de llamadas al modelo."""


class ClienteGrabador:
    """Envuelve al cliente real y guarda cada intercambio con el modelo.

    Envolver en vez de modificar el cliente mantiene la grabación fuera del
    camino de producción: lo que se demuestra es exactamente el mismo código que
    correría en una emergencia.
    """

    registro: list[dict[str, Any]] = []

    def __init__(self, agente: str, interno: ClienteGemini) -> None:
        self._agente = agente
        self._interno = interno

    @property
    def identificador_modelo(self) -> str:
        return self._interno.identificador_modelo

    async def completar(self, system: str, user: str) -> str:
        if len(ClienteGrabador.registro) >= TOPE_LLAMADAS:
            raise ErrorTope(f"tope de {TOPE_LLAMADAS} llamadas alcanzado")

        antes_tokens = self._interno.tokens_totales
        inicio = time.monotonic()
        error = None
        try:
            respuesta = await self._interno.completar(system, user)
        except Exception as fallo:  # noqa: BLE001 - se graba y se relanza
            respuesta, error = "", f"{type(fallo).__name__}: {fallo}"
            raise
        finally:
            ClienteGrabador.registro.append(
                {
                    "agente": self._agente,
                    "modelo": self._interno.identificador_modelo,
                    "system": system,
                    "user": user,
                    "respuesta": respuesta,
                    "error": error,
                    "segundos": round(time.monotonic() - inicio, 3),
                    "tokens": self._interno.tokens_totales - antes_tokens,
                    "momento": datetime.now(UTC).isoformat(),
                }
            )
        return respuesta


def envolver(agente: str, raiz: Any, profundidad: int = 4) -> Any:
    """Busca clientes de Gemini dentro del objeto y los sustituye por grabadores.

    La búsqueda es recursiva porque el cliente no cuelga del caso de uso sino de
    su adaptador de LLM (por ejemplo `caso._extractor._cliente`), y cada agente
    lo nombra a su manera.
    """
    # No se entra en un grabador: el Orquestador guarda referencias a los otros
    # agentes, y sin este corte se envolveria dos veces el mismo cliente.
    if profundidad <= 0 or isinstance(raiz, ClienteGrabador) or not hasattr(raiz, "__dict__"):
        return raiz
    for nombre, valor in list(vars(raiz).items()):
        if isinstance(valor, ClienteGemini):
            setattr(raiz, nombre, ClienteGrabador(agente, valor))
        elif hasattr(valor, "__dict__") and not isinstance(valor, type):
            envolver(agente, valor, profundidad - 1)
    return raiz


class AdaptadorGeoespacial:
    def __init__(self, auditoria: AuditoriaPort) -> None:
        self._rutas, self._zonas = construir_geoespacial(auditoria=auditoria)
        envolver("agente-5-geoespacial", self._rutas)

    async def resolver_ruta(
        self, consulta: ConsultaGeo, correlacion_id: str | None = None
    ) -> RespuestaGeo:
        return await self._rutas.ejecutar(consulta, correlacion_id=correlacion_id)

    async def zonas_afectadas(
        self, incidentes: list[IncidenteVerificado], correlacion_id: str | None = None
    ) -> dict:
        return await self._zonas.ejecutar(incidentes)


async def main(ruta_datos: Path) -> int:
    with ruta_datos.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)

    auditoria = AuditoriaMemoria()
    ingesta = envolver("agente-2-ingesta", construir_ingesta(auditoria=auditoria))
    verificacion = envolver("agente-3-verificacion", construir_verificacion(auditoria=auditoria))
    geoespacial = AdaptadorGeoespacial(auditoria)
    contenedor = construir_orquestador(
        ingesta=ingesta,
        verificacion=verificacion,
        geoespacial=geoespacial,
        auditoria=auditoria,
    )
    envolver("agente-1-orquestador", contenedor.procesar)

    print(f"Procesando {len(datos['reportes'])} reportes con Gemini...", flush=True)
    inicio = time.monotonic()
    resultado = await contenedor.procesar.procesar({"reportes": datos["reportes"]})
    duracion = time.monotonic() - inicio

    firma = None
    if resultado["incidentes"]:
        objetivo = resultado["incidentes"][0]["incidente_id"]
        firma = await contenedor.registrar_decision.registrar(
            {
                "incidente_id": objetivo,
                "aprobada": True,
                "coordinador_id": "coord-ungrd-07",
                "justificacion": "Recursos disponibles, se autoriza el despliegue",
            }
        )

    eventos = [evento.a_dict() for evento in auditoria.por_correlacion(resultado["correlacion_id"])]
    tokens = sum(llamada["tokens"] for llamada in ClienteGrabador.registro)

    grabacion = {
        "momento": datetime.now(UTC).isoformat(),
        "duracion_segundos": round(duracion, 2),
        "escenario": datos.get("descripcion", ""),
        "reportes_entrada": datos["reportes"],
        "resultado": resultado,
        "firma": firma,
        "eventos_auditoria": eventos,
        "llamadas_llm": ClienteGrabador.registro,
        "consumo": {
            "llamadas": len(ClienteGrabador.registro),
            "tokens_totales": tokens,
            "modelo": ClienteGrabador.registro[0]["modelo"] if ClienteGrabador.registro else "-",
        },
    }
    SALIDA.write_text(
        json.dumps(grabacion, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )

    print(f"\nDuracion: {duracion:.1f}s")
    print(f"Llamadas al modelo: {len(ClienteGrabador.registro)}  |  tokens: {tokens}")
    print(f"Reportes: {len(datos['reportes'])} -> admitidos {resultado['reportes_ingeridos']}"
          f"  descartados {resultado['reportes_descartados']['total']}")
    print(f"Incidentes: {len(resultado['incidentes'])}  |  estado: {resultado['estado_operacion']}")
    for paso in resultado["saga"]["pasos"]:
        print(f"  saga {paso['nombre']:14} {paso['estado']}")
    if firma:
        print(f"Firma del coordinador -> {firma.get('estado')}")
    print(f"Eventos de auditoria: {len(eventos)}")
    print(f"\nGrabacion en {SALIDA}")
    return 0


if __name__ == "__main__":
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else DATOS_DEMO
    raise SystemExit(asyncio.run(main(ruta)))
