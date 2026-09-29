# -*- coding: utf-8 -*-
"""Tests unitarios: extractores, contratos, limpieza, DQS, gates, quarantine, features."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.cleaning.clean import clean
from src.cleaning.transform_log import TransformationLog
from src.load import silver
from src.quality import dimensions, model_ready
from src.quality.domain_rules import detect_violations
from src.quality.gates import evaluate_gate
from src.quality.quarantine import push_quarantine
from src.transform.features import derive_features
from src.utils import hashing, versioning
from src.utils.configloader import load_catalogs, load_contract, load_quality_rules, load_settings
from src.validation.contract import validate_contract


# --- extractores ---

def test_extractor_factory_by_source_type():
    from src.extract.factory import get_extractor
    from src.extract.csv_reader import CsvExtractor
    from src.extract.excel_reader import ExcelExtractor
    from src.extract.json_reader import JsonExtractor
    from src.extract.parquet_reader import ParquetExtractor

    assert isinstance(get_extractor({"source_type": "csv"}), CsvExtractor)
    assert isinstance(get_extractor({"source_type": "xlsx"}), ExcelExtractor)
    assert isinstance(get_extractor({"source_type": "json"}), JsonExtractor)
    assert isinstance(get_extractor({"source_type": "parquet"}), ParquetExtractor)


def test_extractor_factory_rejects_unknown_type():
    from src.extract.factory import get_extractor

    with pytest.raises(ValueError):
        get_extractor({"source_type": "avro"})


def test_json_extractor_reads_list(tmp_path):
    import json as _json

    from src.extract.json_reader import JsonExtractor

    p = tmp_path / "d.json"
    p.write_text(_json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]), encoding="utf-8")
    res = JsonExtractor({"dataset": "t", "source_type": "json", "path": str(p)}).extract()
    assert res.frame.shape == (2, 2)


def test_parquet_extractor_roundtrip(tmp_path):
    from src.extract.parquet_reader import ParquetExtractor

    p = tmp_path / "d.parquet"
    pd.DataFrame({"x": [1, 2, 3]}).to_parquet(p)
    res = ParquetExtractor({"dataset": "t", "source_type": "parquet", "path": str(p)}).extract()
    assert res.frame["x"].sum() == 6


def test_bronze_registration_is_idempotent(mini_cinemometros_csv, tmp_path, monkeypatch):
    from src.extract.csv_reader import CsvExtractor
    from src.extract.register_raw import register_bronze
    from src.utils import paths

    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    res = CsvExtractor({"dataset": "cine_test", "source_type": "csv",
                        "path": str(mini_cinemometros_csv), "encoding": "utf-8-sig"}).extract()
    a = register_bronze(res, "run-1", "1.0")
    b = register_bronze(res, "run-2", "1.0")
    assert a["rows"] == 3
    assert b["metadata"]["status"] == "skipped_existing"


# --- contrato ---

def test_contract_detects_missing_column(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    res = validate_contract(onsv_rows.drop(columns=["codigo"]), c)
    assert res["valid"] is False
    assert any(e[1] == "missing_column" for e in res["errors"])


def test_contract_valid_frame(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    res = validate_contract(onsv_rows, c)
    assert res["valid"] is True, res["errors"]


def test_contract_detects_duplicate_pk(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    df = pd.concat([onsv_rows, onsv_rows.head(1)], ignore_index=True)
    res = validate_contract(df, c)
    assert res["valid"] is False
    assert any(e[1] == "unique" for e in res["errors"])


def test_contract_allows_extra_columns(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    df = onsv_rows.assign(columna_nueva=[1, 2, 3])
    res = validate_contract(df, c)
    assert res["valid"] is True
    assert "columna_nueva" in res["details_by_column"]["__extra_columns"]


def test_contract_detects_out_of_range_coordinates(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    df = onsv_rows.copy()
    df.loc[0, "latitud"] = 500.0
    res = validate_contract(df, c)
    assert res["valid"] is False


# --- limpieza ---

def test_clean_renames_and_normalizes(mini_cinemometros_csv, tmp_path):
    from src.extract.csv_reader import CsvExtractor

    s = load_settings()
    raw = CsvExtractor({"dataset": "cinemometros", "source_type": "csv",
                        "path": str(mini_cinemometros_csv), "encoding": "utf-8-sig"}).read_raw()
    tlog = TransformationLog("run-x", "cinemometros", tmp_path)
    out = clean(raw, s["datasets"]["cinemometros"], tlog)
    assert "nro_deteccion" in out.columns
    assert "NRO_DETECCION" not in out.columns
    # LIMA/Lima -> LIMA unificado (el fixture trae 'Lima' en la fila 2)
    assert set(out["region"]) == {"LIMA", "PIURA"}
    # lat/lon duplicadas se descartan
    assert "lat" not in out.columns and "lon" not in out.columns
    assert pd.api.types.is_datetime64_any_dtype(out["fecha_papeleta"])


def test_clean_strips_degree_symbols(mini_onsv_xlsx, tmp_path):
    from src.extract.excel_reader import ExcelExtractor

    s = load_settings()
    spec = {"dataset": "onsv", "source_type": "xlsx", "path": str(mini_onsv_xlsx),
            "sheet": 0, "header_row": 4}
    raw = ExcelExtractor(spec).read_raw()
    raw["COORDENADAS  LONGITUD"] = raw["COORDENADAS  LONGITUD"].astype(object)
    raw.loc[0, "COORDENADAS  LONGITUD"] = "-77.0312°"
    tlog = TransformationLog("run-y", "onsv", tmp_path)
    out = clean(raw, s["datasets"]["onsv"], tlog)
    assert pd.notna(out.loc[0, "longitud"])
    assert out.loc[0, "longitud"] == pytest.approx(-77.0312, abs=1e-4)
    ops = [e.operation for e in tlog.entries]
    assert "strip_numeric_chars" in ops


def test_clean_imputes_configured_columns(mini_onsv_xlsx, tmp_path):
    from src.extract.excel_reader import ExcelExtractor

    s = load_settings()
    spec = {"dataset": "onsv", "source_type": "xlsx", "path": str(mini_onsv_xlsx),
            "sheet": 0, "header_row": 4}
    raw = ExcelExtractor(spec).read_raw()
    raw["CANTIDAD DE VEHICULOS DAÑADOS"] = [None, 1, 2]
    tlog = TransformationLog("run-z", "onsv", tmp_path)
    out = clean(raw, s["datasets"]["onsv"], tlog)
    assert out["vehiculos_danados"].isna().sum() == 0
    assert "impute_median" in [e.operation for e in tlog.entries]


def test_clean_is_idempotent(onsv_rows, tmp_path):
    s = load_settings()
    tlog = TransformationLog("run-i", "onsv", tmp_path)
    once = clean(onsv_rows, s["datasets"]["onsv"], tlog)
    twice = clean(once, s["datasets"]["onsv"], tlog)
    pd.testing.assert_frame_equal(once, twice)


def test_transform_log_persists_json(mini_onsv_xlsx, tmp_path):
    from src.extract.excel_reader import ExcelExtractor

    s = load_settings()
    spec = {"dataset": "onsv", "source_type": "xlsx", "path": str(mini_onsv_xlsx),
            "sheet": 0, "header_row": 4}
    raw = ExcelExtractor(spec).read_raw()
    tlog = TransformationLog("run-tl", "onsv", tmp_path)
    clean(raw, s["datasets"]["onsv"], tlog)
    path = tlog.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == "run-tl"
    assert len(data["operations"]) > 0
    for op in data["operations"]:
        assert "operation" in op and "records_affected" in op


# --- features ---

def test_derive_features_onsv(onsv_rows):
    out = derive_features(onsv_rows, "onsv")
    for col in ("anio", "mes", "dia_semana", "hora_num", "tramo_dia", "geo_valid"):
        assert col in out.columns
    assert out["anio"].iloc[0] == 2023
    assert out["tramo_dia"].iloc[0] in {"madrugada", "manana", "tarde", "noche"}


def test_derive_features_cinemometros(cinemometros_rows):
    out = derive_features(cinemometros_rows, "cinemometros")
    assert "exceso_kmh" in out.columns and "excede_limite" in out.columns
    assert bool(out["excede_limite"].iloc[0]) is True


# --- DQS / reglas / gates ---

def test_dqs_weights_sum_to_one():
    w = load_settings()["quality"]["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_dqs_perfect_dataset(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    dqs = dimensions.compute_dqs(onsv_rows, s, c, load_catalogs("onsv"))
    assert 0 <= dqs["dqs"] <= 100
    for dim in ("completeness", "validity", "uniqueness", "consistency", "integrity", "freshness"):
        assert dim in dqs


def test_dqs_penalizes_duplicates(onsv_rows):
    s = load_settings()
    c = load_contract("onsv", s)
    clean_dqs = dimensions.compute_dqs(onsv_rows, s, c)
    dup = pd.concat([onsv_rows, onsv_rows.head(1)], ignore_index=True)
    dup_dqs = dimensions.compute_dqs(dup, s, c)
    assert dup_dqs["uniqueness"] < clean_dqs["uniqueness"]


def test_domain_rules_detect_bad_coordinates(onsv_rows):
    rules = [{"rule": "coordenadas_peru", "severity": "critical", "columns": ["latitud", "longitud"]}]
    df = onsv_rows.copy()
    df.loc[0, "latitud"] = 10.0  # fuera del rango Perú
    df.loc[0, "longitud"] = 10.0
    v = detect_violations(df, rules, {})
    assert len(v) == 1 and v[0]["count"] == 1 and v[0]["severity"] == "critical"


def test_domain_rules_catalog_mismatch(onsv_rows):
    rules = [{"rule": "departamento_catalogo", "severity": "critical", "columns": ["departamento"]}]
    df = onsv_rows.copy()
    df.loc[0, "departamento"] = "ATLANTIDA"
    v = detect_violations(df, rules, load_catalogs("onsv"))
    assert v and v[0]["count"] == 1


def test_gate_passes_on_clean_data(onsv_rows):
    rules_cfg = load_quality_rules()
    dqs = {"dqs": 95.0}
    g = evaluate_gate(dqs, [], rules_cfg, "onsv", "run-g", source="x", df=None)
    assert g["status"] == "PASSED"
    assert g["n_critical_errors"] == 0


def test_gate_fails_on_critical(onsv_rows):
    rules_cfg = load_quality_rules()
    dqs = {"dqs": 95.0}
    violations = [{"rule": "pk_unique", "severity": "critical", "column": "codigo",
                   "count": 3, "rows": [0, 1, 2]}]
    g = evaluate_gate(dqs, violations, rules_cfg, "onsv", "run-f", source="x", df=onsv_rows)
    assert g["status"] == "FAILED"
    assert g["n_critical_errors"] == 3
    assert g["quarantine_path"] is not None


def test_quarantine_record_structure(onsv_rows):
    violations = [{"rule": "pk_not_null", "severity": "critical", "column": "codigo",
                   "count": 1, "rows": [1]}]
    p = push_quarantine(onsv_rows, violations, "onsv", "run-q", "src.csv")
    recs = json.loads(p.read_text(encoding="utf-8"))
    assert len(recs) == 1
    required = {"record_id", "pipeline_run_id", "dataset", "source", "rule_failed",
                "error_code", "error_description", "original_value", "detected_at"}
    assert required.issubset(recs[0].keys())


def test_quarantine_ignores_warning_rules(onsv_rows):
    violations = [{"rule": "hora_formato", "severity": "warning", "column": "hora",
                   "count": 2, "rows": [0, 2]}]
    p = push_quarantine(onsv_rows, violations, "onsv", "run-q2", "src.csv")
    assert json.loads(p.read_text(encoding="utf-8")) == []


# --- model ready ---

def test_model_ready_true_when_all_conditions_met():
    r = model_ready.is_model_ready("onsv", "VALID", "PASSED", True, 0, 95.0, 90.0, True)
    assert r["model_ready"] is True and r["decision"] == "MODEL_READY"


def test_model_ready_false_on_critical_errors():
    r = model_ready.is_model_ready("onsv", "VALID", "PASSED", True, 3, 95.0, 90.0, True)
    assert r["model_ready"] is False and r["decision"] == "NO_MODEL_READY"


def test_model_ready_false_on_invalid_contract():
    r = model_ready.is_model_ready("onsv", "INVALID", "PASSED", True, 0, 95.0, 90.0, True)
    assert r["model_ready"] is False


def test_model_ready_false_on_low_dqs():
    r = model_ready.is_model_ready("onsv", "VALID", "PASSED", True, 0, 70.0, 90.0, True)
    assert r["model_ready"] is False


# --- silver / utils ---

def test_silver_roundtrip(onsv_rows, tmp_path, monkeypatch):
    from src.utils import paths

    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    out = silver.write_silver(onsv_rows, "onsv", "run-s", "1.0")
    assert Path(out["path"]).exists()
    back = silver.read_silver("onsv", "1.0")
    assert len(back) == len(onsv_rows)


def test_hashing_helpers(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"sipat")
    assert hashing.file_md5(p) == hashing.file_md5(p)
    assert hashing.file_sha256(p) == hashing.file_sha256(p)
    assert hashing.content_sha256("abc") == hashing.content_sha256(b"abc")


def test_run_id_unique():
    a = versioning.new_run_id()
    b = versioning.new_run_id()
    assert a != b and a.startswith("run-")
