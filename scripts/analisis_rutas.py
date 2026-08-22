"""Ranking de departamentos y rutas (ONSV 2021-2025)."""
import numpy as np
import pandas as pd

onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
onsv["fal"] = pd.to_numeric(onsv["CANTIDAD DE FALLECIDOS"], errors="coerce")

# ==== por departamento ====
print("== TOP 15 departamentos por fallecidos ==")
g = onsv.groupby("DEPARTAMENTO").agg(n=("fal", "size"), fal=("fal", "sum"),
                                     nacional=("RED VIAL", lambda s: (s == "NACIONAL").sum()))
g = g.sort_values("fal", ascending=False).head(15)
print(g.to_string())

# ==== por ruta (RED VIAL = NACIONAL) ====
nat = onsv[onsv["RED VIAL"] == "NACIONAL"]
print("\n== TOP 20 rutas por siniestros (nacional) ==")
g2 = nat.groupby("COD CARRETERA").agg(n=("fal", "size"), fal=("fal", "sum")).sort_values("n", ascending=False).head(20)
print(g2.to_string())

# ==== por region geografica (shapefile) ====
d0 = pd.read_csv("data/processed/dataset_modelo.csv")
print("\n== ONSV nacional por region geografica ==")
reg2 = d0.groupby("region").agg(n=("onsv_n", "sum"), fal=("onsv_fallecidos", "sum"), km=("long_km", "sum"))
reg2["tasa_100km"] = 100 * reg2["n"] / reg2["km"]
print(reg2.round(2).to_string())

# ==== top tramos (coordenadas para mapa) ====
print("\n== TOP 15 tramos por siniestros_km (dataset_modelo) ==")
d = pd.read_csv("data/processed/dataset_modelo.csv")
print(d.sort_values("siniestros_km", ascending=False)[
    ["ruta", "km0", "km1", "onsv_n", "onsv_fallecidos", "siniestros_km", "region", "topografia",
     "superficie", "vel_proy", "sinuosidad", "dist_ingemmet_km", "lon_mid", "lat_mid"]].head(15).round(2).to_string(index=False))

# ==== top rutas SUTRAN vs ONSV ====
print("\n== SUTRAN 2020-21: top 15 rutas ==")
s = pd.read_csv("data/processed/sutran_accidentes_geocod.csv")
sut_g = s.groupby("CODIGO_VIA").size().sort_values(ascending=False).head(15)
print(sut_g.to_string())

print("\n== SUTRAN vs ONSV top 10 rutas comparadas ==")
ov = g2[["n"]].rename(columns={"n": "onsv"})
su = s.groupby("CODIGO_VIA").size().rename("sutran")
cmp_ = pd.concat([ov, su], axis=1).fillna(0).astype(int).sort_values("onsv", ascending=False).head(10)
cmp_["ratio_sutran_onsv"] = (cmp_["sutran"] / cmp_["onsv"]).round(2)
print(cmp_.to_string())
