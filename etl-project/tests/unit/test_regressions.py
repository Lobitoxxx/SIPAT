# -*- coding: utf-8 -*-
"""Tests de regresión de los defectos reales detectados y corregidos.

Cada test de este fichero falla con el código anterior a la corrección y documenta
por qué el fallo era un problema de integridad, no un detalle cosmético.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from src.extract.register_raw import _parquet_safe
from src.quality import dimensions
from src.quality.domain_rules import detect_violations
from src.utils.configloader import load_catalogs, load_settings
from src.validation.contract import validate_contract

SETTINGS = load_settings()


# --- Bronze: columnas object con tipos mezclados -------------------------

def test_parquet_safe_handles_mixed_date_column():
    """Regresión: 'FECHA SINIESTRO' mezcla datetime y '01/01/2021' (DD/MM).

    PyArrow lanza `Expected bytes, got a 'datetime.datetime' object` y el pipeline
    abortaba en la etapa register_raw. Bronze debe quedar escribible.
    """
    s = pd.Series([dt.datetime(2021, 1, 1), "01/01/2021", dt.datetime(2021, 3, 5), "03/05/2021"])
    df = pd.DataFrame({"FECHA SINIESTRO": s})
    out = _parquet_safe(df)
    out.to_parquet(Path(__import__("tempfile").gettempdir()) / "_t_safe_date.parquet")
    assert out["FECHA SINIESTRO"].notna().all()


def test_parquet_safe_handles_mixed_numeric_with_degree_symbol():
    """Regresión: 'COORDENADAS  LONGITUD' mezcla float y '-71.325300°'."""
    s = pd.Series([-77.03, "-71.325300°", -71.5, "-68.5°"])
    df = pd.DataFrame({"COORDENADAS  LONGITUD": s})
    out = _parquet_safe(df)
    out.to_parquet(Path(__import__("tempfile").gettempdir()) / "_t_safe_num.parquet")
    assert pd.api.types.is_numeric_dtype(out["COORDENADAS  LONGITUD"])


def test_parquet_safe_keeps_plain_text_columns():
    """Una columna de texto sin valores numéricos/fecha NO debe convertirse."""
    df = pd.DataFrame({"codigo": ["P001", "P002"], "nota": ["a", "b"]})
    out = _parquet_safe(df)
    assert out["codigo"].tolist() == ["P001", "P002"]
    assert out["nota"].tolist() == ["a", "b"]


def test_parquet_safe_preserves_values_for_real_onsv_like_frame():
    """El frame real de ONSV debe escribirse en Parquet sin perder filas."""
    df = pd.DataFrame(
        {
            "FECHA SINIESTRO": [dt.datetime(2021, 1, 1), "02/01/2021", dt.datetime(2021, 3, 5)],
            "COORDENADAS  LONGITUD": [-77.03, "-71.325300°", -71.5],
            "CLASE SINIESTRO": ["CHOQUE", "ATROPELLO", "DESPISTE"],
        }
    )
    out = _parquet_safe(df)
    tmp = Path(__import__("tempfile").gettempdir()) / "_t_safe_real.parquet"
    out.to_parquet(tmp)
    back = pd.read_parquet(tmp)
    assert len(back) == 3
    assert back["CLASE SINIESTRO"].tolist() == ["CHOQUE", "ATROPELLO", "DESPISTE"]


# --- DQS: coordenadas negativas ------------------------------------------

def test_validity_does_not_penalise_negative_coordinates():
    """Regresión: el chequeo `>= 0` puntuaba 0 % a lat/long de Perú (todas negativas).

    Ahora `validity` usa el rango declarado en el contrato.
    """
    df = pd.DataFrame({"latitud": [-12.0, -16.4, -13.5], "longitud": [-77.0, -71.5, -72.0]})
    cols = {
        "latitud": {"type": "float", "min": -18.5, "max": 0.2},
        "longitud": {"type": "float", "min": -81.5, "max": -68.5},
    }
    ranges = dimensions._contract_ranges(cols)
    score = dimensions.validity(df, ["latitud", "longitud"], ranges=ranges)
    assert score == 100.0


def test_contract_ranges_ignores_datetime_columns():
    """Regresión: un `min` de fecha sin `max` producía (lo, None) y `val >= None` lanzaba TypeError."""
    cols = {"fecha": {"type": "datetime", "min": "2000-01-01"}}
    ranges = dimensions._contract_ranges(cols)
    assert "fecha" not in ranges


def test_contract_ranges_uses_infinity_for_open_bounds():
    cols = {"fallecidos": {"type": "integer", "min": 0}}
    ranges = dimensions._contract_ranges(cols)
    assert ranges["fallecidos"] == (0, float("inf"))


def test_dqs_freshness_uses_settings_column(onsv_rows):
    """Regresión: `freshness_column` no estaba en el contrato, la frescura quedaba en 100."""
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    dqs = dimensions.compute_dqs(onsv_rows, SETTINGS, contract, load_catalogs("onsv"), dataset="onsv")
    assert dqs["freshness_column"] == "fecha"
    assert 0.0 <= dqs["freshness"] <= 100.0


def test_dqs_freshness_is_zero_for_stale_data():
    """Datos de 2020 con ventana de 365 días deben dar frescura 0, no 100."""
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    df = pd.DataFrame({"codigo": ["A", "B"], "fecha": pd.to_datetime(["2020-01-01", "2020-06-01"])})
    dqs = dimensions.compute_dqs(df, SETTINGS, contract, {}, dataset="onsv")
    assert dqs["freshness"] == 0.0


# --- Catálogos y folding de acentos ---------------------------------------

def test_validity_resolves_plural_catalog_key_to_singular_column():
    """Regresión: el catálogo se llama 'departamentos' y la columna 'departamento'.

    Sin el alias, la dimensión validez no evaluaba esa columna.
    """
    df = pd.DataFrame({"departamento": ["LIMA", "CUSCO", "CHIMBOTE"]})
    score = dimensions.validity(df, [], catalogs={"departamentos": ["LIMA", "CUSCO"]})
    assert 100 * 2 / 3 == pytest.approx(score, abs=0.01)


def test_validity_catalog_comparison_ignores_accents(onsv_rows):
    """El catálogo se escribe plegado; la comparación debe normalizar igual."""
    cats = {"clase": ["CAIDA DE PASAJERO", "CHOQUE"]}
    df = pd.DataFrame({"clase": ["CAÍDA DE PASAJERO", "CHOQUE"]})
    assert dimensions.validity(df, [], catalogs=cats) == 100.0


def test_domain_rule_catalog_ignores_accents():
    df = pd.DataFrame({"clase": ["CAÍDA DE PASAJERO", "INVENTADO"]})
    v = detect_violations(df, [{"rule": "clase_catalogo", "columns": ["clase"], "severity": "warning"}],
                          {"clase": ["CAIDA DE PASAJERO"]})
    assert v and v[0]["count"] == 1


def test_imputed_domain_value_is_in_catalog(onsv_rows):
    """'DESCONOCIDO' es el valor de imputación configurado y debe ser categoría válida."""
    cats = load_catalogs("onsv")
    assert "DESCONOCIDO" in cats["condicion_climatica"]


# --- Reglas de dominio: comparación de fechas tz-naive -------------------

def test_fecha_no_futura_compares_tz_naive(onsv_rows):
    """Regresión: comparar una columna tz-naive con `datetime.now(timezone.utc)` lanzaba TypeError."""
    rules = [{"rule": "fecha_no_futura", "columns": ["fecha"], "severity": "critical"}]
    v = detect_violations(onsv_rows, rules, {})
    assert v == []


def test_fecha_no_futura_detects_future():
    future = pd.DataFrame({"fecha": pd.to_datetime([dt.datetime.now() + dt.timedelta(days=400)])})
    rules = [{"rule": "fecha_no_futura", "columns": ["fecha"], "severity": "critical"}]
    v = detect_violations(future, rules, {})
    assert v and v[0]["count"] == 1


# --- Validador de contrato: reglas nuevas --------------------------------

def test_contract_detects_wrong_type():
    df = pd.DataFrame({"n": ["a", "b"]})
    res = validate_contract(df, {"contract": {"columns": {"n": {"type": "integer"}}}})
    assert not res["valid"]
    assert any(r == "type" for _, r, _ in res["errors"])


def test_contract_accepts_integer_stored_as_float():
    """Un entero guardado como float64 (por un NaN) sigue siendo 'integer' semánticamente."""
    df = pd.DataFrame({"n": [1.0, 2.0, float("nan")]})
    res = validate_contract(df, {"contract": {"columns": {"n": {"type": "integer", "nullable": True}}}})
    assert res["valid"], res["errors"]


def test_contract_rejects_fractional_as_integer():
    df = pd.DataFrame({"n": [1.5, 2.0]})
    res = validate_contract(df, {"contract": {"columns": {"n": {"type": "integer"}}}})
    assert not res["valid"]


def test_contract_detects_allowed_values_violation():
    df = pd.DataFrame({"zona": ["URBANA", "MARITIMA"]})
    res = validate_contract(df, {"contract": {"columns": {"zona": {"type": "string", "allowed_values": ["RURAL", "URBANA"]}}}})
    assert not res["valid"]
    assert any(r == "allowed_values" for _, r, _ in res["errors"])


def test_contract_allowed_values_tolerates_accents():
    df = pd.DataFrame({"clase": ["CAÍDA DE PASAJERO"]})
    res = validate_contract(df, {"contract": {"columns": {"clase": {"type": "string", "allowed_values": ["CAIDA DE PASAJERO"]}}}})
    assert res["valid"], res["errors"]


def test_contract_detects_future_date_beyond_tolerance():
    future = dt.datetime.now() + dt.timedelta(days=5)
    df = pd.DataFrame({"fecha": pd.to_datetime([future])})
    res = validate_contract(df, {"contract": {"columns": {"fecha": {"type": "datetime", "max_before_today_days": 0}}}})
    assert not res["valid"]
    assert any(r == "max_before_today_days" for _, r, _ in res["errors"])


def test_contract_datetime_min_is_enforced():
    df = pd.DataFrame({"fecha": pd.to_datetime(["1990-01-01"])})
    res = validate_contract(df, {"contract": {"columns": {"fecha": {"type": "datetime", "min": "2000-01-01"}}}})
    assert not res["valid"]
    assert any(r == "min" for _, r, _ in res["errors"])


# --- Agregaciones Gold ---------------------------------------------------

def test_aggregation_sql_rejects_injection_in_column_name():
    from src.load.aggregations import _safe_ident

    with pytest.raises(ValueError):
        _safe_ident("departamento; DROP TABLE runs")


def test_build_aggregations_from_config(onsv_rows):
    """Las agregaciones se configuran en YAML y se traducen a SQL genérico."""
    import tempfile

    from src.load.aggregations import build_aggregations
    from src.sql_engine.engine import duckdb_engine

    con = duckdb_engine(Path(tempfile.gettempdir()) / "test_agg.duckdb")
    con.register("onsv_rows", onsv_rows)
    con.execute("CREATE OR REPLACE TABLE onsv_silver AS SELECT * FROM onsv_rows")
    specs = [
        {"name": "por_dep", "kind": "count_by", "by": ["departamento"]},
        {"name": "fallec", "kind": "sum_by", "by": ["departamento"], "value": "fallecidos"},
    ]
    out = build_aggregations(con, "onsv_silver", specs)
    con.close()
    assert out["por_dep"] and out["por_dep"][0]["n"] == 1
    # La suma por departamento debe cuadrar con el total del fixture (0+1+2 = 3).
    assert sum(r["total_fallecidos"] for r in out["fallec"]) == 3


def test_aggregations_are_separate_accessor():
    from src.utils.configloader import load_aggregations

    specs = load_aggregations("onsv")
    assert isinstance(specs, list) and specs
    assert all("kind" in s and "by" in s for s in specs)


def test_load_catalogs_excludes_aggregations():
    """`load_catalogs` no debe devolver specs de agregación (son dicts, no catálogos)."""
    from src.utils.configloader import load_aggregations, load_catalogs

    cats = load_catalogs("onsv")
    assert "aggregations" not in cats
    assert all(isinstance(v, list) for v in cats.values())
    assert load_aggregations("onsv")


# --- ML: split sin dependencias externas --------------------------------

def test_split_no_leakage_is_deterministic_and_disjoint():
    """El split no puede depender de sklearn (no está en requirements) y debe ser reproducible."""
    from src.ml.placeholder import split_no_leakage

    df = pd.DataFrame({"x": range(100), "y": range(100)})
    a = split_no_leakage(df, "y", test_ratio=0.2, seed=42)
    b = split_no_leakage(df, "y", test_ratio=0.2, seed=42)
    assert len(a["train"]) == 80 and len(a["test"]) == 20
    assert a["train"]["x"].tolist() == b["train"]["x"].tolist()
    assert not set(a["train"]["x"]) & set(a["test"]["x"])


def test_split_no_leakage_requires_target():
    from src.ml.placeholder import split_no_leakage

    with pytest.raises(KeyError):
        split_no_leakage(pd.DataFrame({"x": [1, 2]}), "no_existe")
