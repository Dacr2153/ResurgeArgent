# Agente de Voluntarios / Motor de Asignación

> **Alcance de este documento.** Describe lo que se construye **para el hackatón**: un
> motor de asignación que corre, es determinista y es auditable. La versión de
> investigación (optimización estocástica multiperiodo) está en
> [§8 Roadmap](#8-roadmap-lo-que-no-entra-en-el-hackaton) y en los papers de `papers/`.

**Rol.** Registrar perfiles, capacidades y ubicación de voluntarios, y asignarlos a
tareas de búsqueda y rescate (S1–S5) y primeros auxilios (T1–T3), minimizando la
demanda insatisfecha sin poner voluntarios en riesgo ni saturar la zona.

El agente es **soporte a la decisión**: toda asignación es una *recomendación* que
requiere aprobación humana del Centro de Manejo de Desastres (DMC) antes de
despacharse.

---

## 1. Qué hace el LLM y qué no

Esta separación es la decisión de diseño central del agente.

| Etapa | Motor | Por qué |
|---|---|---|
| Texto libre → perfil estructurado | **LLM** (Gemini Flash) | El lenguaje caótico es donde el LLM gana |
| Filtro de seguridad (SOP) | **Código** | Una regla de vida o muerte no puede alucinar |
| Asignación óptima | **Código** | Debe ser reproducible y auditable ante el DMC |
| Explicación de la asignación | **LLM** | Redacta el porqué para el operador |

Un LLM no decide a quién se rescata primero. Decide qué dice un mensaje de WhatsApp.

---

## 2. Catálogo de tareas y perfiles

**Perfiles de voluntario** (`profesion`)

| ID | Nombre | Riesgo autorizado |
|---|---|---|
| 2 | Búsqueda y Rescate | Alto |
| 5 | Personal Médico | Medio |
| 7 | Primeros Auxilios | Medio |
| 8 | Voluntario Espontáneo / Apoyo | **Bajo únicamente** |

**Tareas**

| Código | Tarea | Riesgo | Recursos requeridos |
|---|---|---|---|
| S1 | Búsqueda en superficie | Medio | — |
| S2 | Rescate entre escombros | **Alto** | — |
| S3 | Traslado a zona segura | Bajo | — |
| S4 | Censo de afectados | Bajo | — |
| S5 | Despeje de acceso | Medio | — |
| T1 | Triaje | Medio | `kits_medicos` |
| T2 | Estabilización | Alto | `kits_medicos`, `ambulancias` |
| T3 | Traslado de heridos | Medio | `ambulancias` |

---

## 3. Schema de entrada

Dos entradas. El agente no inventa demanda: la recibe del **Agente de Necesidades**.

### 3.1 Voluntario (`voluntarios[]`)

```json
{
  "id": "VOL-0042",
  "nombre": "Ana Restrepo",
  "profesion": 7,
  "zona": "Z-03",
  "horas_disponibles": 6.0,
  "certificado": true
}
```

| Campo | Tipo | Nota |
|---|---|---|
| `profesion` | int | 2, 5, 7 u 8 (ver §2) |
| `zona` | string | Zona donde está **ahora**, no donde vive |
| `horas_disponibles` | float | Tope por periodo; previene agotamiento |
| `certificado` | bool | Si es `false`, se degrada a perfil 8 |

### 3.2 Demanda (`demanda[]`) — la produce el Agente de Necesidades

```json
{
  "zona": "Z-03",
  "tarea": "S2",
  "horas_hombre": 40.0,
  "severidad": "critica"
}
```

| Campo | Tipo | Nota |
|---|---|---|
| `horas_hombre` | float | Trabajo estimado, no número de personas |
| `severidad` | enum | `baja` `media` `alta` `critica` → pesos 1/2/4/8 |

### 3.3 Recursos disponibles por zona (`recursos`)

```json
{ "Z-03": { "ambulancias": 2, "kits_medicos": 40 } }
```

---

## 4. Reglas de seguridad (deterministas, no negociables)

Se aplican **antes** de optimizar. Si una regla bloquea una asignación, el motor
registra el motivo; nunca la ejecuta en silencio.

1. **R1 — Riesgo por perfil.** Un voluntario espontáneo (perfil 8) nunca recibe una
   tarea de riesgo alto (S2, T2). Se reubica automáticamente a tareas de apoyo.
2. **R2 — Supervisión.** S2 solo se asigna si hay una unidad de rescate oficial
   presente en la zona. Si no, la demanda queda insatisfecha y se marca como
   `bloqueado_por_supervision`.
3. **R3 — Recursos simultáneos.** No se asignan T1–T3 sin los recursos de §2
   disponibles en esa zona. Sin ambulancia no hay traslado.
4. **R4 — Certificación.** `certificado: false` degrada el perfil a 8 antes de R1.
5. **R5 — Aglomeración.** Máximo `RATIO_AGLOMERACION` (por defecto 3.0) voluntarios
   espontáneos por cada voluntario certificado en una misma zona.
6. **R6 — Fatiga.** Nunca se asignan más horas que `horas_disponibles`.

---

## 5. Algoritmo de asignación

**Greedy por prioridad con drenado de capacidad.** Determinista, O(D log D + D·V),
corre en milisegundos y es explicable línea por línea ante un operador — que es
justamente lo que se necesita para el HITL.

```
1. Filtrar: aplicar R4, luego R1/R2/R3 a cada par (voluntario, tarea)
2. Ordenar demanda por  peso_severidad × horas_hombre  (descendente)
3. Para cada demanda:
     candidatos = voluntarios elegibles en la zona, ordenados por
                  afinidad de perfil (exacto > compatible), luego horas disponibles
     asignar horas hasta cubrir la demanda o agotar candidatos
     descontar horas y recursos consumidos
4. Registrar el remanente como demanda insatisfecha, con motivo
```

**Por qué greedy y no Hungarian:** el problema no es un emparejamiento 1-a-1, es
reparto de horas-hombre con capacidad — un problema de transporte. Hungarian
resolvería el problema equivocado. La mejora real es un LP (PuLP + CBC), y es un
reemplazo directo del paso 3 sin tocar el resto.

---

## 6. Schema de salida

```json
{
  "timestamp": "2026-08-28T14:30:00-05:00",
  "contexto": {
    "tipo_desastre": "inundacion",
    "periodo": 1,
    "municipio": "Mocoa"
  },
  "resumen": {
    "voluntarios_registrados": 48,
    "horas_capacidad_total": 240.0,
    "horas_asignadas": 191.0,
    "cobertura": 0.79
  },
  "asignaciones": [
    {
      "id": "ASG-001",
      "zona": "Z-03",
      "tarea": "S2",
      "voluntario_id": "VOL-0042",
      "profesion": 2,
      "horas": 6.0,
      "severidad": "critica",
      "supervisado_por_unidad_oficial": true,
      "regla_aplicada": null
    }
  ],
  "demanda_insatisfecha": [
    {
      "zona": "Z-07",
      "tarea": "T3",
      "horas_faltantes": 12.0,
      "motivo": "R3: sin ambulancias disponibles en Z-07"
    }
  ],
  "gobernanza": {
    "requiere_aprobacion_humana": true,
    "reglas_evaluadas": ["R1", "R2", "R3", "R4", "R5", "R6"],
    "bloqueos_por_seguridad": 3
  }
}
```

Cada asignación bloqueada dice **cuál regla** la bloqueó. Eso es lo que hace
auditable el sistema.

---

## 7. Stack

Ajustado a lo que hay disponible en el evento (ver `../check_keys.py`).

| Componente | Elección | Nota |
|---|---|---|
| LLM extracción | **`gemini-flash-lite-latest`** | ~1 s; fallback `gemini-3.5-flash-lite` |
| Asignación | **Python stdlib** | Cero dependencias, corre en cualquier portátil |
| Datos | **JSON en disco** | PostgreSQL + PostGIS solo si sobra tiempo |
| API | **FastAPI** | Un endpoint: `POST /asignar` |

> Los modelos **Gemini Pro devuelven 429 (cuota agotada)** con la key del evento.
> Todo el diseño asume familia Flash: tareas acotadas de extracción y clasificación,
> nunca razonamiento largo en una sola llamada.

**Descartado para el hackatón:** CPLEX (licencia comercial), Qwen2.5-72B y GPT-4o
(no hay acceso), Qwen2.5-0.5B en MediaPipe (es un build móvil aparte), ChromaDB y
Langfuse (no aportan al demo en 48 h).

---

## 8. Roadmap (lo que NO entra en el hackatón)

Fundamentado en `papers/`, presentar como visión, no como entregable:

- **Optimización estocástica de dos etapas** con escenarios de severidad, resuelta
  con AUGMECON2 multiobjetivo (minimizar demanda insatisfecha + costo de traslado).
- **Multiperiodo con transferencias interregionales** y modelado de tasa de abandono.
- **Reoptimización adaptativa (AET):** recalcular globalmente solo si el puntaje de
  disrupción supera un umbral; si no, inserción local para no desestabilizar rutas
  ya comprometidas.
- **RAG con citación a SOP** (INSARAG, Sphere) para que cada tarea apunte al párrafo
  que la sustenta. *Requiere ingestar los documentos: hoy no los tenemos.*
- **Modo offline** con modelo cuantizado en el dispositivo, para zonas sin red.

---

## 9. Flujo de datos

```
[ Voluntario se registra por WhatsApp/formulario ]   [ Agente de Necesidades ]
                    │                                          │
                    ▼                                          ▼
        ingesta.py — Gemini Flash                        demanda[] por zona
        texto libre → perfil JSON                               │
                    │                                          │
                    └──────────────┬───────────────────────────┘
                                   ▼
                    solver.py — filtro de seguridad R1..R6
                                   │
                                   ▼
                    asignación greedy por prioridad
                                   │
                                   ▼
                  JSON de salida + motivo de cada bloqueo
                                   │
                                   ▼
                  [ Panel DMC: aprobación humana ] ──► despacho
```

## 10. Archivos

| Archivo | Qué es |
|---|---|
| `solver.py` | Motor de asignación. Cero dependencias. `python3 solver.py` |
| `ingesta.py` | Extracción de perfil con Gemini. Requiere `GEMINI_API_KEY` |
| `datos_demo.json` | Escenario de inundación con 12 voluntarios y 6 zonas |
| `papers/` | Fuentes académicas del modelo completo |
