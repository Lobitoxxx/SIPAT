# -*- coding: utf-8 -*-
"""TransformationLog (sección 21): bitácora JSON de cada operación sobre el dataset."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class LogEntry:
    operation: str
    column: Optional[str]
    records_affected: int
    before_examples: List[Any] = field(default_factory=list)
    after_examples: List[Any] = field(default_factory=list)
    strategy: Optional[str] = None
    detail: Optional[str] = None


class TransformationLog:
    """Acumula operaciones y las vuelca a artifacts/runs/<run_id>/transform_log_<dataset>.json (sección 21)."""

    def __init__(self, run_id: str, dataset: str, run_dir: Path):
        self.run_id = run_id
        self.dataset = dataset
        self.run_dir = run_dir
        self.entries: List[LogEntry] = []

    def add(
        self,
        operation: str,
        column: str | None = None,
        records_affected: int = 0,
        before: list | None = None,
        after: list | None = None,
        strategy: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.entries.append(
            LogEntry(
                operation=operation,
                column=column,
                records_affected=int(records_affected),
                before_examples=before or [],
                after_examples=after or [],
                strategy=strategy,
                detail=detail,
            )
        )

    def save(self) -> Path:
        path = self.run_dir / f"transform_log_{self.dataset}.json"
        payload = {
            "run_id": self.run_id,
            "dataset": self.dataset,
            "operations": [asdict(e) for e in self.entries],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def summarize(self) -> dict:
        return {
            "dataset": self.dataset,
            "n_operations": len(self.entries),
            "operations": [e.operation for e in self.entries],
        }