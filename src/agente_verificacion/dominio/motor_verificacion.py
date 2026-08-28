"""Motor de verificación: agrupa, fusiona y da confianza a reportes (puro, sin I/O).

El LLM nunca decide aquí. `fusionar` recibe un diccionario de similitudes
textuales ya calculado por el puerto de similitud (LLM real o `SimilitudNula`)
y lo usa como una señal más dentro de `VectorAcuerdo`; quien decide fusionar o
no es siempre este módulo, de forma determinista y reproducible — dos
ejecuciones con la misma entrada producen siempre la misma salida, algo que un
LLM no puede garantizar.

Algoritmo, en dos pasos:

1. **Candidatos** (`candidatos`): descarta pares de reportes que obviamente no
   pueden ser el mismo hecho (categoría distinta, demasiado lejos en espacio o
   en tiempo) antes de gastar una llamada al LLM comparando su texto. Es tanto
   una optimización de costo como una primera señal determinista.
2. **Fusión** (`fusionar`): clustering aglomerativo de enlace simple (union-find)
   sobre los pares candidatos cuyo `VectorAcuerdo.score()` supera el umbral. No
   se usa sklearn: con lotes de reportes de un incidente (decenas, no millones)
   un union-find de complejidad casi lineal es más que suficiente y no añade
   una dependencia pesada solo para agrupar puntos.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from agente_verificacion.dominio.value_objects import UMBRAL_FUSION_DEFECTO, VectorAcuerdo
from nucleo.esquemas import (
    Certeza,
    IncidenteVerificado,
    ReporteCrudo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import Punto, centroide, haversine
from nucleo.mensajes import ahora

# Radio de agrupación espacial. 500 m cubre el área de una cuadra/manzana
# urbana afectada por un mismo evento puntual (derrumbe, incendio, explosión);
# más grande empezaría a mezclar barrios distintos con el mismo problema.
RADIO_CLUSTER_KM_DEFECTO = 0.5

# Ventana de agrupación temporal. Los reportes de un mismo evento suelen llegar
# en un lapso de horas mientras la gente se entera y reporta; 6 h separa un
# mismo incidente de un segundo evento no relacionado que ocurra ese mismo día
# en el mismo sitio (p. ej. una réplica sísmica horas después).
VENTANA_TIEMPO_DEFECTO = timedelta(hours=6)

# Fracción del radio/ventana dentro de la cual la evidencia geométrica se
# considera abrumadora por sí sola (ver `MotorVerificacion._fuerza`). 0.5
# porque a la mitad del radio (250 m con el defecto) o de la ventana (3 h con
# el defecto) ya no queda ambigüedad razonable de que sea el mismo punto o el
# mismo momento; más cerca del límite completo empieza a acercarse a otro
# evento distinto que simplemente cae dentro del rango configurado.
ZONA_SEGURA_FRACCION = 0.5

# Vida media del decaimiento exponencial de confianza por antigüedad: a las
# `vida_media_horas`, un reporte vale la mitad de lo que valía al llegar. 12 h
# refleja que en un desastre la situación cambia rápido (una vía puede quedar
# despejada, un incendio puede apagarse) y un reporte de ayer ya no certifica
# el estado de ahora, aunque tampoco se descarta de golpe.
VIDA_MEDIA_HORAS_DEFECTO = 12.0

# Caducidad por urgencia CAP: cuanto más inmediata la urgencia declarada, más
# rápido deja de ser útil el incidente para asignar recursos si nadie lo
# refresca — un incidente "Immediate" sin actividad en 6 h probablemente ya se
# resolvió o escaló a otra cosa; uno "Future" puede seguir vigente días.
VIDA_UTIL_POR_URGENCIA: dict[Urgencia, timedelta] = {
    Urgencia.IMMEDIATE: timedelta(hours=6),
    Urgencia.EXPECTED: timedelta(hours=24),
    Urgencia.FUTURE: timedelta(days=3),
    Urgencia.PAST: timedelta(hours=1),
    Urgencia.UNKNOWN: timedelta(hours=12),
}

# Peso base de credibilidad por tipo de fuente. AUTORIDAD y SENSOR pesan más
# porque su error sistemático es bajo; CIUDADANO pesa menos no por desconfianza
# gratuita sino porque no hay forma de verificar su identidad ni su posición.
PESO_TIPO_FUENTE: dict[TipoFuente, float] = {
    TipoFuente.AUTORIDAD: 1.0,
    TipoFuente.SENSOR: 0.95,
    TipoFuente.ORGANIZACION: 0.85,
    TipoFuente.VOLUNTARIO: 0.7,
    TipoFuente.AFECTADO: 0.6,
    TipoFuente.CIUDADANO: 0.5,
}

# Peso de la certeza CAP declarada por el reporte mismo.
PESO_CERTEZA: dict[Certeza, float] = {
    Certeza.OBSERVED: 1.0,
    Certeza.LIKELY: 0.75,
    Certeza.POSSIBLE: 0.5,
    Certeza.UNLIKELY: 0.25,
    Certeza.UNKNOWN: 0.4,
}

# Orden de severidad usado para desempatar votaciones ponderadas: ante empate
# exacto de peso, gana la lectura más severa (más conservadora para rescate).
ORDEN_SEVERIDAD = [
    Severidad.UNKNOWN,
    Severidad.MINOR,
    Severidad.MODERATE,
    Severidad.SEVERE,
    Severidad.EXTREME,
]


@dataclass(frozen=True, slots=True)
class _Contradiccion:
    """Constancia de que el cluster no era unánime en severidad."""

    valores: dict[str, float]
    ganadora: str

    def a_dict(self) -> dict:
        return {"valores": self.valores, "ganadora": self.ganadora}


class MotorVerificacion:
    """Agrupa reportes en incidentes y calcula su confianza. Determinista."""

    def __init__(
        self,
        radio_cluster_km: float = RADIO_CLUSTER_KM_DEFECTO,
        ventana_tiempo: timedelta = VENTANA_TIEMPO_DEFECTO,
        umbral_fusion: float = UMBRAL_FUSION_DEFECTO,
        vida_media_horas: float = VIDA_MEDIA_HORAS_DEFECTO,
    ) -> None:
        self._radio_km = radio_cluster_km
        self._ventana = ventana_tiempo
        self._umbral = umbral_fusion
        self._vida_media_horas = vida_media_horas

    # ------------------------------------------------------------- candidatos
    def candidatos(self, reportes: list[ReporteCrudo]) -> list[tuple[str, str]]:
        """Pares (id_a, id_b) que vale la pena comparar por texto.

        Descarta pares que ya son deterministamente incompatibles, para no
        gastar una llamada al LLM en pares que jamás se fusionarían de todas
        formas por estar en categorías, lugares o momentos distintos.
        """
        pares: list[tuple[str, str]] = []
        n = len(reportes)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = reportes[i], reportes[j]
                if self._compatibles_determinista(a, b):
                    pares.append((a.id, b.id))
        return pares

    # --------------------------------------------------------------- fusión
    def fusionar(
        self,
        reportes: list[ReporteCrudo],
        similitudes: dict[tuple[str, str], float],
    ) -> list[IncidenteVerificado]:
        """Agrupa `reportes` en incidentes usando las `similitudes` ya calculadas.

        `similitudes` viene del puerto de similitud textual (LLM o nula), en
        cualquier orden de la clave (id_a, id_b) o (id_b, id_a). Un par ausente
        del diccionario se trata como similitud 0.0: si el LLM no respondió por
        ese par, el motor sigue decidiendo con las señales deterministas.
        """
        if not reportes:
            return []

        momento = ahora()
        padre: dict[str, str] = {r.id: r.id for r in reportes}

        def _find(x: str) -> str:
            raiz = x
            while padre[raiz] != raiz:
                raiz = padre[raiz]
            while padre[x] != raiz:
                padre[x], x = raiz, padre[x]
            return raiz

        def _union(x: str, y: str) -> None:
            rx, ry = _find(x), _find(y)
            if rx != ry:
                padre[rx] = ry

        n = len(reportes)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = reportes[i], reportes[j]
                if not self._compatibles_determinista(a, b):
                    continue
                texto_sim = similitudes.get((a.id, b.id))
                if texto_sim is None:
                    texto_sim = similitudes.get((b.id, a.id), 0.0)
                dt = abs((a.recibido_en - b.recibido_en).total_seconds())
                vector = VectorAcuerdo(
                    fuerza_ubicacion=self._fuerza_ubicacion(a, b),
                    coincide_categoria=True,  # ya exigido por _compatibles_determinista
                    fuerza_tiempo=self._fuerza(dt, self._ventana.total_seconds()),
                    similitud_texto=texto_sim,
                )
                if vector.score() >= self._umbral:
                    _union(a.id, b.id)

        grupos: dict[str, list[ReporteCrudo]] = defaultdict(list)
        for r in reportes:
            grupos[_find(r.id)].append(r)

        return [self._construir_incidente(grupo, momento) for grupo in grupos.values()]

    # ------------------------------------------------------------ compatibles
    def _compatibles_determinista(self, a: ReporteCrudo, b: ReporteCrudo) -> bool:
        if a.categoria != b.categoria:
            return False
        if a.ubicacion is not None and b.ubicacion is not None:
            if haversine(a.ubicacion.lat, a.ubicacion.lon, b.ubicacion.lat, b.ubicacion.lon) > (
                self._radio_km
            ):
                return False
        elif a.ubicacion is not None or b.ubicacion is not None:
            # Uno trae ubicación y el otro no: no hay forma de confirmar que
            # están cerca, así que no se arriesga la fusión.
            return False
        dt = abs((a.recibido_en - b.recibido_en).total_seconds())
        return dt <= self._ventana.total_seconds()

    def _fuerza_ubicacion(self, a: ReporteCrudo, b: ReporteCrudo) -> float:
        if a.ubicacion is None or b.ubicacion is None:
            # No hay forma de confirmar cercanía sin coordenadas de ambos: no
            # se le da crédito geométrico, aunque el par siga siendo candidato
            # por categoría y tiempo (el texto puede sostenerlo solo).
            return 0.0
        distancia = haversine(a.ubicacion.lat, a.ubicacion.lon, b.ubicacion.lat, b.ubicacion.lon)
        return self._fuerza(distancia, self._radio_km)

    def _fuerza(self, valor: float, limite: float) -> float:
        """Fuerza de una señal continua (distancia o brecha temporal) en [0,1].

        Dentro de `ZONA_SEGURA_FRACCION` del límite configurado (radio o
        ventana), la señal vale tanto como una coincidencia exacta: co-ubicación
        estrecha o reportes casi simultáneos ya certifican el mismo hecho por sí
        solos. Más allá de esa zona segura decae linealmente hasta 0 justo en el
        límite (donde `_compatibles_determinista` ya habría excluido el par de
        todas formas), dejando que sea el texto quien decida los casos
        fronterizos, que es donde la geometría sola es ambigua.
        """
        if limite <= 0:
            return 1.0 if valor <= 0 else 0.0
        frontera_segura = limite * ZONA_SEGURA_FRACCION
        if valor <= frontera_segura:
            return 1.0
        if valor >= limite:
            return 0.0
        return 1.0 - (valor - frontera_segura) / (limite - frontera_segura)

    # ------------------------------------------------------------ construcción
    def _construir_incidente(
        self, grupo: list[ReporteCrudo], momento: datetime
    ) -> IncidenteVerificado:
        pesos = {r.id: self._peso_fuente(r, momento) for r in grupo}

        ubicaciones = [r.ubicacion for r in grupo if r.ubicacion is not None]
        ubicacion = centroide(ubicaciones) if ubicaciones else Punto(lat=0.0, lon=0.0)

        categoria = self._voto_ponderado(grupo, pesos, lambda r: r.categoria)
        urgencia = self._voto_ponderado(grupo, pesos, lambda r: r.urgencia)
        certeza = self._voto_ponderado(grupo, pesos, lambda r: r.certeza)
        severidad, contradiccion = self._resolver_severidad(grupo, pesos)

        confianza = self._calcular_confianza(grupo, pesos)
        vence_en = momento + VIDA_UTIL_POR_URGENCIA.get(urgencia, timedelta(hours=12))

        representante = max(grupo, key=lambda r: pesos[r.id])

        personas = [r.personas_afectadas for r in grupo if r.personas_afectadas is not None]

        necesidades: list[str] = []
        for r in grupo:
            for necesidad in r.necesidades:
                if necesidad not in necesidades:
                    necesidades.append(necesidad)

        metadatos: dict = {
            "num_fuentes_distintas": len({r.fuente.id for r in grupo}),
            "certeza": str(certeza),
        }
        if contradiccion is not None:
            metadatos["contradiccion_severidad"] = contradiccion.a_dict()

        return IncidenteVerificado(
            categoria=categoria,
            severidad=severidad,
            urgencia=urgencia,
            ubicacion=ubicacion,
            confianza=confianza,
            reportes_origen=tuple(sorted(r.id for r in grupo)),
            resumen=representante.texto,
            personas_afectadas=max(personas) if personas else None,
            necesidades=tuple(necesidades),
            verificado_en=momento,
            vence_en=vence_en,
            metadatos=metadatos,
        )

    # -------------------------------------------------------------- confianza
    def _peso_fuente(self, reporte: ReporteCrudo, momento: datetime) -> float:
        reputacion = reporte.fuente.reputacion
        tipo = PESO_TIPO_FUENTE.get(reporte.fuente.tipo, 0.5)
        certeza = PESO_CERTEZA.get(reporte.certeza, 0.4)
        antiguedad = self._decaimiento(reporte, momento)
        return reputacion * tipo * certeza * antiguedad

    def _decaimiento(self, reporte: ReporteCrudo, momento: datetime) -> float:
        edad_horas = max(0.0, (momento - reporte.recibido_en).total_seconds() / 3600.0)
        return 0.5 ** (edad_horas / self._vida_media_horas)

    def _calcular_confianza(
        self, grupo: list[ReporteCrudo], pesos: dict[str, float]
    ) -> float:
        """Combina corroboraciones independientes por noisy-OR.

        Solo cuenta el reporte de mayor peso por cada `fuente.id`: la misma
        fuente reportando dos veces no debe sumar como si fueran dos fuentes
        independientes corroborando el hecho (eso sería fácil de manipular con
        solo reenviar el mismo mensaje). El noisy-OR (1 - producto de fallos)
        modela "basta con que una fuente confiable tenga razón" y crece hacia 1
        de forma natural a medida que se acumulan corroboraciones
        independientes, sin necesitar un tope arbitrario.
        """
        mejor_por_fuente: dict[str, float] = {}
        for r in grupo:
            peso = pesos[r.id]
            actual = mejor_por_fuente.get(r.fuente.id)
            if actual is None or peso > actual:
                mejor_por_fuente[r.fuente.id] = peso

        producto_fallo = 1.0
        for peso in mejor_por_fuente.values():
            producto_fallo *= 1.0 - min(max(peso, 0.0), 1.0)
        return round(1.0 - producto_fallo, 6)

    # -------------------------------------------------------------- votación
    def _voto_ponderado(self, grupo, pesos, extractor):
        acumulado: dict = defaultdict(float)
        for r in grupo:
            acumulado[extractor(r)] += pesos[r.id]
        return max(acumulado.items(), key=lambda kv: (kv[1], str(kv[0])))[0]

    def _resolver_severidad(
        self, grupo: list[ReporteCrudo], pesos: dict[str, float]
    ) -> tuple[Severidad, _Contradiccion | None]:
        acumulado: dict[Severidad, float] = defaultdict(float)
        for r in grupo:
            acumulado[r.severidad] += pesos[r.id]

        ganadora = max(
            acumulado.items(),
            key=lambda kv: (kv[1], ORDEN_SEVERIDAD.index(kv[0])),
        )[0]

        if len(acumulado) <= 1:
            return ganadora, None

        # Hay discrepancia entre reportes del mismo cluster: se deja
        # constancia de qué severidades se reportaron y con qué peso, para que
        # un humano pueda revisar por qué ganó la que ganó.
        contradiccion = _Contradiccion(
            valores={str(k): round(v, 6) for k, v in acumulado.items()},
            ganadora=str(ganadora),
        )
        return ganadora, contradiccion
