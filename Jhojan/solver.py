#!/usr/bin/env python3
"""
Motor de asignacion del Agente de Voluntarios (ResurgeAgent).

Asigna horas-hombre de voluntarios a demandas de tarea por zona, aplicando
primero las reglas de seguridad R1..R6 y despues un greedy por prioridad.

Determinista y sin dependencias externas: mismo input -> mismo output.
Eso es requisito, no comodidad: el DMC tiene que poder auditar la decision.

Uso:
    python3 solver.py                     # corre con datos_demo.json
    python3 solver.py mi_escenario.json
    python3 solver.py --help
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Catalogo (ver seccion 2 de agente-voluntarios.md)
# --------------------------------------------------------------------------

PROFESIONES = {
    2: "Busqueda y Rescate",
    5: "Personal Medico",
    7: "Primeros Auxilios",
    8: "Voluntario Espontaneo",
}

# riesgo: bajo | medio | alto     recursos: los que consume por hora-hombre
TAREAS = {
    "S1": {"nombre": "Busqueda en superficie", "riesgo": "medio", "recursos": {}},
    "S2": {"nombre": "Rescate entre escombros", "riesgo": "alto", "recursos": {}},
    "S3": {"nombre": "Traslado a zona segura", "riesgo": "bajo", "recursos": {}},
    "S4": {"nombre": "Censo de afectados", "riesgo": "bajo", "recursos": {}},
    "S5": {"nombre": "Despeje de acceso", "riesgo": "medio", "recursos": {}},
    "T1": {"nombre": "Triaje", "riesgo": "medio", "recursos": {"kits_medicos": 1}},
    "T2": {
        "nombre": "Estabilizacion",
        "riesgo": "alto",
        "recursos": {"kits_medicos": 2, "ambulancias": 1},
    },
    "T3": {
        "nombre": "Traslado de heridos",
        "riesgo": "medio",
        "recursos": {"ambulancias": 1},
    },
}

# Que perfiles pueden hacer que tarea, en orden de preferencia.
# El primero de la lista es el perfil idoneo; los siguientes son aceptables.
AFINIDAD = {
    "S1": [2, 8, 7],
    "S2": [2],
    "S3": [8, 7, 2],
    "S4": [8, 7],
    "S5": [2, 8],
    "T1": [5, 7],
    "T2": [5],
    "T3": [7, 5, 8],
}

PESO_SEVERIDAD = {"baja": 1, "media": 2, "alta": 4, "critica": 8}
RIESGO_ALTO = {"S2", "T2"}

# R5. El limite de aglomeracion existe para que los espontaneos no estorben a las
# unidades profesionales en el frente de trabajo. Por eso solo aplica a tareas de
# riesgo medio/alto: un censo o un traslado a zona segura no genera ese problema y
# bloquearlos solo desperdicia gente disponible.
RATIO_AGLOMERACION = 3.0  # espontaneos por cada certificado en la zona
CUPO_MINIMO_ESPONTANEOS = 2  # piso, aun sin certificados presentes


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------


@dataclass
class Voluntario:
    id: str
    nombre: str
    profesion: int
    zona: str
    horas_disponibles: float
    certificado: bool = True
    notas: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # R4: sin certificacion se degrada a perfil de apoyo antes de todo lo demas.
        if not self.certificado and self.profesion != 8:
            self.notas.append(f"R4: perfil {self.profesion} degradado a 8 (sin certificar)")
            self.profesion = 8


@dataclass
class Demanda:
    zona: str
    tarea: str
    horas_hombre: float
    severidad: str

    @property
    def prioridad(self) -> float:
        return PESO_SEVERIDAD.get(self.severidad, 1) * self.horas_hombre


class Escenario:
    def __init__(self, datos: dict):
        self.contexto: dict = datos.get("contexto", {})
        self.voluntarios = [Voluntario(**v) for v in datos["voluntarios"]]
        self.demanda = [Demanda(**d) for d in datos["demanda"]]
        # copia mutable: el solver la va drenando
        self.recursos: dict[str, dict[str, float]] = {
            z: dict(r) for z, r in datos.get("recursos", {}).items()
        }
        self.unidades_oficiales: set[str] = set(datos.get("unidades_oficiales", []))
        self._validar()

    def _validar(self) -> None:
        for v in self.voluntarios:
            if v.profesion not in PROFESIONES:
                raise ValueError(f"{v.id}: profesion {v.profesion} desconocida")
            if v.horas_disponibles < 0:
                raise ValueError(f"{v.id}: horas_disponibles negativas")
        for d in self.demanda:
            if d.tarea not in TAREAS:
                raise ValueError(f"tarea '{d.tarea}' desconocida en zona {d.zona}")
            if d.severidad not in PESO_SEVERIDAD:
                raise ValueError(f"severidad '{d.severidad}' invalida en zona {d.zona}")


# --------------------------------------------------------------------------
# Reglas de seguridad. Cada una devuelve None (pasa) o el motivo del bloqueo.
# --------------------------------------------------------------------------


def r1_riesgo_por_perfil(vol: Voluntario, tarea: str) -> str | None:
    """Un voluntario espontaneo nunca va a una tarea de riesgo alto."""
    if vol.profesion == 8 and tarea in RIESGO_ALTO:
        return f"R1: perfil 8 no puede ejecutar {tarea} (riesgo alto)"
    return None


def r2_supervision(zona: str, tarea: str, oficiales: set[str]) -> str | None:
    """S2 requiere unidad de rescate oficial presente en la zona."""
    if tarea == "S2" and zona not in oficiales:
        return f"R2: S2 requiere unidad oficial presente en {zona}"
    return None


def r3_recursos(zona: str, tarea: str, recursos: dict) -> str | None:
    """Sin ambulancia no hay traslado; sin kit no hay triaje."""
    requeridos = TAREAS[tarea]["recursos"]
    if not requeridos:
        return None
    disponibles = recursos.get(zona, {})
    faltan = [r for r, n in requeridos.items() if disponibles.get(r, 0) < n]
    if faltan:
        return f"R3: sin {', '.join(faltan)} disponibles en {zona}"
    return None


def r5_aglomeracion(vols_zona: list[Voluntario]) -> tuple[int, str | None]:
    """Cupo de espontaneos en tareas de riesgo medio/alto. -> (cupo, aviso)."""
    certificados = sum(1 for v in vols_zona if v.profesion != 8)
    espontaneos = sum(1 for v in vols_zona if v.profesion == 8)
    cupo = max(int(certificados * RATIO_AGLOMERACION), CUPO_MINIMO_ESPONTANEOS)
    if espontaneos > cupo:
        return cupo, (
            f"R5: {espontaneos} espontaneos supera el cupo de {cupo} en tareas de "
            f"riesgo ({certificados} certificados x {RATIO_AGLOMERACION})"
        )
    return cupo, None


def afinidad(vol: Voluntario, tarea: str) -> int | None:
    """Posicion del perfil en la lista de preferencia. None = no apto."""
    orden = AFINIDAD.get(tarea, [])
    return orden.index(vol.profesion) if vol.profesion in orden else None


# --------------------------------------------------------------------------
# Solver
# --------------------------------------------------------------------------


def asignar(esc: Escenario) -> dict:
    restante = {v.id: v.horas_disponibles for v in esc.voluntarios}
    por_zona: dict[str, list[Voluntario]] = {}
    for v in esc.voluntarios:
        por_zona.setdefault(v.zona, []).append(v)

    # R5 se evalua una vez por zona, no por asignacion.
    avisos: list[str] = []
    cupo_espontaneo: dict[str, int] = {}
    for zona, vols in por_zona.items():
        cupo, aviso = r5_aglomeracion(vols)
        cupo_espontaneo[zona] = cupo
        if aviso:
            avisos.append(aviso)
    usados_espontaneos: dict[str, int] = dict.fromkeys(por_zona, 0)

    asignaciones: list[dict] = []
    insatisfecha: list[dict] = []
    bloqueos = 0
    n = 0

    # Prioridad: severidad x volumen. Desempate por zona/tarea para que el
    # resultado sea estable entre corridas.
    for d in sorted(esc.demanda, key=lambda x: (-x.prioridad, x.zona, x.tarea)):
        motivo = r2_supervision(d.zona, d.tarea, esc.unidades_oficiales)
        if motivo:
            bloqueos += 1
            insatisfecha.append(
                {"zona": d.zona, "tarea": d.tarea, "horas_faltantes": d.horas_hombre, "motivo": motivo}
            )
            continue

        pendientes = d.horas_hombre
        candidatos = []
        sin_horas = False  # habia perfil apto, pero ya agotado
        for v in por_zona.get(d.zona, []):
            af = afinidad(v, d.tarea)
            if af is None:
                continue
            if bloqueo := r1_riesgo_por_perfil(v, d.tarea):
                bloqueos += 1
                if bloqueo not in v.notas:
                    v.notas.append(bloqueo)
                continue
            if restante[v.id] <= 0:
                sin_horas = True
                continue
            candidatos.append((af, -restante[v.id], v))
        candidatos.sort(key=lambda x: (x[0], x[1], x[2].id))

        # R5 solo restringe tareas de riesgo medio/alto.
        aplica_r5 = TAREAS[d.tarea]["riesgo"] != "bajo"
        tope_r5 = False

        motivo_recursos = None
        for _, _, v in candidatos:
            if pendientes <= 0:
                break

            # R3 se revalida en cada asignacion: los recursos se van consumiendo.
            if motivo_recursos := r3_recursos(d.zona, d.tarea, esc.recursos):
                bloqueos += 1
                break

            # R5: el cupo de espontaneos se consume al asignarlos.
            if aplica_r5 and v.profesion == 8:
                if usados_espontaneos[d.zona] >= cupo_espontaneo[d.zona]:
                    tope_r5 = True
                    continue
                usados_espontaneos[d.zona] += 1

            horas = min(pendientes, restante[v.id])  # R6: nunca sobre la capacidad
            restante[v.id] -= horas
            pendientes -= horas

            for r, cant in TAREAS[d.tarea]["recursos"].items():
                esc.recursos[d.zona][r] -= cant

            n += 1
            asignaciones.append(
                {
                    "id": f"ASG-{n:03d}",
                    "zona": d.zona,
                    "tarea": d.tarea,
                    "tarea_nombre": TAREAS[d.tarea]["nombre"],
                    "voluntario_id": v.id,
                    "voluntario_nombre": v.nombre,
                    "profesion": v.profesion,
                    "profesion_nombre": PROFESIONES[v.profesion],
                    "horas": round(horas, 2),
                    "severidad": d.severidad,
                    "supervisado_por_unidad_oficial": d.zona in esc.unidades_oficiales,
                }
            )

        if pendientes > 0.01:
            if motivo_recursos:
                motivo = motivo_recursos
            elif tope_r5:
                motivo = f"R5: cupo de voluntarios espontaneos agotado en {d.zona}"
            elif sin_horas or candidatos:
                # Habia perfil apto: o ya venia agotado, o se agoto asignando.
                motivo = f"R6: perfiles aptos en {d.zona} sin horas disponibles"
            else:
                motivo = f"sin voluntarios con perfil apto en {d.zona}"
            insatisfecha.append(
                {
                    "zona": d.zona,
                    "tarea": d.tarea,
                    "horas_faltantes": round(pendientes, 2),
                    "motivo": motivo,
                }
            )

    capacidad = sum(v.horas_disponibles for v in esc.voluntarios)
    asignadas = sum(a["horas"] for a in asignaciones)
    demandadas = sum(d.horas_hombre for d in esc.demanda)

    return {
        "contexto": esc.contexto,
        "resumen": {
            "voluntarios_registrados": len(esc.voluntarios),
            "horas_capacidad_total": round(capacidad, 2),
            "horas_demandadas": round(demandadas, 2),
            "horas_asignadas": round(asignadas, 2),
            "cobertura": round(asignadas / demandadas, 3) if demandadas else 0.0,
            "uso_capacidad": round(asignadas / capacidad, 3) if capacidad else 0.0,
        },
        "asignaciones": asignaciones,
        "demanda_insatisfecha": insatisfecha,
        "gobernanza": {
            "requiere_aprobacion_humana": True,
            "reglas_evaluadas": ["R1", "R2", "R3", "R4", "R5", "R6"],
            "bloqueos_por_seguridad": bloqueos,
            "avisos": avisos,
            "notas_voluntarios": {v.id: v.notas for v in esc.voluntarios if v.notas},
        },
    }


# --------------------------------------------------------------------------


def imprimir(res: dict) -> None:
    r = res["resumen"]
    ctx = res["contexto"]
    print(f"\n{'=' * 74}")
    print(
        f"  {ctx.get('tipo_desastre', 'desastre').upper()} - "
        f"{ctx.get('municipio', '?')}  (periodo {ctx.get('periodo', 1)})"
    )
    print("=" * 74)
    print(
        f"  {r['voluntarios_registrados']} voluntarios | "
        f"{r['horas_capacidad_total']}h capacidad | "
        f"{r['horas_demandadas']}h demandadas"
    )
    print(
        f"  Asignadas {r['horas_asignadas']}h  ->  "
        f"cobertura {r['cobertura']:.0%} | uso de capacidad {r['uso_capacidad']:.0%}"
    )

    print(f"\n  ASIGNACIONES ({len(res['asignaciones'])})")
    print(f"  {'ZONA':<6} {'TAREA':<24} {'VOLUNTARIO':<20} {'PERFIL':<22} {'HRS':>5} SUP")
    print(f"  {'-' * 86}")
    for a in res["asignaciones"]:
        sup = "si" if a["supervisado_por_unidad_oficial"] else "-"
        print(
            f"  {a['zona']:<6} {a['tarea'] + ' ' + a['tarea_nombre']:<24} "
            f"{a['voluntario_nombre']:<20} {a['profesion_nombre']:<22} "
            f"{a['horas']:>5} {sup}"
        )

    if res["demanda_insatisfecha"]:
        print(f"\n  DEMANDA INSATISFECHA ({len(res['demanda_insatisfecha'])})")
        for d in res["demanda_insatisfecha"]:
            print(f"  {d['zona']:<6} {d['tarea']:<4} {d['horas_faltantes']:>6}h  {d['motivo']}")

    g = res["gobernanza"]
    print(f"\n  Bloqueos por seguridad: {g['bloqueos_por_seguridad']}")
    for aviso in g["avisos"]:
        print(f"  ! {aviso}")
    for vid, notas in g["notas_voluntarios"].items():
        for nota in notas:
            print(f"  ! {vid}: {nota}")
    print("\n  >> RECOMENDACION. Requiere aprobacion del DMC antes de despachar.\n")


def main() -> int:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    ruta = Path(args[0]) if args else Path(__file__).parent / "datos_demo.json"
    if not ruta.exists():
        print(f"ERROR: no existe {ruta}", file=sys.stderr)
        return 1

    esc = Escenario(json.loads(ruta.read_text(encoding="utf-8")))
    res = asignar(esc)

    if "--json" in sys.argv:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        imprimir(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
