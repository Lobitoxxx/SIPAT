# -*- coding: utf-8 -*-
"""Validación de contrato (sección 5): comprueba el dataset contra config/contracts/*.yaml.

Reglas soportadas por columna:
  type, nullable, unique, min, max, pattern, allowed_values,
  min_date, max_date, max_before_today_days, min_length, max_length

Devolvemos un dict con violaciones por columna y una decisión sintáctica global.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

_SIMPLE_TYPES = {
    "string": "string",
    "integer": "integer",
    "float": "float",
    "datetime": "datetime",
    "boolean": "boolean",
}


def _norm(value: Any) -> str:
    """Normaliza un valor de catálogo a la forma que produce la limpieza (sin acentos, upper, sin espacios extra)."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().upper()


def _type_ok(s: pd.Series, declared: str) -> bool:
    """Comprobación de tipo 'lógica': acepta int64 o float64 entero para 'integer'."""
    nn = s.dropna()
    if declared == "integer":
        if pd.api.types.is_bool_dtype(s):
            return False
        if pd.api.types.is_integer_dtype(s):
            return True
        if pd.api.types.is_float_dtype(s):
            return bool(np.all(np.mod(nn.to_numpy(dtype="float64"), 1) == 0))
        return False
    if declared == "float":
        return bool(pd.api.types.is_numeric_dtype(s))
    if declared == "datetime":
        return bool(pd.api.types.is_datetime64_any_dtype(s))
    if declared == "boolean":
        return bool(pd.api.types.is_bool_dtype(s))
    if declared == "string":
        return bool(pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s))
    return True


def _as_timestamp(value: Any) -> Optional[pd.Timestamp]:
    try:
        ts = pd.to_datetime(value)
    except (ValueError, TypeError):
        return None
    return None if pd.isna(ts) else pd.Timestamp(ts)


def validate_contract(df: pd.DataFrame, contract: Dict[str, Any]) -> Dict[str, Any]:
    """Devuelve {valid, errors:[(column, rule, message)], details_by_column}."""
    errors: list[tuple[str, str, str]] = []
    details: Dict[str, Any] = {}
    meta = contract.get("contract", contract)
    cols = meta.get("columns", {})

    missing = [c for c in cols if c not in df.columns]
    if missing:
        for c in missing:
            errors.append((c, "missing_column", "Columna requerida por contrato no existe en el dataset"))
    # Columnas extra se toleran por defecto (allow_extra) y se documentan; no invalidan.
    allow_extra = meta.get("allow_extra", True)
    extra = [c for c in df.columns if c not in cols]
    if extra and not allow_extra:
        for c in extra:
            errors.append((c, "extra_column", "Columna no contemplada en el contrato"))
    details["__extra_columns"] = extra

    # Tolerancia configurable de fechas futuras (días). 0 = no se admite ninguna.
    today = pd.Timestamp(datetime.now().date())

    for col, rules in cols.items():
        if col not in df.columns:
            continue
        s = df[col]
        kwargs: dict[str, Any] = {
            "col": col,
            "col_errors": [],
            "non_null": int(s.notna().sum()),
            "nulls": int(s.isna().sum()),
            "null_pct": round(float(s.isna().mean() * 100), 2),
        }
        if not rules.get("nullable", True) and s.isna().any():
            n = int(s.isna().sum())
            kwargs["col_errors"].append(n)
            errors.append((col, "not_nullable", f"{n} valores nulos en columna obligatoria"))

        declared = rules.get("type")
        if declared:
            if not _type_ok(s, declared):
                errors.append(
                    (col, "type", f"tipo declarado '{declared}' pero dtype real '{s.dtype}'")
                )

        if rules.get("unique"):
            dup = int(s.duplicated().sum())
            if dup:
                errors.append((col, "unique", f"{dup} valores duplicados"))

        # min / max: numéricos y también fechas (el YAML puede traer "2000-01-01").
        for rule, op, symbol in (("min", "lt", "<"), ("max", "gt", ">")):
            bound = rules.get(rule)
            if bound is None:
                continue
            if pd.api.types.is_numeric_dtype(s) and not isinstance(bound, str):
                bad = int((s < bound).sum()) if op == "lt" else int((s > bound).sum())
            elif pd.api.types.is_datetime64_any_dtype(s):
                ts = _as_timestamp(bound)
                if ts is None:
                    continue
                cmp_s = s.dropna()
                bad = int((cmp_s < ts).sum()) if op == "lt" else int((cmp_s > ts).sum())
            elif pd.api.types.is_string_dtype(s) and isinstance(bound, str):
                cmp_s = s.dropna().astype(str)
                cmp_ts = pd.to_datetime(cmp_s, errors="coerce")
                ts = _as_timestamp(bound)
                if ts is not None and cmp_ts.notna().all():
                    bad = int((cmp_ts < ts).sum()) if op == "lt" else int((cmp_ts > ts).sum())
                else:
                    bad = int((cmp_s < bound).sum()) if op == "lt" else int((cmp_s > bound).sum())
            else:
                bad = 0
            if bad:
                errors.append((col, rule, f"{bad} valores {symbol} {bound}"))

        # Reglas temporales explícitas.
        is_dt = pd.api.types.is_datetime64_any_dtype(s)
        for rule, op, symbol in (("min_date", "lt", "<"), ("max_date", "gt", ">")):
            bound = _as_timestamp(rules.get(rule)) if rules.get(rule) else None
            if bound is None:
                continue
            cmp_s = s.dropna()
            if not is_dt:
                cmp_s = pd.to_datetime(cmp_s, errors="coerce").dropna()
            bad = int((cmp_s < bound).sum()) if op == "lt" else int((cmp_s > bound).sum())
            if bad:
                errors.append((col, rule, f"{bad} valores {symbol} {bound.date()}"))

        tol = rules.get("max_before_today_days")
        if tol is not None and is_dt:
            cutoff = today - pd.Timedelta(days=int(tol))
            bad = int((s.dropna() > cutoff).sum())
            if bad:
                errors.append(
                    (col, "max_before_today_days", f"{bad} valores con fecha posterior a hoy (+{int(tol)} d)")
                )

        pat = rules.get("pattern")
        if pat and (pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s)):
            rx = re.compile(pat)
            bad = int((~s.dropna().astype(str).map(lambda v: bool(rx.match(v)))).sum())
            if bad:
                errors.append((col, "pattern", f"{bad} valores no cumplen {pat!r}"))

        allowed = rules.get("allowed_values")
        if allowed:
            s_nn = s.dropna()
            if len(s_nn):
                if pd.api.types.is_numeric_dtype(s_nn) and all(isinstance(a, (int, float)) for a in allowed):
                    ok = s_nn.isin(allowed)
                else:
                    norm_allowed = {_norm(a) for a in allowed}
                    ok = s_nn.astype(str).map(_norm).isin(norm_allowed)
                bad = int((~ok).sum())
                if bad:
                    examples = sorted(s_nn.astype(str)[~ok].unique())[:5]
                    errors.append(
                        (col, "allowed_values", f"{bad} valores fuera del catálogo; p.ej. {examples}")
                    )

        for rule, op, symbol in (("min_length", "lt", "<"), ("max_length", "gt", ">")):
            bound = rules.get(rule)
            if bound is None:
                continue
            lens = s.dropna().astype(str).str.len()
            bad = int((lens < bound).sum()) if op == "lt" else int((lens > bound).sum())
            if bad:
                errors.append((col, rule, f"{bad} longitudes {symbol} {bound}"))

        kwargs["n_rule_errors"] = len(kwargs["col_errors"])
        details[col] = kwargs

    return {"valid": len(errors) == 0, "errors": errors, "details_by_column": details, "n_errors": len(errors)}