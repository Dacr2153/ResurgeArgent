"""Motor de ingesta: normalización, idempotencia, validación y back-pressure.

Puro y determinista, sin I/O. Recibe reportes ya estructurados (el LLM, o el
extractor nulo, ya sacaron categoría/urgencia/ubicación del texto libre antes
de llegar aquí) y decide qué entra al sistema. La regla que no se rompe: el
LLM estructura texto, pero es este motor el que decide qué se acepta.

El estado entre llamadas (hashes ya vistos, timestamps dentro de la ventana de
back-pressure) no vive en el motor: se recibe como parámetro y se devuelve
actualizado en el ``ResultadoIngesta``. Así ``procesar`` sigue siendo una
función pura de sus argumentos, fácil de testear sin mocks ni reloj real.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agente_ingesta.dominio.entidades import Descarte, ResultadoIngesta
from agente_ingesta.dominio.value_objects import ConfigVentana, MotivoDescarte
from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    Fuente,
    ReporteCrudo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import GeometriaInvalidaError, Punto

TIPOS_FUENTE_VALIDOS = frozenset(t.value for t in TipoFuente)


class MotorIngesta:
    """El corazón determinista del Agente 2."""

    def __init__(self, config_ventana: ConfigVentana) -> None:
        self._config = config_ventana

    def procesar(
        self,
        items: list[dict[str, Any]],
        vistos: frozenset[str],
        en_ventana: tuple[datetime, ...],
        momento: datetime,
    ) -> ResultadoIngesta:
        """Procesa un lote. No lanza por lote vacío ni por items malformados:
        un lote vacío simplemente no produce nada, y un item inválido se
        descarta sin tumbar el resto — el back-pressure del SRE Book aplica a
        la ingesta completa, no solo a la sobrecarga por volumen."""
        descartados: list[Descarte] = []
        candidatos: list[tuple[int, ReporteCrudo]] = []

        for indice, item in enumerate(items):
            resultado = self._normalizar_y_validar(item)
            if isinstance(resultado, Descarte):
                descartados.append(Descarte(indice, resultado.motivo, resultado.detalle))
                continue
            candidatos.append((indice, resultado))

        # Idempotencia: se descartan duplicados exactos contra lo ya visto y
        # también duplicados dentro del propio lote (mismo reenvío llegando
        # dos veces en la misma ráfaga).
        vistos_actualizados = set(vistos)
        sin_duplicados: list[tuple[int, ReporteCrudo]] = []
        for indice, reporte in candidatos:
            huella = reporte.hash_idempotencia
            if huella in vistos_actualizados:
                descartados.append(
                    Descarte(indice, MotivoDescarte.REENVIO_DUPLICADO, f"hash={huella}")
                )
                continue
            vistos_actualizados.add(huella)
            sin_duplicados.append((indice, reporte))

        # Back-pressure: cuántos caben en lo que queda de la ventana deslizante.
        vigentes = tuple(
            t for t in en_ventana if (momento - t).total_seconds() <= self._config.segundos
        )
        capacidad_restante = max(0, self._config.limite - len(vigentes))

        if len(sin_duplicados) <= capacidad_restante:
            aceptados_finales = sin_duplicados
        else:
            # Sobrevive primero lo de Urgencia.IMMEDIATE y fuente AUTORIDAD.
            # Empates se resuelven por orden de llegada (FIFO) para no
            # favorecer arbitrariamente entradas idénticas en prioridad.
            ordenados = sorted(sin_duplicados, key=lambda par: self._prioridad(par[1], par[0]))
            aceptados_finales = ordenados[:capacidad_restante]
            rechazados_por_saturacion = ordenados[capacidad_restante:]
            for indice, reporte in rechazados_por_saturacion:
                descartados.append(
                    Descarte(
                        indice,
                        MotivoDescarte.SATURACION_VENTANA,
                        f"ventana llena: limite={self._config.limite}",
                    )
                )
                # El reporte no entra: se retira también de "vistos" para no
                # bloquear un reintento legítimo del mismo mensaje más tarde.
                vistos_actualizados.discard(reporte.hash_idempotencia)

        aceptados_finales.sort(key=lambda par: par[0])
        aceptados = tuple(reporte for _, reporte in aceptados_finales)
        descartados.sort(key=lambda d: d.indice)

        nueva_ventana = vigentes + (momento,) * len(aceptados)

        return ResultadoIngesta(
            aceptados=aceptados,
            descartados=tuple(descartados),
            vistos=frozenset(vistos_actualizados),
            en_ventana=nueva_ventana,
        )

    # ------------------------------------------------------------ prioridad
    @staticmethod
    def _prioridad(reporte: ReporteCrudo, indice: int) -> tuple[int, int, int]:
        """Menor tupla = sobrevive primero. Ver el capítulo "Handling Overload"
        del SRE Book: bajo saturación se degrada priorizando lo crítico, no al
        azar."""
        es_inmediato = 0 if reporte.urgencia == Urgencia.IMMEDIATE else 1
        es_autoridad = 0 if reporte.fuente.tipo == TipoFuente.AUTORIDAD else 1
        return (es_inmediato, es_autoridad, indice)

    # -------------------------------------------------------- normalización
    def _normalizar_y_validar(self, item: Any) -> ReporteCrudo | Descarte:
        # El índice real se completa en el llamador (enumerate del lote); aquí
        # solo se necesita distinguir "descartado" de "aceptado" y llevar el
        # motivo, así que se usa -1 como placeholder.
        if not isinstance(item, dict):
            return Descarte(-1, MotivoDescarte.FORMATO_INVALIDO, "el item no es un objeto")

        fuente = self._parsear_fuente(item.get("fuente"))
        if fuente is None:
            return Descarte(
                -1, MotivoDescarte.FUENTE_NO_IDENTIFICADA, "fuente ausente o sin id/tipo válidos"
            )

        texto = item.get("texto", "")
        if not isinstance(texto, str) or not texto.strip():
            return Descarte(-1, MotivoDescarte.TEXTO_VACIO, "texto ausente o vacío")

        canal = item.get("canal")
        try:
            canal_normalizado = self._parsear_canal(canal)
        except ValueError as exc:
            return Descarte(-1, MotivoDescarte.FORMATO_INVALIDO, str(exc))

        try:
            ubicacion = self._parsear_ubicacion(item.get("ubicacion"))
        except (GeometriaInvalidaError, KeyError, TypeError, ValueError) as exc:
            return Descarte(-1, MotivoDescarte.UBICACION_INVALIDA, str(exc))

        try:
            ocurrido_en = self._parsear_fecha(item.get("ocurrido_en"))
        except ValueError as exc:
            return Descarte(-1, MotivoDescarte.FORMATO_INVALIDO, str(exc))

        try:
            categoria = self._parsear_enum(Categoria, item.get("categoria"), Categoria.OTHER)
            urgencia = self._parsear_enum(Urgencia, item.get("urgencia"), Urgencia.UNKNOWN)
            severidad = self._parsear_enum(Severidad, item.get("severidad"), Severidad.UNKNOWN)
            certeza = self._parsear_enum(Certeza, item.get("certeza"), Certeza.UNKNOWN)
        except ValueError as exc:
            return Descarte(-1, MotivoDescarte.FORMATO_INVALIDO, str(exc))

        try:
            return ReporteCrudo(
                texto=texto.strip(),
                fuente=fuente,
                canal=canal_normalizado,
                ubicacion=ubicacion,
                categoria=categoria,
                urgencia=urgencia,
                severidad=severidad,
                certeza=certeza,
                personas_afectadas=item.get("personas_afectadas"),
                necesidades=tuple(item.get("necesidades", ()) or ()),
                ocurrido_en=ocurrido_en,
                metadatos=item.get("metadatos", {}) or {},
            )
        except ValueError as exc:
            return Descarte(-1, MotivoDescarte.FORMATO_INVALIDO, str(exc))

    @staticmethod
    def _parsear_fuente(bruto: Any) -> Fuente | None:
        if not isinstance(bruto, dict):
            return None
        id_fuente = str(bruto.get("id", "")).strip()
        tipo = bruto.get("tipo")
        if not id_fuente or tipo not in TIPOS_FUENTE_VALIDOS:
            return None
        try:
            return Fuente(
                id=id_fuente,
                tipo=TipoFuente(tipo),
                nombre=bruto.get("nombre", ""),
                reputacion=float(bruto.get("reputacion", 0.5)),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parsear_enum(tipo_enum: type, bruto: Any, defecto: Any) -> Any:
        """Convierte a la enum CAP 1.2 correspondiente. Un valor ausente cae al
        default; un valor presente pero inválido es un error de formato, no un
        default silencioso — así no se esconde un dato corrupto como
        "desconocido" legítimo."""
        if bruto is None:
            return defecto
        try:
            return tipo_enum(bruto)
        except ValueError as exc:
            raise ValueError(f"{tipo_enum.__name__} inválido: {bruto!r}") from exc

    @staticmethod
    def _parsear_canal(bruto: Any) -> Canal:
        try:
            return Canal(bruto)
        except ValueError as exc:
            raise ValueError(f"canal desconocido: {bruto!r}") from exc

    @staticmethod
    def _parsear_ubicacion(bruto: Any) -> Punto | None:
        """Acepta las dos formas que llegan de verdad a la frontera del sistema.

        La canónica es GeoJSON RFC 7946 —la que emite ``ReporteCrudo.a_dict()`` y
        la que habla el resto de agentes—, así que el sistema tiene que poder
        releer lo que él mismo produce. La forma corta ``{lat, lon}`` se admite
        porque es la que escribe una persona a mano y la que mandan varios
        formularios y pasarelas SMS, y rechazarla solo obligaría a cada emisor a
        traducir antes de hablar.
        """
        if bruto is None:
            return None
        if not isinstance(bruto, dict):
            raise TypeError("ubicacion debe ser una geometría GeoJSON o un objeto {lat, lon}")
        if "type" in bruto or "coordinates" in bruto:
            return Punto.desde_geojson(bruto)
        if "lat" in bruto and "lon" in bruto:
            return Punto(lat=float(bruto["lat"]), lon=float(bruto["lon"]))
        raise ValueError(f"ubicacion sin coordenadas reconocibles: {sorted(bruto)}")

    @staticmethod
    def _parsear_fecha(bruto: Any) -> datetime | None:
        if bruto is None:
            return None
        if isinstance(bruto, datetime):
            return bruto
        if isinstance(bruto, str):
            try:
                return datetime.fromisoformat(bruto)
            except ValueError as exc:
                raise ValueError(f"ocurrido_en no es fecha ISO válida: {bruto!r}") from exc
        raise ValueError(f"ocurrido_en tiene tipo inesperado: {type(bruto)!r}")


__all__ = ["MotorIngesta", "TIPOS_FUENTE_VALIDOS"]
