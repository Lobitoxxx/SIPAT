#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modelos NegBin multi-fuente para el dashboard (tab5).
Reentrena el modelo de Fase 1 pero con tres respuestas:
  1. y_onsv (ONSV)        - modelo original
  2. y_sutran (SUTRAN)    - nuevo (matched a tramos)
  3. y_total (combinado)  - ONSV + SUTRAN + OSITRAN

Calcula IRRs (Incidence Rate Ratios) con IC95% y p-values.
Guarda: irrs_multi.csv, modelo_stats_multi.json
"""
import sys
import os
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from scipy.spatial import cKDTree

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from build_dashboard_data import OUT_DIR

DATASET = ROOT / "data" / "processed" / "dataset_modelo.csv"
OUT_DIR = Path(OUT_DIR)

# ─── Features del modelo (misma especificacion que modelo_glm.py Fase 1) ─
FEATURES = [
    "topografia_ondulado", "topografia_montanoso", "topografia_llanura",
    "carriles", "vel_proy",
    "sup_buena", "sup_regular",
    "dist_ingemmet_km_log", "dist_peajes_km_log", "dist_cinemometros_km_log",
    "es_panamericana", "es_ruta_nacional",
]
# Variables dummy generadas a partir de categóricas
DUMMY_MAP = {
    "topografia": {"PLANO": "topografia_lplan", "ONDULADO": "topografia_ondulado",
                   "MONTAÑOSO": "topografia_montanoso", "LLANURA": "topografia_llanura"},
    "superficie": {"Buena": "sup_buena", "Regular": "sup_regular", "Mala": "sup_mala"},
}


def build_features(df):
    """Construye features dummy + transformaciones log (matching Fase 1)."""
    out = pd.DataFrame(index=df.index)
    out["carriles"] = df["carriles"].astype(float)
    out["vel_proy"] = df["vel_proy"].astype(float)

    # Topografia dummies
    for val, col in DUMMY_MAP["topografia"].items():
        out[col] = (df["topografia"] == val).astype(float)
    # Superficie dummies
    for val, col in DUMMY_MAP["superficie"].items():
        out[col] = (df["superficie"] == val).astype(float)

    # Log transforms
    out["dist_ingemmet_km_log"] = np.log1p(df["dist_ingemmet_km"].fillna(0))
    out["dist_peajes_km_log"] = np.log1p(df["dist_peajes_km"].fillna(0))
    out["dist_cinemometros_km_log"] = np.log1p(df["dist_cinemometros_km"].fillna(0))

    # Flags
    out["es_panamericana"] = df["es_panamericana"].fillna(0)
    out["es_ruta_nacional"] = (df["red_vial"] == "NACIONAL").astype(float) if "red_vial" in df.columns else 0.0

    out = out.dropna()
    return out


def fit_model(y, X):
    """Ajusta NegBin y devuelve resultados."""
    # Añadir constante
    X_c = sm.add_constant(X)
    # Offset = log(long_km) para tasa
    offset = np.log(X.index.to_series().map(lambda i: X.loc[i, "long_km_log"] if "long_km_log" in X.columns else 1.0).fillna(1.0))
    
    # Simpler: use exposure
    # NegBin con offset
    try:
        model = sm.NegativeBinomial(y, X_c, offset=np.log(X["long_km"] if "long_km" in X.columns else np.ones(len(X))))
        result = model.fit(disp=False, maxiter=200)
    except Exception:
        model = sm.GLM(y, X_c, family=sm.families.NegativeBinomial(), offset=np.log(np.ones(len(X))))
        result = model.fit(maxiter=200)

    # Extract IRRs
    params = result.params
    conf = result.conf_int()
    pvalues = result.pvalues

    irrs = []
    labels_map = {
        "const": "Intercepto",
        "carriles": "Carriles (+1)",
        "vel_proy": "Vel. proyecto (+10 km/h)",
        "topografia_ondulado": "Terreno ondulado",
        "topografia_montanoso": "Terreno montañoso",
        "topografia_llanura": "Terreno llano",
        "topografia_lplan": "Terreno plano (ref)",
        "sup_buena": "Superficie buena",
        "sup_regular": "Superficie regular",
        "sup_mala": "Superficie mala (ref)",
        "dist_ingemmet_km_log": "Dist. INGEMMET (log)",
        "dist_peajes_km_log": "Dist. peaje (log)",
        "dist_cinemometros_km_log": "Dist. cinemómetro (log)",
        "es_panamericana": "Vía panamericana",
        "es_ruta_nacional": "Red nacional",
    }

    for var in params.index:
        label = labels_map.get(var, var)
        irr = np.exp(params[var])
        irrs.append({
            "variable": var,
            "label": label,
            "irr": float(irr),
            "irr_low": float(np.exp(conf.loc[var, 0])),
            "irr_high": float(np.exp(conf.loc[var, 1])),
            "p": float(pvalues[var]),
            "coef": float(params[var]),
        })

    return result, irrs


def main():
    print("[1/5] Cargando dataset modelo + SUTRAN/OSITRAN en tramos...")
    df = pd.read_csv(DATASET)
    print(f"     Tramos: {len(df)}, y_onsv>0: {(df.y_onsv > 0).sum()}")

    # Build SUTRAN response: match SUTRAN events to tramos
    sutran = pd.read_csv(ROOT / "data" / "processed" / "sutran_accidentes_geocod.csv")
    sutran = sutran[sutran["GEOCODIFICADO"] == 1].copy()
    sutran = sutran.dropna(subset=["LONGITUD_GEO", "LATITUD_GEO"])

    tramos_xy = df[["lon_mid", "lat_mid"]].values
    tree = cKDTree(tramos_xy)
    sutran_xy = sutran[["LONGITUD_GEO", "LATITUD_GEO"]].values
    dist, idx_tramo = tree.query(sutran_xy, k=1, distance_upper_bound=0.02)
    sutran["tramo_idx"] = idx_tramo
    sutran = sutran[sutran["tramo_idx"] < len(df)].copy()

    sutran_agg = sutran.groupby("tramo_idx").agg(
        y_sutran=("FECHA", "size"),
        sutran_fal=("FALLECIDOS", "sum"),
    ).reset_index()
    df = df.merge(sutran_agg, left_index=True, right_on="tramo_idx", how="left")
    df.drop(columns=["tramo_idx"], inplace=True, errors="ignore")
    df["y_sutran"] = df["y_sutran"].fillna(0).astype(int)
    print(f"     SUTRAN tramos: {len(sutran_agg)}, y_sutran>0: {(df.y_sutran > 0).sum()}")

    # OSITRAN: join con tramos por ruta (siglas), distribuir por longitud de tramo
    ositran_acc = pd.read_csv(ROOT / "data" / "processed" / "ositran_accidentes.csv")

    # Contar accidentes por ruta
    ositran_by_ruta = ositran_acc.groupby("ruta").agg(
        ositran_n_total=("cant_accidentes", "sum"),
    ).reset_index()

    # Unir y distribuir por longitud de tramo
    df = df.merge(ositran_by_ruta, on="ruta", how="left")
    df["ositran_n_total"] = df["ositran_n_total"].fillna(0)

    # Distribuir: cada tramo de la ruta recibe proporcionalmente según su longitud
    # Agrupamos por ruta y distribuimos el total entre tramos de esa ruta
    for ruta in df["ruta"].unique():
        mask = df["ruta"] == ruta
        total = df.loc[mask, "ositran_n_total"].iloc[0] if mask.any() else 0
        if total > 0 and mask.sum() > 0:
            # Distribir uniformemente entre tramos (simplificación)
            n_tramos = mask.sum()
            df.loc[mask, "ositran_n"] = round(total / n_tramos)
        else:
            df.loc[mask, "ositran_n"] = 0
    df["y_ositran"] = df["ositran_n"].astype(int)
    print(f"     OSITRAN: tramos con datos {df.y_ositran.sum()} accidentes distribuidos")

    # SUTRAN por ruta también (simplificación)
    sutran_by_ruta = sutran.groupby("CODIGO_VIA" if "CODIGO_VIA" in sutran.columns else "RED VIAL").agg(
        sutran_n_ruta=("FECHA", "size"),
    ).reset_index()
    
    # Total combinado
    df["y_total"] = df["y_onsv"] + df["y_sutran"] + df["y_ositran"]
    print(f"     Total y: onsv={df.y_onsv.sum()}, sutran={df.y_sutran.sum()}, ositran={df.y_ositran.sum()}, total={df.y_total.sum()}")

    # ─── Features ────────────────────────────────────────────────────────
    print("[3/5] Construyendo features...")
    df["dist_ingemmet_km_log"] = np.log1p(df["dist_ingemmet_km"].fillna(0))
    df["dist_peajes_km_log"] = np.log1p(df["dist_peajes_km"].fillna(0))
    df["dist_cinemometros_km_log"] = np.log1p(df["dist_cinemometros_km"].fillna(0))
    df["long_km_log"] = np.log1p(df["long_km"].fillna(1))
    df["es_ruta_nacional"] = (df.get("red_vial", pd.Series()) == "NACIONAL").astype(float) if "red_vial" in df.columns else 0.0

    X = pd.DataFrame(index=df.index)
    X["carriles"] = df["carriles"].astype(float)
    X["vel_proy"] = df["vel_proy"].astype(float)
    X["topografia_ondulado"] = (df["topografia"] == "ONDULADO").astype(float)
    X["topografia_montanoso"] = (df["topografia"] == "MONTAÑOSO").astype(float)
    X["topografia_llanura"] = (df["topografia"] == "LLANURA").astype(float)
    X["sup_buena"] = (df["superficie"] == "Buena").astype(float)
    X["sup_regular"] = (df["superficie"] == "Regular").astype(float)
    X["dist_ingemmet_km_log"] = df["dist_ingemmet_km_log"]
    X["dist_peajes_km_log"] = df["dist_peajes_km_log"]
    X["dist_cinemometros_km_log"] = df["dist_cinemometros_km_log"]
    X["es_panamericana"] = df["es_panamericana"].fillna(0)
    X["es_ruta_nacional"] = df["es_ruta_nacional"]
    X["long_km"] = df["long_km"].replace(0, 1)

    # Limpieza: reemplazar inf/nan
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

    # ─── 3. Ajustar 3 modelos ────────────────────────────────────────────
    print("[3/5] Ajustando NegBin ONSV...")
    mask_onsv = df["y_onsv"] > 0
    r_onsv, irr_onsv = fit_model(df.loc[mask_onsv, "y_onsv"], X.loc[mask_onsv])
    print(f"     IRRs ONSV: {len(irr_onsv)}, alpha={r_onsv.lnalpha+0 if hasattr(r_onsv, 'lnalpha') else 'N/A'}")

    print("[4/5] Ajustando NegBin SUTRAN...")
    mask_sut = df["y_sutran"] > 0
    r_sut, irr_sut = fit_model(df.loc[mask_sut, "y_sutran"], X.loc[mask_sut])
    print(f"     IRRs SUTRAN: {len(irr_sut)}")

    print("[5/5] Ajustando NegBin combinado...")
    mask_tot = df["y_total"] > 0
    r_tot, irr_tot = fit_model(df.loc[mask_tot, "y_total"], X.loc[mask_tot])
    print(f"     IRRs total: {len(irr_tot)}")

    # ─── Guardar IRRs combinados ────────────────────────────────────────
    for irrs, fuente in [(irr_onsv, "ONSV"), (irr_sut, "SUTRAN"), (irr_tot, "COMBINADO")]:
        for r in irrs:
            r["fuente"] = fuente
    all_irrs = irr_onsv + irr_sut + irr_tot

    irrs_df = pd.DataFrame(all_irrs)
    irrs_df.to_csv(OUT_DIR / "irrs_multi.csv", index=False, encoding="utf-8-sig")
    print(f"     Guardado: {OUT_DIR / 'irrs_multi.csv'} ({len(irrs_df)} rows)")

    # Guardar stats del modelo
    stats_out = {
        "onsv": {"n_tramos": int(mask_onsv.sum()), "n_accidentes": int(df.y_onsv.sum()),
                  "pseudo_r2": float(r_onsv.prsquared) if hasattr(r_onsv, "prsquared") else None},
        "sutran": {"n_tramos": int(mask_sut.sum()), "n_accidentes": int(df.y_sutran.sum()),
                    "pseudo_r2": float(r_sut.prsquared) if hasattr(r_sut, "prsquared") else None},
        "total": {"n_tramos": int(mask_tot.sum()), "n_accidentes": int(df.y_total.sum()),
                   "pseudo_r2": float(r_tot.prsquared) if hasattr(r_tot, "prsquared") else None},
        "features": list(X.columns),
    }
    with open(OUT_DIR / "modelo_stats_multi.json", "w", encoding="utf-8") as f:
        json.dump(stats_out, f, ensure_ascii=False, indent=2)
    print(f"     Guardado: {OUT_DIR / 'modelo_stats_multi.json'}")

    print("\n[OK] Modelos multi-fuente completados")

if __name__ == "__main__":
    main()