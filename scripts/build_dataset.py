"""Construye el dataset espacial de analisis:
1. data/processed/tramos_red.csv      : 3,750 tramos con atributos SINAC + peaje de referencia
2. data/processed/onsv_nacional_geocod.csv : ONSV RED VIAL=NACIONAL limpio + tramo/km asignado
3. data/processed/cinemometros_clean.csv   : cinemometros 2019-2021 limpios
"""
import os

import numpy as np
import pandas as pd
from shapely.geometry import Point

import geocode
from geocode import _load

os.makedirs("data/processed", exist_ok=True)
_load()

# ---------- 1. Tramo de red ----------
tramos = pd.DataFrame([{
    "id_tramo": i,
    "ruta": s["route"],
    "km0": s["km0"],
    "km1": s["km1"],
    "dpto": s["dpto"],
    "region": s["region"],
    "clasifica": s["clasifica"],
    "topografia": s["topografia"],
    "carriles": s["carriles"],
    "vel_proy": s["vel_proy"],
    "superficie": s["superficie"],
    "lon0": s["geom"].coords[0][0],
    "lat0": s["geom"].coords[0][1],
    "lon1": s["geom"].coords[-1][0],
    "lat1": s["geom"].coords[-1][1],
} for i, s in enumerate(geocode._SEGMENTS)])
tramos["long_km"] = tramos["km1"] - tramos["km0"]
tramos.to_csv("data/processed/tramos_red.csv", index=False, encoding="utf-8-sig")
print(f"tramos_red.csv: {len(tramos)} tramos, {tramos['ruta'].nunique()} rutas")

# ---------- 2. ONSV nacional ----------
onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
onsv["lat"] = pd.to_numeric(onsv["COORDENADAS LATITUD"], errors="coerce")
onsv["lon"] = pd.to_numeric(onsv["COORDENADAS  LONGITUD"], errors="coerce")
nat = onsv[onsv["RED VIAL"] == "NACIONAL"].copy()
print(f"ONSV nacional: {len(nat)}")

# fecha
fc = [c for c in nat.columns if "FECHA" in c.upper() and "CORTE" not in c.upper()]
fecha_col = fc[0]
print(f"  columna fecha: {fecha_col}")
nat["fecha"] = pd.to_datetime(nat[fecha_col], format="%d/%m/%Y", errors="coerce")
nat["fallecidos"] = pd.to_numeric(nat["CANTIDAD DE FALLECIDOS"], errors="coerce")

# asignar tramo + km + coords si faltan (solo ruta en red)
routes = geocode.routes()
seg_by_route = {}
for s in geocode._SEGMENTS:
    seg_by_route.setdefault(s["route"], []).append(s)

def assign(r):
    ruta = r["COD CARRETERA"]
    if ruta not in routes:
        return ruta, np.nan, np.nan, np.nan, np.nan
    # km real por proyeccion de la coordenada reportada
    if pd.isna(r["lat"]) or pd.isna(r["lon"]):
        return ruta, np.nan, np.nan, np.nan, np.nan
    pt = Point(r["lon"], r["lat"])
    best = None
    for s in seg_by_route[ruta]:
        d = pt.distance(s["geom"])
        if best is None or d < best[0]:
            best = (d, s)
    if best is None:
        return ruta, np.nan, np.nan, np.nan, np.nan
    _, s = best
    proj = s["geom"].project(pt, normalized=True)
    km = s["km0"] + proj * (s["km1"] - s["km0"])
    return ruta, km, best[0] * 111.32, s["km0"], s["km1"]

out = []
for _, r in nat.iterrows():
    ruta, km, d_km, km0, km1 = assign(r)
    out.append((ruta, km, d_km, km0, km1))
nat["ruta", ] = [o[0] for o in out]
nat["km_red"] = [o[1] for o in out]
nat["dist_linea_km"] = [o[2] for o in out]
nat["tramo_km0"] = [o[3] for o in out]
nat["tramo_km1"] = [o[4] for o in out]

nat.to_csv("data/processed/onsv_nacional_geocod.csv", index=False, encoding="utf-8-sig")
print(f"  guardado oNSV_nacional_geocod.csv con km_red y dist_linea_km")
print(f"  con coords: {nat['lat'].notna().sum()}   sin coords: {nat['lat'].isna().sum()}")

# ---------- 3. Cinemometros 2019-2021 ----------
cin = pd.read_csv("data/raw/sutran_cinemometros/cinemometros_2019-2021.csv", sep=";", encoding="latin-1")
cin["lat"] = pd.to_numeric(cin.get("LATITUD"), errors="coerce")
cin["lon"] = pd.to_numeric(cin.get("LONGITUD"), errors="coerce")
cin = cin[cin["lat"].notna() & cin["lon"].notna()].copy()
print(f"cinemometros 2019-21 con coords: {len(cin)}")
cin.to_csv("data/processed/cinemometros_clean.csv", index=False, encoding="utf-8-sig")
