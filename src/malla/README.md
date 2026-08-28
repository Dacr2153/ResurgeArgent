# Malla P2P — red de emergencia entre teléfonos

## Qué resuelve

En un desastre lo primero que cae son las comunicaciones: por saturación de las
celdas o por daño físico a la infraestructura. Un sistema de reportes que asume
que siempre hay internet pierde justamente los reportes que más importan, los
de la zona afectada.

La malla convierte cada teléfono con la aplicación instalada en un nodo. Un
reporte salta de teléfono en teléfono hasta llegar a alguno que sí tenga salida
a internet, y ese lo sube por todos. El resto del sistema (Ingesta,
Verificación, Orquestador) no se entera: recibe reportes normales, solo que
algunos llegaron dando siete saltos.

## Topología

No hay servidor ni coordinador. Cada nodo es igual a los demás y solo conoce a
sus vecinos inmediatos. La propagación es de rumor (*epidemic routing*): quien
recibe algo nuevo se lo pasa a todos los vecinos que aún no lo tienen.

```
   [teléfono A] ──── [teléfono B] ──── [teléfono C]
        │      \        │                   │
        │       \       │                   │
   [teléfono D] ─ [teléfono E] ──── [teléfono F con señal] ──► Orquestador
```

Tres propiedades sostienen esto y están todas en `dominio/motor_malla.py`:

- **Identidad estable del mensaje.** El `id_mensaje` se deriva de
  `ReporteCrudo.hash_idempotencia`, la misma primitiva que usa Ingesta, que
  redondea la ubicación a ~100 m para absorber la deriva del GPS. El mismo
  reporte llegando por tres caminos colapsa en uno, en la malla y también
  después en la nube.
- **Anti-bucle y TTL.** Un nodo que ya está en la ruta del sobre no lo reenvía,
  y un sobre que agotó sus saltos muere. Sin lo primero, tres nodos en triángulo
  se saturan entre sí en segundos.
- **Firma en origen.** Ver más abajo.

## Formato del sobre

```json
{
  "version": "1.0",
  "id_mensaje": "a3f1...  (32 hex — hash_idempotencia del reporte)",
  "tipo_carga": "reporte | acuse",
  "nodo_origen": "de2834c1b0ceceb1  (16 hex — derivado de la clave pública)",
  "clave_publica_origen": "  (64 hex — Ed25519 raw)",
  "firma": "  (128 hex — Ed25519, 64 bytes)",
  "momento_origen": "2026-08-28T14:03:11.482913+00:00",
  "ttl": 8,
  "saltos": 3,
  "ruta": ["nodo-b", "nodo-e", "nodo-f"],
  "carga": { "...": "ReporteCrudo.a_dict()" }
}
```

**La firma cubre**: `version`, `id_mensaje`, `tipo_carga`, `nodo_origen`,
`momento_origen`, `ttl` y `carga`, serializados canónicamente (claves ordenadas,
sin espacios, UTF-8).

**La firma NO cubre**: `saltos` ni `ruta`, porque cambian legítimamente en cada
retransmisión. Si entraran, ningún sobre reenviado verificaría jamás.

Que el `ttl` esté dentro de la firma es deliberado: un retransmisor no puede
inflarlo a mil saltos para inundar la red. Y que el `nodo_origen` se derive de
la clave pública impide que alguien firme con su clave y se presente como otro.

### Por qué se firma, y solo en origen

Un reporte de emergencia atraviesa los teléfonos de desconocidos antes de llegar
a alguien con internet. Sin firma, un nodo malicioso en medio del camino puede
mover un derrumbe a otro barrio, inflar el número de víctimas o inventar un
incidente entero — y el sistema despacharía rescates hacia donde no hay nadie.

Se firma **solo en origen**. Quien retransmite puede negarse a reenviar, pero no
puede alterar el contenido sin invalidar la firma. Firmar en cada salto
encarecería el reenvío sin aportar la propiedad que hace falta, que es "esto es
lo que dijo el origen", no "esto pasó por aquí".

## TTL y prioridad

**TTL por defecto: 8.** En una red de rumor, los saltos necesarios para cubrir
la componente conexa crecen como log_d(N), con `d` el grado medio. Con un grado
realista de 4 vecinos al alcance y una zona afectada de ~10.000 dispositivos,
log_4(10000) ≈ 6.6; 8 deja margen para topologías irregulares (calles,
edificios) sin permitir circulación indefinida. Cada salto añade además segundos
de latencia: más allá de 8, el reporte llega tarde para servir de algo.
El receptor rechaza cualquier sobre con `ttl > 16` (`TTL_MAXIMO_ACEPTADO`).

**Prioridad**: `(urgencia CAP, tipo de fuente, antigüedad)`. Primero
`Immediate`, luego `Expected`, `Future`, `Past`; a igualdad de urgencia, primero
`autoridad`, luego `sensor`/`organizacion`, y al final `ciudadano`; a igualdad
de ambas, primero el más viejo. Importa porque un enlace de malla es lento: si
se manda todo en orden de llegada, un `Immediate` de bomberos puede quedar
detrás de cincuenta reportes rutinarios y no salir nunca.

## Transportes: qué funciona hoy y qué no

Esta es la parte que conviene leer con honestidad antes de prometer nada.

| Transporte | Estado | Qué hace falta |
|---|---|---|
| **HTTP en red local** (`adaptadores/salida/transporte_http.py`) | **Funciona hoy.** Es el que se puede demostrar entre varios puertos de una máquina o varias máquinas del mismo Wi-Fi. | Nada. Ya ejercita toda la lógica de malla: flooding, deduplicación, TTL, prioridad, almacenar-y-reenviar. |
| **WebRTC entre navegadores** | **Parcial.** El punto de encuentro (`adaptadores/entrada/senalizacion.py`) está implementado y probado; el `RTCPeerConnection` del lado del navegador y su adaptador de transporte **no**. | Código de navegador, y alguien que sostenga la señalización: sin infraestructura ninguna, dos navegadores no se encuentran. |
| **Bluetooth LE / Bluetooth Mesh** | **No funciona.** Es la malla de verdad, la que opera sin ninguna infraestructura. | Una aplicación **nativa** (Android/iOS). El navegador no puede hablar Bluetooth de esta forma. |
| **Wi-Fi Direct / Wi-Fi Aware** | **No funciona.** | Igual: envoltorio nativo. |

Que el proyecto tenga hoy una malla de navegador y no una malla de bolsillo es
una limitación real, no un detalle de implementación. Lo que sí está resuelto es
que migrar no toca el dominio: `TransportePort` (`enviar`, `vecinos`) es todo lo
que un transporte nuevo tiene que cumplir, y el motor de propagación no sabe ni
tiene por qué saber por dónde viaja el sobre.

## API REST del nodo

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/health` | Vivo o no. |
| `GET` | `/nodo` | Identidad pública y estado: `id_nodo`, `clave_publica`, `ttl_por_defecto`, `vecinos`, `pendientes`, `ultima_secuencia`, `salida_internet`. Es también el sondeo que usan los vecinos. |
| `POST` | `/sobres` | Recibir un sobre de un vecino. Siempre 202; el veredicto va en `resultado`. |
| `GET` | `/sobres?desde=&limite=` | Que un vecino se lleve lo que no tiene, paginado por secuencia local. |
| `POST` | `/reportes` | Originar un reporte en este teléfono: se firma y se difunde. |
| `POST` | `/sincronizar` | Forzar la subida del lote acumulado a la nube. |
| `POST` | `/senalizacion/anuncios` | Un navegador se presenta. |
| `GET` | `/senalizacion/pares?excluir=` | Con quién intentar conexión directa. |
| `POST` | `/senalizacion/senales` | Dejar oferta SDP / respuesta / candidato ICE. |
| `GET` | `/senalizacion/senales?destino=` | Recoger el buzón (se vacía al leerse). |

`POST /sobres` responde 202 incluso cuando rechaza el sobre por firma inválida.
Es deliberado: quien lo entregó normalmente no es el atacante, sino otro nodo
honesto retransmitiendo lo que le llegó; un 4xx le haría reintentar en bucle
algo que nunca va a ser aceptado. El rechazo queda en la auditoría.

## Persistencia

Los pendientes van a SQLite (`adaptadores/salida/almacen_sqlite.py`) y la clave
privada a disco con permisos 0600. Ambas cosas deben sobrevivir a que se cierre
la aplicación —o a que el sistema la mate por batería, que es lo que pasa de
verdad en una emergencia—: si los pendientes viven en memoria no hay
almacenar-y-reenviar que valga, y si la identidad cambia en cada arranque todos
los sobres que ya circulan con esa firma quedan huérfanos.

## Configuración

Variables con prefijo `MALLA_` (ver `config/settings.py`):
`MALLA_RUTA_IDENTIDAD`, `MALLA_RUTA_ALMACEN`, `MALLA_TTL_POR_DEFECTO`,
`MALLA_VECINOS` (URLs separadas por coma), `MALLA_CAPACIDAD_LOTE`,
`MALLA_URL_NUBE` (vacío = este nodo no es pasarela y nunca lo intenta).

## Estructura

```
src/malla/
├── dominio/          sobre, firma Ed25519, motor de propagación, vecino  (puro)
├── aplicacion/       puertos (Protocol) y casos de uso
├── adaptadores/
│   ├── entrada/      api_rest, senalizacion, modelos
│   └── salida/       transporte_http, nube_http, almacen_sqlite, almacen_memoria
└── config/           settings, contenedor
```
