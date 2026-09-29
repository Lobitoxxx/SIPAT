# -*- coding: utf-8 -*-
"""Limpieza parametrizable (sección 11-12) con bitácora TransformationLog.

Estrategias: rename canónico, drop de columnas redundantes, normalización de
cadenas (mayúsculas/acentos), fechas multi-formato, números, dedupe con keep,
imputación (median/mode/keep) y categorización de 'DESCONOCIDO'.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Optional

import pandas as pd

from src.cleaning.transform_log import TransformationLog

_RE_ACCENTS = re.compile(r"[áéíóúüÁÉÍÓÚÜ]")
_ACCENT_MAP = {
    "á": "A", "é": "E", "í": "I", "ó": "O", "ú": "U", "ü": "U",
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U",
}


def _norm_text(v: Any, fold_accents: bool = True) -> Any:
    if pd.isna(v):
        return v
    s = str(v).strip()
    if not s:
        return pd.NA
    if fold_accents:
        s = _ACCENT_MAP.get(s, s) if len(s) == 1 else unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch)).upper()
    else:
        s = s.upper()
    return re.sub(r"\s+", " ", s)


def _parse_dates(df: pd.DataFrame, cols: Dict[str, list], tlog: TransformationLog) -> pd.DataFrame:
    for col, fmts in cols.items():
        if col not in df.columns:
            continue
        before = int(df[col].isna().sum())
        s = df[col]
        words = s.astype(str).str.strip().replace(r"\.0$", "", regex=True)
        tmp = pd.to_datetime(words, errors="coerce", format=fmts[0]) if fmts else pd.to_datetime(s, errors="coerce")
        mask = tmp.isna() & s.notna()
        for f in fmts[1:]:
            if not mask.any():
                break
            tmp.loc[mask] = pd.to_datetime(words.loc[mask], errors="coerce", format=f)
            mask = tmp.isna() & s.notna()
        if mask.any():  # último recurso: parser poco estricto con prioridad día-mes
            tmp.loc[mask] = pd.to_datetime(s.loc[mask], errors="coerce", dayfirst=True)
        after = int(tmp.isna().sum())
        df[col] = tmp
        tlog.add("parse_date", col, records_affected=int(df[col].notna().sum()),
                 strategy=";".join(fmts), detail=f"nulls {before}->{after}")
    return df


def _impute(df: pd.DataFrame, plan: Dict[str, Dict[str, str]], numeric_cols: list, tlog: TransformationLog) -> pd.DataFrame:
    for col, cfg in plan.items():
        if col not in df.columns:
            continue
        s = df[col]
        n = int(s.isna().sum())
        if n == 0:
            continue
        strategy = cfg.get("strategy", "keep")
        if strategy == "median" and col in numeric_cols:
            df[col] = s.fillna(s.median())
            tlog.add("impute_median", col, n, strategy="median")
        elif strategy == "domain_rule":
            df[col] = s.fillna(cfg["value"])
            tlog.add("impute_domain_rule", col, n, strategy=str(cfg["value"]))
        elif strategy == "mode":
            m = s.mode()
            if not m.empty:
                df[col] = s.fillna(m[0])
                tlog.add("impute_mode", col, n, strategy="mode")
        else:
            tlog.add("impute_keep", col, n, strategy="keep")
    return df


def clean(
    df: pd.DataFrame,
    ds_cfg: Dict[str, Any],
    tlog: TransformationLog,
    contract: Dict[str, Any] | None = None,
) -> pd.DataFrame:
    frame = df.copy()
    rename = ds_cfg.get("rename", {})
    if rename:
        renamed_cols = {k: v for k, v in rename.items() if k in frame.columns}
        frame = frame.rename(columns=renamed_cols)
        tlog.add("rename_canonical", None, len(renamed_cols),
                 strategy="estándar ONSV/SUTRAN", detail=",".join(renamed_cols.values()))

    # '¿' delante de nombres: solo el rename previo los contempla
    for c in ds_cfg.get("drop_columns", []):
        if c in frame.columns:
            frame = frame.drop(columns=[c])

    for c in ds_cfg.get("category_cols", []):
        if c in frame.columns:
            frame[c] = frame[c].map(lambda v: _norm_text(v, ds_cfg.get("fold_accents", True)))

    date_cols = ds_cfg.get("date_columns", {})
    if date_cols:
        frame = _parse_dates(frame, date_cols, tlog)

    numeric = ds_cfg.get("numeric", [])
    strip_chars = ds_cfg.get("numeric_strip_chars")
    for c in numeric:
        if c in frame.columns:
            before = frame[c].dtype
            series = frame[c]
            if strip_chars and series.map(lambda v: isinstance(v, str)).any():
                rx = "|".join(re.escape(ch) for ch in strip_chars)
                series = series.map(
                    lambda v: re.sub(rx, "", v) if isinstance(v, str) else v
                )
                n_fixed = int(
                    (frame[c].map(lambda v: isinstance(v, str)).sum())
                    - (series.map(lambda v: isinstance(v, str) and bool(re.search(rx, v))).sum())
                )
                if n_fixed:
                    tlog.add("strip_numeric_chars", c, n_fixed, strategy=rx)
            frame[c] = pd.to_numeric(series, errors="coerce")
            if str(frame[c].dtype) != str(before):
                tlog.add("to_numeric", c, int(frame[c].isna().sum()), strategy=str(frame[c].dtype))

    plan = ds_cfg.get("fill", {})
    if plan:
        frame = _impute(frame, plan, numeric, tlog)

    if ds_cfg.get("dedup_keys"):
        keys = [k for k in ds_cfg["dedup_keys"] if k in frame.columns and frame[k].notna().any()]
        if keys:
            before = len(frame)
            frame = frame.drop_duplicates(subset=keys, keep="first")
            dup = before - len(frame)
            if dup:
                tlog.add("dedupe", ",".join(keys), dup, strategy="keep_first")
    return frame