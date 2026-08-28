"""Configuración del nodo de malla (variables de entorno)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from malla.dominio.motor_malla import TTL_MAXIMO_ACEPTADO, TTL_POR_DEFECTO


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MALLA_", env_file=".env", extra="ignore")

    # Identidad y estado local. Van a disco porque ambos deben sobrevivir a que
    # se cierre la aplicación: la clave, para no perder la identidad del nodo;
    # los pendientes, para no perder reportes que aún no encontraron vecino.
    ruta_identidad: str = "datos/malla/identidad.key"
    ruta_almacen: str = "datos/malla/sobres.sqlite3"

    ttl_por_defecto: int = TTL_POR_DEFECTO
    ttl_maximo_aceptado: int = TTL_MAXIMO_ACEPTADO

    # Vecinos de red local, separados por coma: "http://192.168.1.20:8100,http://..."
    vecinos: str = ""
    capacidad_lote: int = 20
    sondear_vecinos: bool = True

    # Salida a internet. Vacío = este nodo no es pasarela y nunca lo intenta.
    url_nube: str = ""
    ruta_subida_nube: str = "/emergencias"
    tamano_lote_nube: int = 50

    ruta_auditoria: str = "datos/malla/auditoria.jsonl"

    @property
    def lista_vecinos(self) -> list[str]:
        return [v.strip() for v in self.vecinos.split(",") if v.strip()]
