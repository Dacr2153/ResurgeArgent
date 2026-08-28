"""Recorrido end-to-end del flujo: Ingesta → Verificación → Geoespacial → Orquestador.

Los cuatro agentes se construyen de verdad, con sus contenedores reales, y se
inyectan en el Orquestador a través de los protocolos de `nucleo.puertos`. No hay
dobles aquí: lo único simulado es la firma del coordinador humano, que en
producción llega desde la interfaz.

Todo corre sin red y sin API key: cada agente cae en su adaptador nulo.

Uso:
    python demo_flujo.py [ruta_json]
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from agente_geoespacial.config.contenedor import construir_contenedor as construir_geoespacial
from agente_ingesta.config.contenedor import construir_contenedor as construir_ingesta
from agente_orquestador.config.contenedor import construir_contenedor as construir_orquestador
from agente_verificacion.config.contenedor import construir_contenedor as construir_verificacion
from nucleo.auditoria import AuditoriaMemoria
from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, RespuestaGeo
from nucleo.puertos import AuditoriaPort

RAIZ = Path(__file__).resolve().parent
DATOS_DEMO = RAIZ / "datos" / "reportes_demo.json"
ANCHO = 78


class AdaptadorGeoespacial:
    """Une los dos casos de uso del agente 5 en un solo objeto.

    El agente geoespacial expone rutas y zonas por separado, pero
    `nucleo.puertos.GeoespacialPort` los pide juntos: el Orquestador quiere un
    interlocutor, no dos. Esta costura vive en la capa de integración y no
    obliga al agente a cambiar su forma interna.
    """

    def __init__(self, auditoria: AuditoriaPort) -> None:
        self._rutas, self._zonas = construir_geoespacial(auditoria=auditoria)

    async def resolver_ruta(
        self, consulta: ConsultaGeo, correlacion_id: str | None = None
    ) -> RespuestaGeo:
        return await self._rutas.ejecutar(consulta, correlacion_id=correlacion_id)

    async def zonas_afectadas(
        self, incidentes: list[IncidenteVerificado], correlacion_id: str | None = None
    ) -> dict:
        return await self._zonas.ejecutar(incidentes)


def titulo(texto: str) -> None:
    print(f"\n{'=' * ANCHO}\n{texto}\n{'=' * ANCHO}")


def paso(numero: int, texto: str) -> None:
    print(f"\n[{numero}] {texto}\n{'-' * ANCHO}")


def cargar(ruta: Path) -> dict[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


async def main(ruta_datos: Path) -> int:
    datos = cargar(ruta_datos)

    titulo("SISTEMA DE COORDINACIÓN DE RESPUESTA — RECORRIDO COMPLETO")
    print(datos.get("descripcion", ""))

    # Una sola traza para los cuatro agentes. El correlacion_id existe justamente
    # para reconstruir una operación completa de punta a punta, y con un log por
    # agente eso sería imposible.
    auditoria = AuditoriaMemoria()

    # Una sola instancia de cada agente durante toda la operación: la idempotencia
    # y el back-pressure de la ingesta viven en la instancia, así que reconstruirla
    # por lote los volvería inútiles.
    contenedor = construir_orquestador(
        ingesta=construir_ingesta(auditoria=auditoria),
        verificacion=construir_verificacion(auditoria=auditoria),
        geoespacial=AdaptadorGeoespacial(auditoria),
        auditoria=auditoria,
    )

    paso(1, "Entra la información cruda")
    entrada = {"reportes": datos["reportes"]}
    fuentes = {r["fuente"]["id"] for r in datos["reportes"]}
    canales = {r["canal"] for r in datos["reportes"]}
    print(f"{len(datos['reportes'])} reportes de {len(fuentes)} fuentes distintas, "
          f"por {len(canales)} canales")

    resultado = await contenedor.procesar.procesar(entrada)

    paso(2, "Ingesta normaliza y descarta reenvíos")
    descartes = resultado["reportes_descartados"]
    print(f"reportes admitidos: {resultado['reportes_ingeridos']} "
          f"(de {len(datos['reportes'])} recibidos)")
    print(f"descartados: {descartes['total']}")
    for motivo, cuantos in descartes["por_motivo"].items():
        print(f"  · {cuantos} por {motivo}")

    paso(3, "Verificación fusiona lo que es el mismo hecho")
    incidentes = resultado["incidentes"]
    print(f"incidentes verificados: {len(incidentes)}")
    for inc in incidentes:
        triage = inc.get("triage") or {}
        print(f"  · {inc['incidente_id'][:8]}  estado={inc['estado']:22} "
              f"prioridad={triage.get('posicion', '?')}  "
              f"{'requiere firma' if inc['requiere_firma'] else ''}")

    paso(4, "Geoespacial ubica las zonas afectadas")
    zonas = resultado.get("zonas_afectadas") or {}
    celdas = zonas.get("features", [])
    print(f"celdas con incidentes: {len(celdas)}")
    for celda in celdas:
        props = celda.get("properties", {})
        print(f"  · celda {props.get('celda_id', '?')}: "
              f"{props.get('conteo_incidentes', '?')} incidente(s), "
              f"severidad {props.get('severidad_agregada', '?')}")

    paso(5, "El Orquestador prioriza y se detiene ante el gate humano")
    print(f"estado de la operación: {resultado['estado_operacion'].upper()}")
    print(f"operación degradada: {'sí' if resultado['degradada'] else 'no'}")
    print("\npasos de la saga:")
    for p in resultado["saga"]["pasos"]:
        marca = "obligatorio" if p["obligatorio"] else "opcional   "
        print(f"  · {p['nombre']:14} {marca}  {p['estado']}"
              + (f"  ({p['error']})" if p["error"] else ""))

    paso(6, "El gate: sin firma humana no hay asignación")
    correlacion = resultado["correlacion_id"]
    if not incidentes:
        print("  sin incidentes que firmar")
        return 1
    # Las operaciones se indexan por incidente, no por lote: cada incidente lleva
    # su propia firma porque el coordinador aprueba respuestas, no tandas.
    objetivo = incidentes[0]["incidente_id"]
    print(f"  incidente a aprobar: {objetivo}")
    try:
        await contenedor.registrar_decision.registrar(
            {"incidente_id": objetivo, "aprobada": True, "coordinador_id": "",
             "justificacion": "intento sin coordinador identificado"}
        )
        print("  FALLO: se aceptó una decisión sin coordinador")
        return 1
    except Exception as error:
        print(f"  intento sin coordinador identificado -> rechazado ({type(error).__name__})")

    firmada = await contenedor.registrar_decision.registrar(
        {"incidente_id": objetivo, "aprobada": True, "coordinador_id": "coord-ungrd-07",
         "justificacion": "Recursos disponibles, se autoriza el despliegue"}
    )
    print(f"  firmada por coord-ungrd-07 -> estado {str(firmada.get('estado', '?')).upper()}")

    paso(7, "Resumen para el coordinador")
    print(resultado["resumen_situacion"])

    paso(8, "Traza de auditoría")
    eventos = contenedor.eventos_de(correlacion)
    print(f"{len(eventos)} eventos registrados; toda decisión es reconstruible")
    for evento in eventos[:8]:
        print(f"  · {evento['momento'][11:19]}  {evento['agente']:22} {evento['tipo']}")
    if len(eventos) > 8:
        print(f"  … y {len(eventos) - 8} más")

    titulo("FIN DEL RECORRIDO")
    return 0


if __name__ == "__main__":
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else DATOS_DEMO
    raise SystemExit(asyncio.run(main(ruta)))
