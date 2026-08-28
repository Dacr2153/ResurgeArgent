"""Núcleo compartido: contratos entre agentes.

Sin lógica de negocio. Solo los tipos que cruzan fronteras, los puertos comunes y
helpers puros. Cualquier agente puede importar de aquí; nada de aquí importa a un
agente.
"""

from nucleo.esquemas import (
    Canal,
    Categoria,
    Certeza,
    ConsultaGeo,
    DecisionHumana,
    Fuente,
    IncidenteVerificado,
    ModoTransporte,
    ReporteCrudo,
    RespuestaGeo,
    Severidad,
    TipoFuente,
    Urgencia,
)
from nucleo.geo import GeometriaInvalidaError, Punto, bbox, centroide, haversine, validar_geojson
from nucleo.mensajes import (
    Agente,
    EventoAuditoria,
    Mensaje,
    Performativa,
    TipoEvento,
    ahora,
    nuevo_id,
)
from nucleo.puertos import AuditoriaPort, GeoespacialPort, IngestaPort, VerificacionPort

__all__ = [
    "Agente", "AuditoriaPort", "Canal", "Categoria", "Certeza", "ConsultaGeo",
    "DecisionHumana", "EventoAuditoria", "Fuente", "GeoespacialPort",
    "GeometriaInvalidaError", "IncidenteVerificado", "IngestaPort", "Mensaje",
    "ModoTransporte", "Performativa", "Punto", "ReporteCrudo", "RespuestaGeo",
    "Severidad", "TipoEvento", "TipoFuente", "Urgencia", "VerificacionPort",
    "ahora", "bbox", "centroide", "haversine", "nuevo_id", "validar_geojson",
]
