"""Analiza errores de peajes en detalle (rutas, km, nombres)."""
import json

import numpy as np
from shapely.geometry import Point

import geocode

gj = json.load(open("data/raw/mtc_flujo_peajes/unidades_peaje_2024-2025.geojson", encoding="utf-8"))
rows = []
for f in gj["features"]:
    p = f["properties"]
    coords = f["geometry"]["coordinates"]
    rows.append({"ruta": p["CODRUTA"], "km": float(p["INICIO"]), "lon": coords[0], "lat": coords[1],
                 "nom": p["NOMBRE"], "depto": p["DEPARTAMEN"]})

res = []
for r in rows:
    pt = geocode.locate(r["ruta"], r["km"])
    if pt is None:
        res.append((None, r))
        continue
    real = Point(r["lon"], r["lat"])
    res.append((real.distance(pt) * 111.32, r))

ok = [r for r in res if r[0] is not None]
errs = np.array([r[0] for r in ok])
print(f"peajes con ruta: {len(ok)}/{len(rows)}")
print(f"  <1km: {(errs<1).mean()*100:.1f}%  <2km: {(errs<2).mean()*100:.1f}%  <5km: {(errs<5).mean()*100:.1f}%")
print(f"  >=20km: {(errs>=20).sum()}")

by_ruta = {}
for e, r in ok:
    by_ruta.setdefault(r["ruta"], []).append(e)
print("\nerror mediano por ruta (con >=5 peajes):")
for ruta, es in sorted(by_ruta.items(), key=lambda kv: -len(kv[1])):
    if len(es) >= 5:
        print(f"  {ruta}: n={len(es)}  mediana={np.median(es):.2f} km")

print("\npeores 15:")
for e, r in sorted(ok, key=lambda x: -(x[0] or 0))[:15]:
    print(f"  {e:8.1f} km  {r['nom'][:28]:28s} {r['ruta']} km {r['km']:.0f}  ({r['depto'][:18]})")

print("\nmejores 15:")
for e, r in sorted(ok, key=lambda x: x[0] or 0)[:15]:
    print(f"  {e:8.3f} km  {r['nom'][:28]:28s} {r['ruta']} km {r['km']:.0f}  ({r['depto'][:18]})")
