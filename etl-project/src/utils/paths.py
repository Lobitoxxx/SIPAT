# -*- coding: utf-8 -*-
"""Rutas del proyecto SIPAT-ETL."""
from __future__ import annotations

from pathlib import Path

# etl-project/  (src/utils/paths.py -> parents[2])
ROOT = Path(__file__).resolve().parents[2]

SRC = ROOT / "src"
CONFIG = ROOT / "config"
DATA = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"


def ensure(base: Path, *parts: str) -> Path:
    p = base if not parts else base.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_dir(*parts: str) -> Path:
    return ensure(DATA, *parts)


def artifacts_dir(*parts: str) -> Path:
    return ensure(ARTIFACTS, *parts)


def reports_dir(*parts: str) -> Path:
    return ensure(REPORTS, *parts)


def config_path(*parts: str) -> Path:
    return Path(CONFIG, *parts)