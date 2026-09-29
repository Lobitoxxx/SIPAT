# -*- coding: utf-8 -*-
"""Extractor JSON (listas de objetos o dict)."""
from __future__ import annotations

import json

import pandas as pd

from .base import BaseExtractor


class JsonExtractor(BaseExtractor):
    source_type = "json"

    def read_raw(self) -> pd.DataFrame:
        path = self.spec["path"]
        orient = self.spec.get("orient", "records")
        with open(path, encoding=self.spec.get("encoding", "utf-8")) as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict):
            return pd.DataFrame.from_dict(data, orient=orient if orient in ("index", "columns") else "index")
        raise ValueError("JSON de estructura no soportada: se esperaba lista u objeto")