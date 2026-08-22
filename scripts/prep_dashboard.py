"""Prepara archivos ligeros para el dashboard (data/processed/dashboard/)."""
import json
import os

import numpy as np
import pandas as pd
import shapefile

import geocode
from geocode import _load

OUT = "data/processed/dashboard"
os.makedirs(OUT, exist_ok=True)

# ---------- 1. Eventos ONSV limpios ----------
onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
cols = list(onsv.columns)
fecha = [c for c in cols if "FECHA" in c.upper() and "CORTE" not in c.upper()][0]
hora = [c for c in cols if c.upper() == "HORA SINIESTRO"][0]
clima = [c for c in cols if "CONDICI" in c.upper()][0]
sup = [c for c in cols if "SUPERFICIE DE" in c.upper()][0]
sv = [c for c in cols if "VERTICAL" in c.upper() and "EXISTE" in c.upper()]
sh = [c for c in cols if "HORIZONTAL" in c.upper() and "EXISTE" in c.upper()]
causa = [c for c in cols if "CAUSA FACTOR" in c.upper()][0]

ev = pd.DataFrame({
    "fecha": pd.to_datetime(onsv[fecha], format="%d/%m/%Y", errors="coerce"),
    "hora": pd.to_numeric(onsv[hora].astype(str).str.replace(":", ".", 1), errors="coerce"),
    "clase": onsv["CLASE SINIESTRO"],
    "depto": onsv["DEPARTAMENTO"],
    "provincia": onsv["PROVINCIA"],
    "distrito": onsv["DISTRITO"],
    "red_vial": onsv["RED VIAL"],
    "ruta": onsv["COD CARRETERA"],
    "clima": onsv[clima],
    "superficie": onsv[sup],
    "causa": onsv[causa],
    "senal_vertical": onsv[sv[0]] if sv else None,
    "senal_horizontal": onsv[sh[0]] if sh else None,
    "lat": pd.to_numeric(onsv["COORDENADAS LATITUD"], errors="coerce"),
    "lon": pd.to_numeric(onsv["COORDENADAS  LONGITUD"], errors="coerce"),
    "fallecidos": pd.to_numeric(onsv["CANTIDAD DE FALLECIDOS"], errors="coerce"),
    "lesionados": pd.to_numeric(onsv["CANTIDAD DE LESIONADOS"], errors="coerce"),
})
ev["anio"] = ev["fecha"].dt.year
ev["mes"] = ev["fecha"].dt.month
ev["dia_semana"] = ev["fecha"].dt.dayofweek
ev["hora3"] = (ev["hora"] // 3) * 3
ev.to_csv(f"{OUT}/onsv_events.csv", index=False, encoding="utf-8-sig")
print(f"onsv_events.csv: {len(ev)} eventos")

# ---------- 2. Tramos con geometria + metricas ----------
_load()
d = pd.read_csv("data/processed/dataset_modelo.csv")
sf = shapefile.Reader(geocode.SH, encoding="iso-8859-1")
fields = [f[0] for f in sf.fields[1:]]

geo = {}
for rec, shp in zip(sf.iterRecords(), sf.iterShapes()):
    a = dict(zip(fields, list(rec)))
    geo[a["cCodRutaDi"]] = shp.points

tramos = []
for i, r in d.iterrows():
    pts = geo.get(r["ruta"], [])
    # tramo i corresponde al segmento i (orden de iteracion del shapefile)
    if pts and len(pts) >= 2:
        coords = [[p[0], p[1]] for p in pts]
    else:
        coords = [[r["lon_mid"], r["lat_mid"]]]
    tramos.append({
        "id": int(r["id_tramo"]),
        "ruta": r["ruta"],
        "km0": round(r["km0"], 3),
        "km1": round(r["km1"], 3),
        "region": str(r["region"]),
        "topografia": str(r["topografia"]),
        "superficie": str(r["superficie"]),
        "vel_proy": (None if pd.isna(r["vel_proy"]) else round(r["vel_proy"], 1)),
        "carriles": (None if pd.isna(r["carriles"]) else int(r["carriles"])),
        "sinuosidad": round(r["sinuosidad"], 3),
        "onsv_n": int(r["onsv_n"]),
        "fallecidos": int(r["onsv_fallecidos"]),
        "sutran_n": int(r["sutran_n"]),
        "siniestros_km": round(r["siniestros_km"], 3),
        "dist_ingemmet_km": round(r["dist_ingemmet_km"], 2),
        "dist_peajes_km": round(r["dist_peajes_km"], 1),
        "dist_cinemometros_km": round(r["dist_cinemometros_km"], 1),
        "coords": coords,
        "lon_mid": round(r["lon_mid"], 5),
        "lat_mid": round(r["lat_mid"], 5),
    })
with open(f"{OUT}/tramos_geo.json", "w", encoding="utf-8") as f:
    json.dump(tramos, f)
print(f"tramos_geo.json: {len(tramos)} tramos")

# ---------- 3. Puntos negros con coords ----------
pn = pd.read_csv("data/processed/puntos_negros.csv")
pn2 = pn.merge(d[["ruta", "km0", "km1", "lon_mid", "lat_mid"]], on=["ruta", "km0", "km1"], how="left")
puntos = []
for _, r in pn2.iterrows():
    puntos.append({
        "ruta": r["ruta"], "km0": round(r["km0"], 2), "km1": round(r["km1"], 2),
        "siniestros": int(r["y_onsv"]), "pred": round(r["pred"], 1),
        "residual": round(r["pearson"], 2),
        "lat": round(r["lat_mid"], 5), "lon": round(r["lon_mid"], 5),
    })
with open(f"{OUT}/puntos_negros.json", "w", encoding="utf-8") as f:
    json.dump(puntos, f)
print(f"puntos_negros.json: {len(puntos)}")

# ---------- 4. IRRs del modelo ----------
d3 = d.copy()
d3["vel_proy"] = d3["vel_proy"].fillna(d3["vel_proy"].median())
d3["carriles"] = d3["carriles"].fillna(d3["carriles"].median())
reg = pd.get_dummies(d3["region"], prefix="reg", drop_first=True)
top = pd.get_dummies(d3["topografia"], prefix="top", drop_first=True)
X = pd.concat([reg, top], axis=1).astype(float)
X["carriles"] = d3["carriles"]
X["vel_proy"] = d3["vel_proy"]
X["sinuosidad"] = d3["sinuosidad"].clip(upper=d3["sinuosidad"].quantile(0.99))
X["log_ingemmet"] = np.log1p(d3["dist_ingemmet_km"])
X["log_cine"] = np.log1p(d3["dist_cinemometros_km"])
X["sup_buena"] = d3["sup_buena"]
import statsmodels.api as sm
Xc = sm.add_constant(X)
y = d3["y_onsv"].values.astype(float)
m = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=1.0), offset=np.log(d3["expo_km"])).fit()
ci = m.conf_int()
labels = {
    "reg_SELVA": "Región: Selva", "reg_SIERRA": "Región: Sierra",
    "top_ONDULADO": "Terreno ondulado", "top_PLANO": "Terreno plano",
    "carriles": "Carriles (por carril)", "vel_proy": "Vel. proyecto (por +10 km/h)",
    "sinuosidad": "Sinuosidad", "log_ingemmet": "Dist. INGEMMET (log, cerca=+)",
    "log_cine": "Dist. cinemómetro (log, cerca=+)", "sup_buena": "Superficie buena",
}
irrs = pd.DataFrame({
    "variable": [k for k in labels],
    "label": [labels[k] for k in labels],
    "irr": [float(np.exp(m.params[k])) for k in labels],
    "irr_low": [float(np.exp(ci.loc[k, 0])) for k in labels],
    "irr_high": [float(np.exp(ci.loc[k, 1])) for k in labels],
    "p": [float(m.pvalues[k]) for k in labels],
})
irrs.to_csv(f"{OUT}/irrs.csv", index=False, encoding="utf-8-sig")
print("irrs.csv OK (alpha=1.0, sin cluster)")

print("\nDASHBOARD DATA LISTO")
