# -*- coding: utf-8 -*-
"""Cuarentena (secciones 8 y 12): reglas con severidad critical separan registros dudosos.

data/quarantine/<dataset>_quarantine_<run_id>.json
Estructura por registro: record_id, pipeline_run_id, dataset, source, rule_failed,
error_code, error_description, original_value, detected_at.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.utils import hashing, paths


def push_quarantine(
    df: pd.DataFrame,
    violations: List[Dict[str, Any]],
    dataset: str,
    run_id: str,
    source: str,
) -> Path:
    """Escribe en data/quarantine los registros que violan reglas criticales (persistencia inmutable)."""
    bad_rows: Dict[int, Dict[str, Any]] = {}
    for v in violations:
        if v["severity"] != "critical":
            continue
        rule = v["rule"]
        for idx in v["rows"]:
            if idx >= len(df):
                continue
            row = df.iloc[idx]
            bad_rows.setdefault(int(idx), []).append(rule)

    records = []
    for idx, rules in bad_rows.items():
        row = df.iloc[idx]
        original = {str(k): _serialize(v) for k, v in row.items()}
        for rule in rules:
            records.append(
                {
                    "record_id": hashing.content_sha256(f"{rule}:{idx}:{str(original)}"),
                    "pipeline_run_id": run_id,
                    "dataset": dataset,
                    "source": source,
                    "row_index": int(idx),
                    "rule_failed": rule,
                    "error_code": "DQ_CRITICAL",
                    "error_description": f"Registro separado por regla crítica {rule!r}",
                    "original_value": original,
                    "detected_at": hashing.now_iso(),
                }
            )
    out_dir = paths.ensure(paths.DATA, "quarantine")
    out = out_dir / f"{dataset}_quarantine_{run_id}.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return out


def _serialize(v):
    import numpy as np

    if v is pd.NA or (isinstance(v, np.floating) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (np.integer, np.floating)):
        return v.item()
    return v


def missing_after_clean_counts(df: pd.DataFrame) -> Dict[str, Any]:
    return {c: int(df[c].isna().sum()) for c in df.columns}