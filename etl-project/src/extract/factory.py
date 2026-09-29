# -*- coding: utf-8 -*-
"""Fábrica de extractores: elegir clase según source_type (sección 4)."""
from __future__ import annotations

from typing import Any, Dict

from .base import BaseExtractor
from .csv_reader import CsvExtractor
from .excel_reader import ExcelExtractor
from .json_reader import JsonExtractor
from .parquet_reader import ParquetExtractor

_REGISTRY = {
    "csv": CsvExtractor,
    "xlsx": ExcelExtractor,
    "json": JsonExtractor,
    "parquet": ParquetExtractor,
}


def get_extractor(spec: Dict[str, Any], logger=None) -> BaseExtractor:
    st = spec.get("source_type")
    if st not in _REGISTRY:
        raise ValueError(f"Tipo de fuente no soportado: {st!r}. Soportados: {sorted(_REGISTRY)}")
    return _REGISTRY[st](spec, logger=logger)