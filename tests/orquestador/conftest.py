"""Fixtures de los tests del Orquestador.

Los dobles viven en `dobles.py`; aquí solo se exponen como fixtures.
"""

from __future__ import annotations

import pytest

from tests.orquestador.dobles import GeoespacialFake, IngestaFake, VerificacionFake


@pytest.fixture
def ingesta() -> IngestaFake:
    return IngestaFake()


@pytest.fixture
def verificacion() -> VerificacionFake:
    return VerificacionFake()


@pytest.fixture
def geoespacial() -> GeoespacialFake:
    return GeoespacialFake()
