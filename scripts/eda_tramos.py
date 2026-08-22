"""EDA del dataset de tramos."""
import numpy as np
import pandas as pd

d = pd.read_csv("data/processed/dataset_tramos.csv")
print(f"tramos: {len(d)}   rutas: {d['ruta'].nunique()}")

# 1. Cobertura y distribucion
print("\n== Atributos SINAC ==")
for c in ["region", "clasifica", "topografia", "superficie"]:
    print(f"\n{c}:")
    print(d[c].value_counts().head(8).to_string())
print("\ncarriles (dNroCarril) unicos:", sorted(d["carriles"].dropna().unique()))

# 2. Siniestros agregados
print("\n== Siniestros ==")
print(f"ONSV nacional en red: {d['onsv_n'].sum()} siniestros, {d['onsv_fallecidos'].sum()} fallecidos")
print(f"SUTRAN (2020-21) en red: {d['sutran_n'].sum()} accidentes, {d['sutran_fallecidos'].sum()} fallecidos")
print(f"tramos sin ONSV: {(d['onsv_n']==0).sum()} ({(d['onsv_n']==0).mean()*100:.0f}%)")
print(f"tramos con >=3 ONSV: {(d['onsv_n']>=3).sum()}")

# 3. Ranking por ruta (tasa por km)
g = d.groupby("ruta").agg(
    km=("long_km", "sum"), n=("onsv_n", "sum"), fal=("onsv_fallecidos", "sum"),
    sut=("sutran_n", "sum")).reset_index()
g["tasa_100km"] = 100 * g["n"] / g["km"]
print("\n== Top 12 rutas por tasa ONSV (por 100 km) ==")
print(g.sort_values("tasa_100km", ascending=False).head(12).round(2).to_string(index=False))

# 4. Correlaciones con tasa de siniestralidad
num = d[["siniestros_km", "dist_ingemmet_km", "dist_peajes_km", "dist_cinemometros_km",
         "ingemmet_c5km", "cinemometros_c2km", "cinemometros_c10km", "vel_proy"]].copy()
num["vel_proy"] = pd.to_numeric(num["vel_proy"], errors="coerce")
print("\n== Correlacion con siniestros_km ==")
print(num.corr()["siniestros_km"].round(3).to_string())

# 5. Top tramos peligrosos
print("\n== Top 10 tramos por siniestros_km ==")
top = d.sort_values("siniestros_km", ascending=False).head(10)
print(top[["ruta", "km0", "km1", "long_km", "onsv_n", "onsv_fallecidos", "siniestros_km",
           "region", "topografia", "superficie", "dist_ingemmet_km"]].round(2).to_string(index=False))

# 6. Tramos con cinemometros cercanos: relacion?
c = d[["siniestros_km", "cinemometros_c2km"]]
print("\nsiniestros_km por tramo con/sin cinemometro <=2km:")
print(c.assign(con_cine=c["cinemometros_c2km"] > 0).groupby("con_cine")["siniestros_km"].agg(["mean", "median", "count"]).round(3).to_string())
