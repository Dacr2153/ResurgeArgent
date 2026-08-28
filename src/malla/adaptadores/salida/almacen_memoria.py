"""Almacén en memoria. Para tests y para un nodo efímero de demostración.

No sirve para almacenar-y-reenviar de verdad —cerrar la app lo borra— y por eso
el contenedor usa SQLite por defecto.
"""

from __future__ import annotations

from malla.aplicacion.puertos.salida import RegistroSobre
from malla.dominio.sobre import SobreMalla


class AlmacenMemoria:
    """Misma forma que `AlmacenSQLite`, sin disco."""

    def __init__(self) -> None:
        self._registros: list[RegistroSobre] = []
        self._indice: dict[str, int] = {}

    async def guardar(self, sobre: SobreMalla) -> bool:
        if sobre.id_mensaje in self._indice:
            return False
        registro = RegistroSobre(secuencia=len(self._registros) + 1, sobre=sobre)
        self._registros.append(registro)
        self._indice[sobre.id_mensaje] = registro.secuencia
        return True

    async def ids_vistos(self) -> frozenset[str]:
        return frozenset(self._indice)

    async def pendientes(self, limite: int | None = None) -> list[SobreMalla]:
        sobres = [r.sobre for r in self._registros if not r.entregado]
        return sobres if limite is None else sobres[:limite]

    async def listar_desde(self, secuencia: int, limite: int) -> list[RegistroSobre]:
        return [r for r in self._registros if r.secuencia > secuencia][:limite]

    async def marcar_entregados(self, ids: list[str]) -> int:
        objetivo = set(ids)
        marcados = 0
        for indice, registro in enumerate(self._registros):
            if registro.sobre.id_mensaje in objetivo and not registro.entregado:
                self._registros[indice] = RegistroSobre(
                    registro.secuencia, registro.sobre, entregado=True
                )
                marcados += 1
        return marcados

    async def ultima_secuencia(self) -> int:
        return self._registros[-1].secuencia if self._registros else 0

    async def contar_pendientes(self) -> int:
        return sum(1 for r in self._registros if not r.entregado)
