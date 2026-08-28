# Frontend — Plataforma de Gestión de Emergencias

Implementación del diseño `Diseño UI minimalista` (Claude Design, design system
**Broadsheet**) como app real. **Todos los datos son mocks**: no hay backend
conectado todavía.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build
```

## Las 11 pantallas

| Ruta | Pantalla | Rol |
| --- | --- | --- |
| `/` | Landing | público |
| `/reportar` | Reporte (stepper de 3 pasos + confirmación) | ciudadano |
| `/seguimiento/:id` | Seguimiento del reporte | ciudadano |
| `/registro` | Registro de voluntario | voluntario |
| `/voluntario/misiones` | Muro de misiones | voluntario |
| `/voluntario/mapa/:id` | Ruta y ejecución de misión | voluntario |
| `/login` | Acceso RBAC | coordinador |
| `/dashboard` | Mapa operativo + cola de incidentes | coordinador |
| `/matching/:id` | Asignación sugerida | coordinador |
| `/recuperacion/:id` | Evaluación de daños y hoja de ruta | ciudadano |
| `/offline` | Cola local de sincronización | todos |

## Cómo conectar el backend

Toda la I/O pasa por `src/api/client.ts`. Ahí vive la interfaz `EmergencyApi`
y su única implementación actual, `MockApi`, que resuelve contra `src/mocks/`
con latencia simulada.

Para conectar el backend real:

1. Escribir `class HttpApi implements EmergencyApi` en `src/api/http.ts`.
2. Cambiar la última línea de `client.ts`: `export const api: EmergencyApi = new HttpApi()`.

Ninguna pantalla importa `src/mocks/` directamente, así que no hay que tocar
componentes. Los tipos del contrato están en `src/api/types.ts`.

## Decisiones que vienen del diseño, no del capricho

- **La prioridad nunca se comunica solo por color.** Cada disco de banda lleva
  un glifo (`!` crítico, `▲` alto, `●` medio) y va acompañado de la etiqueta
  textual y el score. Ver `src/components/PriorityMark.tsx` y `src/lib/band.ts`.
- **Los tokens del design system están en `src/styles/tokens.css`** y son la
  fuente de verdad. No hardcodear hex fuera de ese archivo (la excepción son los
  marcadores de Leaflet en `MapView.tsx`, que se inyectan como HTML suelto y no
  resuelven custom properties).
- **Las teselas del mapa van desaturadas** para que la tinta de los marcadores
  lea primero — es el registro de prensa del sistema Broadsheet.
- **El OTP nunca bloquea un reporte**: "Enviar sin verificar" deja el reporte en
  `pendiente_verificacion` y ya entra a la cola del coordinador.
- **La evaluación de daños guarda progreso en `localStorage`**: se contesta en
  momentos malos y tiene que sobrevivir a que cierren la app.

## Barra de demo

`src/components/DemoBar.tsx` fuerza los estados transversales que en producción
vienen del dispositivo (red, permiso de GPS) o del token (alcance RBAC). Se
apaga con `VITE_DEMO_BAR=0` y **no debe llegar a producción**.

## Pendiente

- Autenticación real y refresh silencioso del token (hoy `/login` solo navega).
- WebSocket del muro de misiones (hoy es un fetch con badge estático "WS activo").
- IndexedDB + Background Sync reales para la cola offline (hoy es estado en memoria).
- Chat con el coordinador, descarga del PDF de la hoja de ruta y subida real de
  foto con limpieza de EXIF: son botones sin implementación.
