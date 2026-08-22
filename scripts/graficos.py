"""Visualizaciones del proyecto SIPAT."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapefile

os.makedirs("docs/figuras", exist_ok=True)
plt.rcParams.update({"font.size": 9, "axes.titlesize": 11})

KM = 111.32

# ---------------- 1. Mapa de la red: siniestros por tramo ----------------
sf = shapefile.Reader(r"data/raw/mtc_datos_espaciales/rvn_dic16/red_vial_nacional_dic16.shp", encoding="iso-8859-1")
fields = [f[0] for f in sf.fields[1:]]
segs = []
for rec, sh in zip(sf.iterRecords(), sf.iterShapes()):
    a = dict(zip(fields, list(rec)))
    segs.append((a["cCodRutaDi"], sh.points))

d = pd.read_csv("data/processed/dataset_modelo.csv")
sini = dict(zip(d["id_tramo"], d["siniestros_km"]))

fig, ax = plt.subplots(figsize=(8, 12))
cmap = plt.cm.YlOrRd
vmax = 2.0
for i, (ruta, pts) in enumerate(segs):
    v = sini.get(i, 0.0)
    if v > 0:
        x, y = zip(*pts)
        c = cmap(min(v / vmax, 1.0))
        ax.plot(x, y, color=c, lw=1.2)
    else:
        x, y = zip(*pts)
        ax.plot(x, y, color="0.82", lw=0.6)
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, vmax))
plt.colorbar(sm, ax=ax, fraction=0.025, label="Siniestros fatales / km (2021-2025)")
ax.set_title("Siniestralidad fatal en la Red Vial Nacional\n(ONSV 2021-2025, por tramo)")
ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
fig.tight_layout()
fig.savefig("docs/figuras/mapa_siniestros_tramos.png", dpi=110)
plt.close(fig)
print("mapa_siniestros_tramos.png OK")

# ---------------- 2. Mapa puntos negros (residual > 1.5) ----------------
cand = pd.read_csv("data/processed/puntos_negros.csv")
cand2 = cand.merge(d[["ruta", "km0", "km1", "lon_mid", "lat_mid"]], on=["ruta", "km0", "km1"], how="left")

fig, ax = plt.subplots(figsize=(8, 12))
for ruta, pts in segs:
    x, y = zip(*pts)
    ax.plot(x, y, color="0.82", lw=0.6)
sc = ax.scatter(cand2["lon_mid"], cand2["lat_mid"], s=40, c=cand2["pearson"],
                cmap="Reds", edgecolor="black", lw=0.4, zorder=5)
plt.colorbar(sc, ax=ax, fraction=0.025, label="Residual (exceso siniestros)")
ax.set_title("Puntos negros: tramos con exceso de siniestros fatales\n(residual NegBin > 1.5)")
ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
fig.tight_layout()
fig.savefig("docs/figuras/mapa_puntos_negros.png", dpi=110)
plt.close(fig)
print("mapa_puntos_negros.png OK")

# ---------------- 3. Tendencia temporal ----------------
onsv = pd.read_excel("data/raw/onsv/siniestros_fatales_2021-2025.xlsx", sheet_name="SINIESTROS", header=4)
fecha = [c for c in onsv.columns if "FECHA" in c.upper() and "CORTE" not in c.upper()][0]
onsv["fecha"] = pd.to_datetime(onsv[fecha], format="%d/%m/%Y", errors="coerce")
onsv["fal"] = pd.to_numeric(onsv["CANTIDAD DE FALLECIDOS"], errors="coerce")

fig, axes = plt.subplots(2, 2, figsize=(10, 7))
# por año
g = onsv.groupby(onsv["fecha"].dt.year).agg(n=("fecha", "size"), fal=("fal", "sum"))
axes[0, 0].bar(g.index.astype(int), g["n"], color="#b02a2a", label="Siniestros")
axes[0, 0].set_title("Siniestros fatales por año (2025 preliminar)")
axes[0, 0].set_ylabel("Nº siniestros")
for x, v in zip(g.index, g["n"]):
    axes[0, 0].text(x, v, str(int(v)), ha="center", va="bottom", fontsize=8)
# por mes
m = onsv[onsv["fecha"].dt.year < 2025].groupby(onsv["fecha"].dt.month).size()
axes[0, 1].plot(m.index, m.values, "o-", color="#b02a2a")
axes[0, 1].set_title("Siniestros por mes (2021-2024)")
axes[0, 1].set_ylabel("Nº siniestros")
axes[0, 1].set_xticks(range(1, 13))
# por dia de semana
dias = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
dow = onsv.groupby(onsv["fecha"].dt.dayofweek).size()
axes[1, 0].bar(range(7), dow.values, color="#b02a2a")
axes[1, 0].set_xticks(range(7)); axes[1, 0].set_xticklabels(dias)
axes[1, 0].set_title("Siniestros por día de la semana")
axes[1, 0].set_ylabel("Nº siniestros")
# fallecidos/siniestro por año
axes[1, 1].plot(g.index.astype(int), (g["fal"] / g["n"]).values, "o-", color="#b02a2a")
axes[1, 1].set_title("Fallecidos por siniestro (gravedad)")
axes[1, 1].set_ylabel("Fallecidos / siniestro")
axes[1, 1].set_ylim(1.1, 1.3)
fig.suptitle("Panorama temporal ONSV 2021-2025", y=1.0)
fig.tight_layout()
fig.savefig("docs/figuras/tendencia_temporal.png", dpi=110)
plt.close(fig)
print("tendencia_temporal.png OK")

# ---------------- 4. Ranking rutas ----------------
nat = onsv[onsv["RED VIAL"] == "NACIONAL"]
gr = nat.groupby("COD CARRETERA").size().sort_values(ascending=False).head(15)
fig, ax = plt.subplots(figsize=(7, 6))
ax.barh(gr.index[::-1], gr.values[::-1], color="#b02a2a")
ax.set_title("Top 15 rutas por siniestros fatales (red nacional)")
ax.set_xlabel("Nº siniestros")
fig.tight_layout()
fig.savefig("docs/figuras/ranking_rutas.png", dpi=110)
plt.close(fig)
print("ranking_rutas.png OK")

# ---------------- 5. Mapa de regiones + peajes + ingemmet ----------------
fig, ax = plt.subplots(figsize=(8, 12))
for ruta, pts in segs:
    x, y = zip(*pts)
    ax.plot(x, y, color="0.82", lw=0.6)
# INGEMMET muestreo
import json
ing = json.load(open("data/raw/ingemmet/layer0_Peligros_Geológicos.geojson", encoding="utf-8"))
ix = [f["geometry"]["x"] for f in ing["features"][::5]]
iy = [f["geometry"]["y"] for f in ing["features"][::5]]
ax.scatter(ix, iy, s=1.5, c="orange", alpha=0.5, label="INGEMMET (peligros geol.)", zorder=3)
# peajes
gj = json.load(open("data/raw/mtc_flujo_peajes/unidades_peaje_2024-2025.geojson", encoding="utf-8"))
px = [f["geometry"]["coordinates"][0] for f in gj["features"]]
py = [f["geometry"]["coordinates"][1] for f in gj["features"]]
ax.scatter(px, py, s=25, c="navy", marker="^", edgecolor="black", lw=0.3, label="Peajes MTC", zorder=4)
# cinemometros muestra
cin = pd.read_csv("data/processed/cinemometros_clean.csv")
cx = cin["LONGITUD"].values[::40]; cy = cin["LATITUD"].values[::40]
ax.scatter(cx, cy, s=2, c="green", alpha=0.6, label="Cinemómetros (muestra)", zorder=3)
ax.set_title("Contexto espacial: red vial, peligros geológicos, peajes y cinemómetros")
ax.legend(loc="lower left", fontsize=7, markerscale=1)
ax.set_xlabel("Longitud"); ax.set_ylabel("Latitud")
fig.tight_layout()
fig.savefig("docs/figuras/contexto_espacial.png", dpi=110)
plt.close(fig)
print("contexto_espacial.png OK")

# ---------------- 6. Forest plot de IRRs ----------------
import statsmodels.api as sm
d3 = pd.read_csv("data/processed/dataset_modelo.csv")
d3["vel_proy"] = d3["vel_proy"].fillna(d3["vel_proy"].median())
d3["carriles"] = d3["carriles"].fillna(d3["carriles"].median())
d3["sinuosidad"] = d3["sinuosidad"].clip(upper=d3["sinuosidad"].quantile(0.99))
reg = pd.get_dummies(d3["region"], prefix="reg", drop_first=True)
top = pd.get_dummies(d3["topografia"], prefix="top", drop_first=True)
X = pd.concat([reg, top], axis=1).astype(float)
X["carriles"] = d3["carriles"]
X["vel_proy"] = d3["vel_proy"]
X["sinuosidad"] = d3["sinuosidad"]
X["log_ingemmet"] = np.log1p(d3["dist_ingemmet_km"])
X["log_cine"] = np.log1p(d3["dist_cinemometros_km"])
X["sup_buena"] = d3["sup_buena"]
Xc = sm.add_constant(X)
y = d3["y_onsv"].values.astype(float)
m = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=1.0), offset=np.log(d3["expo_km"])).fit()
ci = m.conf_int()
labels = ["Región: Selva", "Región: Sierra", "Terr. ondulado", "Terr. plano",
          "Carriles (por carril)", "Vel. proyecto (por km/h)", "Sinuosidad",
          "Dist. INGEMMET (log, más cerca=+)", "Dist. cinemómetro (log, más cerca=+)",
          "Superficie buena"]
fig, ax = plt.subplots(figsize=(7, 6))
idx = np.arange(len(labels))
vals = np.exp(m.params[1:])
lo = np.exp(ci.iloc[1:, 0]); hi = np.exp(ci.iloc[1:, 1])
colors = ["#444"] * len(labels)
for k in [0, 1, 5, 6, 8, 9]:
    colors[k] = "#b02a2a"
ax.axvline(1, color="0.4", lw=0.8, ls="--")
ax.errorbar(vals, idx, xerr=[vals - lo, hi - vals], fmt="o", ms=5, color="#b02a2a", capsize=3)
for v, i in zip(vals, idx):
    ax.text(v, i, f" {v:.2f}", va="center", fontsize=8)
ax.set_yticks(idx); ax.set_yticklabels(labels)
ax.set_xscale("log")
ax.set_xlim(0.3, 5)
ax.set_xlabel("IRR (razón de tasas) — escala log")
ax.set_title("Modelo NegBin: factores asociados a siniestros fatales por km\n(color rojo: significativo p<0.05)")
fig.tight_layout()
fig.savefig("docs/figuras/irr_modelo.png", dpi=110)
plt.close(fig)
print("irr_modelo.png OK")

print("\nTODAS LAS FIGURAS GENERADAS")
