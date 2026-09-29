# -*- coding: utf-8 -*-
"""Transformaciones de dominio (sección 15): features derivadas para silver/gold.

Características comunes SUTRAN IMT (repositorio oficial de datos abiertos ONSV) —
mantuvo coherencia con los nombres reales de columnas del proyecto.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd


def derive_features(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    out = df.copy()
    if dataset == "onsv" and "fecha" in out.columns:
        out["anio"] = out["fecha"].dt.year
        out["mes"] = out["fecha"].dt.month
        out["dia_semana"] = out["fecha"].dt.dayofweek
        if "hora" in out.columns:
            hh = out["hora"].astype(str).str.extract(r"(\d{1,2})").astype(float)
            out["hora_num"] = hh[0]
            out["tramo_dia"] = pd.cut(
                hh[0],
                bins=[-1, 6, 12, 18, 23],
                labels=["madrugada", "manana", "tarde", "noche"],
            ).astype(str)
    if dataset == "onsv" and {"latitud", "longitud"}.issubset(out.columns):
        out["geo_valid"] = out["latitud"].between(-18.5, 0.2) & out["longitud"].between(-81.5, -68.5)
    if dataset == "cinemometros" and {"velocidad_detectada", "limite_velocidad"}.issubset(out.columns):
        out["exceso_kmh"] = (out["velocidad_detectada"] - out["limite_velocidad"]).clip(lower=0)
        out["excede_limite"] = out["velocidad_detectada"] > out["limite_velocidad"]
        if "fecha_papeleta" in out.columns:
            out["anio"] = out["fecha_papeleta"].dt.year
            out["mes"] = out["fecha_papeleta"].dt.month
    return out