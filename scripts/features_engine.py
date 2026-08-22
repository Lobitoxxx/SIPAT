"""Feature engineering: sinuosidad por tramo y dataset listo para modelar."""
import numpy as np
import pandas as pd

import geocode
from geocode import _load, _haversine

_load()

# sinuosidad por tramo
rows = []
for i, s in enumerate(geocode._SEGMENTS):
    pts = list(s["geom"].coords)
    geodesic = sum(_haversine(pts[j], pts[j + 1]) for j in range(len(pts) - 1))
    straight = _haversine(pts[0], pts[-1])
    rows.append({"id_tramo": i, "sinuosidad": geodesic / straight if straight > 0 else 1.0,
                 "n_vertices": len(pts), "long_geo_km": geodesic})

geo = pd.DataFrame(rows)
d = pd.read_csv("data/processed/dataset_tramos.csv")
d = d.merge(geo, on="id_tramo", how="left")

# numericos
d["carriles"] = pd.to_numeric(d["carriles"], errors="coerce").replace(0, np.nan)
d["vel_proy"] = pd.to_numeric(d["vel_proy"], errors="coerce")
d["dist_ingemmet_km"] = pd.to_numeric(d["dist_ingemmet_km"], errors="coerce")
d["dist_peajes_km"] = pd.to_numeric(d["dist_peajes_km"], errors="coerce")
d["dist_cinemometros_km"] = pd.to_numeric(d["dist_cinemometros_km"], errors="coerce")

# categorias de velocidad de proyecto
d["vel_cat"] = pd.cut(d["vel_proy"], bins=[0, 60, 80, 100, 200],
                      labels=["<60", "60-80", "80-100", ">100"])
# estado superficie simplificado
d["sup_buena"] = (d["superficie"] == "Buena").astype(int)

# control: red de alta velocidad (panamericana: 1N,1S,1SD)
d["es_panamericana"] = d["ruta"].str.startswith("PE-1").astype(int)

# exposicion (km) -> offset
d["expo_km"] = d["long_km"].clip(lower=0.001)

# variable objetivo estandarizada por año: ONSV cubre 2021-2025; 2025 es parcial (~1/3)
# usamos conteo total 2021-2025 con offset log(km)
d["y_onsv"] = d["onsv_n"]
d["y_fal"] = d["onsv_fallecidos"]

d.to_csv("data/processed/dataset_modelo.csv", index=False, encoding="utf-8-sig")
print("dataset_modelo.csv:", d.shape)
print(d[["sinuosidad", "carriles", "vel_proy", "vel_cat", "sup_buena", "es_panamericana"]].head().to_string())
print("\nvel_cat:")
print(d["vel_cat"].value_counts(dropna=False).to_string())
print("\nsinuosidad describe:")
print(d["sinuosidad"].describe().round(3).to_string())
