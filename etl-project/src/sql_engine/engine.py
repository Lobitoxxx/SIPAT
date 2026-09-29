# -*- coding: utf-8 -*-
"""Motor SQL local DuckDB (sección 16): engine de análisis con catálogo de lineage."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import duckdb

from src.utils import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  dataset   VARCHAR PRIMARY KEY,
  source_name VARCHAR,
  source_type VARCHAR,
  raw_path  VARCHAR
);
CREATE TABLE IF NOT EXISTS runs (
  run_id    VARCHAR PRIMARY KEY,
  project   VARCHAR,
  version   VARCHAR,
  status    VARCHAR,
  started_at TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS dataset_lines (
  dataset   VARCHAR,
  layer     VARCHAR,
  run_id    VARCHAR,
  path      VARCHAR,
  rows      BIGINT,
  cols      BIGINT,
  file_md5  VARCHAR,
  created_at TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS quality_scores (
  run_id    VARCHAR,
  dataset   VARCHAR,
  stage     VARCHAR,
  score     DOUBLE,
  dimensions VARCHAR,
  gate      VARCHAR,
  created_at TIMESTAMP DEFAULT now()
);
-- Claves únicas para que el lineage sea idempotente (upsert por identidad lógica).
CREATE UNIQUE INDEX IF NOT EXISTS ux_dataset_lines
  ON dataset_lines (dataset, layer, run_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_quality_scores
  ON quality_scores (run_id, dataset, stage);
"""


def duckdb_engine(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    if db_path is None:
        db_path = paths.ARTIFACTS / "lineage" / "sipat_lineage.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(_SCHEMA)
    return con


def _row_to_dict(cols, row) -> dict:
    return {k: v for k, v in zip(cols, row)}


def query_to_dicts(con: duckdb.DuckDBPyConnection, sql: str, params=None) -> list[dict]:
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [_row_to_dict(cols, r) for r in rel.fetchall()]