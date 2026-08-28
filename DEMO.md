# Demostración en tres comandos

## 1. Sembrar la base (segundos, sin gastar crédito)

```bash
.venv/bin/python sembrar_demo.py --limpiar
```

Procesa los 13 reportes del escenario con los adaptadores de reglas y deja dos
incidentes verificados, priorizados y **sin firmar**: el gate humano es lo que hay
que enseñar en vivo, así que no se siembra ya resuelto.

## 2. Levantar el backend

```bash
BASE="$PWD/datos/resurge.sqlite3"
AGENTE1_RUTA_SQLITE="$BASE" PLATAFORMA_RUTA_SQLITE="$BASE" \
  .venv/bin/python -m uvicorn main:app --port 8000
```

`GET /salud` lista los servicios montados. CORS ya admite los puertos 5173 y 5174.

## 3. Levantar el frontend

```bash
cd frontend && npm install && npm run dev
```

## El recorrido ante el jurado

1. **`/dashboard`** — el tablero del coordinador. Los dos incidentes ya están, con
   su prioridad. Aquí se ven los resultados; no hace falta otra pantalla.
2. **`/matching/:id`** — se firma. Sin identificar al coordinador, el sistema
   rechaza la firma. Un rechazo sin justificación, también.
3. **El panel de traza** — qué agente hizo qué y cuándo, bajo un solo hilo de
   correlación.
4. **`/reportar`** — un reporte nuevo entra en vivo y aparece en el tablero.

## Con el modelo real

La ejecución con `gemini-2.5-pro` por Vertex está grabada entera en
`datos/ejecucion_real.json`: cada prompt, cada respuesta, tokens y tiempos.
15 llamadas, 28.542 tokens, 147 segundos, cero errores.

Para repetirla en vivo (consume crédito y tarda ~2,5 min):

```bash
set -a && . env.vertex && set +a && .venv/bin/python ejecucion_real.py
```

## Si se cae la red o el modelo

No pasa nada, y eso es parte de la demostración: cada agente degrada a su
adaptador de reglas y la operación se completa igual. Se verificó con el modelo
devolviendo 429 en todas las llamadas.
