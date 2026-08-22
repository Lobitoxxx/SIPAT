"""Features espaciales por tramo de la red (SINAC + siniestros + exposicion)."""
import json

import numpy as np
import pandas as pd
from shapely.geometry import Point, box
from shapely.strtree import STRtree

import geocode
from geocode import _load

_load()
segs = geocode._SEGMENTS
geoms = [s["geom"] for s in segs]
tree = STRtree(geoms)
id_by_geom = {id(g): i for i, g in enumerate(geoms)}

KM = 111.32  # grados -> km aprox


def haversine_km(p1, p2):
    from geocode import _haversine
    return _haversine((p1.x, p1.y), (p2.x, p2.y))


def nearest_features(points, max_n=3):
    """Por cada tramo: distancia (km) a los max_n vecinos y conteos."""
    out = {i: {} for i in range(len(segs))}
    return out


# ---- por tramo: distancia al vecino mas cercano de cada capa ----
layers = {}

# INGEMMET (todos los puntos de peligros)
ing = []
for lyr in ["layer0_Peligros_Geológicos", "layer1_Otros_Peligros_Geológicos", "layer2_Zonas_Críticas"]:
    d = json.load(open(f"data/raw/ingemmet/{lyr}.geojson", encoding="utf-8"))
    for f in d["features"]:
        c = f["geometry"]
        ing.append(Point(c["x"], c["y"]))
layers["ingemmet"] = np.array(ing, dtype=object)
print(f"ingemmet pts: {len(ing)}")

# peajes
peajes = []
gj = json.load(open("data/raw/mtc_flujo_peajes/unidades_peaje_2024-2025.geojson", encoding="utf-8"))
for f in gj["features"]:
    c = f["geometry"]["coordinates"]
    peajes.append(Point(c[0], c[1]))
layers["peajes"] = np.array(peajes, dtype=object)
print(f"peajes: {len(peajes)}")

# cinemometros (muestra para velocidad)
cin = pd.read_csv("data/processed/cinemometros_clean.csv")
cin_pts = np.array([Point(x, y) for x, y in zip(cin["LONGITUD"], cin["LATITUD"])], dtype=object)
layers["cinemometros"] = cin_pts
print(f"cinemometros: {len(cin_pts)}")


def build_forest(layer):
    idx = STRtree([Point(p.x, p.y) for p in layer])
    return idx


forests = {k: build_forest(v) for k, v in layers.items()}

# resultados por tramo
res = {i: {} for i in range(len(segs))}
for i, g in enumerate(geoms):
    mid = Point((g.coords[0][0] + g.coords[-1][0]) / 2, (g.coords[0][1] + g.coords[-1][1]) / 2)
    res[i]["lon_mid"] = mid.x
    res[i]["lat_mid"] = mid.y
    for name, f in forests.items():
        near = f.nearest(mid)
        if near is not None and not hasattr(near, "x"):
            near = layers[name][int(near)]
        res[i][f"dist_{name}_km"] = haversine_km(mid, near) if near is not None else np.nan
        # conteos por radio (caja aproximada)
        if name == "ingemmet":
            r5 = 5.0 / KM
            hits = f.query(box(mid.x - r5, mid.y - r5, mid.x + r5, mid.y + r5), predicate="intersects")
            res[i]["ingemmet_c5km"] = len(hits)
        elif name == "cinemometros":
            r2 = 2.0 / KM
            hits = f.query(box(mid.x - r2, mid.y - r2, mid.x + r2, mid.y + r2), predicate="intersects")
            res[i]["cinemometros_c2km"] = len(hits)
            r10 = 10.0 / KM
            hits10 = f.query(box(mid.x - r10, mid.y - r10, mid.x + r10, mid.y + r10), predicate="intersects")
            res[i]["cinemometros_c10km"] = len(hits10)

feat = pd.DataFrame(res).T.reset_index().rename(columns={"index": "id_tramo"})
feat.to_csv("data/processed/features_distancia.csv", index=False, encoding="utf-8-sig")
print("features_distancia.csv:", feat.shape)

# ---- siniestros por tramo ----
tramos = pd.read_csv("data/processed/tramos_red.csv", encoding="utf-8-sig")

onsv = pd.read_csv("data/processed/onsv_nacional_geocod.csv", encoding="utf-8-sig")
onsv["km_red"] = pd.to_numeric(onsv["km_red"], errors="coerce")
onsv["fallecidos"] = pd.to_numeric(onsv["fallecidos"], errors="coerce")

# asignar tramo por ruta + km_red
def tramo_id(ruta, km):
    if pd.isna(km):
        return np.nan
    m = (tramos["ruta"] == ruta) & (tramos["km0"] <= km) & (tramos["km1"] >= km)
    hit = tramos[m]
    if len(hit) == 0:
        return np.nan
    return int(hit.iloc[0]["id_tramo"])

onsv["id_tramo"] = [tramo_id(r, k) for r, k in zip(onsv["COD CARRETERA"], onsv["km_red"])]
cnt = onsv.groupby("id_tramo").size().rename("onsv_n")
fal = onsv.groupby("id_tramo")["fallecidos"].sum().rename("onsv_fallecidos")
a = onsv[onsv["fallecidos"] > 1].groupby("id_tramo").size().rename("onsv_multiples")

# SUTRAN geocodificado
sut = pd.read_csv("data/processed/sutran_accidentes_geocod.csv", encoding="utf-8-sig")
sut["KM"] = pd.to_numeric(sut["KM"], errors="coerce")
sut["id_tramo"] = [tramo_id(r, k) if r in set(tramos["ruta"]) else np.nan
                   for r, k in zip(sut["CODIGO_VIA"], sut["KM"])]
sut["fallecidos_n"] = pd.to_numeric(sut["FALLECIDOS"], errors="coerce")
sut_cnt = sut.groupby("id_tramo").size().rename("sutran_n")
sut_fal = sut.groupby("id_tramo")["fallecidos_n"].sum().rename("sutran_fallecidos")

analisis = tramos.merge(cnt, on="id_tramo", how="left").merge(fal, on="id_tramo", how="left").merge(
    a, on="id_tramo", how="left").merge(sut_cnt, on="id_tramo", how="left").merge(sut_fal, on="id_tramo", how="left")
analisis = analisis.merge(feat, on="id_tramo", how="left")
for c in ["onsv_n", "onsv_fallecidos", "onsv_multiples", "sutran_n", "sutran_fallecidos"]:
    analisis[c] = analisis[c].fillna(0).astype(int)
analisis["siniestros_km"] = analisis["onsv_n"] / analisis["long_km"].replace(0, np.nan)
analisis["fallecidos_km"] = analisis["onsv_fallecidos"] / analisis["long_km"].replace(0, np.nan)
analisis.to_csv("data/processed/dataset_tramos.csv", index=False, encoding="utf-8-sig")
print("dataset_tramos.csv:", analisis.shape)
print(analisis[["onsv_n", "onsv_fallecidos", "sutran_n", "dist_ingemmet_km", "dist_peajes_km", "dist_cinemometros_km", "siniestros_km"]].describe().round(3).to_string())
