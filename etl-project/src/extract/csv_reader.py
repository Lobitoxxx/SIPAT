# -*- coding: utf-8 -*-
"""Extractor CSV (encoding y separador configurables)."""
from __future__ import annotations

import pandas as pd

from .base import BaseExtractor


class CsvExtractor(BaseExtractor):
    source_type = "csv"

    def read_raw(self) -> pd.DataFrame:
        return pd.read_csv(
            self.spec["path"],
            encoding=self.spec.get("encoding", "utf-8"),
            sep=self.spec.get("delimiter", ","),
            dtype=self.spec.get("dtype"),
            parse_dates=self.spec.get("parse_dates") or False,
        )