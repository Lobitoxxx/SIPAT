# -*- coding: utf-8 -*-
"""Extractor XLSX. Soporta cabeceras con preámbulo (header_row configurable)."""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from .base import BaseExtractor


class ExcelExtractor(BaseExtractor):
    source_type = "xlsx"

    def read_raw(self) -> pd.DataFrame:
        sheet = self.spec.get("sheet", 0)
        header = self.spec.get("header_row", 0)
        usecols = self.spec.get("usecols")
        dtype = self.spec.get("dtype")
        return pd.read_excel(
            self.spec["path"],
            sheet_name=sheet,
            header=header,
            usecols=usecols,
            dtype=dtype,
        )