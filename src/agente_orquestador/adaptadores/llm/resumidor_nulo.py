"""Resumidor sin red: arma el parte de situación con plantillas deterministas.

Es el adaptador por defecto. Todo el agente corre y todos los tests pasan sin API
key y sin conexión, porque el LLM no aporta ninguna decisión: solo redacta. Si el
texto lo escribe una plantilla en vez de un modelo, el sistema decide igual.
"""

from __future__ import annotations


class ResumidorNulo:
    """Genera un parte de situación legible a partir del contexto ya resuelto."""

    async def resumir_situacion(self, contexto: dict) -> str:
        incidentes = contexto.get("incidentes", [])
        if not incidentes:
            return (
                "Sin incidentes verificados en este lote "
                f"(correlación {contexto.get('correlacion_id', 'desconocida')})."
            )

        lineas = [
            f"Operación {contexto.get('correlacion_id', 'desconocida')}: "
            f"{len(incidentes)} incidente(s) verificado(s), "
            f"{contexto.get('reportes_ingeridos', 0)} reporte(s) ingerido(s).",
        ]
        if contexto.get("degradada"):
            fallidos = ", ".join(contexto.get("saga", {}).get("fallidos", [])) or "desconocido"
            lineas.append(
                f"Información incompleta: no respondieron los pasos [{fallidos}]. "
                "El orden de atención se calculó con los datos disponibles."
            )

        pendientes = [i for i in incidentes if i.get("requiere_firma")]
        lineas.append(f"{len(pendientes)} incidente(s) esperan firma del coordinador.")
        for incidente in incidentes[:5]:
            triage = incidente.get("triage") or {}
            lineas.append(
                f"  {triage.get('posicion', '-')}. incidente {incidente['incidente_id']} "
                f"en estado {incidente['estado']} "
                f"(puntuación {triage.get('puntuacion', 0)})."
            )
        return "\n".join(lineas)
