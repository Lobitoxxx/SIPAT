# -*- coding: utf-8 -*-
"""Capa Silver (sección 3 y 26): datos limpios, canónicos y vector-derminados en Parquet."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.utils import hashing, paths


def write_silver(
    df: pd.DataFrame,
    dataset: str,
    run_id: str,
    dataset_version: str,
) -> Dict[str, Any]:
    out_dir = paths.ensure(paths.DATA, "silver")
    out = out_dir / f"{dataset}_silver_{dataset_version}.parquet"
    df.to_parquet(out, engine="pyarrow", index=False)
    meta = {
        "dataset": dataset,
        "layer": "silver",
        "run_id": run_id,
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "file_md5": hashing.file_md5(out),
        "written_at": hashing.now_iso(),
    }
    with open(out_dir / f"{dataset}_silver.meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return {"path": str(out), "rows": len(df), "metadata": meta}


def read_silver(dataset: str, dataset_version: str) -> pd.DataFrame:
    return pd.read_parquet(paths.DATA / "silver" / f"{dataset}_silver_{dataset_version}.parquet")