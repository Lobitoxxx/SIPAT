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
    """SHA corto del commit actual si el repo etl-project existe (Git), si no ''.

    OJO: tras integrar `etl-project/` en el repositorio SIPAT, esto devuelve el
    HEAD del repo PADRE, que cambia por motivos ajenos al ETL (editar un README,
    un informe...). Para attributable una variación del DQS NO sirve. Para eso
    está `measurement_fingerprint()`.
    """
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


# Ficheros que, si cambian, pueden alterar el DQS o los gates.
#
# IMPORTANTE: se listan EXPLÍCITAMENTE y NO con un glob de `src/quality/*.py`.
# `reliability.py` audita la medición pero no la produce: incluirlo haría que
# tocar el auditor cambiara la huella y las corridas dejaran de ser comparables
# entre sí, que es justo lo que la huella debe evitar.
_MEASUREMENT_FILES = (
    "config/settings.yaml",
    "config/contracts/onsv_contract.yaml",
    "config/contracts/cinemometros_contract.yaml",
    "config/quality/quality_rules.yaml",
    "config/quality/catalogs/onsv.yaml",
    "config/quality/catalogs/cinemometros.yaml",
    "src/quality/dimensions.py",
    "src/quality/domain_rules.py",
    "src/quality/gates.py",
    "src/quality/model_ready.py",
    "src/validation/contract.py",
    "src/cleaning/clean.py",
)

_MEASUREMENT_GLOBS = _MEASUREMENT_FILES


def measurement_fingerprint() -> str:
    """Huella corta del código y la config que PRODUCEN las métricas.

    A diferencia de `git_commit()`, esta huella SOLO cambia cuando cambia algo
    que puede mover el DQS, el gate o la validación. Es la clave correcta para
    atribuir una variación del DQS: si dos corridas comparten huella, su DQS
    debe ser idéntico, y cualquier diferencia es inestabilidad real.
    """
    import hashlib

    h = hashlib.sha256()
    for rel in _MEASUREMENT_FILES:
        p = ROOT / rel
        if p.is_file():
            h.update(rel.encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()[:10]


def save_run_manifest(run_id: str, payload: Dict[str, Any], extra: Optional[dict] = None) -> Path:
    """Manifiesto JSON del run: resultados por etapa + metadatos de trazabilidad."""
    manifest = {
        "run_id": run_id,
        "project": payload.get("project", "SIPAT-ETL"),
        "version": read_version(),
        "git_commit": git_commit(),
        "measurement_fingerprint": measurement_fingerprint(),
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