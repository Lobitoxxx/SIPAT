# -*- coding: utf-8 -*-
"""Base de extractores (sección 4): interfaz común para CSV/XLSX/JSON/Parquet."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from src.utils import hashing


@dataclass
class ExtractResult:
    """Contrato de salida de todo extractor, independiente del formato."""
    dataset: str
    source_name: str
    frame: pd.DataFrame
    raw_path: str
    read_bytes: int
    md5: str
    sha256: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class BaseExtractor(ABC):
    source_type: str = "generic"

    def __init__(self, spec: Dict[str, Any], logger=None):
        self.spec = spec
        self.dataset = spec.get("dataset", "?")
        self.logger = logger

    def _log(self, level: str, msg: str, **kw) -> None:
        if self.logger is None:
            return
        fn = getattr(self.logger, level, self.logger.info)
        fn(msg, extra={"dataset": self.dataset, "operation": "extract"})

    @abstractmethod
    def read_raw(self) -> pd.DataFrame:
        """Lee el fichero fuente y devuelve el DataFrame crudo (sin validar)."""

    def extract(self) -> ExtractResult:
        path = self.spec["path"]
        frame = self.read_raw()
        meta = hashing.file_metadata(path)
        self._log("info", f"extraído dataset={self.dataset} filas={len(frame)} origen={path}", **{})
        return ExtractResult(
            dataset=self.dataset,
            source_name=self.spec.get("name", self.source_type),
            frame=frame,
            raw_path=path,
            read_bytes=meta["file_size_bytes"],
            md5=meta["file_md5"],
            sha256=meta["file_sha256"],
            metadata=meta,
        )