"""Reaudita todos los archivos crudos y escribe reporte UTF-8 en docs/auditorias."""
import json
from pathlib import Path

import pandas as pd

OUT = Path("docs/auditorias/inventario_raw.txt")


def w(s: str) -> None:
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


FILES = [
    "data/raw/sutran_accidentes/accidentes_carreteras_2020-2021_sutran.csv",
    "data/raw/sutran_reportes_cgm/reportes_preliminares_cgm_2020-2021.csv",
    "data/raw/sutran_cinemometros/cinemometros_2019-2021.csv",
    "data/raw/sutran_cinemometros/cinemometros_2022.xlsx",
    "data/raw/onsv/historico_2008-2025.xlsx",
    "data/raw/onsv/siniestros_fatales_2021-2025.xlsx",
    "data/raw/mtc_red_vial/red_vial_nacional_2022-2024.csv",
]


def load(p: Path):
    if p.suffix.lower() in (".csv", ".txt"):
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return pd.read_csv(p, low_memory=False, encoding=enc, sep=";", on_bad_lines="skip")
            except Exception:
                continue
        return pd.read_csv(p, low_memory=False, encoding="latin-1", sep=";", on_bad_lines="skip")
    return pd.read_excel(p)


for fp in FILES:
    p = Path(fp)
    try:
        df = load(p)
    except Exception as e:
        w(f"\n### {fp}\nERROR: {e}")
        continue
    w(f"\n### {fp}  ({p.stat().st_size:,} bytes)")
    w(f"shape={df.shape}")
    w("cols=" + "|".join(str(c) for c in df.columns))
    for c in df.columns:
        w(f"  {c}: nulos={int(df[c].isna().sum())} unicos={df[c].nunique()} tipo={df[c].dtype}")
    w("head=" + df.head(2).to_csv(sep="|").replace("\n", " ~ "))

# geojson peajes
gj = json.load(open("data/raw/mtc_flujo_peajes/unidades_peaje_2024-2025.geojson", encoding="utf-8"))
feats = gj["features"]
w("\n### data/raw/mtc_flujo_peajes/unidades_peaje_2024-2025.geojson")
w(f"tipo={gj['type']} features={len(feats)}")
w("cols=" + "|".join(feats[0]["properties"].keys()))
w("muestra=" + json.dumps(feats[0]["properties"], ensure_ascii=False))
w("---FIN---")
print("OK")
