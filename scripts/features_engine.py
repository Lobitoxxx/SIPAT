"""Feature engineering: sinuosidad por tramo y dataset listo para modelar.

DEFECTO CORREGIDO (ver tests/test_features_engine.py)
----------------------------------------------------
El archivo decía, en un comentario:

    # variable objetivo estandarizada por año: ONSV cubre 2021-2025; 2025 es parcial
    d["y_onsv"] = d["onsv_n"]

y expuesta en km:

    d["expo_km"] = d["long_km"]

Las dos frases eran ciertas y ninguna se aplicaba. `y_onsv` era el conteo bruto y
`expo_km` era km, no km·año: dos tramos con distinta cobertura temporal tenían el
mismo denominador. "Estandarizada por año" era una etiqueta sin implementación, que
es la forma más difícil de detectar de un bug: el código funcionaba y la promesa no.

Ahora la exposición se construye en **km·año**, que es lo que hace comparables
tramos con distinta cobertura, y el conteo por año vive en un panel
(`panel_anual.py`) que el holdout temporal necesita. La densidad anual por km es
lo comparable entre años, no el conteo bruto.
"""
import numpy as np
import pandas as pd

import geocode
from geocode import _load, _haversine

import panel_anual

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

# ─── Exposición real: km·año, no km ──────────────────────────────────────
# El panel cuenta los siniestros por tramo y año. `n_anios_cubiertos` es el
# tamaño de la rejilla: la exposición de un tramo es su longitud por ese número
# de años, no su longitud a secas.
ONSV_GEOCOD = "data/processed/onsv_nacional_geocod.csv"
onsv = pd.read_csv(ONSV_GEOCOD)
onsv["fecha_dt"] = pd.to_datetime(onsv["fecha"], errors="coerce")
onsv["fallecidos"] = pd.to_numeric(onsv["fallecidos"], errors="coerce")
onsv["km_red"] = pd.to_numeric(onsv["km_red"], errors="coerce")

# Asignación por (ruta, km en la red): la misma que produjo `onsv_n`, para que
# el panel y el agregado no puedan discrepar (la guardia de abajo lo verifica).
eventos = panel_anual.asignar_por_km_red(
    onsv,
    d.rename(columns={"ruta": "ruta", "km0": "km0", "km1": "km1"}),
    col_ruta="COD CARRETERA",
    col_km="km_red",
)
ANIOS = sorted(int(a) for a in eventos["anio"].dropna().unique())
panel = panel_anual.construir_panel(
    eventos,
    tramo_ids=d["id_tramo"],
    long_km=d["long_km"],
    anios=ANIOS,
)

d["n_anios_cubiertos"] = len(ANIOS)
agregado = panel_anual.panel_a_agregado_tramo(panel, prefijo="onsv_p_")
agregado.index.name = "id_tramo"
d = d.merge(agregado, left_on="id_tramo", right_index=True, how="left")
d["onsv_p_anios_con_evento"] = d["onsv_p_anios_con_evento"].fillna(0).astype(int)
d["anios_sin_siniestro"] = d["n_anios_cubiertos"] - d["onsv_p_anios_con_evento"]

d["expo_km"] = pd.to_numeric(d["long_km"], errors="coerce").clip(lower=0.001)
d["expo_km_anio"] = d["expo_km"] * d["n_anios_cubiertos"]

# Objetivo: conteo y densidad anual. Las dos cosas, porque cada modelo necesita
# una: `y_onsv` con offset en km·año para el NegBin, y `densidad_anual` para
# comparar tramos y años sin que la longitud domine el número.
d["y_onsv"] = pd.to_numeric(d["onsv_n"], errors="coerce").fillna(0)
d["y_fal"] = pd.to_numeric(d["onsv_fallecidos"], errors="coerce").fillna(0)
d["densidad_anual"] = np.where(d["expo_km"] > 0, d["y_onsv"] / d["expo_km_anio"], np.nan)

# Coherencia: el panel y el agregado por tramo tienen que decir lo mismo.
desajuste = int((d["onsv_p_total"].fillna(0) != d["y_onsv"]).sum())
if desajuste:
    raise SystemExit(
        f"El panel anual y 'onsv_n' no coinciden en {desajuste} tramos. Si "
        "'onsv_n' viene de otra asignación de eventos, alinea la asignación "
        "antes de usar el panel: exposición y respuesta tienen que salir del "
        "mismo emparejamiento."
    )

d.to_csv("data/processed/dataset_modelo.csv", index=False, encoding="utf-8-sig")
print("dataset_modelo.csv:", d.shape)
print(d[["sinuosidad", "carriles", "vel_proy", "vel_cat", "sup_buena", "es_panamericana"]].head().to_string())
print("\nvel_cat:")
print(d["vel_cat"].value_counts(dropna=False).to_string())
print("\nsinuosidad describe:")
print(d["sinuosidad"].describe().round(3).to_string())
print(f"\naños cubiertos: {len(ANIOS)} ({ANIOS[0]}-{ANIOS[-1]})")
print(f"km·año totales: {d['expo_km_anio'].sum():,.0f}")
print(f"densidad global: {d['y_onsv'].sum() / d['expo_km_anio'].sum():.4f} sini/km·año")
print("\nsiniestro por año (panel):")
print(panel.groupby("anio")["n_eventos"].sum().to_string())