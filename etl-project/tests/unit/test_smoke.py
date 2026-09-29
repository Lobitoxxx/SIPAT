# -*- coding: utf-8 -*-
"""Smoke test: end-to-end del pipeline sobre fixtures mini (sin datos reales)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_extract_xlsx_with_preamble(mini_onsv_xlsx, monkeypatch, tmp_path):
    """Verifica la lectura de XLSX con cabecera desplazada (header_row configurable)."""
    from src.extract.excel_reader import ExcelExtractor

    spec = {
        "dataset": "onsv",
        "name": "onsv_xlsx",
        "source_type": "xlsx",
        "path": str(mini_onsv_xlsx),
        "sheet": 0,
        "header_row": 4,
    }
    res = ExcelExtractor(spec).extract()
    assert res.frame.shape == (3, 16)
    assert "CÓDIGO SINIESTRO" in res.frame.columns
    assert res.frame["CÓDIGO SINIESTRO"].tolist() == ["P0001", "P0002", "P0003"]
    assert res.md5  # checksum de trazabilidad


def test_extract_csv_utf8_sig(mini_cinemometros_csv):
    from src.extract.csv_reader import CsvExtractor

    spec = {
        "dataset": "cinemometros",
        "name": "cinemometros_csv",
        "source_type": "csv",
        "path": str(mini_cinemometros_csv),
        "encoding": "utf-8-sig",
    }
    res = CsvExtractor(spec).extract()
    assert res.frame.shape == (3, 11)
    assert "NRO_DETECCION" in res.frame.columns


def test_all_modules_importable_by_config(settings_fresh=None):
    """Cada paquete src/* debe importarse sin error (importación estática)."""
    import importlib

    modules = [
        "src.utils.paths", "src.utils.configloader", "src.utils.hashing",
        "src.utils.logging_util", "src.utils.versioning",
        "src.extract.base", "src.extract.excel_reader", "src.extract.csv_reader",
        "src.extract.json_reader", "src.extract.parquet_reader", "src.extract.factory",
        "src.extract.register_raw", "src.profiling.profile",
        "src.validation.contract", "src.cleaning.clean", "src.cleaning.transform_log",
        "src.transform.features", "src.quality.dimensions", "src.quality.domain_rules",
        "src.quality.gates", "src.quality.quarantine", "src.quality.model_ready",
        "src.load.silver", "src.load.gold", "src.sql_engine.engine", "src.lineage.registry",
        "src.orchestration.flow", "src.reports.report", "src.ml.placeholder",
    ]
    for m in modules:
        importlib.import_module(m)


def test_pipeline_mini_end_to_end(mini_onsv_xlsx, mini_cinemometros_csv, tmp_path, monkeypatch):
    """Corrida completa del pipeline sobre fixtures mini con DuckDB temporal."""
    from src.sql_engine.engine import duckdb_engine
    from src.orchestration.flow import run_pipeline

    # Aísla las rutas de salida: el smoke test no debe escribir en data/, reports/
    # ni artifacts/ del proyecto real.
    from src.utils import paths

    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setattr(paths, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(paths, "REPORTS", tmp_path / "reports")

    db = tmp_path / "mini_lineage.duckdb"
    monkeypatch.setattr("src.utils.configloader.sipat_root", lambda: tmp_path)
    # apuntamos las fuentes a los mini ficheros
    import yaml

    src_dir = Path(__file__).resolve().parents[2] / "config" / "sources"
    onsv_cfg = yaml.safe_load((src_dir / "onsv_xlsx.yaml").read_text(encoding="utf-8"))
    onsv_cfg["source"]["path"] = str(mini_onsv_xlsx)
    onsv_cfg["source"]["header_row"] = 4
    cin_cfg = yaml.safe_load((src_dir / "cinemometros_csv.yaml").read_text(encoding="utf-8"))
    cin_cfg["source"]["path"] = str(mini_cinemometros_csv)

    monkeypatch.setattr(
        "src.orchestration.flow.load_sources",
        lambda: {"onsv": onsv_cfg["source"], "cinemometros": cin_cfg["source"]},
    )

    result = run_pipeline(datasets=["onsv", "cinemometros"], db_path=db)
    assert result["status"] == "OK"
    for ds, r in result["results"].items():
        assert r["gate"]["status"] in ("PASSED", "WARNING")
        assert r["gate"]["dqs"] >= 90
    assert db.exists()
