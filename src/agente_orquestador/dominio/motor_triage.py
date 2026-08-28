"""Motor de triage: ordena incidentes para asignarles recursos escasos.

Determinista por construcción. Mismo lote de entrada, mismo orden de salida,
siempre — sin relojes, sin aleatoriedad, sin depender del orden en que llegaron
los incidentes a la lista.

La fórmula
----------

    base       = w_sev * peso(severidad) + w_urg * peso(urgencia)
                 + w_per * factor(personas_afectadas)
    puntuacion = base * factor_confianza(confianza)

y el orden final es por `puntuacion` descendente, desempatando por
`incidente_id` ascendente.

Por qué así:

- **La confianza multiplica, no resta.** Un incidente dudoso no pierde una
  cantidad fija de puntos: pierde una fracción de lo que vale. Así un rumor sobre
  un evento catastrófico y un rumor sobre un evento menor se degradan en
  proporción a lo que estaba en juego, en vez de quedar ambos al mismo nivel.
- **El piso de confianza es 0.5** (ver `value_objects`): la información no
  confirmada se descuenta, no se ignora. En las primeras horas de un desastre
  casi nada está confirmado, y un sistema que solo atiende lo confirmado no
  atiende nada.
- **Severidad pesa más que urgencia** (0.45 vs 0.35). Ambas vienen de CAP y miden
  cosas distintas: severidad es cuánto daño hay, urgencia es cuánto margen queda.
  Con recursos escasos la magnitud manda, pero la urgencia es lo que hace que una
  asignación no se pueda posponer, así que va muy cerca.
- **Personas afectadas pesa lo menos** (0.20). Está fuertemente correlacionada
  con la severidad, así que subirla sería contar dos veces lo mismo; su trabajo
  real es romper empates entre incidentes igual de graves.
- **El desempate es por `incidente_id`, no por hora de llegada.** El id es
  estable entre ejecuciones; la hora de llegada depende de la red y haría que
  reordenar el mismo lote diera resultados distintos.
"""

from __future__ import annotations

from agente_orquestador.dominio.value_objects import (
    PESO_SEVERIDAD,
    PESO_URGENCIA,
    PesosTriage,
    PuntuacionTriage,
    factor_confianza,
    factor_personas,
)
from nucleo.esquemas import IncidenteVerificado

#: Decimales a los que se redondea la puntuación antes de ordenar. Sin este
#: redondeo, dos incidentes idénticos podrían separarse por ruido de coma
#: flotante y el desempate explícito por id nunca llegaría a aplicarse.
DECIMALES_ORDEN = 9


class MotorTriage:
    """Ordena incidentes verificados por prioridad de atención."""

    def __init__(self, pesos: PesosTriage | None = None) -> None:
        self._pesos = pesos or PesosTriage()

    @property
    def pesos(self) -> PesosTriage:
        return self._pesos

    def puntuar(self, incidente: IncidenteVerificado) -> PuntuacionTriage:
        """Calcula la puntuación de un único incidente con su desglose."""
        p = self._pesos
        componente_severidad = p.severidad * PESO_SEVERIDAD.get(incidente.severidad, 0.30)
        componente_urgencia = p.urgencia * PESO_URGENCIA.get(incidente.urgencia, 0.30)
        componente_personas = p.personas * factor_personas(incidente.personas_afectadas)
        multiplicador = factor_confianza(incidente.confianza)

        base = componente_severidad + componente_urgencia + componente_personas
        return PuntuacionTriage(
            incidente_id=incidente.id,
            puntuacion=base * multiplicador,
            componentes={
                "severidad": componente_severidad,
                "urgencia": componente_urgencia,
                "personas": componente_personas,
                "base": base,
                "multiplicador_confianza": multiplicador,
            },
        )

    def ordenar(self, incidentes: list[IncidenteVerificado]) -> list[PuntuacionTriage]:
        """Devuelve las puntuaciones del lote, de mayor a menor prioridad.

        La `posicion` que lleva cada puntuación empieza en 1 y es la que se le
        muestra al coordinador: "atienda el 1 antes que el 2" no admite dudas.
        """
        puntuaciones = [self.puntuar(inc) for inc in incidentes]
        ordenadas = sorted(
            puntuaciones,
            key=lambda p: (-round(p.puntuacion, DECIMALES_ORDEN), p.incidente_id),
        )
        return [
            PuntuacionTriage(
                incidente_id=p.incidente_id,
                puntuacion=p.puntuacion,
                componentes=p.componentes,
                posicion=indice,
            )
            for indice, p in enumerate(ordenadas, start=1)
        ]
