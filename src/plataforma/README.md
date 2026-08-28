# plataforma

Los dominios del sistema que **no tienen un agente detrás**: voluntarios,
misiones, recuperación y cola de sincronización offline.

## Qué es

Un paquete hexagonal más, con la misma forma que los agentes (`dominio/`,
`aplicacion/`, `adaptadores/`, `config/`) y los mismos puertos como
`typing.Protocol`. Se monta bajo el prefijo `/plataforma` y sirve:

| Ruta | Qué devuelve |
| --- | --- |
| `GET /reportes/{id}` | recorrido real de un reporte, derivado del estado de su operación en el Orquestador |
| `POST /voluntarios` | alta persistida; siempre en verificación |
| `POST /misiones` | apertura de una misión sobre un incidente ya priorizado |
| `GET /misiones?radio_km=&lat=&lon=` | misiones abiertas dentro del radio, por distancia Haversine real |
| `GET /misiones/{id}` | detalle de la misión, con ETA calculado desde el punto de consulta |
| `GET /recuperacion/preguntas` | cuestionario persistido |
| `POST /recuperacion/plan` | hoja de ruta derivada por reglas deterministas |
| `GET /sincronizacion` | reportes encolados sin red |
| `POST /sincronizacion` | vaciado de la cola |
| `POST /sincronizacion/reportes` | encolado de un reporte creado sin cobertura |

## Qué no es

**No es un agente.** No delibera, no negocia con otros agentes por Contract Net,
no emite mensajes FIPA-ACL y no llama a ningún LLM. No lo necesita: todo lo que
responde es una consulta a datos persistidos o la aplicación de una tabla de
reglas.

**No decide sobre incidentes.** El recorrido de un reporte se *lee* del
Orquestador y se traduce a lenguaje de ciudadano; plataforma nunca mueve una
operación de estado. Eso sigue exigiendo la firma del coordinador humano.

## Por qué existe

Porque estos cuatro dominios eran lo único que el frontend resolvía con datos de
ejemplo, y un dato de ejemplo en una respuesta a desastres es una mentira con
consecuencias: un voluntario que sale hacia un ETA inventado llega tarde, y un
damnificado al que se le muestra un plan de recuperación fijo tramita lo que no
le toca.

Dos decisiones concretas que se derivan de eso:

- **El plan de recuperación es una tabla de reglas, no texto generado.** Se puede
  señalar la regla exacta que puso (o no puso) un trámite en la hoja de ruta de
  una familia. Un LLM daría planes distintos a dos familias en la misma
  situación, y en ayuda estatal eso es discriminación.
- **La cola offline se marca enviada, no se borra.** Un reporte que salió tarde
  por falta de red es evidencia de dónde falló la cobertura durante el desastre.

## Persistencia

En memoria por defecto. Con `PLATAFORMA_RUTA_SQLITE` apuntando a un archivo,
voluntarios, misiones, cuestionario y cola offline sobreviven al reinicio. El
seguimiento de reportes lee el repositorio de operaciones del Orquestador: para
que funcione entre procesos, `AGENTE1_RUTA_SQLITE` debe apuntar al mismo archivo
que use el Agente 1.
