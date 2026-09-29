# -*- coding: utf-8 -*-
"""Extractor Parquet."""
from __future__ import annotations

import pandas as pd

from .base import BaseExtractor


class ParquetExtractor(BaseExtractor):
    source_type = "parquet"

    def read_raw(self) -> pd.DataFrame:
        return pd.read_parquet(
            self.spec["path"],
            engine=self.spec.get("engine", "pyarrow"),
        )