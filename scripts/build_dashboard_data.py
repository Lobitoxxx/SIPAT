#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Construye tramos_geo.json unificado con ONSV + SUTRAN + OSITRAN + alertas históricas.
Genera también eventos CSV por fuente para tabs 1-5.
"""
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.spatial import cKDTree

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from scripts.riesgo_red import RiesgoIndex

OUT_DIR = ROOT / "data" / "processed" / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── 1. Cargar tramos base (modelo) ─────────────────────────────────────
print("[1/8] Cargando dataset_modelo.csv (3750 tramos base)...")
df_tramos = pd.read_csv(ROOT / "data" / "processed" / "dataset_modelo.csv")
# Dropear columnas ONSV/SUTRAN existentes para re-agregar desde fuentes frescas
drop_cols = [c for c in df_tramos.columns if c.startswith(("onsv_", "sutran_", "y_onsv", "y_fal"))]
if drop_cols:
    df_tramos = df_tramos.drop(columns=drop_cols)

# Cargar geometrías desde tramos_geo.json original
print("     Cargando geometrías desde tramos_geo.json...")
with open(OUT_DIR / "tramos_geo.json", encoding="utf-8") as f:
    tramos_geo_orig = json.load(f)
coords_map = {int(t["id"]): t["coords"] for t in tramos_geo_orig}
df_tramos["coords"] = df_tramos["id_tramo"].map(coords_map)
print(f"     Tramos: {len(df_tramos)} (dropped {drop_cols})")

# ─── 2. ONSV: eventos geocodificados ────────────────────────────────────
print("[2/8] Cargando ONSV geocodificado...")
onsv = pd.read_csv(ROOT / "data" / "processed" / "onsv_nacional_geocod.csv")
onsv["fecha"] = pd.to_datetime(onsv["fecha"], errors="coerce")
onsv["anio"] = onsv["fecha"].dt.year
onsv["mes"] = onsv["fecha"].dt.month
onsv["dia_semana"] = onsv["fecha"].dt.dayofweek  # 0=Lun
onsv["hora3"] = (onsv["fecha"].dt.hour // 3) * 3

# Agregar por tramo (match por tramo_km0/tramo_km1)
onsv_agg = onsv.groupby(["tramo_km0", "tramo_km1"]).agg(
    onsv_n=("CÓDIGO SINIESTRO", "size"),
    onsv_fallecidos=("fallecidos", "sum"),
    onsv_lesionados=("CANTIDAD DE LESIONADOS", "sum"),
).reset_index()
onsv_agg.rename(columns={"tramo_km0": "km0", "tramo_km1": "km1"}, inplace=True)
print(f"     Tramos con ONSV: {len(onsv_agg)}")

# ─── 3. SUTRAN: eventos geocodificados ──────────────────────────────────
print("[3/8] Cargando SUTRAN geocodificado...")
sutran = pd.read_csv(ROOT / "data" / "processed" / "sutran_accidentes_geocod.csv")
sutran = sutran[sutran["GEOCODIFICADO"] == 1].copy()
sutran["fecha_dt"] = pd.to_datetime(sutran["FECHA_DT"], errors="coerce")
sutran["anio"] = sutran["fecha_dt"].dt.year
sutran["mes"] = sutran["fecha_dt"].dt.month
sutran["dia_semana"] = sutran["fecha_dt"].dt.dayofweek
sutran["hora3"] = (sutran["fecha_dt"].dt.hour // 3) * 3

# Match SUTRAN a tramos por distancia (cKDTree sobre centroides)
# Filtrar NaN en coords
sutran_geo = sutran.dropna(subset=["LONGITUD_GEO", "LATITUD_GEO"]).copy()
tramos_xy = df_tramos[["lon_mid", "lat_mid"]].values
tree = cKDTree(tramos_xy)
sutran_xy = sutran_geo[["LONGITUD_GEO", "LATITUD_GEO"]].values
dist, idx = tree.query(sutran_xy, k=1, distance_upper_bound=0.02)  # ~2km
sutran_geo["tramo_idx"] = idx
sutran_matched = sutran_geo[sutran_geo["tramo_idx"] < len(df_tramos)].copy()

sutran_agg = sutran_matched.groupby("tramo_idx").agg(
    sutran_n=("FECHA", "size"),
    sutran_fallecidos=("FALLECIDOS", "sum"),
    sutran_heridos=("HERIDOS", "sum"),
).reset_index()
print(f"     Tramos con SUTRAN matched: {len(sutran_agg)}")

# ─── 4. OSITRAN: accidentes + tramos concesionados ──────────────────────
print("[4/8] Cargando OSITRAN...")
ositran_acc = pd.read_csv(ROOT / "data" / "processed" / "ositran_accidentes.csv")
ositran_tramos = pd.read_csv(ROOT / "data" / "processed" / "ositran_tramos_geocod.csv")

# OSITRAN accidents: contar por ruta, distribuir proporcionalmente entre tramos de la ruta
ositran_by_ruta = ositran_acc.groupby("ruta").agg(
    ositran_n_total=("cant_accidentes", "sum"),
    ositran_total_afectados=("cant_afectados", "sum"),
    ositran_total_veh=("cant_vehinvolucrados", "sum"),
).reset_index()
print(f"     Tramos con OSITRAN accidentes por ruta: {len(ositran_by_ruta)}")

# ─── 5. Alertas históricas SUTRAN ───────────────────────────────────────
print("[5/8] Cargando alertas históricas SUTRAN...")
with open(ROOT / "data" / "processed" / "dashboard" / "sutran_alertas_historico.json", encoding="utf-8") as f:
    alertas_hist = json.load(f)
alertas_df = pd.DataFrame(alertas_hist)
alertas_df["lat"] = pd.to_numeric(alertas_df["lat"], errors="coerce")
alertas_df["lon"] = pd.to_numeric(alertas_df["lon"], errors="coerce")
alertas_df = alertas_df.dropna(subset=["lat", "lon"])

# Match alertas a tramos (buffer ~2km)
if len(alertas_df):
    alertas_xy = alertas_df[["lon", "lat"]].values
    dist_a, idx_a = tree.query(alertas_xy, k=1, distance_upper_bound=0.02)
    alertas_df["tramo_idx"] = idx_a
    alertas_matched = alertas_df[alertas_df["tramo_idx"] < len(df_tramos)].copy()
    
    # Ponderar por estado
    estado_peso = {"INTERRUMPIDO": 2.0, "RESTRINGIDO": 1.0, "NORMAL": 0.3, "TRANSITO NORMAL": 0.3}
    alertas_matched["peso"] = alertas_matched["estado"].map(estado_peso).fillna(0.5)
    
    alertas_agg = alertas_matched.groupby("tramo_idx").agg(
        alertas_hist_n=("item", "size"),
        alertas_hist_peso=("peso", "sum"),
    ).reset_index()
    print(f"     Tramos con alertas históricas: {len(alertas_agg)}")
else:
    alertas_agg = pd.DataFrame(columns=["tramo_idx", "alertas_hist_n", "alertas_hist_peso"])

# ─── 6. Merge todo a df_tramos ──────────────────────────────────────────
print("[6/8] Fusionando fuentes en tramos base...")

# ONSV merge por km0/km1
df = df_tramos.merge(onsv_agg, on=["km0", "km1"], how="left")

# SUTRAN merge por idx
df = df.merge(sutran_agg, left_index=True, right_on="tramo_idx", how="left")
df.drop(columns=["tramo_idx"], inplace=True, errors="ignore")

# OSITRAN merge por ruta - distribuir proporcionalmente entre tramos de la misma ruta
df = df.merge(ositran_by_ruta, on="ruta", how="left")

# Distribuir accidentes OSITRAN proporcionalmente a long_km dentro de cada ruta
df["long_km_safe"] = df["long_km"].replace(0, 0.001)
for ruta in df["ruta"].unique():
    mask = df["ruta"] == ruta
    total = df.loc[mask, "ositran_n_total"].iloc[0] if mask.any() and not pd.isna(df.loc[mask, "ositran_n_total"].iloc[0]) else 0
    if total > 0 and mask.sum() > 1:
        total_long = df.loc[mask, "long_km_safe"].sum()
        if total_long > 0:
            df.loc[mask, "ositran_n"] = (total * df.loc[mask, "long_km_safe"] / total_long).round()
    elif total > 0 and mask.sum() == 1:
        df.loc[mask, "ositran_n"] = total
    else:
        df.loc[mask, "ositran_n"] = 0

# Afectados/fallecidos similares (OSITRAN no distingue, usar afectados)
for ruta in df["ruta"].unique():
    mask = df["ruta"] == ruta
    total = df.loc[mask, "ositran_total_afectados"].iloc[0] if mask.any() and not pd.isna(df.loc[mask, "ositran_total_afectados"].iloc[0]) else 0
    if total > 0 and mask.sum() > 1:
        total_long = df.loc[mask, "long_km_safe"].sum()
        if total_long > 0:
            df.loc[mask, "ositran_fallecidos"] = (total * df.loc[mask, "long_km_safe"] / total_long).round()
            df.loc[mask, "ositran_heridos"] = (total * df.loc[mask, "long_km_safe"] / total_long).round()
    elif total > 0 and mask.sum() == 1:
        df.loc[mask, "ositran_fallecidos"] = total
        df.loc[mask, "ositran_heridos"] = total
    else:
        df.loc[mask, "ositran_fallecidos"] = 0
        df.loc[mask, "ositran_heridos"] = 0

df["ositran_n"] = df["ositran_n"].fillna(0).astype(int)
df["ositran_fallecidos"] = df["ositran_fallecidos"].fillna(0).astype(int)
df["ositran_heridos"] = df["ositran_heridos"].fillna(0).astype(int)

# Alertas merge por idx
df = df.merge(alertas_agg, left_index=True, right_on="tramo_idx", how="left")
df.drop(columns=["tramo_idx"], inplace=True, errors="ignore")

# Fillna - keep as float, convert to int in JSON output
cols_num = ["onsv_n", "onsv_fallecidos", "onsv_lesionados",
            "sutran_n", "sutran_fallecidos", "sutran_heridos",
            "ositran_n", "ositran_fallecidos", "ositran_heridos",
            "alertas_hist_n", "sutran_fal", "sutran_heridos"]
for c in cols_num:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).clip(lower=0)

# Peso columns as float
if "alertas_hist_peso" in df.columns:
    df["alertas_hist_peso"] = pd.to_numeric(df["alertas_hist_peso"], errors="coerce").fillna(0.0)

# Totales
df["siniestros_total"] = df["onsv_n"] + df["sutran_n"] + df["ositran_n"]
df["fallecidos_total"] = df["onsv_fallecidos"] + df["sutran_fallecidos"]  # OSITRAN no distingue fallecidos
df["lesionados_total"] = df["onsv_lesionados"] + df["sutran_heridos"] + df["ositran_heridos"]
df["long_km"] = df["km1"] - df["km0"]
df["siniestros_total_km"] = df["siniestros_total"] / df["long_km"].replace(0, np.nan)
df["fallecidos_total_km"] = df["fallecidos_total"] / df["long_km"].replace(0, np.nan)

print(f"     Tramos con siniestros_total>0: {(df.siniestros_total > 0).sum()}")

# ─── 7. Preparar salida JSON para dashboard ─────────────────────────────
print("[7/8] Preparando tramos_geo.json...")

# Reducir precision de coords para tamaño
def round_coords(coords, prec=5):
    return [[round(x, prec), round(y, prec)] for x, y in coords]

tramos_out = []
for _, t in df.iterrows():
    coords = json.loads(t["coords"]) if isinstance(t["coords"], str) else t["coords"]
    tramos_out.append({
        "id": int(t["id_tramo"]),
        "ruta": t["ruta"],
        "km0": float(t["km0"]),
        "km1": float(t["km1"]),
        "region": t["region"],
        "topografia": t["topografia"],
        "superficie": t["superficie"],
        "vel_proy": float(t["vel_proy"]),
        "carriles": float(t["carriles"]),
        "sinuosidad": float(t["sinuosidad"]),
        "long_km": float(t["long_km"]),
        # ONSV
        "onsv_n": int(t["onsv_n"]),
        "onsv_fallecidos": int(t["onsv_fallecidos"]),
        "onsv_lesionados": int(t["onsv_lesionados"]),
        # SUTRAN
        "sutran_n": int(t["sutran_n"]),
        "sutran_fallecidos": int(t["sutran_fallecidos"]),
        "sutran_heridos": int(t["sutran_heridos"]),
        # OSITRAN
        "ositran_n": int(t["ositran_n"]),
        "ositran_fallecidos": int(t["ositran_fallecidos"]),
        "ositran_heridos": int(t["ositran_heridos"]),
        # Totales
        "siniestros_total": int(t["siniestros_total"]),
        "fallecidos_total": int(t["fallecidos_total"]),
        "lesionados_total": int(t["lesionados_total"]),
        "siniestros_total_km": float(t["siniestros_total_km"]) if not np.isnan(t["siniestros_total_km"]) else 0.0,
        "fallecidos_total_km": float(t["fallecidos_total_km"]) if not np.isnan(t["fallecidos_total_km"]) else 0.0,
        # Alertas
        "alertas_hist_n": int(t.get("alertas_hist_n", 0)),
        "alertas_hist_peso": float(t.get("alertas_hist_peso", 0.0)),
        # Tráfico (ya en df_tramos como dist_peajes_km)
        "trafico_km": float(t.get("dist_peajes_km", 0.0)) if not np.isnan(t.get("dist_peajes_km", 0.0)) else 0.0,
        # Geometría
        "coords": round_coords(coords),
        "lon_mid": float(t["lon_mid"]),
        "lat_mid": float(t["lat_mid"]),
    })

with open(OUT_DIR / "tramos_geo.json", "w", encoding="utf-8") as f:
    json.dump(tramos_out, f, ensure_ascii=False)
print(f"     Guardado: {OUT_DIR / 'tramos_geo.json'} ({len(tramos_out)} tramos)")

# ─── 8. Exportar eventos CSV por fuente ─────────────────────────────────
print("[8/8] Exportando eventos CSV por fuente...")

# ONSV events - use actual column names
onsv_cols = ["fecha", "anio", "mes", "dia_semana", "hora3",
             "fallecidos", "CANTIDAD DE LESIONADOS", "CLASE SINIESTRO", "CAUSA FACTOR PRINCIPAL", "SUPERFICIE DE CALZADA",
             "TIPO DE VÍA", "RED VIAL", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
             "lat", "lon", "('ruta',)", "km_red"]
onsv_cols = [c for c in onsv_cols if c in onsv.columns]
onsv_out = onsv[onsv_cols].copy()
onsv_out.to_csv(OUT_DIR / "onsv_events.csv", index=False, encoding="utf-8-sig")
print(f"     onsv_events.csv: {len(onsv_out)} eventos")

# SUTRAN events
sutran_out = sutran_matched[["fecha_dt", "anio", "mes", "dia_semana", "hora3",
                              "FALLECIDOS", "HERIDOS", "MODALIDAD",
                              "DEPARTAMENTO", "CODIGO_VIA", "KILOMETRO",
                              "LATITUD_GEO", "LONGITUD_GEO"]].copy()
sutran_out.columns = ["fecha", "anio", "mes", "dia_semana", "hora3",
                       "fallecidos", "heridos", "modalidad",
                       "depto", "via_codigo", "kilometro",
                       "lat", "lon"]
sutran_out.to_csv(OUT_DIR / "sutran_events.csv", index=False, encoding="utf-8-sig")
print(f"     sutran_events.csv: {len(sutran_out)} eventos")

# OSITRAN events - join con tramos para lat/lon
# Normalizar tramo names
ositran_acc["tramo_norm"] = ositran_acc["tramo"].str.strip()
ositran_tramos["tramo_norm"] = ositran_tramos["tramo"].str.strip()
# Calcular centroides de tramos OSITRAN
ositran_tramos["lat_mid"] = (ositran_tramos["lat0"] + ositran_tramos["lat1"]) / 2
ositran_tramos["lon_mid"] = (ositran_tramos["lon0"] + ositran_tramos["lon1"]) / 2

# Join accidentes con tramos: siglas (en acc) = siglas (en tramos)
tramos_geo_os = ositran_tramos[["siglas", "tramo_norm", "lat_mid", "lon_mid"]].copy()
ositran_events = ositran_acc.merge(tramos_geo_os, on=["siglas", "tramo_norm"], how="left")
# Exponer lat/lon en el output
if "lat_mid" in ositran_events.columns:
    ositran_events["lat"] = ositran_events["lat_mid"]
if "lon_mid" in ositran_events.columns:
    ositran_events["lon"] = ositran_events["lon_mid"]
# Usar siglas como ruta
if "siglas" in ositran_events.columns:
    ositran_events["ruta"] = ositran_events["siglas"]

# OSITRAN no tiene fecha exacta, solo anio/mes - crear fecha aproximada (día 15)
ositran_events["fecha"] = pd.to_datetime(dict(year=ositran_events["anio"], month=ositran_events["mes"], day=15), errors="coerce")
ositran_events["dia_semana"] = ositran_events["fecha"].dt.dayofweek
ositran_events["hora3"] = 12  # mediodía por defecto

# Usar columnas disponibles
cols = ["fecha", "anio", "mes", "dia_semana", "hora3",
        "cant_afectados", "tipo", "causa", "CLIMA",
        "concesion"]
if "ruta" in ositran_events.columns:
    cols.append("ruta")
if "lat_mid" in ositran_events.columns:
    cols.append("lat_mid")
if "lon_mid" in ositran_events.columns:
    cols.append("lon_mid")

ositran_out = ositran_events[cols].copy()
# Renombrar
rename_map = {
    "cant_afectados": "heridos",
    "CLIMA": "clima",
    "lat_mid": "lat",
    "lon_mid": "lon"
}
ositran_out.columns = [rename_map.get(c, c) for c in ositran_out.columns]
# Añadir fallecidos (OSITRAN no los separa, usar 0 como placeholder)
ositran_out["fallecidos"] = 0
# Reordenar
cols_order = ["fecha", "anio", "mes", "dia_semana", "hora3",
              "fallecidos", "heridos", "tipo", "causa", "clima",
              "concesion", "ruta", "lat", "lon"]
cols_order = [c for c in cols_order if c in ositran_out.columns]
ositran_out = ositran_out[cols_order]
ositran_out.to_csv(OUT_DIR / "ositran_events.csv", index=False, encoding="utf-8-sig")
print(f"     ositran_events.csv: {len(ositran_out)} eventos")

# Stats resumen
df_stats = df[["id_tramo", "ruta", "km0", "km1", "region", "long_km",
               "onsv_n", "onsv_fallecidos", "sutran_n", "sutran_fallecidos",
               "ositran_n", "ositran_fallecidos", "siniestros_total", "fallecidos_total",
               "siniestros_total_km", "fallecidos_total_km",
               "alertas_hist_n", "alertas_hist_peso", "dist_peajes_km"]].copy()
df_stats.to_csv(OUT_DIR / "tramos_stats.csv", index=False, encoding="utf-8-sig")
print(f"     tramos_stats.csv: {len(df_stats)} tramos")

print("\n[OK] Build completado")