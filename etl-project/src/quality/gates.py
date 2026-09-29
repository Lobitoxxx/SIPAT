# -*- coding: utf-8 -*-
"""Quality gates (sección 8): PASSED / WARNING / FAILED según reglas y umbral global."""
from __future__ import annotations

from typing import Any, Dict, List

from src.quality import quarantine as qz
from src.utils import hashing, paths


def evaluate_gate(
    dqs: Dict[str, Any],
    violations: List[Dict[str, Any]],
    rules_cfg: Dict[str, Any],
    dataset: str,
    run_id: str,
    source: str | None = None,
    df=None,
) -> Dict[str, Any]:
    """Evalua umbrales: min_quality_score y reglas criticales al 100% (configuradas)."""
    gates = rules_cfg.get("quality_gates", {})
    min_score = gates.get("min_quality_score", 90)
    critical = [v for v in violations if v["severity"] == "critical"]
    warnings = [v for v in violations if v["severity"] != "critical"]

    ok_score = dqs["dqs"] >= min_score
    ok_critical = all(v["count"] == 0 for v in critical)

    # Cuarentena de registros con reglas críticas (si se requiere)
    quarantine_path = None
    if df is not None and critical and gates.get("quarantine_on_critical", True):
        quarantine_path = qz.push_quarantine(df, violations, dataset, run_id, source or dataset)

    if ok_score and ok_critical:
        status = "PASSED"
    elif ok_critical and not ok_score:
        status = "WARNING"
    else:
        status = "FAILED"

    result = {
        "dataset": dataset,
        "dqs": dqs["dqs"],
        "min_quality_score": min_score,
        "status": status,
        "n_critical_errors": sum(v["count"] for v in critical),
        "n_warnings": sum(v["count"] for v in warnings),
        "critical_rules_failed": [v["rule"] for v in critical],
        "warning_rules_failed": [v["rule"] for v in warnings],
        "quarantine_path": str(quarantine_path) if quarantine_path else None,
        "quarantine_records": len(qz_push_records(quarantine_path)) if quarantine_path else 0,
        "evaluated_at": hashing.now_iso(),
    }
    return result


def qz_push_records(path) -> list:
    try:
        import json

        return json.loads(open(path, encoding="utf-8").read())
    except Exception:
        return []