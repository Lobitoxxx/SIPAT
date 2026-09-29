# -*- coding: utf-8 -*-
"""Capa Bronze (sección 3): copia inmutable e idempotente del dato fuente + metadatos.

La capa Bronze NO se modifica jamás: se lee y se regenera (copy_if_missing). Si el
fichero fuente cambia (nuevo checksum) se registra una nueva versión con sufijo.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from src.utils import hashing, paths
from src.utils.logging_util import get_logger

logger = get_logger("bronze")


def bronze_dir() -> Path:
    return paths.ensure(paths.DATA, "bronze")


def register_bronze(
    result: "ExtractResult",
    run_id: str,
    dataset_version: str,
    extra_meta: Dict[str, Any] | None = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Escribe data/bronze/<dataset>_<dataset_version>.parquet de forma idempotente.

    Idempotencia real: la comparación se hace contra el `source_md5` registrado en
    el `.meta.json` del Bronze existente, NO contra el md5 del parquet (que siempre
    difiere por la compresión). Si la fuente cambió, el Bronze previo se archiva con
    sufijo de versión y se registra el nuevo; así la trazabilidad no miente.
    """
    ds_dir = paths.ensure(bronze_dir(), result.dataset)
    sink = ds_dir / f"{result.dataset}_{dataset_version}.parquet"
    meta_path = ds_dir / f"{sink.stem}.meta.json"

    if sink.exists() and not overwrite:
        recorded_md5 = _recorded_source_md5(meta_path)
        if recorded_md5 == result.md5:
            logger.info(
                "bronze ya existe (idempotente): %s", sink,
                extra={"run_id": run_id, "dataset": result.dataset, "operation": "register_bronze"},
            )
            meta = dict(result.metadata)
            meta["status"] = "skipped_existing"
            rows, cols = _parquet_shape(sink)
            return {
                "path": str(sink),
                "rows": rows,
                "cols": cols,
                "md5": hashing.file_md5(sink),
                "metadata": meta,
            }
        # La fuente cambió: el Bronze previo deja de ser válido para esta versión.
        archived = _archive_previous(ds_dir, sink, meta_path, dataset_version)
        logger.warning(
            "fuente modificada (md5 %s -> %s); bronze previo archivado en %s",
            recorded_md5, result.md5, archived.name,
            extra={"run_id": run_id, "dataset": result.dataset, "operation": "register_bronze"},
        )

    frame = _parquet_safe(result.frame.copy())
    if "fecha" in frame.columns:
        frame["fecha"] = pd.to_datetime(frame["fecha"], errors="coerce")

    certa_meta = dict(result.metadata)
    certa_meta.update(
        {
            "dataset": result.dataset,
            "dataset_version": dataset_version,
            "run_id": run_id,
            "layer": "bronze",
            "ingested_rows": len(frame),
            "ingested_cols": frame.shape[1],
            "ingestion_timestamp": hashing.now_iso(),
            "source_md5": result.md5,
        }
    )
    if extra_meta:
        certa_meta.update(extra_meta)

    frame.to_parquet(sink, engine="pyarrow", index=False)
    meta_path.write_text(_json(certa_meta), encoding="utf-8")
    logger.info(
        "bronze registrado: %s (filas=%d)", sink, len(frame),
        extra={"run_id": run_id, "dataset": result.dataset, "operation": "register_bronze"},
    )
    return {
        "path": str(sink),
        "rows": len(frame),
        "cols": int(frame.shape[1]),
        "md5": hashing.file_md5(sink),
        "metadata": certa_meta,
    }


def _parquet_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Hace escribible el frame en Parquet sin perder información.

    Parquet exige un tipo único por columna, pero el crudo trae columnas `object`
    que mezclan tipos (casos reales de ONSV):
      * `FECHA SINIESTRO`       -> `datetime` + `'01/01/2021'`
      * `COORDENADAS  LONGITUD` -> `float` + `'-71.325300°'`

    Bronze guarda el dato TAL COMO LLEGA, así que no tipamos por nombre de columna
    sino por contenido, y solo cuando la conversión no destruye valores:
      1. si la columna mezcla tipos y un subconjunto es numérico -> `to_numeric`
         (los valores con sufijo no parseable pasan a NaN, como haría cualquier
          lectura; el CleaningLog de Silver deja constancia del cambio);
      2. si un subconjunto es fecha -> `to_datetime`;
      3. si ninguna conversión es aplicable -> `astype(str)` (representación literal).
    """
    import datetime as _dt

    out = df
    for col in out.columns:
        s = out[col]
        if s.dtype != object:
            continue
        non_null = s.dropna()
        if non_null.empty:
            continue
        out = out.copy() if out is df else out

        n_numeric = int(non_null.map(lambda v: isinstance(v, (int, float, np.integer, np.floating))
                                      and not isinstance(v, bool)).sum())
        n_date = int(non_null.map(lambda v: isinstance(v, (_dt.datetime, _dt.date))).sum())
        mixed = n_numeric + n_date < non_null.shape[0]

        if mixed and n_numeric:
            # 1) Mayoría numérica con algo de texto ('-71.325300°').
            conv = pd.to_numeric(s, errors="coerce")
            if conv.notna().sum() >= n_numeric:
                out[col] = conv
                continue
        if n_date:
            # 2) Fechas (con o sin formatos textuales mezclados).
            conv = pd.to_datetime(s, errors="coerce")
            if int(conv.isna().sum()) <= int(s.isna().sum()) and conv.notna().any():
                out[col] = conv
                continue
        if mixed:
            # 3) Sin conversión viable: literal.
            out[col] = s.astype(str)
    return out


def _recorded_source_md5(meta_path: Path) -> str | None:
    """Lee el source_md5 del Bronze existente; None si falta o está corrupto."""
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("source_md5")
    except (json.JSONDecodeError, OSError):
        return None


def _archive_previous(ds_dir: Path, sink: Path, meta_path: Path, dataset_version: str) -> Path:
    """Renombra el Bronze obsoleto a <dataset>_<version>_superseded_<md5corto>.parquet.

    No se borra nada: la capa Bronze es inmutable y todo queda en disco.
    """
    stamp = hashing.now_iso().replace(":", "").replace("-", "")[:15]
    archived = ds_dir / f"{sink.stem}_superseded_{stamp}.parquet"
    sink.replace(archived)
    if meta_path.exists():
        meta_path.replace(ds_dir / f"{archived.stem}.meta.json")
    return archived


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _parquet_shape(path: Path) -> tuple[int, int]:
    """Lee solo los metadatos del Parquet (no carga el frame en memoria)."""
    import pyarrow.parquet as pq

    m = pq.ParquetFile(path).metadata
    return int(m.num_rows), int(m.num_columns)