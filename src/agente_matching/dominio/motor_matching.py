"""Motor de matching: algoritmo de flujo de costo mínimo (puro, sin I/O).

Modelo de grafo (dos etapas):

1) Transporte óptimo recurso→necesidad (min_cost_flow) con un cuello de botella
   global de flota y un nodo SLACK para la demanda no cubierta:

       S ─[cap=flota_total]─► F ─[cap=X_l]─► Recurso(l) ─[cost=dist+prioridad]─►
       Necesidad(n) ─[cap=req_n]─► T
       S ─[cap=Σreq]─► SLACK ─[cost=w3]─► Necesidad(n)

2) Atribución de empresas (greedy): reparte el transporte entre las empresas,
   prefiriendo (w4) las que ya están en tránsito y respetando la flota de cada una
   y su zona de cobertura.

Las causas de "no cubierto" se determinan comparando el flujo ideal (sin límite de
flota) contra el flujo real:
  - sin_recurso:    demanda no cubierta incluso con flota infinita.
  - sin_capacidad:  demanda cubierta en el ideal pero no por falta de flota.
  - zona_fuera_cobertura: transporte que no pudo atribuirse a ninguna empresa.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import networkx as nx

from agente_matching.dominio.entidades import (
    Asignacion,
    Empresa,
    Necesidad,
    NoCubierto,
    Recurso,
    ResultadoMatching,
    ResumenMatching,
)
from agente_matching.dominio.excepciones import (
    CapacidadInsuficienteError,
    ErrorDominio,
    SinDemandaError,
)

SIN_RECURSO = "sin_recurso"
SIN_CAPACIDAD = "sin_capacidad"
ZONA_FUERA_COBERTURA = "zona_fuera_cobertura"


@dataclass(frozen=True)
class _Transporte:
    recurso_id: str
    necesidad_id: str
    cantidad: float
    distancia_km: float
    costo_unitario: float


class MotorMatching:
    def __init__(
        self, pesos: dict[str, float], factor_escala: int = 100, capacidad_uniforme: float = 10.0
    ):
        self._pesos = pesos
        self._factor = factor_escala
        self._capacidad_uniforme = capacidad_uniforme

    # ------------------------------------------------------------------ público
    def ejecutar(
        self,
        necesidades: list[Necesidad],
        recursos: list[Recurso],
        empresas: list[Empresa],
        asignaciones_fijas: list[dict] | None = None,
    ) -> ResultadoMatching:
        if not necesidades:
            raise SinDemandaError("No hay necesidades para matchear")

        fijas = self._validar_fijas(asignaciones_fijas or [], necesidades, recursos, empresas)

        reservas = self._reservas(fijas)
        self._capacidad_suficiente(reservas, recursos, empresas)

        flota_total = sum(
            e.flota(self._capacidad_uniforme) - reservas["empresa"][e.id] for e in empresas
        )

        # Flujo ideal: sin límite de flota, para distinguir sin_recurso de sin_capacidad.
        transporte_ideal, _ = self._resolver(necesidades, recursos, reservas, flota_total=None)
        transporte_real, slack_real = self._resolver(
            necesidades, recursos, reservas, flota_total=flota_total
        )

        slack_ideal = self._slack_por_necesidad(necesidades, transporte_ideal)

        # Atribución de empresas sobre el transporte real.
        asignaciones, no_atribuible = self._atribuir(
            transporte_real, slack_real, necesidades, empresas, reservas
        )

        # Construir asignaciones de las fijas + las atribuidas.
        fijas_entidad = self._fijas_a_asignaciones(fijas, necesidades, recursos)

        no_cubierto = self._construir_no_cubierto(
            necesidades, slack_real, slack_ideal, no_atribuible
        )

        resumen = self._resumen(
            necesidades,
            empresas,
            fijas_entidad,
            asignaciones,
            no_cubierto,
        )

        return ResultadoMatching(
            asignaciones=fijas_entidad + asignaciones,
            no_cubierto=no_cubierto,
            resumen=resumen,
        )

    # ------------------------------------------------------------------ gráfo
    def _resolver(
        self,
        necesidades: list[Necesidad],
        recursos: list[Recurso],
        reservas: dict,
        flota_total: float | None,
    ) -> tuple[list[_Transporte], dict[str, float]]:
        """Resuelve el transporte óptimo. Devuelve (transporte, slack_por_necesidad)."""
        f = self._factor
        g = nx.DiGraph()

        s, t, flota_nodo, slack_nodo = "S", "T", "F", "SLACK"

        req_total = sum(self._req(n, reservas) for n in necesidades)
        req_total_i = self._a_entero(req_total)

        g.add_node(s, demand=-req_total_i)
        g.add_node(t, demand=req_total_i)
        g.add_node(flota_nodo, demand=0)
        g.add_node(slack_nodo, demand=0)

        flota_i = req_total_i if flota_total is None else self._a_entero(flota_total)
        g.add_edge(s, flota_nodo, capacity=flota_i, weight=0)
        g.add_edge(s, slack_nodo, capacity=req_total_i, weight=0)

        for n in necesidades:
            g.add_node(f"N:{n.id}", demand=0)

        for r in recursos:
            rn = f"R:{r.id}"
            g.add_node(rn, demand=0)
            cap_r = self._a_entero(self._stock(r, reservas))
            g.add_edge(flota_nodo, rn, capacity=cap_r, weight=0)
            for n in necesidades:
                if n.tipo == r.tipo:
                    nn = f"N:{n.id}"
                    cap = min(cap_r, self._a_entero(self._req(n, reservas)))
                    g.add_edge(rn, nn, capacity=cap, weight=self._costo(r, n))

        for n in necesidades:
            nn = f"N:{n.id}"
            cap_n = self._a_entero(self._req(n, reservas))
            g.add_edge(nn, t, capacity=cap_n, weight=0)
            g.add_edge(slack_nodo, nn, capacity=cap_n, weight=self._costo_slack())

        flujo = nx.min_cost_flow(g)

        transporte: list[_Transporte] = []
        slack: dict[str, float] = defaultdict(float)

        rec_por_id = {r.id: r for r in recursos}
        nec_por_id = {n.id: n for n in necesidades}

        for r in recursos:
            for n in necesidades:
                cantidad_i = flujo.get(f"R:{r.id}", {}).get(f"N:{n.id}", 0)
                if cantidad_i <= 0:
                    continue
                cantidad = cantidad_i / f
                dist = rec_por_id[r.id].ubicacion.distancia_a(nec_por_id[n.id].ubicacion)
                costo = self._costo_unitario(r, n)
                transporte.append(
                    _Transporte(
                        recurso_id=r.id,
                        necesidad_id=n.id,
                        cantidad=cantidad,
                        distancia_km=dist,
                        costo_unitario=costo,
                    )
                )

        for n in necesidades:
            slack[n.id] = flujo.get(slack_nodo, {}).get(f"N:{n.id}", 0) / f

        return transporte, dict(slack)

    # ------------------------------------------------------------------ costos
    def _costo_unitario(self, r: Recurso, n: Necesidad) -> float:
        dist = r.ubicacion.distancia_a(n.ubicacion)
        return self._pesos.get("w1", 0.0) * dist + self._pesos.get("w2", 0.0) / n.prioridad.valor

    def _costo(self, r: Recurso, n: Necesidad) -> int:
        return round(self._costo_unitario(r, n) * self._factor)

    def _costo_slack(self) -> int:
        return round(self._pesos.get("w3", 0.0) * self._factor)

    # ----------------------------------------------------------- atribución
    def _atribuir(
        self,
        transporte: list[_Transporte],
        slack_real: dict[str, float],
        necesidades: list[Necesidad],
        empresas: list[Empresa],
        reservas: dict,
    ) -> tuple[list[Asignacion], dict[str, float]]:
        nec_por_id = {n.id: n for n in necesidades}

        ordenadas = sorted(
            empresas,
            key=lambda e: (-e.fraccion_transito(), e.id),
        )

        restante = {
            e.id: e.flota(self._capacidad_uniforme) - reservas["empresa"][e.id] for e in empresas
        }

        asignaciones: list[Asignacion] = []
        no_atribuible: dict[str, float] = defaultdict(float)

        for tr in transporte:
            pendiente = tr.cantidad
            necesidad = nec_por_id[tr.necesidad_id]
            for e in ordenadas:
                if pendiente <= 1e-9:
                    break
                if not e.cubre_zona(necesidad.zona_id):
                    continue
                disponible = restante[e.id]
                if disponible <= 1e-9:
                    continue
                tomado = min(pendiente, disponible)
                restante[e.id] -= tomado
                pendiente -= tomado
                asignaciones.append(
                    Asignacion(
                        empresa_id=e.id,
                        recurso_id=tr.recurso_id,
                        necesidad_id=tr.necesidad_id,
                        cantidad=tomado,
                        distancia_km=tr.distancia_km,
                        costo_unitario=tr.costo_unitario,
                    )
                )
            if pendiente > 1e-9:
                no_atribuible[tr.necesidad_id] += pendiente

        # Redondear valores casi-cero para evitar ruido de punto flotante.
        asignaciones = [a for a in asignaciones if a.cantidad > 1e-9]
        return asignaciones, dict(no_atribuible)

    # ----------------------------------------------------------- no cubierto
    def _slack_por_necesidad(self, necesidades, transporte) -> dict[str, float]:
        slack = {n.id: n.cantidad_requerida for n in necesidades}
        for tr in transporte:
            slack[tr.necesidad_id] -= tr.cantidad
        return slack

    def _construir_no_cubierto(self, necesidades, slack_real, slack_ideal, no_atribuible):
        resultado: list[NoCubierto] = []

        def _agregar(acumulado, necesidad_id, cantidad, causa):
            if cantidad > 1e-9:
                acumulado.setdefault((necesidad_id, causa), 0.0)
                acumulado[(necesidad_id, causa)] += cantidad

        acum: dict[tuple[str, str], float] = {}
        for n in necesidades:
            real = slack_real.get(n.id, 0.0)
            ideal = slack_ideal.get(n.id, 0.0)
            _agregar(acum, n.id, min(real, ideal), SIN_RECURSO)
            _agregar(acum, n.id, max(0.0, real - ideal), SIN_CAPACIDAD)

        for necesidad_id, cantidad in no_atribuible.items():
            # El transporte no atribuible se convierte en demanda no cubierta.
            # Se descuenta de la causa sin_capacidad si ya se reportó.
            _agregar(acum, necesidad_id, cantidad, ZONA_FUERA_COBERTURA)

        for (necesidad_id, causa), cantidad in acum.items():
            if cantidad > 1e-9:
                resultado.append(
                    NoCubierto(necesidad_id=necesidad_id, cantidad=cantidad, causa=causa)
                )

        return sorted(resultado, key=lambda x: (x.necesidad_id, x.causa))

    # ----------------------------------------------------------- resumen
    def _resumen(
        self,
        necesidades,
        empresas,
        fijas,
        asignaciones,
        no_cubierto,
    ):
        demanda_total = sum(n.cantidad_requerida for n in necesidades)

        sin_cubrir = sum(nc.cantidad for nc in no_cubierto)
        cubierta = demanda_total - sin_cubrir

        costo_total = 0.0
        for a in list(fijas) + list(asignaciones):
            costo_total += a.cantidad * a.costo_unitario

        por_empresa: dict[str, dict] = {}
        for e in empresas:
            por_empresa[e.id] = {
                "flota_total": e.flota(self._capacidad_uniforme),
                "asignado": 0.0,
            }

        def _acumular(lista_asis):
            for a in lista_asis:
                if a.empresa_id in por_empresa:
                    por_empresa[a.empresa_id]["asignado"] += a.cantidad

        _acumular(fijas)
        _acumular(asignaciones)

        for e in empresas:
            por_empresa[e.id]["flota_disponible"] = (
                por_empresa[e.id]["flota_total"] - por_empresa[e.id]["asignado"]
            )

        return ResumenMatching(
            demanda_total=round(demanda_total, 6),
            demanda_cubierta=round(cubierta, 6),
            demanda_sin_cubrir=round(sin_cubrir, 6),
            costo_total=round(costo_total, 6),
            por_empresa={
                k: {kk: round(vv, 6) for kk, vv in v.items()} for k, v in por_empresa.items()
            },
        )

    # ----------------------------------------------------------- helpers
    def _a_entero(self, valor: float) -> int:
        return round(valor * self._factor)

    def _req(self, n: Necesidad, reservas: dict) -> float:
        return n.cantidad_requerida - reservas["necesidad"][n.id]

    def _stock(self, r: Recurso, reservas: dict) -> float:
        return r.cantidad_disponible - reservas["recurso"][r.id]

    def _validar_fijas(self, fijas, necesidades, recursos, empresas):
        rec = {r.id for r in recursos}
        nec = {n.id for n in necesidades}
        emp = {e.id for e in empresas}
        for fija in fijas:
            if fija.get("recurso_id") not in rec:
                raise ErrorDominio(
                    f"Asignación fija con recurso desconocido: {fija.get('recurso_id')}"
                )
            if fija.get("necesidad_id") not in nec:
                raise ErrorDominio(
                    f"Asignación fija con necesidad desconocida: {fija.get('necesidad_id')}"
                )
            if fija.get("empresa_id") not in emp:
                raise ErrorDominio(
                    f"Asignación fija con empresa desconocida: {fija.get('empresa_id')}"
                )
            if fija.get("cantidad", 0) < 0:
                raise ErrorDominio("Asignación fija con cantidad negativa")
        return fijas

    def _reservas(self, fijas):
        reservas = {
            "recurso": defaultdict(float),
            "necesidad": defaultdict(float),
            "empresa": defaultdict(float),
        }
        for fija in fijas:
            reservas["recurso"][fija["recurso_id"]] += fija["cantidad"]
            reservas["necesidad"][fija["necesidad_id"]] += fija["cantidad"]
            reservas["empresa"][fija["empresa_id"]] += fija["cantidad"]
        return reservas

    def _fijas_a_asignaciones(self, fijas, necesidades, recursos):
        nec = {n.id: n for n in necesidades}
        rec = {r.id: r for r in recursos}
        resultado = []
        for fija in fijas:
            n = nec[fija["necesidad_id"]]
            r = rec[fija["recurso_id"]]
            resultado.append(
                Asignacion(
                    empresa_id=fija["empresa_id"],
                    recurso_id=fija["recurso_id"],
                    necesidad_id=fija["necesidad_id"],
                    cantidad=fija["cantidad"],
                    distancia_km=r.ubicacion.distancia_a(n.ubicacion),
                    costo_unitario=self._costo_unitario(r, n),
                )
            )
        return resultado

    def _capacidad_suficiente(self, reservas, recursos, empresas):
        # Validación de capacidades tras reservar las asignaciones fijas.
        for r in recursos:
            if self._stock(r, reservas) < -1e-9:
                raise CapacidadInsuficienteError(
                    f"Recurso {r.id}: asignaciones fijas exceden stock"
                )
        for e in empresas:
            if e.flota(self._capacidad_uniforme) - reservas["empresa"][e.id] < -1e-9:
                raise CapacidadInsuficienteError(
                    f"Empresa {e.id}: asignaciones fijas exceden flota"
                )
