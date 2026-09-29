# -*- coding: utf-8 -*-
"""Capa Gold (sección 3 y 26): datasets analíticos + MODEL_READY.

La capa Gold NO mezcla detalle con agregado: cada artefacto es autocontenido.
Las métricas agregadas se generan en `src/load/aggregations.py` (SQL declarativo
configurado por dataset) y se publican como JSON aparte.
"""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from src.utils import paths


def write_gold_analytics(df: pd.DataFrame, dataset: str, run_id: str, version: str) -> Dict[str, Any]:
    out_dir = paths.ensure(paths.DATA, "gold")
    out = out_dir / f"{dataset}_analytics_{version}.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    return {
        "path": str(out),
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "dataset": dataset,
        "layer": "gold.analytics",
    }


def write_model_ready(df: pd.DataFrame, dataset: str, run_id: str, version: str) -> Dict[str, Any]:
    """Solo se escribe cuando is_model_ready() == True (sección 31)."""
    out_dir = paths.ensure(paths.DATA, "gold")
    out = out_dir / f"{dataset}_model_ready_{version}.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    return {
        "path": str(out),
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "dataset": dataset,
        "layer": "gold.model_ready",
    }