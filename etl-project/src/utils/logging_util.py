# -*- coding: utf-8 -*-
"""Logging estructurado (sección 23): timestamp, level, module, run_id, dataset, operation."""
from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .paths import artifacts_dir

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        for key in ("run_id", "dataset", "operation"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(
    name: str,
    run_id: Optional[str] = None,
    dataset: Optional[str] = None,
    log_dir: Optional[Path] = None,
) -> logging.Logger:
    """Logger con consola (estructurada) y fichero rotatorio en artifacts/logs."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(JsonFormatter())
    logger.addHandler(console)

    if log_dir is None:
        log_dir = artifacts_dir("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        log_dir / "etl.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(JsonFormatter())
    logger.addHandler(fh)
    return logger


def bind(logger: logging.Logger, **kw) -> None:
    """Adjunta campos estructurados (run_id, dataset, operation) a logs posteriores."""
    logger._bind = {**getattr(logger, "_bind", {}), **kw}


def bind_attrs(logger: logging.Logger) -> dict:
    return dict(getattr(logger, "_bind", {}))