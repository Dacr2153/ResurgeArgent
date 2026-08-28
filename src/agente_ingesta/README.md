# Agente 2 — Ingesta de Información

Convierte reportes heterogéneos (ciudadanos, afectados, voluntarios,
organizaciones, autoridades, sensores) en `ReporteCrudo` bien formados
(esquema canónico CAP 1.2, definido en `nucleo`).

## Qué hace

1. **Normalización**: cada entrada cruda (texto libre o dato de sensor) se
   convierte al esquema canónico.
2. **Idempotencia**: descarta reenvíos exactos vía
   `ReporteCrudo.hash_idempotencia`.
3. **Validación**: coordenadas válidas, texto no vacío, fuente identificada.
   Lo inválido se descarta con motivo (`MotivoDescarte`), sin tumbar el lote.
4. **Back-pressure**: límite de reportes por ventana de tiempo deslizante.
   Ante saturación, sobreviven primero `Urgencia.IMMEDIATE` y fuente
   `AUTORIDAD` (SRE Book, "Handling Overload").
5. **Enriquecimiento**: texto libre en español pasa por un extractor (LLM o
   reglas de palabras clave) que propone categoría, urgencia, severidad,
   ubicación mencionada, personas afectadas y necesidades. Un sensor con
   datos ya estructurados se mapea directo, sin pasar por el extractor.

La regla que no se rompe: **el LLM nunca decide**. El extractor solo
estructura texto; `MotorIngesta` —puro, determinista, sin I/O— es quien
decide qué se acepta.

## Qué NO hace

- No juzga si un reporte es cierto (eso es del Agente 3, Verificación).
- No detecta duplicados semánticos (dos reportes distintos del mismo hecho):
  solo descarta reenvíos *exactos* del mismo reporte.
- No decide relevancia ni prioriza incidentes: solo prioriza qué reportes
  sobreviven al back-pressure cuando el lote excede la capacidad de la
  ventana.

## Cómo correrlo

Todo corre sin red y sin API key por defecto, vía `ExtractorNulo` (reglas de
palabras clave). Para usar un LLM real, configura `AGENTE2_LLM_PROVEEDOR` y la
API key correspondiente (ver `config/settings.py`).

```bash
# Desde este worktree, con el intérprete compartido del proyecto:
pytest -q
ruff check src tests
```

El puerto de entrada (`aplicacion/puertos/entrada.py`) cumple
`nucleo.puertos.IngestaPort` por forma: `async def ingerir(self, entrada:
dict) -> list[ReporteCrudo]`. `entrada` es `{"reportes": [...], "correlacion_id":
"..."?}`, donde cada item de `reportes` trae `fuente`, `canal` y, según el
canal, `texto` (SMS, WhatsApp, llamada, web, app, USSD, radio) o
`datos_sensor` (canal `sensor`).

El adaptador REST expone `POST /ingesta` con ese mismo contrato y `GET
/health`.
