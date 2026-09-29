# -*- coding: utf-8 -*-
"""Consola DuckDB utilitaria sobre el catálogo de lineage SIPAT-ETL.

Uso: python scripts/duckdb_shell.py "SELECT * FROM dataset_lines;"
Sin argumento: ejecuta una consulta por defecto y sale.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.sql_engine.engine import duckdb_engine, query_to_dicts  # noqa: E402


def main() -> int:
    sql = " ".join(sys.argv[1:]) or "SELECT dataset, layer, run_id, rows, path FROM dataset_lines ORDER BY id DESC LIMIT 5;"
    con = duckdb_engine()
    rows = query_to_dicts(con, sql)
    if not rows:
        print("(sin resultados)")
        return 0
    cols = rows[0].keys()
    print("\t".join(map(str, cols)))
    for r in rows:
        print("\t".join(str(r[c]) for c in cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
