# Agente 1 — Orquestador

Coordina a los demás agentes del sistema, consolida lo que devuelven y determina
qué se ejecuta y en qué orden.

## Qué hace

- Delega en los agentes 2 (Ingesta), 3 (Verificación) y 5 (Geoespacial) a través
  de los puertos de `nucleo.puertos`, dentro de una **saga** con compensación.
- Lleva la **máquina de estados** de cada incidente y valida cada transición.
- Ejecuta el **triage determinista** que decide el orden de atención.
- Deja cada incidente en `PENDIENTE_APROBACION` y **se detiene ahí**.
- Aplica la `DecisionHumana` firmada por el coordinador y mueve el incidente.
- Emite auditoría de todo: `TRANSICION_ESTADO`, `TAREA_DELEGADA`,
  `DECISION_HUMANA_REGISTRADA`, `AGENTE_SIN_RESPUESTA`, `COMPENSACION_EJECUTADA`.

## Qué NO hace

- No captura datos de fuentes externas (Agente 2).
- No juzga si un reporte es cierto (Agente 3).
- No calcula rutas ni zonas afectadas (Agente 5).
- No asigna recursos a necesidades (Agente 7).
- **No decide con un LLM.** El LLM solo redacta el parte de situación para el
  coordinador. Toda transición, prioridad, delegación y compensación es
  determinista y testeable. Sin API key el agente funciona igual
  (`resumidor_nulo.py`).
- **No despacha sin firma humana.** No existe ningún camino automático a
  `ASIGNADO`.

## Diagrama de estados

```
                 (automático)                       (automático)
  RECIBIDO ─────► VERIFICADO ─────► LOCALIZADO ─────► PRIORIZADO
                                                          │
                                                          ▼
                                              PENDIENTE_APROBACION
                                                          │
                          DecisionHumana(aprobada=True) ── ┤ ── DecisionHumana(aprobada=False)
                                                          │              │
                                                          ▼              ▼
                                                      ASIGNADO    DESCARTADO / SUSPENDIDO
                                                          │
                                                          ▼
                                                    EN_EJECUCION ─────► RESUELTO

  Fuera de la línea principal, desde cualquier estado no terminal:
    · ──► SUSPENDIDO   (timeout, ciclo detectado, rechazo con `suspender`)
    · ──► DESCARTADO   (falso, duplicado, rechazo)
    SUSPENDIDO ──► PRIORIZADO   (reanudar: vuelve a la cola, se re-tría)
    RESUELTO y DESCARTADO son terminales: no tienen salida.
```

El único paso que exige `DecisionHumana` es `PENDIENTE_APROBACION → ASIGNADO`, y
exige además que venga `aprobada=True`. Una decisión rechazada solo puede llevar
a `DESCARTADO` o `SUSPENDIDO`.

## Triage

```
base       = 0.45·severidad(CAP) + 0.35·urgencia(CAP) + 0.20·factor(personas)
puntuacion = base × (0.5 + 0.5·confianza)
orden      = puntuacion descendente, desempate por incidente_id ascendente
```

Mismo lote de entrada, mismo orden de salida. El razonamiento de cada peso está
documentado en `dominio/motor_triage.py` y `dominio/value_objects.py`.

## Saga y resiliencia

Cada paso delegado declara su `accion_compensatoria`. Si un paso **obligatorio**
falla o agota su timeout, se deshacen en orden inverso los pasos ya completados y
la saga aborta. Si falla un paso **opcional** (el geoespacial), se registra
`AGENTE_SIN_RESPUESTA` y la operación continúa degradada, con respuesta parcial.
Ninguna excepción de un agente delegado sale del caso de uso.

Un incidente que vuelve al mismo estado más de `AGENTE1_LIMITE_VISITAS_ESTADO`
veces (3 por defecto) se suspende en vez de seguir dando vueltas.

## Cómo correrlo

```bash
# tests (sin red, sin API key)
pytest -q tests/orquestador
ruff check src tests

# API, montada por el punto de entrada del sistema
uvicorn main:app --reload      # -> http://localhost:8000/orquestador
```

Endpoints: `GET /health`, `POST /emergencias`, `POST /decisiones`,
`GET /operaciones/{incidente_id}`, `GET /auditoria/{correlacion_id}`.

```bash
curl -X POST localhost:8000/orquestador/emergencias \
  -H 'content-type: application/json' \
  -d '{"entrada": {"canal": "sms", "texto": "edificio colapsado"},
       "origen_despacho": {"lat": 4.65, "lon": -74.09}}'

curl -X POST localhost:8000/orquestador/decisiones \
  -H 'content-type: application/json' \
  -d '{"incidente_id": "INC-1", "aprobada": true,
       "coordinador_id": "COORD-7", "justificacion": "unidad disponible"}'
```

Configuración por entorno con prefijo `AGENTE1_` (ver `config/settings.py`):
timeouts por agente, pesos del triage, `AGENTE1_ORIGEN_LAT/LON` (base de
despacho, sin la cual no se piden rutas), `AGENTE1_RUTA_AUDITORIA` (JSONL
append-only) y `AGENTE1_LLM_PROVEEDOR` (`nulo` por defecto).
