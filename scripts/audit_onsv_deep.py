"""Auditoria profunda ONSV siniestros fatales."""
from pathlib import Path

import pandas as pd

OUT = Path("docs/auditorias/onsv_profundo.txt")


def w(s: str) -> None:
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


df = pd.read_excel(
    r"data/raw/onsv/siniestros_fatales_2021-2025.xlsx",
    sheet_name="SINIESTROS",
    header=4,
)
w(f"shape={df.shape}")
d = df.copy()
d["FECHA_SINIESTRO"] = pd.to_datetime(d["FECHA SINIESTRO"], errors="coerce", dayfirst=True)
w(f"RANGO_FECHAS={d['FECHA_SINIESTRO'].min()} -> {d['FECHA_SINIESTRO'].max()}")
w(f"POR_ANIO={d['FECHA_SINIESTRO'].dt.year.value_counts().sort_index().to_dict()}")
lat = pd.to_numeric(d["COORDENADAS LATITUD"], errors="coerce")
lon = pd.to_numeric(d["COORDENADAS  LONGITUD"], errors="coerce")
w(f"LAT nulos={lat.isna().sum()}  LON nulos={lon.isna().sum()}")
w(f"LAT fuera de rango PERU (abs>=-20): {(abs(lat) < 20).sum()}")
w(f"RED_VIAL={d['RED VIAL'].value_counts().to_dict()}")
w(f"TIPO_VIA={d['TIPO DE VÍA'].value_counts().to_dict()}")
w(f"CLASE_SINIESTRO={d['CLASE SINIESTRO'].value_counts().to_dict()}")
w(f"CAUSA_FACTOR unicos={d['CAUSA FACTOR PRINCIPAL'].nunique()}")
w(f"CAUSA_FACTOR top={d['CAUSA FACTOR PRINCIPAL'].value_counts().head(12).to_dict()}")
w(f"SEÑAL_VERTICAL={d['¿EXISTE SEÑAL VERTICAL?'].value_counts().to_dict()}")
w(f"SUPERFICIE_CALZADA={d['SUPERFICIE DE CALZADA'].value_counts().to_dict()}")
w(f"DEPARTAMENTO n={d['DEPARTAMENTO'].nunique()}")
w(f"COD_CARRETERA n={d['COD CARRETERA'].nunique()}  nulos={d['COD CARRETERA'].isna().sum()}")
w(f"COD_CARRETERA muestra={d['COD CARRETERA'].dropna().unique()[:15].tolist()}")
w(f"FALLECIDOS total={d['CANTIDAD DE FALLECIDOS'].sum()}  LESIONADOS total={d['CANTIDAD DE LESIONADOS'].sum()}")
w("---FIN---")
print("OK")
