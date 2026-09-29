# -*- coding: utf-8 -*-
"""Agregaciones Gold sobre DuckDB (sección 16).

Cada dataset publica métricas agregadas listas para consumo analítico, sin que
el consumidor tenga que reescribir SQL. Las agregaciones son CONFIGURABLES por
dataset desde `config/quality/catalogs/<dataset>.yaml` -> clave `aggregations`,
de modo que no hay consultas hardcodeadas en el código.

Cada agregación devuelve además su salida en JSON para el reporte.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.sql_engine.engine import query_to_dicts
from src.utils import paths

# Catálogo de agregaciones disponibles. `by` = columna(s) de agrupación,
# `metrics` = columnas numéricas agregadas. La forma del SQL es genérica.
_TEMPLATES: Dict[str, str] = {
    "count_by": """
        SELECT {by}, COUNT(*) AS n
        FROM {table}
        GROUP BY {by}
        ORDER BY n DESC
        LIMIT {limit}
    """,
    "sum_by": """
        SELECT {by}, SUM({value}) AS total_{value}, AVG({value}) AS avg_{value}
        FROM {table}
        GROUP BY {by}
        ORDER BY total_{value} DESC
        LIMIT {limit}
    """,
    "mean_by": """
        SELECT {by}, AVG({value}) AS avg_{value}, COUNT({value}) AS n_{value}
        FROM {table}
        WHERE {value} IS NOT NULL
        GROUP BY {by}
        ORDER BY avg_{value} DESC
        LIMIT {limit}
    """,
}

_SAFE_ID = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _safe_ident(name: str) -> str:
    """Valida un identificador SQL para evitar inyección vía config."""
    if not name or not set(name) <= _SAFE_ID:
        raise ValueError(f"identificador no permitido: {name!r}")
    return name


def _build_sql(spec: Dict[str, Any], table: str) -> str:
    template = _TEMPLATES.get(spec.get("kind", "count_by"))
    if template is None:
        raise ValueError(f"agregación desconocida: {spec.get('kind')!r}")
    by = ", ".join(_safe_ident(c) for c in spec["by"])
    fmt = {"table": _safe_ident(table), "by": by, "limit": int(spec.get("limit", 20))}
    if "value" in spec:
        fmt["value"] = _safe_ident(spec["value"])
    return template.format(**fmt)


def build_aggregations(
    duck: Any,
    table: str,
    specs: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Ejecuta las agregaciones configuradas sobre `table` y devuelve {nombre: filas}."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for i, spec in enumerate(specs or []):
        name = spec.get("name") or f"agg_{i}"
        sql = _build_sql(spec, table)
        out[name] = query_to_dicts(duck, sql)
    return out


def persist_aggregations(
    duck: Any,
    dataset: str,
    results: Dict[str, List[Dict[str, Any]]],
    run_id: str,
) -> Path:
    """Guarda las agregaciones como JSON en reports/quality/ y devuelve la ruta."""
    out_dir = paths.reports_dir("quality") / "aggregations"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{dataset}_aggregations_{run_id}.json"
    payload = {"dataset": dataset, "run_id": run_id, "aggregations": results}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)
