"""Valida interpolacion km->punto contra CGM (coords + progresiva), y genera dataset procesado."""
import pandas as pd
from shapely.geometry import Point
from shapely import distance

import geocode

# CGM
cgm = pd.read_csv("data/raw/sutran_reportes_cgm/reportes_preliminares_cgm_2020-2021.csv", sep=";", encoding="cp1252")
cgm["lat"] = pd.to_numeric(cgm["LATITUD"], errors="coerce")
cgm["lon"] = pd.to_numeric(cgm["LONGITUD"], errors="coerce")
cgm["km"] = pd.to_numeric(cgm["PROGRESIVA"], errors="coerce")

sub = cgm[(cgm["CODIGO_VIA"].isin(geocode.routes())) & cgm["km"].notna() & cgm["lat"].notna()].copy()
print(f"CGM con ruta+km+coords: {len(sub)}")

import numpy as np

rows = []
errs = []
for _, r in sub.iterrows():
    p = geocode.locate(r["CODIGO_VIA"], float(r["km"]))
    if p is None:
        continue
    real = Point(r["lon"], r["lat"])
    d = real.distance(p) * 111.32  # km aprox
    errs.append(d)
errs = np.array(errs)
print(f"interpolados: {len(errs)}")
print(f"error km->punto: media={errs.mean():.3f} mediana={np.median(errs):.3f}")
for p in (90, 95, 99):
    print(f"  p{p}: {np.percentile(errs, p):.3f} km")
print(f"  <100m: {(errs<0.1).mean()*100:.1f}%   <500m: {(errs<0.5).mean()*100:.1f}%   <2km: {(errs<2).mean()*100:.1f}%")

# --- Dataset procesado: SUTRAN accidentes geocodificado ---
acc = pd.read_csv("data/raw/sutran_accidentes/accidentes_carreteras_2020-2021_sutran.csv", sep=";", encoding="cp1252")

def to_km(v):
    s = str(v).strip().replace(",", ".")
    return float(s) if s.replace(".", "", 1).replace("-", "", 1).isdigit() else None

acc["KM"] = acc["KILOMETRO"].apply(to_km)
acc["FECHA_DT"] = pd.to_datetime(acc["FECHA"].astype(str), format="%Y%m%d", errors="coerce")
acc["CODIGO_VIA"] = acc["CODIGO_VÍA"]

lats, lons = [], []
n_ok = 0
for _, r in acc.iterrows():
    if r["KM"] is None or r["CODIGO_VIA"] not in geocode.routes():
        lats.append(None)
        lons.append(None)
        continue
    p = geocode.locate(r["CODIGO_VIA"], r["KM"])
    if p is None:
        lats.append(None)
        lons.append(None)
    else:
        lats.append(p.y)
        lons.append(p.x)
        n_ok += 1
acc["LATITUD_GEO"] = lats
acc["LONGITUD_GEO"] = lons
acc["GEOCODIFICADO"] = lats != None
print(f"\nSUTRAN accidentes: total={len(acc)}  geocodificados={n_ok} ({100*n_ok/len(acc):.1f}%)")

import os
os.makedirs("data/processed", exist_ok=True)
acc.to_csv("data/processed/sutran_accidentes_geocod.csv", index=False, encoding="utf-8-sig")
print("guardado data/processed/sutran_accidentes_geocod.csv")
