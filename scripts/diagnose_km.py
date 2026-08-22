"""Diagnostico: km real del punto proyectado sobre la ruta vs PROGRESIVA."""
import pandas as pd
from shapely.geometry import Point

import geocode
import numpy as np

# cargar segmentos indexados
cgm = pd.read_csv("data/raw/sutran_reportes_cgm/reportes_preliminares_cgm_2020-2021.csv", sep=";", encoding="cp1252")
cgm["lat"] = pd.to_numeric(cgm["LATITUD"], errors="coerce")
cgm["lon"] = pd.to_numeric(cgm["LONGITUD"], errors="coerce")
cgm["km"] = pd.to_numeric(cgm["PROGRESIVA"], errors="coerce")

sub = cgm[(cgm["CODIGO_VIA"].isin(geocode.routes())) & cgm["km"].notna() & cgm["lat"].notna()].copy()
print(f"muestra: {len(sub)}")


def project_to_km(lon, lat, route):
    """Devuelve el km aproximado del punto proyectado sobre la ruta."""
    pt = Point(lon, lat)
    best = None
    for s in geocode._SEGMENTS:
        if s["route"] != route:
            continue
        d = pt.distance(s["geom"])
        if best is None or d < best[0]:
            best = (d, s)
    if best is None:
        return None, None
    _, s = best
    # fraccion a lo largo del segmento
    geom = s["geom"]
    proj = geom.project(pt, normalized=True)
    km = s["km0"] + proj * (s["km1"] - s["km0"])
    return km, best[0] * 111.32


diffs = []
for _, r in sub.head(4000).iterrows():
    km_true, dseg = project_to_km(r["lon"], r["lat"], r["CODIGO_VIA"])
    if km_true is None:
        continue
    diffs.append(abs(km_true - r["km"]))
diffs = np.array(diffs)
print(f"|km_real - PROGRESIVA|: media={diffs.mean():.3f} mediana={np.median(diffs):.3f}")
for p in (75, 90, 95, 99):
    print(f"  p{p}: {np.percentile(diffs, p):.3f} km")
print(f"  <0.5km: {(diffs<0.5).mean()*100:.1f}%   <2km: {(diffs<2).mean()*100:.1f}%   <5km: {(diffs<5).mean()*100:.1f}%")

# rutas con errores grandes
res = []
for _, r in sub.iterrows():
    km_true, dseg = project_to_km(r["lon"], r["lat"], r["CODIGO_VIA"])
    if km_true is None:
        continue
    res.append((r["CODIGO_VIA"], abs(km_true - r["km"])))
big = pd.DataFrame(res, columns=["ruta", "err"])
print("\nTop rutas con |km| error > 5km:")
print(big[big["err"] > 5].groupby("ruta")["err"].agg(["count", "median"]).sort_values("count", ascending=False).head(10).to_string())
