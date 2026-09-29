# -*- coding: utf-8 -*-
"""Versionado y run_id (secciones 3, 18 y 19): trazabilidad end-to-end."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .paths import ROOT, artifacts_dir


def new_run_id(prefix: str = "run") -> str:
    """run_id único por ejecución: run-YYYYMMDD-HHMMSS-<uuid8>."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}-{uuid.uuid4().hex[:8]}"


def read_version() -> str:
    vf = ROOT / "VERSION"
    return vf.read_text(encoding="utf-8").strip() if vf.exists() else "0.0.0"


def git_commit() -> str:
    """SHA corto del commit actual si el repo etl-project existe (Git), si no ''."""
    from io import BytesIO
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def save_run_manifest(run_id: str, payload: Dict[str, Any], extra: Optional[dict] = None) -> Path:
    """Manifiesto JSON del run: resultados por etapa + metadatos de trazabilidad."""
    manifest = {
        "run_id": run_id,
        "project": payload.get("project", "SIPAT-ETL"),
        "version": read_version(),
        "git_commit": git_commit(),
        "started_at": payload.get("started_at"),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": payload.get("status", "unknown"),
        "stages": payload.get("stages", {}),
        "datasets": payload.get("datasets", {}),
    }
    if extra:
        manifest.update(extra)
    p = artifacts_dir("runs", run_id) / "manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return p