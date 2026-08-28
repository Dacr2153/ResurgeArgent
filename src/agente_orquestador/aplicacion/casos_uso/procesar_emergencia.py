"""Caso de uso: procesar una emergencia de punta a punta.

El flujo es siempre el mismo y siempre en este orden:

    IngestaPort.ingerir -> VerificacionPort.verificar -> GeoespacialPort -> triage
    -> PENDIENTE_APROBACION

Los tres primeros pasos son delegaciones y van dentro de una saga, porque son las
que pueden fallar contra otro proceso. El triage y las transiciones son locales,
deterministas y no fallan: no necesitan compensación.

Todo mensaje y todo evento lleva el mismo `correlacion_id`. Ese hilo es lo que
permite, semanas después, responder "por qué se envió esa ambulancia allí y no
allá" leyendo solo el log.

El LLM aparece una única vez, al final, para redactar el resumen que leerá el
coordinador. Ya no queda ninguna decisión por tomar cuando se le llama.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from agente_orquestador.aplicacion.puertos.salida import (
    PublicadorPort,
    RepositorioOperacionesPort,
    ResumidorPort,
)
from agente_orquestador.dominio.entidades import LIMITE_VISITAS_POR_ESTADO, Operacion
from agente_orquestador.dominio.estados import EstadoIncidente
from agente_orquestador.dominio.motor_triage import MotorTriage
from agente_orquestador.dominio.saga import TIMEOUT_PASO_S, PasoSaga, ResultadoSaga, Saga
from nucleo.esquemas import ConsultaGeo, IncidenteVerificado, ModoTransporte, ReporteCrudo
from nucleo.geo import Punto
from nucleo.mensajes import (
    Agente,
    EventoAuditoria,
    Mensaje,
    Performativa,
    TipoEvento,
    nuevo_id,
)
from nucleo.puertos import AuditoriaPort, GeoespacialPort, IngestaPort, VerificacionPort

#: Cuántas rutas se piden al Agente Geoespacial por lote. Pedir una ruta por cada
#: incidente satura al agente justo cuando más carga tiene; el coordinador solo va
#: a despachar los primeros de la cola, así que se calculan esas.
RUTAS_POR_LOTE = 5


class ProcesarEmergencia:
    """Orquesta el flujo completo delegando en los puertos de `nucleo`."""

    def __init__(
        self,
        ingesta: IngestaPort,
        verificacion: VerificacionPort,
        geoespacial: GeoespacialPort,
        motor: MotorTriage,
        resumidor: ResumidorPort,
        repositorio: RepositorioOperacionesPort,
        publicador: PublicadorPort,
        auditoria: AuditoriaPort,
        origen_despacho: Punto | None = None,
        timeout_ingesta_s: float = TIMEOUT_PASO_S,
        timeout_verificacion_s: float = TIMEOUT_PASO_S,
        timeout_geo_s: float = TIMEOUT_PASO_S,
        limite_visitas: int = LIMITE_VISITAS_POR_ESTADO,
        rutas_por_lote: int = RUTAS_POR_LOTE,
    ) -> None:
        self._ingesta = ingesta
        self._verificacion = verificacion
        self._geoespacial = geoespacial
        self._motor = motor
        self._resumidor = resumidor
        self._repositorio = repositorio
        self._publicador = publicador
        self._auditoria = auditoria
        self._origen_despacho = origen_despacho
        self._timeout_ingesta_s = timeout_ingesta_s
        self._timeout_verificacion_s = timeout_verificacion_s
        self._timeout_geo_s = timeout_geo_s
        self._limite_visitas = limite_visitas
        self._rutas_por_lote = rutas_por_lote

    async def procesar(self, entrada: dict) -> dict:
        """Ejecuta el flujo y devuelve el estado global de la operación."""
        correlacion_id = entrada.get("correlacion_id") or nuevo_id()
        carga = entrada.get("entrada") if isinstance(entrada.get("entrada"), dict) else entrada
        origen = self._punto_de(entrada.get("origen_despacho")) or self._origen_despacho

        contexto: dict[str, Any] = {"reportes": [], "incidentes": [], "geo": {}}

        resultado_saga = await self._delegar(correlacion_id, carga, origen, contexto)

        incidentes: list[IncidenteVerificado] = contexto["incidentes"]
        operaciones = [
            Operacion(
                incidente_id=inc.id,
                correlacion_id=correlacion_id,
                limite_visitas=self._limite_visitas,
            )
            for inc in incidentes
        ]

        if incidentes:
            await self._avanzar_hasta_aprobacion(operaciones, incidentes, contexto, resultado_saga)

        for operacion in operaciones:
            await self._repositorio.guardar(operacion)

        salida = self._consolidar(correlacion_id, operaciones, contexto, resultado_saga)
        salida["resumen_situacion"] = await self._resumidor.resumir_situacion(salida)

        await self._publicador.publicar(salida)
        return salida

    # ------------------------------------------------------------- delegaciones
    async def _delegar(
        self,
        correlacion_id: str,
        carga: dict,
        origen: Punto | None,
        contexto: dict[str, Any],
    ) -> ResultadoSaga:
        """Arma y corre la saga de delegación a los agentes 2, 3 y 5."""

        async def ingerir() -> list[ReporteCrudo]:
            await self._mensaje(correlacion_id, Agente.INGESTA, Performativa.REQUEST, {})
            reportes = await self._ingesta.ingerir({**carga, "correlacion_id": correlacion_id})
            contexto["reportes"] = list(reportes)
            return list(reportes)

        async def descartar_reportes() -> None:
            # Compensar la ingesta es soltar los reportes consumidos: si nadie los
            # verificó, no pueden quedar marcados como procesados o se perderían
            # en el siguiente lote.
            contexto["reportes_descartados"] = [r.id for r in contexto["reportes"]]
            contexto["reportes"] = []

        async def verificar() -> list[IncidenteVerificado]:
            await self._mensaje(correlacion_id, Agente.VERIFICACION, Performativa.REQUEST, {})
            incidentes = await self._verificacion.verificar(
                contexto["reportes"], correlacion_id=correlacion_id
            )
            contexto["incidentes"] = list(incidentes)
            return list(incidentes)

        async def descartar_incidentes() -> None:
            contexto["incidentes"] = []

        async def resolver_geo() -> dict:
            await self._mensaje(correlacion_id, Agente.GEOESPACIAL, Performativa.CFP, {})
            geo = await self._contexto_geo(contexto["incidentes"], origen, correlacion_id)
            contexto["geo"] = geo
            return geo

        pasos = [
            PasoSaga(
                nombre="ingesta",
                agente=Agente.INGESTA,
                accion=ingerir,
                accion_compensatoria=descartar_reportes,
                obligatorio=True,
                timeout_s=self._timeout_ingesta_s,
            ),
            PasoSaga(
                nombre="verificacion",
                agente=Agente.VERIFICACION,
                accion=verificar,
                accion_compensatoria=descartar_incidentes,
                obligatorio=True,
                timeout_s=self._timeout_verificacion_s,
            ),
            # El único paso opcional: sin rutas todavía hay incidentes con
            # coordenadas propias, y una lista priorizada sin rutas es mejor que
            # ninguna lista. Ver `saga.py` para el criterio.
            PasoSaga(
                nombre="geoespacial",
                agente=Agente.GEOESPACIAL,
                accion=resolver_geo,
                accion_compensatoria=None,
                obligatorio=False,
                timeout_s=self._timeout_geo_s,
            ),
        ]

        return await Saga(correlacion_id, pasos, self._auditoria).ejecutar()

    async def _contexto_geo(
        self,
        incidentes: list[IncidenteVerificado],
        origen: Punto | None,
        correlacion_id: str,
    ) -> dict[str, Any]:
        """Pide zonas afectadas y las rutas de los incidentes más relevantes."""
        zonas = await self._geoespacial.zonas_afectadas(incidentes, correlacion_id=correlacion_id)
        rutas: list[dict[str, Any]] = []
        if origen is not None:
            for incidente in incidentes[: self._rutas_por_lote]:
                consulta = ConsultaGeo(
                    origen=origen, destino=incidente.ubicacion, modo=ModoTransporte.AUTO
                )
                respuesta = await self._geoespacial.resolver_ruta(
                    consulta, correlacion_id=correlacion_id
                )
                rutas.append({"incidente_id": incidente.id, **respuesta.a_dict()})
        return {"zonas_afectadas": zonas, "rutas": rutas}

    # --------------------------------------------------------------- estados
    async def _avanzar_hasta_aprobacion(
        self,
        operaciones: list[Operacion],
        incidentes: list[IncidenteVerificado],
        contexto: dict[str, Any],
        resultado_saga: ResultadoSaga,
    ) -> None:
        """Lleva cada incidente de RECIBIDO a PENDIENTE_APROBACION.

        El último salto es siempre a PENDIENTE_APROBACION y nunca más allá: el
        Orquestador prepara la decisión, no la toma.
        """
        geo_ok = "geoespacial" not in resultado_saga.fallidos
        rutas_por_incidente = {
            ruta["incidente_id"]: ruta for ruta in contexto["geo"].get("rutas", [])
        }
        por_id = {inc.id: inc for inc in incidentes}

        for operacion in operaciones:
            await self._transicionar(
                operacion,
                EstadoIncidente.VERIFICADO,
                motivo=(
                    f"corroborado por {por_id[operacion.incidente_id].corroboraciones} "
                    f"reporte(s), confianza {por_id[operacion.incidente_id].confianza:.2f}"
                ),
            )
            ruta = rutas_por_incidente.get(operacion.incidente_id)
            motivo_geo = (
                f"ruta resuelta por el agente geoespacial ({ruta['distancia_km']} km)"
                if ruta
                else (
                    "ubicación propia del incidente; sin rutas del agente geoespacial"
                    if not geo_ok
                    else "ubicación propia del incidente; ruta no solicitada en este lote"
                )
            )
            operacion.datos["ruta"] = ruta
            operacion.datos["geo_degradado"] = not geo_ok
            await self._transicionar(operacion, EstadoIncidente.LOCALIZADO, motivo=motivo_geo)

        puntuaciones = self._motor.ordenar(incidentes)
        por_incidente = {p.incidente_id: p for p in puntuaciones}
        # Se recorre en orden de triage, no en orden de llegada: el historial de
        # auditoría queda ordenado igual que la cola que verá el coordinador.
        operaciones.sort(key=lambda o: por_incidente[o.incidente_id].posicion)

        for operacion in operaciones:
            puntuacion = por_incidente[operacion.incidente_id]
            operacion.puntuacion = puntuacion
            await self._transicionar(
                operacion,
                EstadoIncidente.PRIORIZADO,
                motivo=(
                    f"posición {puntuacion.posicion} del lote, "
                    f"puntuación {puntuacion.puntuacion:.4f}"
                ),
            )
            await self._transicionar(
                operacion,
                EstadoIncidente.PENDIENTE_APROBACION,
                motivo="a la espera de la firma del coordinador humano",
            )

    async def _transicionar(
        self, operacion: Operacion, destino: EstadoIncidente, motivo: str
    ) -> None:
        registro = operacion.transicionar(destino, motivo=motivo)
        await self._auditar(
            operacion.correlacion_id,
            TipoEvento.TRANSICION_ESTADO,
            {"incidente_id": operacion.incidente_id, **registro.a_dict()},
        )

    # ---------------------------------------------------------- consolidación
    def _consolidar(
        self,
        correlacion_id: str,
        operaciones: list[Operacion],
        contexto: dict[str, Any],
        resultado_saga: ResultadoSaga,
    ) -> dict[str, Any]:
        return {
            "correlacion_id": correlacion_id,
            "estado_operacion": self._estado_global(operaciones, resultado_saga),
            "degradada": resultado_saga.parcial,
            "saga": resultado_saga.a_dict(),
            "reportes_ingeridos": len(contexto["reportes"]),
            "reportes_descartados": self._descartes(correlacion_id),
            "incidentes": [
                {
                    **operacion.a_dict(),
                    "requiere_firma": operacion.estado is EstadoIncidente.PENDIENTE_APROBACION,
                }
                for operacion in operaciones
            ],
            "zonas_afectadas": contexto["geo"].get("zonas_afectadas", {}),
            "rutas": contexto["geo"].get("rutas", []),
        }

    def _descartes(self, correlacion_id: str) -> dict[str, Any]:
        """Descartes de la ingesta, por motivo, leídos de la traza compartida.

        Que un lote quede en cero reportes no significa lo mismo si no llegó nada
        que si se descartó todo: en una emergencia esa diferencia decide si se
        busca la avería en la red o en el formato de quien envía. El dato ya
        estaba en los eventos de auditoría; aquí solo se hace visible.

        Si el adaptador de auditoría no sabe releerse (por ejemplo uno que solo
        escribe a un sistema externo), se devuelve vacío en vez de fallar: la
        observabilidad no puede tumbar la operación.
        """
        leer = getattr(self._auditoria, "por_correlacion", None)
        if leer is None:
            return {"total": 0, "por_motivo": {}, "detalle_disponible": False}

        motivos: Counter[str] = Counter()
        for evento in leer(correlacion_id):
            if evento.tipo is not TipoEvento.REPORTE_DESCARTADO:
                continue
            motivos[str(evento.detalle.get("motivo", "desconocido"))] += 1
        return {
            "total": sum(motivos.values()),
            "por_motivo": dict(motivos),
            "detalle_disponible": True,
        }

    @staticmethod
    def _estado_global(operaciones: list[Operacion], resultado_saga: ResultadoSaga) -> str:
        """Resumen de una palabra del lote, para el tablero del coordinador."""
        if not operaciones:
            return "sin_incidentes" if resultado_saga.exitosa else "abortada"
        if all(o.estado is EstadoIncidente.PENDIENTE_APROBACION for o in operaciones):
            return "pendiente_aprobacion"
        if any(o.suspendida for o in operaciones):
            return "parcial_suspendida"
        return "en_curso"

    @staticmethod
    def _punto_de(valor: Any) -> Punto | None:
        if isinstance(valor, Punto):
            return valor
        if isinstance(valor, dict) and "lat" in valor and "lon" in valor:
            return Punto(lat=float(valor["lat"]), lon=float(valor["lon"]))
        return None

    # ------------------------------------------------------------------ traza
    async def _mensaje(
        self,
        correlacion_id: str,
        receptor: Agente,
        performativa: Performativa,
        contenido: dict[str, Any],
    ) -> Mensaje:
        """Construye y audita el sobre FIPA-ACL de una delegación.

        El mensaje se materializa aunque el transporte sea una llamada directa a
        un puerto: es lo que hace que el log muestre un intercambio entre agentes
        y no una pila de llamadas a funciones.
        """
        mensaje = Mensaje(
            emisor=Agente.ORQUESTADOR,
            receptor=receptor,
            performativa=performativa,
            contenido=contenido,
            correlacion_id=correlacion_id,
        )
        await self._auditar(correlacion_id, TipoEvento.TAREA_DELEGADA, mensaje.a_dict())
        return mensaje

    async def _auditar(
        self, correlacion_id: str, tipo: TipoEvento, detalle: dict[str, Any]
    ) -> None:
        await self._auditoria.registrar(
            EventoAuditoria(
                tipo=tipo,
                agente=Agente.ORQUESTADOR,
                correlacion_id=correlacion_id,
                detalle=detalle,
            )
        )
