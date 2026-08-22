"""Validación de la geometría del shapefile contra puntos reales (ONSV/CGM)."""
import sys

import pandas as pd
from shapely.geometry import Point

import geocode

# ONSV nacional
onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
lat = pd.to_numeric(onsv["COORDENADAS LATITUD"], errors="coerce")
lon = pd.to_numeric(onsv["COORDENADAS  LONGITUD"], errors="coerce")
onsv["lat"] = lat
onsv["lon"] = lon

sub = onsv[(onsv["RED VIAL"] == "NACIONAL") & (onsv["COD CARRETERA"].isin(geocode.routes()))].copy()
print(f"ONSV nacional con codigo en red: {len(sub)}")

import numpy as np

dists = []
bad = 0
n = len(sub)
for i, r in sub.iterrows():
    if pd.isna(r["lat"]) or pd.isna(r["lon"]):
        continue
    d = geocode.snap_distance(Point(r["lon"], r["lat"]), r["COD CARRETERA"])
    if d is None:
        bad += 1
        continue
    dists.append(d)
dists = np.array(dists)
print(f"puntos validados: {len(dists)}  sin ruta: {bad}")
km = dists * 111.32  # aprox: 1 grado ~ 111 km
print(f"distancia al shapefile: media={km.mean():.3f} km  mediana={np.median(km):.3f} km")
for p in (90, 95, 99):
    print(f"  p{p}: {np.percentile(km, p):.3f} km")
print(f"  <100m: {(km < 0.1).sum()} ({(km < 0.1).mean()*100:.1f}%)")
print(f"  <1km: {(km < 1).sum()} ({(km < 1).mean()*100:.1f}%)")
print(f"  <5km: {(km < 5).sum()} ({(km < 5).mean()*100:.1f}%)")
print(f"  <10km: {(km < 10).sum()} ({(km < 10).mean()*100:.1f}%)")
