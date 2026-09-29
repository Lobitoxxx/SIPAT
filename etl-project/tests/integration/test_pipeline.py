# -*- coding: utf-8 -*-
"""Tests de integración: pipeline completo, lineage DuckDB, idempotencia, report HTML."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

STAGES = [
    "start", "extract", "register_raw", "profiling_before", "clean", "schema_validation",
    "transform", "data_quality", "quarantine", "quality_gate", "load_silver", "build_gold",
    "profiling_after", "generate_report", "finish",
]


@pytest.fixture
def patch_sources(monkeypatch, mini_onsv_xlsx, mini_cinemometros_csv):
    src_dir = Path(__file__).resolve().parents[2] / "config" / "sources"
    onsv = yaml.safe_load((src_dir / "onsv_xlsx.yaml").read_text(encoding="utf-8"))
    onsv["source"]["path"] = str(mini_onsv_xlsx)
    onsv["source"]["header_row"] = 4
    cine = yaml.safe_load((src_dir / "cinemometros_csv.yaml").read_text(encoding="utf-8"))
    cine["source"]["path"] = str(mini_cinemometros_csv)
    monkeypatch.setattr(
        "src.orchestration.flow.load_sources",
        lambda: {"onsv": onsv["source"], "cinemometros": cine["source"]},
    )
    return onsv, cine


@pytest.fixture
def isolated_project(monkeypatch, tmp_path):
    """Redirige data/, artifacts/ y reports/ a un tmp_path para no tocar el proyecto."""
    from src.utils import paths

    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setattr(paths, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(paths, "REPORTS", tmp_path / "reports")
    return tmp_path


def test_pipeline_all_stages_executed(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    result = run_pipeline(datasets=["onsv", "cinemometros"], db_path=tmp_path / "l.duckdb")
    assert result["status"] == "OK"
    for ds in ("onsv", "cinemometros"):
        stages = result["results"][ds]["stages"]
        for name in STAGES:
            assert name in stages, f"falta etapa {name} en {ds}"
            assert stages[name]["status"] == "OK", f"etapa {name} falló en {ds}"


def test_pipeline_writes_manifest(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    result = run_pipeline(datasets=["onsv"], db_path=tmp_path / "l2.duckdb")
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert manifest["run_id"] == result["run_id"]
    assert "onsv" in manifest["datasets"]
    assert manifest["datasets"]["onsv"]["gate"] in ("PASSED", "WARNING")


def test_pipeline_writes_silver_gold_and_report(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    result = run_pipeline(datasets=["onsv", "cinemometros"], db_path=tmp_path / "l3.duckdb")
    data = isolated_project / "data"
    assert list((data / "silver").glob("*.parquet"))
    assert list((data / "gold").glob("*_analytics_*.parquet"))
    reports = list((isolated_project / "reports" / "quality").glob("*.html"))
    assert len(reports) >= 1
    assert "Quality Gate" in reports[0].read_text(encoding="utf-8")


def test_pipeline_is_idempotent(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    db = tmp_path / "l4.duckdb"
    r1 = run_pipeline(datasets=["cinemometros"], db_path=db)
    r2 = run_pipeline(datasets=["cinemometros"], db_path=db)
    assert r1["run_id"] != r2["run_id"]
    # silver determinista: mismo nº de filas
    a = r1["results"]["cinemometros"]["gate"]["dqs"]
    b = r2["results"]["cinemometros"]["gate"]["dqs"]
    assert a == b


def test_lineage_registered_in_duckdb(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline
    from src.sql_engine.engine import duckdb_engine, query_to_dicts

    db = tmp_path / "l5.duckdb"
    run_pipeline(datasets=["cinemometros"], db_path=db)
    con = duckdb_engine(db)
    rows = query_to_dicts(con, "SELECT dataset, layer, rows FROM dataset_lines ORDER BY created_at")
    assert any(r["layer"] == "silver" and r["dataset"] == "cinemometros" for r in rows)
    runs = query_to_dicts(con, "SELECT run_id, status FROM runs")
    assert runs and runs[0]["status"] == "OK"


def test_transform_log_written_per_dataset(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    result = run_pipeline(datasets=["onsv"], db_path=tmp_path / "l6.duckdb")
    run_id = result["run_id"]
    p = isolated_project / "artifacts" / "runs" / run_id / "transform_log_onsv.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    ops = {o["operation"] for o in data["operations"]}
    assert "parse_date" in ops and "rename_canonical" in ops


def test_profiles_before_and_after(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    run_pipeline(datasets=["onsv"], db_path=tmp_path / "l7.duckdb")
    prof = isolated_project / "reports" / "profiling"
    for stage in ("before", "after"):
        for ext in ("json", "csv", "html"):
            assert (prof / f"onsv_{stage}_profile.{ext}").exists()


def test_quarantine_file_created_even_when_empty(patch_sources, isolated_project, tmp_path):
    from src.orchestration.flow import run_pipeline

    run_pipeline(datasets=["onsv"], db_path=tmp_path / "l8.duckdb")
    q = list((isolated_project / "data" / "quarantine").glob("onsv_quarantine_*.json"))
    assert q and json.loads(q[0].read_text(encoding="utf-8")) == []


def test_duckdb_aggregations_onsv(isolated_project, tmp_path, patch_sources):
    """La capa Gold es consultable con SQL sobre la tabla silver registrada."""
    from src.orchestration.flow import run_pipeline
    from src.sql_engine.engine import duckdb_engine, query_to_dicts

    db = tmp_path / "l9.duckdb"
    run_pipeline(datasets=["onsv"], db_path=db)
    con = duckdb_engine(db)
    rows = query_to_dicts(
        con, "SELECT departamento, COUNT(*) AS n FROM onsv_silver GROUP BY 1 ORDER BY n DESC"
    )
    assert rows and rows[0]["n"] > 0
