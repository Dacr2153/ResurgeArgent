# Agente 5 — Geoespacial y Movilidad

## Qué hace

Resuelve rutas entre dos puntos sobre una red vial modelada como grafo dirigido
(`networkx`), y agrupa incidentes verificados en zonas afectadas usando una
rejilla geográfica. Detecta vías bloqueadas a partir de reportes en texto libre
(vía un intérprete que puede ser un LLM o un modo nulo por palabras clave) y
las remueve del grafo antes de calcular — un derrumbe elimina la vía, no la
encarece. Cuando el destino queda incomunicado, lo informa como dato
(`accesible=False`), no como error. Cuando existe, ofrece al menos una ruta
alternativa además de la principal.

## Qué NO hace

- No decide qué recurso va a qué necesidad (eso es el Agente de
  Matching/Asignación).
- No prioriza incidentes ni asigna urgencia (eso es el Orquestador).
- No verifica ni corrobora reportes (eso es el Agente de Verificación): recibe
  `IncidenteVerificado` ya hechos.
- El LLM que usa nunca decide una ruta ni descarta un tramo por su cuenta: solo
  traduce lenguaje natural a una lista de ids de tramo bloqueados; la decisión
  de cómo rutear alrededor de eso es siempre del motor determinista
  (`MotorRutas`).

## Cómo correrlo

Desde el worktree, con el intérprete/venv compartido de `ResurgeAgent`:

```bash
/home/kevin/ResurgeAgent/.venv/bin/pytest -q
/home/kevin/ResurgeAgent/.venv/bin/ruff check src tests
```

Sin red y sin API key: el contenedor (`config/contenedor.py`) usa
`InterpreteNulo` por defecto (`AGENTE5_LLM_PROVEEDOR=nulo`). Para levantar solo
este agente como API REST (montado también por `main.py` del repo bajo
`/geoespacial`):

```python
from agente_geoespacial.config.contenedor import construir_contenedor
from agente_geoespacial.adaptadores.entrada.api_rest import crear_app

app = crear_app(construir_contenedor())
```

`POST /rutas` recibe `{origen, destino, modo, evitar_zonas, reportes_bloqueo}`
y devuelve `RespuestaGeo` extendida con `alternativas`. `POST /zonas` recibe
`{incidentes: [...]}` (espejo de `IncidenteVerificado`) y devuelve un
`FeatureCollection` GeoJSON de celdas afectadas.

## De dónde saldría el grafo real (producción)

`config/contenedor.py` usa `grafo_demo()`: tres nodos de ejemplo, solo para que
el contenedor levante sin depender de red. En producción el grafo vial se
cargaría de **OpenStreetMap** — típicamente extrayendo la red de calles de un
extracto `.osm.pbf` de la zona de operación (p. ej. con Overpass API o un
extracto pre-descargado de Geofabrik), y traduciendo nodos/ways de OSM a
`NodoVial`/`TramoVial` (un `way` con varios nodos intermedios se parte en
tantos `TramoVial` como segmentos entre nodos, y `oneway=yes` se traduce a
`bidireccional=False`). Ese cargador implementaría `RepositorioGrafoPort`
(`aplicacion/puertos/salida.py`) — p. ej. `RepositorioGrafoOSM` — y se
inyectaría en `construir_contenedor()` en vez de `grafo_demo()`. No se agrega
aquí porque requiere red y un archivo de datos que el hackatón no provee; el
puerto ya está listo para recibirlo sin tocar el resto del agente.
