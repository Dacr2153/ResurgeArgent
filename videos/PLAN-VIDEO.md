# Plan del video — ResurgeAgent (3 min)

> **Estado: preparado, no ejecutado.** La aplicación todavía no existe, así que no se
> corrió el workflow. Este archivo deja decidido lo que el workflow preguntaría, para
> que cuando haya prototipo la construcción arranque sin discusión.
>
> **No es `BRIEF.md` a propósito.** `product-launch-video` escribe su propio `BRIEF.md`
> en el Paso 0 con confirmación del usuario; dejarle uno a medias haría que se salte esa
> entrevista con supuestos míos.

---

## 1. Ruta y comandos

Skill instalada en `~/ResurgeAgent/.agents/skills/` (26 skills, `hyperframes` es la puerta de entrada).

```bash
npx hyperframes skills update product-launch-video   # refrescar antes de usar
# la construcción arranca leyendo /hyperframes, que enruta y hace la entrevista
```

Ruta prevista: **`product-launch-video`** — es demo de producto con intención de
mostrarlo tal cual. Trabaja en `videos/<proyecto>/` y va por 7 pasos:
setup → captura → design system → storyboard/guion → audio → frames → render.

---

## 2. Campos del brief (propuesta a confirmar)

| Campo | Valor propuesto | Razón |
|---|---|---|
| `destination` | Presentación ante jurado | Es un hackatón, se proyecta |
| `aspect` | `1920x1080` | Derivado de destino desktop/proyector |
| `length` | 180 s | **Impuesto por el usuario**, no recomendado por el material |
| `language` | Español | Idioma del proyecto y del jurado |
| `audience` | Jurado técnico + entidades de gestión de riesgo | Define el vocabulario |
| `message` | "Convierte reportes caóticos de una emergencia en asignaciones seguras y auditables" | Una sola frase; sin esto no hay storyboard |
| `angle` | Demo del flujo end-to-end sobre un caso real | Muestra el sistema, no la arquitectura |
| `narration` | `yes` | A 3 minutos no se sostiene sin voz |
| `flow` / `storyboard` | `automation` / `yes` → modo colaborativo | Conviene revisar el board antes de renderizar |

---

## 3. Estructura de 3 minutos

Ocho bloques. Cada uno nombra **qué se ve en pantalla**, que es lo que hay que tener
construido en la app antes de grabar.

| # | Tiempo | Bloque | Qué se ve |
|---|---|---|---|
| 1 | 0:00–0:20 | **El problema** | Reportes crudos entrando en avalancha: WhatsApp, llamadas, redes. Ruido, duplicados, contradicciones |
| 2 | 0:20–0:40 | **Qué es** | Nombre, una frase, el diagrama del núcleo de 5 agentes |
| 3 | 0:40–1:05 | **Ingesta** | Mensaje real de WhatsApp → JSON estructurado apareciendo campo a campo. *Aquí el LLM gana* |
| 4 | 1:05–1:30 | **Verificación** | 40 reportes del mismo derrumbe colapsando en 1 incidente, con nivel de confianza |
| 5 | 1:30–1:50 | **Necesidades y prioridad** | Mapa de Mocoa, zonas coloreadas por severidad, cola priorizada |
| 6 | 1:50–2:25 | **Asignación** ⭐ | `solver.py` corriendo: 12 asignaciones y, sobre todo, **las bloqueadas con su regla** (R2 sin unidad oficial, R3 sin ambulancia) |
| 7 | 2:25–2:45 | **Humano en el loop** | El coordinador ve el motivo y firma. Nada se despacha solo |
| 8 | 2:45–3:00 | **Cierre** | Cobertura 74%, y la fase de recuperación como roadmap |

**El bloque 6 es el corazón del video.** Lo que diferencia este proyecto no es que
asigne, es que **explica por qué no pudo asignar**. Debe ocupar el tiempo más largo y
el mensaje central de la narración.

**El bloque 7 vende el proyecto ante una entidad real.** Un sistema que despacha
rescates sin firma humana no lo adopta nadie; mostrar el gate es un argumento
comercial, no un detalle técnico.

---

## 4. Estado del toolchain (`npx hyperframes doctor`)

| Check | Estado |
|---|---|
| hyperframes 0.8.17, Node v25.8.1, FFmpeg n8.1, Chromium, Docker | ✅ |
| CPU 20 cores, disco 37.6 GB | ✅ |
| **Memoria: 1.6 GB libres de 7.5 GB** | ⚠️ **"renders may fail"** |
| chrome-headless-shell | instalándose (sin él la captura cae a modo screenshot, más lento) |
| whisper-cpp (transcripción) | ❌ opcional |
| **TTS y música** | ❌ **ver abajo** |

### El bloqueo real: no hay voz

`npx hyperframes auth status` → **no hay sesión de HeyGen**, y los motores locales
tampoco están instalados. A 3 minutos la narración no es opcional. Dos caminos:

```bash
# A) Cuenta HeyGen (mejor calidad de voz, requiere navegador)
npx hyperframes auth login

# B) Motores locales, gratis y offline
pip install kokoro-onnx soundfile              # voz
pip install transformers torch soundfile numpy # música
```

**Recomendación: A.** El login es una vez y la voz en español queda mucho mejor; la
opción B además descarga torch, que son varios GB sobre un disco con 37 GB y una
máquina con poca RAM libre.

**Además, cerrar aplicaciones antes de renderizar.** 1.6 GB libres es poco para un
render de 3 minutos a 1080p.

---

## 5. Lo que falta del lado de la aplicación

El video no se puede construir con lo que hay hoy. Para grabarlo hace falta, en orden:

1. **UI con mapa** — bloques 1, 4, 5, 7. Es lo más pesado y lo que más pantalla ocupa.
2. **`ingesta.py`** — bloque 3. Ya está pedido y sin escribir.
3. **Agente de Verificación** — bloque 4. Sin construir; es el mayor diferenciador.
4. **Panel de aprobación del coordinador** — bloque 7.

`solver.py` (bloque 6) **ya corre** y da salida presentable. Si el tiempo aprieta, ese
bloque se puede grabar hoy contra la terminal y el resto reducirse.

---

## 6. Advertencia sobre la duración

**3 minutos es largo** para este formato; el promedio de un demo de producto es 60–90 s.
Es alcanzable porque hay sustancia real que mostrar, pero exige que cada bloque tenga
material grabable: tres minutos de diagramas y texto se sienten el doble de largos.

Si al llegar al storyboard no hay suficiente UI construida, **90 segundos bien llenos
puntúan mejor que 180 con relleno**. Conviene decidirlo con el material a la vista, no
ahora.
