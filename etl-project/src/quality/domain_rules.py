# -*- coding: utf-8 -*-
"""Reglas de dominio (secciones 6 y 12): detectan violaciones con severidad critical/warning.

Es la capa semántica declarativa; las EXCEPCIONES con severidad critical pueden ir a cuarentena.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

import pandas as pd

_CRITICAL_MSG = {"rules criticales": "incumplimiento crítico del contrato de datos"}


def _norm(value: Any) -> str:
    """Normalización idéntica a la de la limpieza (sin acentos, upper, espacios colapsados)."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().upper()


# Mapeo columna -> clave de catálogo en config/quality/catalogs/<dataset>.yaml
_CATALOG_ALIAS = {
    "departamento": "departamentos",
    "clase": "clase",
    "condicion": "condicion_climatica",
    "condicion_climatica": "condicion_climatica",
    "causa_principal": "causa_factor_principal",
    "red_vial": "red_vial",
    "zona": "zona",
    "region": "regiones_validas",
    "carretera": "carreteras",
}


def detect_violations(
    df: pd.DataFrame,
    rules: Iterable[Dict[str, Any]],
    catalogs: Dict[str, list] | None = None,
    context: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Devuelve lista de violaciones: {rule, column, severity, count, rows:[índices]}."""
    catalogs = catalogs or {}
    ctx = context or {}
    violations: List[Dict[str, Any]] = []
    # Columnas de fecha son tz-naive; comparar con un timestamp tz-aware lanza TypeError.
    today = pd.Timestamp(datetime.now().date())

    for spec in rules:
        rule = spec["rule"]
        cols = spec.get("columns", []) or []
        sev = spec.get("severity", "warning")
        detail: List[int] = []

        if rule == "pk_not_null":
            c = cols[0]
            detail = df.index[df[c].isna()].tolist() if c in df.columns else []
        elif rule == "pk_unique":
            c = cols[0]
            detail = df.index[df[c].duplicated()].tolist() if c in df.columns else []
        elif rule == "fecha_parsable":
            c = cols[0]
            detail = df.index[df[c].isna()].tolist() if c in df.columns else []
        elif rule == "fecha_no_futura":
            c = cols[0]
            if c in df.columns and pd.api.types.is_datetime64_any_dtype(df[c]):
                detail = df.index[df[c] > today].tolist()
        elif rule == "coordenadas_peru":
            lat, lon = cols[0], cols[1]
            if lat in df.columns and lon in df.columns:
                mask = ~(
                    df[lat].between(-18.5, 0.2) & df[lon].between(-81.5, -68.5)
                ) & df[lat].notna() & df[lon].notna()
                detail = df.index[mask].tolist()
            elif lat in df.columns and df[lat].isna().any():
                detail = df.index[df[lat].isna()].tolist()
        elif rule == "contadores_no_negativos":
            for c in cols:
                if c in df.columns:
                    detail += df.index[df[c] < 0].tolist()
        elif rule.endswith("_catalogo"):
            c = cols[0]
            allowed = catalogs.get(_CATALOG_ALIAS.get(c, c))
            if allowed and c in df.columns:
                s = df[c].dropna()
                if len(s):
                    norm_allowed = {_norm(v) for v in allowed}
                    detail = s[~s.astype(str).map(_norm).isin(norm_allowed)].index.tolist()
        elif rule == "velocidad_rango":
            v, l = cols
            if v in df.columns and l in df.columns:
                detail = df.index[(df[v] > 300) | (df[v] < 1)].tolist()
                detail += df.index[df[l] > 160].tolist()
        elif rule == "hora_formato":
            c = cols[0]
            if c in df.columns:
                s = df[c].astype(str)
                detail = df.index[~s.str.match(r"^\d{1,2}:\d{2}$") & (s != "nan")].tolist()
        elif rule == "consistencia_ubigeo":
            dep, prov = cols[0], cols[1]
            if dep in df.columns and prov in df.columns:
                # placeholder: provincia debería empezar por el departamento en muchos casos; se
                # registra warning solo cuando hay NULL en provincia con departamento no-nulo.
                detail = df.index[df[dep].notna() & df[prov].isna()].tolist()[:200]

        if detail:
            violations.append(
                {
                    "rule": rule,
                    "column": ",".join(cols),
                    "severity": sev,
                    "count": len(detail),
                    "rows": detail[:1000],
                }
            )
    return violations