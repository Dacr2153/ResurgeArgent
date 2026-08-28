"""Value objects del dominio de verificación.

`VectorAcuerdo` es el vector de coincidencia del record linkage clásico
(Fellegi-Sunter): por cada par de reportes candidatos, señales que el motor
combina en un único score para decidir si fusiona.

La ubicación y el tiempo no se tratan como todo-o-nada. Cada una se traduce en
una `fuerza` continua en [0,1] (ver `MotorVerificacion._fuerza`): 1.0 cuando el
par está *muy* por debajo del radio/ventana configurados ("misma esquina",
"casi simultáneo"), decayendo linealmente hacia 0 solo cerca del límite
configurado. Esto es la corrección directa a un defecto real: con
`coincide_ubicacion`/`coincide_tiempo` booleanos, la suma máxima posible de las
tres señales deterministas (ubicación + categoría + tiempo) quedaba por debajo
del umbral de fusión, así que la fusión SIEMPRE dependía de que el puerto de
similitud textual aportara algo — y con `SimilitudNula` (Jaccard léxico), dos
paráfrasis reales de un mismo hecho ("se cayó el puente" vs "colapsó la
estructura sobre el río") comparten pocas palabras, así que el sistema en modo
offline nunca fusionaba nada. Eso violaba la regla del proyecto: el LLM no
puede ser necesario para la función central del agente.

Con la fuerza continua, los pesos quedan calibrados así:

- Cuando el par está muy cerca en espacio y tiempo (fuerza ~1.0 en ambos) y
  comparte categoría, la suma de las tres señales deterministas por sí sola
  (PESO_UBICACION + PESO_CATEGORIA + PESO_TIEMPO = 0.70) YA supera el umbral
  (0.65): cuarenta personas describiendo algo en la misma esquina, en la misma
  media hora, de la misma categoría, están hablando del mismo hecho, escriban
  lo que escriban. El texto ya no puede bloquear esa fusión.
- Cuando el par está cerca del borde del radio o de la ventana (fuerza baja),
  la evidencia geométrica sola no alcanza y el texto pasa a decidir — que es
  justo donde el texto aporta información que la geometría no tiene (dos
  hechos distintos que ocurren cerca en espacio y tiempo y comparten categoría,
  p. ej. un incendio y un choque, los dos `Categoria.SAFETY`, a media cuadra y
  media hora de diferencia, no deben fusionarse solo por eso).
- Similitud textual perfecta sola (0.30) sigue sin bastar: dos reportes que
  por casualidad usan palabras parecidas pero ocurrieron lejos en espacio o
  tiempo no se fusionan solo por el texto (de hecho ni siquiera llegan a
  evaluarse: `MotorVerificacion._compatibles_determinista` los descarta antes).

Así el LLM (que aporta `similitud_texto`) nunca puede fusionar por sí solo, y
ya no puede bloquear una fusión que la geometría por sí sola sostiene con
fuerza abrumadora. Es la traducción literal de "el LLM opina, el dominio
decide" al puntaje, en ambas direcciones.
"""

from __future__ import annotations

from dataclasses import dataclass

from agente_verificacion.dominio.excepciones import VectorAcuerdoInvalidoError

PESO_UBICACION = 0.35
PESO_CATEGORIA = 0.15
PESO_TIEMPO = 0.20
PESO_TEXTO = 0.30

UMBRAL_FUSION_DEFECTO = 0.65


@dataclass(frozen=True, slots=True)
class VectorAcuerdo:
    """Vector de coincidencia de Fellegi-Sunter para un par de reportes."""

    fuerza_ubicacion: float
    coincide_categoria: bool
    fuerza_tiempo: float
    similitud_texto: float

    def __post_init__(self) -> None:
        for nombre, valor in (
            ("fuerza_ubicacion", self.fuerza_ubicacion),
            ("fuerza_tiempo", self.fuerza_tiempo),
            ("similitud_texto", self.similitud_texto),
        ):
            if not 0.0 <= valor <= 1.0:
                raise VectorAcuerdoInvalidoError(f"{nombre} debe estar en [0,1]: {valor}")

    def score(self) -> float:
        """Puntaje ponderado en [0,1] que alimenta la decisión de fusión."""
        return (
            PESO_UBICACION * self.fuerza_ubicacion
            + PESO_CATEGORIA * self.coincide_categoria
            + PESO_TIEMPO * self.fuerza_tiempo
            + PESO_TEXTO * self.similitud_texto
        )
