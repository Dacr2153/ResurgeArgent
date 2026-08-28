# Agente 5 — Geoespacial y Movilidad

## Qué hace

Resuelve rutas entre dos puntos, y agrupa incidentes verificados en zonas
afectadas usando una rejilla geográfica. Detecta vías bloqueadas a partir de
reportes en texto libre (vía un intérprete que puede ser un LLM o un modo nulo
por palabras clave) y las evita al calcular — un derrumbe elimina la vía, no la
encarece. Cuando el destino queda incomunicado, lo informa como dato
(`accesible=False`), no como error. Cuando existe, ofrece al menos una ruta
alternativa además de la principal.

Hay dos motores de ruteo posibles, elegidos por configuración
(`AGENTE5_RUTEADOR=grafo|osrm`, **`grafo` por defecto**):

- **Grafo propio** (`dominio/motor_rutas.py`, `networkx`): red vial modelada a
  mano (o cargada por un `RepositorioGrafoPort`), sin red, determinista. Un
  tramo bloqueado se **remueve** del grafo, no se encarece.
- **OSRM** (`adaptadores/salida/ruteo_osrm.py`): servidor público
  `router.project-osrm.org`, gratuito y sin clave, que devuelve geometría real
  sobre calles de OpenStreetMap en vez de líneas rectas entre nodos de un grafo
  simplificado.

**El grafo propio es siempre el respaldo**, incluso con `AGENTE5_RUTEADOR=osrm`
activo: si OSRM no responde, tarda más de `AGENTE5_OSRM_TIMEOUT_SEG` (4 s por
defecto) o devuelve algo inválido, `ResolverRuta` cae al grafo sin que la
petición falle. Un servicio público sin SLA no puede tumbar una ruta de
emergencia en plena demostración en vivo. Cuál de los dos resolvió queda en
`detalle.motor_resolucion` del evento de auditoría `RUTA_CALCULADA`, y si hubo
caída a respaldo también se anota en `RespuestaGeo.motivo`.

### Fuentes libres usadas y sus límites

- **OSRM público** (`router.project-osrm.org`): sin clave, sin registro,
  gratuito. **Límite real**: no tiene SLA (puede estar lento o caído en
  cualquier momento — de ahí el respaldo obligatorio) y **no admite excluir
  tramos arbitrarios** de la ruta — solo clases de vía predefinidas del
  perfil (`motorway`, etc.), no un segmento puntual como "esta cuadra está
  bloqueada por un derrumbe". Este agente lo rodea con un **desvío por
  waypoint**: si el tramo bloqueado cae sobre la ruta devuelta, se vuelve a
  pedir la ruta forzando un punto intermedio desplazado del bloqueo. Es una
  **heurística sin garantía** — OSRM sigue libre de recalcular por donde
  quiera entre ese punto y los extremos, así que puede seguir cruzando el
  tramo si sigue siendo el camino más corto. Es una restricción real del
  servicio gratuito, no una decisión de diseño: ver el docstring de
  `ruteo_osrm.py` para el detalle completo.
- **Nominatim** (`nominatim.openstreetmap.org`): geocodificación (dirección en
  texto → coordenadas), sin clave. Su política de uso **exige** un
  `User-Agent` propio (no el de una librería HTTP genérica) y **máximo una
  petición por segundo**; incumplirlas hace que bloqueen la IP. Ambas están
  implementadas de verdad en `adaptadores/salida/geocodificador_nominatim.py`
  (`GeocodificadorNominatim` fija el `User-Agent`; `LimitadorRitmo` espera el
  intervalo mínimo antes de cada llamada, async-safe con un lock).

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

`POST /geocodificar` recibe `{"direccion": "Carrera 7, Bogotá"}` y devuelve
`{"punto": {"type": "Point", "coordinates": [lon, lat]}}`, o `{"punto": null}`
si Nominatim no encontró nada (o no respondió) — nunca un error 500 para ese
caso, porque no tener resultado es una respuesta válida, no una falla.

El geocodificador **no viaja dentro de `construir_contenedor()`**: ese
contenedor sigue devolviendo exactamente `(ResolverRuta, AnalizarZonas)`
porque `agente_orquestador` depende de esa forma exacta (`AdaptadorGeoespacial(*construido)`)
y no está en el alcance de este cambio tocar esa integración. `crear_app`
acepta el geocodificador como segundo argumento opcional:

```python
from agente_geoespacial.config.contenedor import (
    construir_contenedor,
    construir_geocodificador,
)
from agente_geoespacial.config.settings import Settings

settings = Settings()
app = crear_app(construir_contenedor(settings), construir_geocodificador(settings))
```

Montado vía `main.py` (que llama `crear_app(construir_contenedor())` sin el
segundo argumento, igual que antes), `/geocodificar` responde `503` — no hay
geocodificador configurado en ese camino de arranque genérico; para activarlo
ahí hace falta que quien monte el agente pase también el geocodificador, algo
fuera del alcance de este cambio (`main.py` no se tocó).

Para activar el ruteo por calles reales en vez del grafo propio:
`AGENTE5_RUTEADOR=osrm` (variable de entorno o `.env`). Con el valor por
defecto (`grafo`) el comportamiento es exactamente el de antes, sin red.

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
