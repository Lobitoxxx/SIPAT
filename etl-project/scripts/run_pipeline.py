# -*- coding: utf-8 -*-
"""Punto de entrada: ejecuta el pipeline ETL completo.

Uso:
    python scripts/run_pipeline.py                     # todos los datasets
    python scripts/run_pipeline.py --dataset onsv
    python scripts/run_pipeline.py --dataset onsv,cinemometros
    python scripts/run_pipeline.py --engine sequential  # sin Prefect
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.prefect_flow import run_pipeline_auto  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="SIPAT-ETL: pipeline de 15 etapas por dataset.")
    ap.add_argument("--dataset", default=None, help="Filtrar datasets (coma separada). Vacío = todos.")
    ap.add_argument("--db", default=None, help="Ruta DuckDB de lineage (opcional).")
    ap.add_argument(
        "--engine",
        default="auto",
        choices=("auto", "prefect", "sequential"),
        help="Orquestador: auto (Prefect si disponible), prefect o sequential.",
    )
    args = ap.parse_args()

    datasets = [d.strip() for d in args.dataset.split(",") if d.strip()] if args.dataset else None
    result = run_pipeline_auto(
        datasets=datasets, db_path=Path(args.db) if args.db else None, engine=args.engine
    )

    print("=" * 60)
    print(f"PIPELINE {result['status']}  (run_id={result['run_id']}, engine={args.engine})")
    print(f"manifest: {result['manifest']}")
    for ds, r in result["results"].items():
        g = r.get("gate", {})
        print(f"  - {ds}: dqs={g.get('dqs')} gate={g.get('status')} "
              f"crit={g.get('n_critical_errors')} q={g.get('quarantine_records')}")
    if result["status"] == "FAILED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())