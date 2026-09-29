# -*- coding: utf-8 -*-
"""Pytest: sys.path + fixtures compartidos para tests unit/integration/data_quality."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --- mini dataframes compatibles con el contrato canónico ---

@pytest.fixture
def onsv_rows():
    return pd.DataFrame(
        {
            "codigo": ["P00001", "P00002", "P00003"],
            "fecha": pd.to_datetime(["2023-01-02", "2023-02-03", "2023-03-04"]),
            "hora": ["08:30", "13:15", "21:00"],
            "clase": ["CHOQUE", "ATROPELLO", "DESPISTE"],
            "fallecidos": [0, 1, 2],
            "lesionados": [2, 0, 3],
            "vehiculos_danados": [2, 0, 1],
            "departamento": ["LIMA", "AREQUIPA", "CUSCO"],
            "provincia": ["LIMA", "AREQUIPA", "CUSCO"],
            "distrito": ["SAN JUAN DE LURIGANCHO", "MIRAFLORES", "WANCHAQ"],
            "zona": ["URBANA", "URBANA", "RURAL"],
            "red_vial": ["URBANO", "NACIONAL", "DEPARTAMENTAL"],
            "condicion_climatica": ["DESPEJADO", "LLUVIOSO", "NIEBLA"],
            "causa_principal": ["IMPERICIA DEL CONDUCTOR", "IMPRUDENCIA DEL PEATÓN", "EN PROCESO DE INVESTIGACIÓN"],
            "latitud": [-12.00, -16.40, -13.52],
            "longitud": [-77.03, -71.53, -71.97],
        }
    )


@pytest.fixture
def cinemometros_rows():
    return pd.DataFrame(
        {
            "nro_deteccion": [1001, 1002, 1003],
            "fecha_papeleta": pd.to_datetime(["2019-10-31", "2020-11-01", "2021-06-15"]),
            "fecha_corte": pd.to_datetime(["2019-10-31", "2020-11-01", "2021-06-15"]),
            "region": ["LIMA", "AREQUIPA", "PIURA"],
            "carretera": ["PANAMERICANA NORTE", "PANAMERICANA SUR", "PANAMERICANA NORTE"],
            "latitud": [-11.45, -16.40, -5.20],
            "longitud": [-77.31, -71.53, -80.63],
            "limite_velocidad": [60, 90, 80],
            "velocidad_detectada": [72, 95, 84],
        }
    )


@pytest.fixture
def mini_onsv_xlsx(tmp_path: Path) -> Path:
    """Emula el XLSX ONSV: 4 filas de preámbulo + cabecera en fila 6 (índice 4)."""
    import numpy as np

    path = tmp_path / "mini_onsv.xlsx"
    header = [
        "CÓDIGO SINIESTRO", "FECHA SINIESTRO", "HORA SINIESTRO", "CLASE SINIESTRO",
        "CANTIDAD DE FALLECIDOS", "CANTIDAD DE LESIONADOS", "CANTIDAD DE VEHICULOS DAÑADOS",
        "DEPARTAMENTO", "PROVINCIA", "DISTRITO", "ZONA", "RED VIAL", "CONDICIÓN CLIMÁTICA",
        "COORDENADAS LATITUD", "COORDENADAS  LONGITUD", "CAUSA FACTOR PRINCIPAL",
    ]
    data = [
        ["P0001", "2020-09-05", "04:30", "CHOQUE", 2, 1, 1, "LIMA", "LIMA", "LURIN", "URBANA", "URBANO", "DESPEJADO", -12.0, -77.0, "IMPERICIA DEL CONDUCTOR"],
        ["P0002", "2021-01-02", "18:00", "ATROPELLO", 0, 2, 0, "AREQUIPA", "AREQUIPA", "MIRAFLORES", "URBANA", "NACIONAL", "LLUVIOSO", -16.4, -71.5, "IMPRUDENCIA DEL PEATÓN"],
        ["P0003", "2022-03-03", "09:45", "DESPISTE", 1, 0, 1, "CUSCO", "CUSCO", "WANCHAQ", "RURAL", "DEPARTAMENTAL", "NIEBLA", -13.5, -72.0, "EN PROCESO DE INVESTIGACIÓN"],
    ]
    ncols = len(header)
    rows = [[f"preámbulo {i}"] * ncols for i in range(4)]
    rows.append(header)
    rows.extend(data)
    pd.DataFrame(np.array(rows)).to_excel(path, header=False, index=False)
    return path


@pytest.fixture
def mini_cinemometros_csv(tmp_path: Path) -> Path:
    path = tmp_path / "mini_cinemometros.csv"
    pd.DataFrame(
        {
            "NRO_DETECCION": [10, 11, 12],
            "FECHA_PAPELETA": [20191031, 20201101, 20210615],
            "REGION": ["LIMA", "Lima", "PIURA"],
            "CARRETERA": ["PANAMERICANA NORTE", "Panamericana Sur", "PANAMERICANA NORTE"],
            "LATITUD": [-11.45, -16.40, -5.20],
            "LONGITUD": [-77.31, -71.53, -80.63],
            "LIMITE_VELOCIDAD": [60, 90, 80],
            "VELOCIDAD_DETECTADA": [72, 95, 84],
            "FECHA_CORTE": [20191031, 20201101, 20210615],
            "lat": [-11.45, -16.40, -5.20],
            "lon": [-77.31, -71.53, -80.63],
        }
    ).to_csv(path, index=False, encoding="utf-8-sig")
    return path