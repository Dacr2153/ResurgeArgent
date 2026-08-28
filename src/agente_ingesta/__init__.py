"""Agente 2 — Ingesta de Información.

Convierte reportes heterogéneos (ciudadanos, voluntarios, organizaciones,
autoridades, sensores) en ``ReporteCrudo`` bien formados. No juzga si son
ciertos, duplicados semánticos o relevantes: eso es trabajo del Agente 3
(Verificación). Ingesta solo garantiza forma, unicidad e integridad de entrada.
"""

from __future__ import annotations
