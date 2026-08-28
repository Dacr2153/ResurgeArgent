"""Deja la base lista para una demostración, sin esperar ni gastar crédito.

Procesa el escenario completo con los adaptadores de reglas —sin llamar a ningún
modelo— y guarda el resultado en SQLite. El coordinador abre el tablero y los
incidentes ya están ahí, priorizados y esperando firma.

Por qué existe: la pasada con modelo real tarda unos dos minutos y medio y
consume crédito. Delante de un jurado eso es tiempo muerto y un riesgo si la red
del sitio falla. Aquí se siembra lo mismo en segundos, y la ejecución con modelo
queda para enseñarla aparte, grabada en `datos/ejecucion_real.json`.

Uso:
    python sembrar_demo.py            # siembra y deja la base lista
    python sembrar_demo.py --limpiar  # borra la base antes de sembrar
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from agente_geoespacial.config.contenedor import construir_contenedor as construir_geoespacial
from agente_geoespacial.config.settings import Settings as SettingsGeo
from agente_ingesta.config.contenedor import construir_contenedor as construir_ingesta
from agente_orquestador.config.contenedor import construir_contenedor as construir_orquestador
from agente_orquestador.config.settings import Settings as SettingsOrquestador
from agente_verificacion.config.contenedor import construir_contenedor as construir_verificacion
from nucleo.auditoria import AuditoriaSQLite
from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, RespuestaGeo
from nucleo.puertos import AuditoriaPort

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos" / "reportes_demo.json"
BASE = RAIZ / "datos" / "resurge.sqlite3"

# Base de despacho, al norte de la zona del derrumbe. Sin un origen el
# Orquestador no pide rutas, y sin rutas el tablero en alcance de zona sale
# vacio: el coordinador filtra por distancia, y sin ruta no hay distancia.
ORIGEN_DESPACHO = (4.6200, -74.0850)


class AdaptadorGeoespacial:
    """Une rutas y zonas en un solo interlocutor del puerto."""

    def __init__(self, auditoria: AuditoriaPort) -> None:
        # OSRM da geometria real de calles; el grafo de desarrollo solo cubre
        # unos pocos nodos de otra zona de la ciudad. Si OSRM no responde, el
        # agente cae solo al grafo.
        self._rutas, self._zonas = construir_geoespacial(
            settings=SettingsGeo(ruteador="osrm"), auditoria=auditoria
        )

    async def resolver_ruta(
        self, consulta: ConsultaGeo, correlacion_id: str | None = None
    ) -> RespuestaGeo:
        return await self._rutas.ejecutar(consulta, correlacion_id=correlacion_id)

    async def zonas_afectadas(
        self, incidentes: list[IncidenteVerificado], correlacion_id: str | None = None
    ) -> dict:
        return await self._zonas.ejecutar(incidentes)


async def main(limpiar: bool) -> int:
    if limpiar and BASE.exists():
        BASE.unlink()
        print(f"Base anterior borrada: {BASE.name}")

    BASE.parent.mkdir(parents=True, exist_ok=True)
    with DATOS.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)

    # Persistencia en disco: lo sembrado tiene que seguir ahí tras reiniciar el
    # servidor, que es justo lo que una demostración no puede permitirse perder.
    ajustes = SettingsOrquestador(
        ruta_sqlite=str(BASE),
        origen_lat=ORIGEN_DESPACHO[0],
        origen_lon=ORIGEN_DESPACHO[1],
    )
    auditoria = AuditoriaSQLite(BASE)

    contenedor = construir_orquestador(
        settings=ajustes,
        ingesta=construir_ingesta(auditoria=auditoria),
        verificacion=construir_verificacion(auditoria=auditoria),
        geoespacial=AdaptadorGeoespacial(auditoria),
        auditoria=auditoria,
    )

    print(f"Procesando {len(datos['reportes'])} reportes con adaptadores de reglas...")
    resultado = await contenedor.procesar.procesar({"reportes": datos["reportes"]})

    print(f"  admitidos: {resultado['reportes_ingeridos']}"
          f"  descartados: {resultado['reportes_descartados']['total']}")
    print(f"  incidentes: {len(resultado['incidentes'])}"
          f"  estado: {resultado['estado_operacion']}")
    for ruta in resultado.get("rutas", []):
        print(f"  ruta {ruta['incidente_id'][:8]}: {ruta['distancia_km']} km"
              f"  {ruta['duracion_min']} min")

    # Se deja SIN firmar a proposito: el gate humano es lo que hay que enseñar en
    # vivo, y sembrarlo ya firmado quitaria de la demostracion justamente la
    # garantia que sostiene el proyecto.
    pendientes = [i["incidente_id"] for i in resultado["incidentes"] if i["requiere_firma"]]
    print(f"  esperando firma del coordinador: {len(pendientes)}")
    for incidente in pendientes:
        print(f"    {incidente}")

    print(f"\nBase lista en {BASE}")
    print("Arranca el servidor apuntando a esta base:")
    print(f'  AGENTE1_RUTA_SQLITE="{BASE}" PLATAFORMA_RUTA_SQLITE="{BASE}" \\')
    print("    .venv/bin/python -m uvicorn main:app --port 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main("--limpiar" in sys.argv)))
