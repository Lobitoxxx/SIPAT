# -*- coding: utf-8 -*-
"""Checksums (MD5/SHA256) y metadatos de ficheros para trazabilidad Bronze (sección 3 y 19)."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def file_md5(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def file_sha256(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def content_sha256(data: bytes | str) -> str:
    """SHA-256 de un contenido en memoria (para claves de registro sin fichero)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_metadata(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    st = path.stat()
    return {
        "file_name": path.name,
        "file_size_bytes": st.st_size,
        "file_md5": file_md5(path),
        "file_sha256": file_sha256(path),
        "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    }


def write_json(path: str | Path, payload: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)