"""Estadisticas de calidad INGEMMET para la matriz tecnica."""
import json
from pathlib import Path

import pandas as pd

OUT = Path("docs/auditorias/ingemmet_stats.txt")


def w(s: str) -> None:
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


import glob

files = sorted(glob.glob("data/raw/ingemmet/layer*.geojson"))
for fp in files:
    name = fp.split("\\")[-1]
    gj = json.load(open(fp, encoding="utf-8"))
    atts = [f.get("attributes", f.get("properties", {})) for f in gj["features"]]
    df = pd.DataFrame(atts)
    w(f"\n### {name}: {len(df):,} features")
    if "FECHA" in df.columns:
        s = pd.to_datetime(df["FECHA"], unit="ms", errors="coerce")
        w(f"FECHA rango: {s.min()} -> {s.max()}  nulos={s.isna().sum()}")
    if "TIP_PELIGRO" in df.columns:
        w("TIP_PELIGRO top: " + str(df["TIP_PELIGRO"].value_counts().head(8).to_dict()))
    if "ANIO" in df.columns:
        w("ANIO: " + str(df["ANIO"].value_counts().sort_index().head(12).to_dict()))
    for c in ("NM_DPTO", "NM_PROV", "NM_DIST"):
        if c in df.columns:
            w(f"{c}: nulos={int(df[c].isna().sum())} unicos={df[c].nunique()}")
w("---FIN---")
print("OK")
