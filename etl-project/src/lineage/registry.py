# -*- coding: utf-8 -*-
"""Registro de lineage (sección 19): tablas sources / runs / dataset_lines /
quality_scores en DuckDB. Cada artefacto publicado (bronze, silver, gold) queda
registrado con su ruta, checksum y nº de filas, de modo que el origen de cada
tabla consultable por SQL sea trazable hasta el fichero fuente."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


class Lineage:
    """Persistencia de trazabilidad en DuckDB (catálogo de lineage)."""

    def __init__(self, duck: Any):
        self.db = duck

    def register_source(self, dataset: str, source_spec: Dict[str, Any]) -> None:
        self.db.execute(
            """INSERT INTO sources (dataset, source_name, source_type, raw_path)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (dataset) DO UPDATE SET
                 source_name=excluded.source_name, source_type=excluded.source_type, raw_path=excluded.raw_path""",
            [dataset, source_spec.get("name"), source_spec.get("source_type"), source_spec.get("path")],
        )

    def open_run(self, run_id: str, project: str, version: str) -> None:
        self.db.execute(
            """INSERT INTO runs (run_id, project, version, status)
               VALUES (?, ?, ?, 'running')
               ON CONFLICT (run_id) DO NOTHING""",
            [run_id, project, version],
        )

    def close_run(self, run_id: str, status: str) -> None:
        self.db.execute("UPDATE runs SET status=? WHERE run_id=?", [status, run_id])

    def register_dataset_line(
        self, dataset: str, layer: str, run_id: str, path: str, rows: int, cols: int, file_md5: str
    ) -> None:
        """Idempotente por (dataset, layer, run_id): reejecutar el pipeline no duplica."""
        self.db.execute(
            """INSERT INTO dataset_lines (dataset, layer, run_id, path, rows, cols, file_md5)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (dataset, layer, run_id) DO UPDATE SET
                 path=excluded.path, rows=excluded.rows, cols=excluded.cols,
                 file_md5=excluded.file_md5, created_at=now()""",
            [dataset, layer, run_id, path, rows, cols, file_md5],
        )

    # Backwards-compatible alias
    def upsert_dataset_version(
        self, dataset: str, layer: str, run_id: str, path: str, rows: int, cols: int, file_md5: str
    ) -> None:
        self.register_dataset_line(dataset, layer, run_id, path, rows, cols, file_md5)

    def record_quality_score(
        self, run_id: str, dataset: str, dqs: Dict[str, Any], gate_status: str
    ) -> None:
        """Persiste el DQS por dimensión para poder comparar corridas en el tiempo."""
        dims = {k: v for k, v in dqs.items() if k in
                ("completeness", "validity", "uniqueness", "consistency", "integrity", "freshness", "dqs")}
        self.db.execute(
            """INSERT INTO quality_scores (run_id, dataset, stage, score, dimensions, gate)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (run_id, dataset, stage) DO UPDATE SET
                 score=excluded.score, dimensions=excluded.dimensions,
                 gate=excluded.gate, created_at=now()""",
            [run_id, dataset, "post_quality_gate", dqs.get("dqs"), json.dumps(dims, ensure_ascii=False), gate_status],
        )

    def line_of(self, dataset: str, layer: str, run_id: str) -> Optional[Dict[str, Any]]:
        rel = self.db.execute(
            "SELECT * FROM dataset_lines WHERE dataset=? AND layer=? AND run_id=?",
            [dataset, layer, run_id],
        )
        cols = [d[0] for d in rel.description]
        row = rel.fetchone()
        return dict(zip(cols, row)) if row else None