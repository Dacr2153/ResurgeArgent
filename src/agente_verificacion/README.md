# Agente 3 — Verificación

Recibe reportes crudos (`nucleo.esquemas.ReporteCrudo`) de varias fuentes sobre
posiblemente el mismo hecho, y los colapsa en incidentes verificados
(`nucleo.esquemas.IncidenteVerificado`) con una confianza en `[0,1]`. Es el
puerto de entrada que consume el Orquestador vía `nucleo.puertos.VerificacionPort`.

## Qué hace

1. **Agrupa** reportes que son cercanos en espacio (radio configurable sobre
   `haversine`), en tiempo (ventana configurable) y que comparten categoría.
2. **Decide la fusión** con un vector de acuerdo tipo Fellegi-Sunter: ubicación,
   categoría, tiempo (deterministas) + similitud textual (opinión de un puerto
   de similitud, LLM o léxico). El **motor determinista decide siempre**; el
   puerto de similitud solo aporta una señal más — nunca fusiona por sí solo,
   ni puede bloquear una fusión que las señales deterministas ya sostienen con
   fuerza suficiente.
3. **Calcula confianza** combinando (noisy-OR) el peso de cada fuente
   independiente: reputación declarada, tipo de fuente (`AUTORIDAD` pesa más
   que `CIUDADANO`), certeza CAP y decaimiento por antigüedad. La misma fuente
   repitiendo el mismo reporte no suma como una corroboración adicional.
4. **Fija caducidad** (`vence_en`) según la urgencia CAP declarada.
5. **Deja constancia de contradicciones**: si el cluster no es unánime en
   severidad, gana la evidencia con más peso y queda registrado en
   `metadatos["contradiccion_severidad"]`.
6. **Audita** cada paso relevante (`REPORTE_RECIBIDO`, `CONFIANZA_CALCULADA`,
   `INCIDENTE_FUSIONADO`, `INCIDENTE_VERIFICADO`) vía `AuditoriaPort`.

## Qué NO hace

- No decide a quién se le asignan recursos (Orquestador / Agente de Matching).
- No calcula rutas ni accesibilidad (Agente Geoespacial).
- No normaliza reportes crudos ni descarta duplicados por idempotencia — eso
  es del Agente de Ingesta; aquí ya llegan bien formados.

## Cómo correrlo

Sin red y sin API key por defecto (`AGENTE3_LLM_PROVEEDOR=nulo`): usa
`SimilitudNula`, similitud léxica (Jaccard sobre tokens) en vez de embeddings.
Para usar un LLM real, exporta `AGENTE3_LLM_PROVEEDOR=anthropic` (o `deepseek`)
y la API key correspondiente (`AGENTE3_ANTHROPIC_API_KEY` / `AGENTE3_DEEPSEEK_API_KEY`).

```bash
# API REST standalone del agente
python -c "
from agente_verificacion.config.contenedor import construir_contenedor
from agente_verificacion.adaptadores.entrada.api_rest import crear_app
import uvicorn
uvicorn.run(crear_app(construir_contenedor()), host='0.0.0.0', port=8003)
"

# En proceso, como lo usaría el Orquestador (cumple VerificacionPort):
from agente_verificacion.config.contenedor import construir_contenedor
caso_uso = construir_contenedor()
incidentes = await caso_uso.verificar(reportes)  # reportes: list[ReporteCrudo]
```

Montado junto a los demás agentes vía `main.py` (raíz del repo) bajo el
prefijo `/verificacion`, cuando este paquete está presente.

## Tests

```bash
pytest -q tests/verificacion
```

Incluye el caso estrella: 40 reportes del mismo derrumbe, de fuentes
distintas, con texto variado y GPS ligeramente disperso, colapsan en
exactamente un `IncidenteVerificado` con 40 corroboraciones y confianza alta.
