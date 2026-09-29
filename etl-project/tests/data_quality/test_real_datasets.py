# -*- coding: utf-8 -*-
"""Tests de calidad de datos: DQS, contratos y reglas de dominio sobre datos reales
del workspace SIPAT (se omiten con skip si el fichero fuente no existe)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.cleaning.clean import clean
from src.cleaning.transform_log import TransformationLog
from src.quality import dimensions
from src.quality.domain_rules import detect_violations
from src.utils.configloader import (
    expand_path,
    load_catalogs,
    load_contract,
    load_quality_rules,
    load_settings,
    load_sources,
)
from src.validation.contract import validate_contract

SETTINGS = load_settings()
RULES = load_quality_rules()


def _real_raw(dataset: str):
    spec = load_sources()[dataset].copy()
    spec["path"] = expand_path(spec["path"])
    path = Path(spec["path"])
    if not path.exists():
        pytest.skip(f"fuente real ausente: {path}")
    from src.extract.factory import get_extractor

    return get_extractor(spec).read_raw()


@pytest.fixture(scope="module")
def clean_onsv(tmp_path_factory):
    raw = _real_raw("onsv")
    tl = TransformationLog("t", "onsv", tmp_path_factory.mktemp("q"))
    return clean(raw, SETTINGS["datasets"]["onsv"], tl)


@pytest.fixture(scope="module")
def clean_cine(tmp_path_factory):
    raw = _real_raw("cinemometros")
    tl = TransformationLog("t", "cinemometros", tmp_path_factory.mktemp("q"))
    return clean(raw, SETTINGS["datasets"]["cinemometros"], tl)


def test_real_onsv_contract_valid(clean_onsv):
    c = load_contract("onsv", SETTINGS)
    res = validate_contract(clean_onsv, c)
    assert res["valid"] is True, res["errors"][:8]


def test_real_cinemometros_contract_valid(clean_cine):
    c = load_contract("cinemometros", SETTINGS)
    res = validate_contract(clean_cine, c)
    assert res["valid"] is True, res["errors"][:8]


def test_real_onsv_dqs_above_threshold(clean_onsv):
    c = load_contract("onsv", SETTINGS)
    dqs = dimensions.compute_dqs(clean_onsv, SETTINGS, c, load_catalogs("onsv"))
    min_score = RULES["quality_gates"]["min_quality_score"]
    assert dqs["dqs"] >= min_score, dqs


def test_real_onsv_dates_fully_parsed(clean_onsv):
    """Todas las fechas deben parsear (el bug de dayfirst se cubrió con 5463 registros)."""
    assert clean_onsv["fecha"].isna().sum() == 0


def test_real_onsv_coordinates_parsed(clean_onsv):
    assert clean_onsv["latitud"].notna().all()
    assert clean_onsv["longitud"].notna().all()
    assert clean_onsv["longitud"].between(-81.5, -68.5).all()


def test_real_onsv_no_duplicate_pk(clean_onsv):
    assert clean_onsv["codigo"].duplicated().sum() == 0
    assert clean_onsv["codigo"].isna().sum() == 0


def test_real_onsv_categoricals_upper(clean_onsv):
    for col in ("departamento", "clase", "zona", "red_vial"):
        s = clean_onsv[col].dropna().astype(str)
        assert (s == s.str.upper()).all(), col


def test_real_cine_region_case_normalized(clean_cine):
    """La inconsistencia real 'LIMA' vs 'Lima' debe quedar unificada en LIMA."""
    s = set(clean_cine["region"].dropna().astype(str))
    assert "Lima" not in s
    assert "LIMA" in s


def test_real_cine_no_duplicate_pk(clean_cine):
    assert clean_cine["nro_deteccion"].duplicated().sum() == 0


def test_real_cine_redundant_cols_dropped(clean_cine):
    assert "lat" not in clean_cine.columns and "lon" not in clean_cine.columns


def test_real_onsv_domain_rules_critical_clean(clean_onsv):
    rules = RULES["domain_rules"]["onsv"]["rules"]
    v = detect_violations(clean_onsv, rules, load_catalogs("onsv"))
    crit = [x for x in v if x["severity"] == "critical"]
    assert crit == [], crit


def test_real_cine_domain_rules_critical_clean(clean_cine):
    rules = RULES["domain_rules"]["cinemometros"]["rules"]
    v = detect_violations(clean_cine, rules, load_catalogs("cinemometros"))
    crit = [x for x in v if x["severity"] == "critical"]
    assert crit == [], crit


def test_critical_rules_all_cleared_real_data(clean_onsv, clean_cine):
    """Ninguna regla crítica debe dispararse en los datasets reales ya limpiados."""
    for ds, df in (("onsv", clean_onsv), ("cinemometros", clean_cine)):
        rules = RULES["domain_rules"][ds]["rules"]
        v = detect_violations(df, rules, load_catalogs(ds))
        n = sum(x["count"] for x in v if x["severity"] == "critical")
        assert n == 0, f"{ds}: {n} violaciones críticas"
