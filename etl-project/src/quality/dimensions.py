# -*- coding: utf-8 -*-
"""Dimensiones DQS (secciones 6-7): puntuaciones 0-100 POR dimensión y puntuación ponderada.

DQS es un INDICADOR INTERNO de calidad (no una probabilidad de verdad de los datos).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.utils.configloader import load_catalogs


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().upper()


def completeness(df: pd.DataFrame, required: List[str]) -> float:
    if not required:
        return 100.0
    cols = [c for c in required if c in df.columns]
    if not cols:
        return 0.0
    return round(100.0 * float(df[cols].notna().mean().mean()), 2)


# Alias catálogo -> columna real del dataset. Los catálogos se llaman a menudo
# por el nombre conceptual ("departamentos") y la columna canónica es en singular
# ("departamento"). Sin este mapeo, la dimensión 'validity' no evaluaba nada.
CATALOG_ALIAS: Dict[str, str] = {
    "departamentos": "departamento",
    "departamento": "departamento",
    "provincias": "provincia",
    "distritos": "distrito",
    "clase": "clase",
    "clases": "clase",
    "condicion_climatica": "condicion_climatica",
    "causa_factor_principal": "causa_principal",
    "causa_principal": "causa_principal",
    "red_vial": "red_vial",
    "zona": "zona",
    "region": "region",
    "regiones": "region",
    "carretera": "carretera",
    "carreteras": "carretera",
    "velocidad": "velocidad_detectada",
    "limite": "limite_velocidad",
}


def _resolve_catalogs(df: pd.DataFrame, catalogs: Dict[str, list] | None) -> Dict[str, list]:
    """Mapea claves de catálogo a columnas presentes en el dataset."""
    if not catalogs:
        return {}
    resolved: Dict[str, list] = {}
    for key, vals in catalogs.items():
        if not vals:
            continue
        col = CATALOG_ALIAS.get(key)
        if col is None or col not in df.columns:
            continue
        resolved[col] = vals
    return resolved


def validity(df: pd.DataFrame, numeric: List[str], ranges: Dict[str, tuple] | None = None, catalogs: Dict[str, list] | None = None) -> float:
    """Puntaje de validez 0-100.

    Cada columna numérica se evalúa contra el rango declarado en el contrato
    (si existe) o, en su defecto, contra `>= 0`. Importante: las coordenadas de
    Perú son NEGATIVAS, así que el chequeo por defecto `>= 0` solo se aplica a
    columnas sin rango declarado. Aplicar `>= 0` a la latitud scored 0%.
    """
    checks: List[float] = []
    ranges = ranges or {}
    for c in numeric:
        if c not in df.columns:
            continue
        keep = df[c].dropna()
        if not len(keep):
            continue
        if c in ranges:
            lo, hi = ranges[c]
        else:
            lo, hi = 0.0, float("inf")
        checks.append(100.0 * float(((keep >= lo) & (keep <= hi)).mean()))
    for c, vals in _resolve_catalogs(df, catalogs).items():
        s = df[c].dropna()
        if len(s):
            norm_vals = {_norm(v) for v in vals}
            ok = s.astype(str).map(_norm).isin(norm_vals)
            checks.append(100.0 * float(ok.mean()))
    if ranges:
        # Columnas con rango que no son de tipo numérico en el contrato.
        contract_num = set(numeric)
        for c, (lo, hi) in ranges.items():
            if c in df.columns and c not in contract_num:
                keep = df[c].dropna()
                if len(keep):
                    checks.append(100.0 * float(((keep >= lo) & (keep <= hi)).mean()))
    return round(sum(checks) / len(checks), 2) if checks else 100.0


def uniqueness(df: pd.DataFrame, keys: List[str]) -> float:
    keys = [k for k in keys if k in df.columns]
    if not keys:
        return 100.0
    ndup = df.duplicated(subset=keys).sum()
    return round(100.0 * (1 - ndup / len(df)), 2)


def consistency(df: pd.DataFrame, normalization: List[str] = ("region",)) -> float:
    """Detecta incoherencias de caja (p. ej. 'Lima' vs 'LIMA') en columnas nominales."""
    checks: List[float] = []
    for c in normalization:
        if c not in df.columns:
            continue
        s = df[c].dropna().astype(str)
        if len(s) == 0:
            continue
        upper = s.str.upper()
        mixed = (s != upper).mean()
        checks.append(100.0 * (1 - float(mixed)))
    return round(sum(checks) / len(checks), 2) if checks else 100.0


def integrity(df: pd.DataFrame, fks: Dict[str, str] | None, ref: Dict[str, pd.DataFrame]) -> float:
    checks: List[float] = []
    for col, ref_col in (fks or {}).items():
        if col not in df.columns:
            continue
        s = df[col].dropna()
        if len(s) == 0:
            continue
        allowed = set(ref_df[ref_col].unique()) if (ref_df := ref.get(col)) is not None else set()
        if not allowed:
            continue
        checks.append(100.0 * float(s.isin(allowed).mean()))
    return round(sum(checks) / len(checks), 2) if checks else 100.0


def freshness(dates: pd.Series, window_days: int = 365) -> float:
    s = pd.to_datetime(dates, errors="coerce").dropna()
    if s.empty:
        return 0.0
    # La serie es tz-naive: el corte debe serlo también (comparar tz-aware lanza TypeError).
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_localize(None)
    cutoff = pd.Timestamp(datetime.now().date()) - pd.Timedelta(days=window_days)
    within = (s >= cutoff).mean()
    return round(100.0 * float(within), 2)


def _contract_ranges(cols: Dict[str, dict]) -> Dict[str, tuple]:
    """Extrae (min, max) numéricos declarados en el contrato.

    Solo se consideran columnas numéricas: los límites de fecha del contrato se
    validan en `validation.contract`, y comparar una serie datetime contra `None`
    (cuando el contrato declara solo `min` o solo `max`) sería inválido.
    """
    ranges: Dict[str, tuple] = {}
    for c, r in cols.items():
        if r.get("type") not in ("integer", "float"):
            continue
        lo, hi = r.get("min"), r.get("max")
        if lo is None and hi is None:
            continue
        # Sustituye extremos abiertos por ±infinito: `validity` compara siempre ambos lados.
        ranges[c] = (lo if lo is not None else -float("inf"), hi if hi is not None else float("inf"))
    return ranges


def compute_dqs(
    df: pd.DataFrame,
    cfg: Dict[str, Any],
    contract: Dict[str, Any],
    catalogs: Dict[str, list] | None = None,
    dataset: str | None = None,
) -> Dict[str, Any]:
    meta = contract.get("contract", contract)
    cols = meta.get("columns", {})
    weights = cfg["quality"]["weights"]
    required = [c for c, r in cols.items() if not r.get("nullable", True) and c in df.columns]
    numeric = [c for c, r in cols.items() if r.get("type") in ("integer", "float") and c in df.columns]
    pk = meta.get("primary_key")

    # freshness_column vive en settings.datasets.<dataset> (no en el contrato).
    ds_name = dataset or meta.get("dataset")
    fresh_col = None
    if ds_name:
        fresh_col = (cfg.get("datasets", {}).get(ds_name) or {}).get("freshness_column")
    fresh_col = fresh_col or meta.get("freshness_column")
    window = cfg["quality"].get("freshness_window_days", 365)
    fresh = freshness(df[fresh_col], window) if fresh_col in df.columns else None

    d = {
        "completeness": completeness(df, required),
        "validity": validity(df, numeric, ranges=_contract_ranges(cols), catalogs=catalogs),
        "uniqueness": uniqueness(df, [pk] if pk else []),
        "consistency": consistency(df, [c for c in ("region", "carretera", "clase", "zona") if c in df.columns]),
        "integrity": 100.0,
        "freshness": 100.0 if fresh is None else fresh,
    }
    d["dqs"] = round(sum(d[k] * weights[k] for k in weights), 2)
    d["weights"] = weights
    d["n_rows"] = int(len(df))
    d["freshness_column"] = fresh_col
    d["freshness_window_days"] = window
    return d