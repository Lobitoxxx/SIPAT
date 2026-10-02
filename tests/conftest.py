"""Configuración compartida de los tests de SIPAT (raíz).

Los módulos de `scripts/` no son un paquete instalable: se importan por nombre
plano porque todos hacen `sys.path.insert(0, ROOT)` al ejecutarse. Los tests
reproducen eso en lugar de inventar una instalación que el proyecto no tiene.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DATA = ROOT / "data" / "processed"

for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """`data/processed`. Se marca skip si los datos reales no están presentes."""
    if not DATA.exists():
        pytest.skip("data/processed no existe: los datos reales no están en el workspace")
    return DATA


@pytest.fixture(scope="session")
def tramos_modelo():
    """`dataset_modelo.csv` real, para los tests que validan contra datos reales."""
    f = DATA / "dataset_modelo.csv"
    if not f.exists():
        pytest.skip("falta data/processed/dataset_modelo.csv")
    import pandas as pd

    return pd.read_csv(f)


@pytest.fixture(scope="session")
def eventos_onsv():
    f = DATA / "onsv_nacional_geocod.csv"
    if not f.exists():
        pytest.skip("falta data/processed/onsv_nacional_geocod.csv")
    import pandas as pd

    return pd.read_csv(f)


@pytest.fixture(scope="session")
def eventos_sutran():
    f = DATA / "sutran_accidentes_geocod.csv"
    if not f.exists():
        pytest.skip("falta data/processed/sutran_accidentes_geocod.csv")
    import pandas as pd

    return pd.read_csv(f)