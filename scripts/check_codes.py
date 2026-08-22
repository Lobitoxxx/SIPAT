"""Tasa de coincidencia de codigos de via entre accidentes y red vial."""
from pathlib import Path

import pandas as pd
import shapefile

SH = Path("data/raw/mtc_datos_espaciales/rvn_dic16/red_vial_nacional_dic16.shp")
sf = shapefile.Reader(str(SH), encoding="iso-8859-1")
fields = [f[0] for f in sf.fields[1:]]
recs = []
for r in sf.iterRecords():
    recs.append(dict(zip(fields, list(r))))
rv = pd.DataFrame(recs)
rutas = set(rv["cCodRutaDi"].unique())
print(f"RUTAS RED: {len(rutas)}")

# km max por ruta en la red
km_max = rv.groupby("cCodRutaDi")["dkmFinal"].max().to_dict()


def match_codes(codes, label):
    codes = set(codes)
    in_red = codes & rutas
    not_in = sorted(codes - rutas)
    print(f"\n[{label}] codigos unicos={len(codes)}  en red={len(in_red)} ({100*len(in_red)/max(len(codes),1):.1f}%)")
    print(f"  NO en red ({len(not_in)}): {not_in[:30]}")


def read_csv(p):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(p, sep=";", encoding=enc)
        except Exception:
            continue
    return pd.read_csv(p, sep=";", encoding="latin-1", errors="replace")


# SUTRAN accidentes
acc = read_csv("data/raw/sutran_accidentes/accidentes_carreteras_2020-2021_sutran.csv")
match_codes(acc["CODIGO_VÍA"].dropna(), "SUTRAN accidentes")

# SUTRAN CGM
cgm = read_csv("data/raw/sutran_reportes_cgm/reportes_preliminares_cgm_2020-2021.csv")
match_codes(cgm["CODIGO_VIA"].dropna(), "SUTRAN CGM")

# ONSV
onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
match_codes(onsv["COD CARRETERA"].dropna(), "ONSV COD CARRETERA")

# km fuera de rango en SUTRAN accidentes (que si tienen codigo en red)
print("\n--- km de SUTRAN accidentes fuera del rango de su ruta ---")
out = 0
tot = 0
for cod, km in acc[["CODIGO_VÍA", "KILOMETRO"]].dropna().itertuples(index=False):
    if cod in km_max:
        tot += 1
        try:
            k = float(str(km).replace(",", "."))
        except ValueError:
            continue
        if k > km_max[cod] + 5:
            out += 1
print(f"registros con ruta en red: {tot} | km excede rango (+5km): {out} ({100*out/max(tot,1):.1f}%)")

# muestra de valores KILOMETRO raros
km_vals = acc["KILOMETRO"].dropna().astype(str)
raros = [v for v in km_vals.unique() if not v.replace(".", "").isdigit()]
print("\nKILOMETRO no numericos:", raros[:20])
print("HORA no HH:MM:", [v for v in acc['HORA'].astype(str).unique() if len(v) != 5][:20])
print("FALLECIDOS valores:", sorted(acc['FALLECIDOS'].dropna().astype(str).unique())[:20])
