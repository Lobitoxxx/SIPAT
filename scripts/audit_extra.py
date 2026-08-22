"""Auditoria corregida: sep automatico + ONSV por hojas + red vial."""
from pathlib import Path

import pandas as pd

OUT = Path("docs/auditorias/inventario_raw2.txt")


def w(s: str) -> None:
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def load_csv(p: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(p, low_memory=False, encoding=enc, sep=",", on_bad_lines="skip")
        except Exception:
            continue
    return pd.DataFrame()


# red vial con sep automatico
p = Path("data/raw/mtc_red_vial/red_vial_nacional_2022-2024.csv")
df = load_csv(p)
w("### red_vial_nacional_2022-2024.csv")
w(f"shape={df.shape}")
w("cols=" + "|".join(str(c) for c in df.columns))
w("INICIO/FINAL min-max: " + str((df["INICIO"].astype(str).nunique(), df["FINAL"].astype(str).nunique())))
w("FECHA_CORTE unicos: " + str(sorted(df["FECHA_CORTE"].unique())[:10]))
w("CODIGO_RUTA unicos: " + str(df["CODIGO_RUTA"].nunique()))
w("JERARQUIA: " + str(df["JERARQUIA"].value_counts().to_dict()))
w("SUPERFICIE_L: " + str(df["SUPERFICIE_L"].value_counts().to_dict()))
w("ESTADO_L: " + str(df["ESTADO_L"].value_counts().to_dict()))
w("NRO_CARRILES: " + str(df["NRO_CARRILES"].value_counts().to_dict()))

# ONSV siniestros fatales por hoja
p = Path("data/raw/onsv/siniestros_fatales_2021-2025.xlsx")
xl = pd.ExcelFile(p)
w("\n### ONSV siniestros_fatales_2021-2025.xlsx")
w("HOJAS=" + str(xl.sheet_names))
for sheet in xl.sheet_names:
    df = pd.read_excel(p, sheet_name=sheet, header=None)
    w(f"\n  HOJA[{sheet}] shape={df.shape}")
    for i in range(min(6, len(df))):
        row = [str(x) for x in df.iloc[i].tolist()[:10] if pd.notna(x)]
        w(f"    fila{i}: {row}")

# ONSV historico: ver estructura real de cabecera
p = Path("data/raw/onsv/historico_2008-2025.xlsx")
df = pd.read_excel(p, header=None)
w("\n### ONSV historico_2008-2025.xlsx")
w(f"shape={df.shape}")
for i in range(min(8, len(df))):
    row = [str(x) for x in df.iloc[i].tolist()[:8] if pd.notna(x)]
    w(f"  fila{i}: {row}")
w("---FIN---")
print("OK")
