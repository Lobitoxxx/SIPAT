# -*- coding: utf-8 -*-
"""Tests del motor de confiabilidad (src/quality/reliability.py).

Foco: que cada eje mida lo que dice medir, que sea determinista y que
aplique los umbrales leídos de config/quality/reliability_rules.yaml.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.quality import dimensions, reliability as R
from src.utils.configloader import load_settings
from src.utils.paths import CONFIG

SETTINGS = load_settings()
RULES = R._rules()


# --------------------------------------------------------------------------
# 0) La configuración de reglas es válida y sin números mágicos
# --------------------------------------------------------------------------
def test_reliability_rules_yaml_exists_and_has_all_axes():
    f = CONFIG / "quality" / "reliability_rules.yaml"
    assert f.exists(), "debe existir config/quality/reliability_rules.yaml"
    d = R._rules()
    for eje in (
        "weight_sensitivity", "bootstrap", "catalog_circularity",
        "coverage", "cross_dataset", "drift", "integrity_dimension", "imputation",
    ):
        assert eje in d, f"falta el eje '{eje}' en la configuración"


def test_reliability_rules_verdicts_are_ordered():
    v = RULES["verdicts"]
    assert v == ["alta", "media", "baja", "no_verificable"]


def test_reliability_weight_scenarios_sum_to_one():
    """Un escenario con pesos que no suman 1 produciría un DQS sin sentido."""
    for spec in RULES["weight_sensitivity"]["weight_scenarios"]:
        total = sum(spec["weights"].values())
        assert abs(total - 1.0) < 1e-3, f"'{spec['name']}' suma {total}"


# --------------------------------------------------------------------------
# 1) Huella de medición
# --------------------------------------------------------------------------
def test_measurement_fingerprint_is_stable():
    from src.utils import versioning

    a = versioning.measurement_fingerprint()
    b = versioning.measurement_fingerprint()
    assert a == b and len(a) == 10


def test_measurement_fingerprint_changes_when_measurement_config_changes(tmp_path, monkeypatch):
    """La huella debe cambiar si cambia settings.yaml (los pesos del DQS)."""
    from src.utils import versioning

    antes = versioning.measurement_fingerprint()
    src = CONFIG / "settings.yaml"
    original = src.read_text(encoding="utf-8")
    try:
        src.write_text(original + "\n# comentario de prueba\n", encoding="utf-8")
        assert versioning.measurement_fingerprint() != antes
    finally:
        src.write_text(original, encoding="utf-8")


# --------------------------------------------------------------------------
# 2) Sensibilidad a los pesos
# --------------------------------------------------------------------------
def test_weight_sensitivity_detects_dqs_that_depends_on_weights(cinemometros_rows):
    """Si el DQS no cambiara con los pesos, la función debe reportarlo frágil.

    Caso sintético: un dataset con muchos nulos y datos muy antiguos hace que
    el DQS dependa claramente del peso de frescura/completitud.
    """
    df = cinemometros_rows.copy()
    df.loc[df.index[:2], "velocidad_detectada"] = np.nan
    df["fecha_papeleta"] = pd.to_datetime(["2019-01-01", "2019-06-01", "2020-03-01"])
    contract = {"contract": {"dataset": "cinemometros", "primary_key": "nro_deteccion",
                             "columns": {
                                 "nro_deteccion": {"type": "string", "nullable": False, "unique": True},
                                 "fecha_papeleta": {"type": "datetime", "nullable": False},
                                 "velocidad_detectada": {"type": "float", "nullable": True},
                             }}}
    res = R.weight_sensitivity(df, SETTINGS, contract, {}, "cinemometros", RULES)
    assert res["enabled"] is True
    assert res["distribucion"]["p05"] <= res["distribucion"]["p95"]
    assert res["spread_p05_p95"] > 0, "el DQS debe variar al cambiar los pesos"
    assert res["verdict"] in RULES["verdicts"]


def test_weight_sensitivity_is_deterministic(onsv_rows):
    """Con la misma semilla debe dar exactamente la misma distribución."""
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    a = R.weight_sensitivity(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    b = R.weight_sensitivity(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    assert a["distribucion"] == b["distribucion"]


def test_weight_sensitivity_scenarios_recompute_dqs(onsv_rows):
    """Los escenarios alternativos deben producir DQS distintos y plausibles."""
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    res = R.weight_sensitivity(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    nombres = {s["name"] for s in res["scenarios"]}
    assert {"uniforme", "frescura_critica", "integridad_critica", "solo_contrato"} <= nombres
    for s in res["scenarios"]:
        assert 0.0 <= s["dqs"] <= 100.0


def test_with_weights_does_not_mutate_settings():
    """Cambiar los pesos para el análisis no puede tocar la configuración real."""
    original = dict(SETTINGS["quality"]["weights"])
    copy = R._with_weights(SETTINGS, {k: 1 / 6 for k in original})
    assert copy["quality"]["weights"] != original
    assert SETTINGS["quality"]["weights"] == original, "settings fue mutado"


# --------------------------------------------------------------------------
# 3) Bootstrap: la trampa del remuestreo con reemplazo
# --------------------------------------------------------------------------
def test_bootstrap_ic_is_centred_on_point_estimate(onsv_rows):
    """REGRESIÓN: remuestrear con reemplazo duplica las PK y hunde la unicidad,
    produciendo un IC descentrado (punto 92.07 contra IC [86.45, 86.65]).
    Las dimensiones invariantes al muestreo de filas deben fijarse."""
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    res = R.bootstrap_dqs(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    d = res["dqs"]
    assert d["punto"] == pytest.approx(dimensions.compute_dqs(
        onsv_rows, SETTINGS, contract, {}, dataset="onsv")["dqs"], abs=0.01)
    assert d["centrado"] is True, (
        f"IC descentrado: punto {d['punto']} fuera de [{d['ic_inf']}, {d['ic_sup']}]")
    assert res["fix_dimensions"], "deben declararse las dimensiones invariantes"


def test_bootstrap_fixes_uniqueness_and_integrity(onsv_rows):
    """La unicidad no puede variar al remuestrear filas: es fija por diseño."""
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    res = R.bootstrap_dqs(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    assert res["uniqueness"]["amplitud"] == 0.0
    assert res["integrity"]["amplitud"] == 0.0


def test_bootstrap_is_deterministic(onsv_rows):
    contract = {"contract": {"dataset": "onsv", "primary_key": "codigo", "columns": {
        "codigo": {"type": "string", "nullable": False, "unique": True},
        "fecha": {"type": "datetime", "nullable": False},
    }}}
    a = R.bootstrap_dqs(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    b = R.bootstrap_dqs(onsv_rows, SETTINGS, contract, {}, "onsv", RULES)
    assert a["dqs"] == b["dqs"]


# --------------------------------------------------------------------------
# 4) Circularidad de catálogos
# --------------------------------------------------------------------------
def test_catalog_circularity_detects_self_derived_catalogs(onsv_rows):
    """Un catálogo construido íntegramente con el propio dataset es circular.

    Es la limitación metodológica más importante del proyecto: validar contra
    un catálogo derivado de los mismos datos es consistencia interna, no
    validación externa.
    """
    df = onsv_rows.copy()
    df["clase"] = ["CHOQUE", "ATROPELLO", "CAIDA DE PASAJERO"]  # exactamente los del fixture
    cats = {"clase": ["CHOQUE", "ATROPELLO", "CAIDA DE PASAJERO"]}
    res = R.catalog_circularity(df, cats, RULES)
    det = res["detalle"][0]
    assert det["pct_valores_derivados_del_dato"] == 100.0
    assert det["circular"] is True
    assert res["todos_circulares"] is True


def test_catalog_circularity_flags_missing_values(onsv_rows):
    """Un valor fuera del catálogo debe aparecer en 'valores_fuera_de_catalogo'."""
    df = onsv_rows.copy()
    df["clase"] = ["CHOQUE", "INVENTADO", "DESPISTE"]
    res = R.catalog_circularity(df, {"clase": ["CHOQUE", "DESPISTE"]}, RULES)
    assert "INVENTADO" in res["detalle"][0]["valores_fuera_de_catalogo"]


def test_catalog_circularity_ignores_absent_columns(onsv_rows):
    res = R.catalog_circularity(onsv_rows, {"no_existe": ["A", "B"]}, RULES)
    assert res["detalle"] == []


# --------------------------------------------------------------------------
# 5) Cobertura
# --------------------------------------------------------------------------
def test_coverage_profile_reports_range_and_years(onsv_rows):
    res = R.coverage_profile(onsv_rows, "onsv", SETTINGS, RULES)
    assert res["disponible"] is True
    assert res["rango_anios"] == [2023, 2023]
    assert res["anios"][2023] == 3
    assert res["n_fechas_nulas"] == 0


def test_coverage_profile_flags_missing_years():
    df = pd.DataFrame({"fecha": pd.to_datetime(["2021-01-05", "2023-06-01"])})
    res = R.coverage_profile(df, "onsv", SETTINGS, RULES)
    assert 2022 in res["anios_vacios"], "debe detectar el hueco de cobertura"


def test_coverage_profile_handles_absent_date_column(onsv_rows):
    res = R.coverage_profile(onsv_rows.drop(columns=["fecha"]), "onsv", SETTINGS, RULES)
    assert res["disponible"] is False and res["motivo"]


# --------------------------------------------------------------------------
# 6) Consistencia entre datasets
# --------------------------------------------------------------------------
def test_cross_dataset_consistency_detects_divergence(onsv_rows, cinemometros_rows):
    """ONSV usa `departamento` y cinemómetros `region`: la MISMA dimensión con
    distinto nombre, por eso la config declara key_a / key_b."""
    frames = {"onsv": onsv_rows, "cinemometros": cinemometros_rows}
    res = R.cross_dataset_consistency(frames, RULES)
    comp = res["comparaciones"][0]
    assert comp["disponible"] is True, comp.get("motivo")
    assert comp["columnas"] == ["departamento", "region"]
    assert set(comp["solo_en_a"]) | set(comp["solo_en_b"]), "debe reportar la divergencia"
    assert 0.0 <= comp["jaccard"] <= 1.0


def test_cross_dataset_consistency_uses_key_a_and_key_b(onsv_rows, cinemometros_rows):
    """Sin el mapeo por lado, `departamento` no existe en cinemómetros."""
    rules = json.loads(json.dumps(RULES))
    del rules["cross_dataset"]["compare"][0]["key_a"]
    del rules["cross_dataset"]["compare"][0]["key_b"]
    res = R.cross_dataset_consistency(
        {"onsv": onsv_rows, "cinemometros": cinemometros_rows}, rules
    )
    comp = res["comparaciones"][0]
    assert comp["disponible"] is False
    assert "departamento" in comp["faltan"]


def test_cross_dataset_consistency_high_when_identical():
    """Mismas regiones en ambos lados (con nombres de columna distintos) -> jaccard 1."""
    a = pd.DataFrame({"departamento": ["LIMA", "CUSCO", "PIURA"]})
    b = pd.DataFrame({"region": ["lima", "cusco", "piura"]})  # distinta caja a propósito
    res = R.cross_dataset_consistency({"onsv": a, "cinemometros": b}, RULES)
    comp = res["comparaciones"][0]
    assert comp["disponible"] is True
    assert comp["jaccard"] == 1.0, "la comparación debe normalizar la caja"
    assert res["verdict"] == "alta"


def test_cross_dataset_consistency_handles_missing_dataset(onsv_rows):
    res = R.cross_dataset_consistency({"onsv": onsv_rows}, RULES)
    comp = res["comparaciones"][0]
    assert comp["disponible"] is False
    assert res["verdict"] == "no_verificable"


# --------------------------------------------------------------------------
# 7) Deriva
# --------------------------------------------------------------------------
def test_run_drift_detects_no_drift_within_same_fingerprint(tmp_path):
    runs = tmp_path / "runs"
    for i, dqs in enumerate([92.07, 92.07, 92.07]):
        d = runs / f"run-20260929-00000{i}" / "manifest.json"
        d.parent.mkdir(parents=True)
        d.write_text(json.dumps({
            "run_id": f"run-20260929-00000{i}", "version": "1.0.0",
            "git_commit": "abc", "measurement_fingerprint": "fp1",
            "datasets": {"onsv": {"dqs": dqs, "gate": "PASSED"}},
        }), encoding="utf-8")
    res = R.run_drift(runs, RULES)
    det = res["datasets"]["onsv"]
    assert det["deriva_detectada"] is False
    assert det["rango_huella_vigente"] == 0.0
    assert res["verdict"] in ("alta", "media")


def test_run_drift_detects_real_drift(tmp_path):
    runs = tmp_path / "runs"
    for i, dqs in enumerate([92.07, 88.5, 91.0]):
        d = runs / f"run-20260929-00000{i}" / "manifest.json"
        d.parent.mkdir(parents=True)
        d.write_text(json.dumps({
            "run_id": f"run-20260929-00000{i}", "version": "1.0.0",
            "git_commit": "abc", "measurement_fingerprint": "fp1",
            "datasets": {"onsv": {"dqs": dqs, "gate": "PASSED"}},
        }), encoding="utf-8")
    res = R.run_drift(runs, RULES)
    assert res["datasets"]["onsv"]["deriva_detectada"] is True
    assert res["verdict"] == "baja"


def test_run_drift_separates_measurement_changes_from_drift(tmp_path):
    """Un DQS que cambia entre huellas es CORRECCIÓN, no inestabilidad.

    Es la distinción que evita Condenar al pipeline por haber arreglado un bug.
    """
    runs = tmp_path / "runs"
    # 1 corrida con la huella antigua (DQS roto) y 3 con la nueva (DQS correcto).
    specs = [("fp_vieja", 94.97), ("fp_nueva", 92.07), ("fp_nueva", 92.07), ("fp_nueva", 92.07)]
    for i, (fp, dqs) in enumerate(specs):
        d = runs / f"run-20260929-00000{i}" / "manifest.json"
        d.parent.mkdir(parents=True)
        d.write_text(json.dumps({
            "run_id": f"run-20260929-00000{i}", "version": "1.0.0",
            "git_commit": "x", "measurement_fingerprint": fp,
            "datasets": {"onsv": {"dqs": dqs, "gate": "PASSED"}},
        }), encoding="utf-8")
    res = R.run_drift(runs, RULES)
    det = res["datasets"]["onsv"]
    # Dentro de la huella nueva no hay deriva...
    assert det["deriva_por_huella"]["fp_nueva"]["deriva"] is False
    # ...pero el cambio entre huellas queda reportado aparte.
    assert res["cambios_entre_huellas"]["onsv"]["cambio_max_entre_huellas"] == pytest.approx(2.90, abs=0.01)


def test_run_drift_not_verifiable_without_runs(tmp_path):
    res = R.run_drift(tmp_path / "vacio", RULES)
    assert res["verdict"] == "no_verificable"


# --------------------------------------------------------------------------
# 8) Dimensión integridad
# --------------------------------------------------------------------------
def test_integrity_audit_flags_permanently_100():
    res = R.integrity_dimension_audit({"integrity": 100.0}, RULES)
    assert res["es_vacia"] is True
    assert res["verdict"] == "no_verificable"
    assert "claves foráneas" in res["motivo"]


def test_integrity_audit_ok_when_it_varies():
    res = R.integrity_dimension_audit({"integrity": 87.5}, RULES)
    assert res["es_vacia"] is False
    assert res["verdict"] == "media"


# --------------------------------------------------------------------------
# 9) Imputación
# --------------------------------------------------------------------------
def test_imputation_audit_lists_filled_columns():
    df = pd.DataFrame({"vehiculos_danados": [1.0, 2.0, 3.0], "otro": [1, 2, 3]})
    res = R.imputation_audit(df, "onsv", SETTINGS, RULES)
    cols = {c["columna"]: c for c in res["columnas_imputadas"]}
    assert "vehiculos_danados" in cols
    assert cols["vehiculos_danados"]["estrategia"] == "median"
    assert "ESTIMACIONES" in res["motivo"]


def test_imputation_audit_reports_none_when_no_fill():
    res = R.imputation_audit(pd.DataFrame({"a": [1]}), "cinemometros", SETTINGS, RULES)
    assert res["n_columnas"] == 0


# --------------------------------------------------------------------------
# 10) Ensamblado
# --------------------------------------------------------------------------
def test_assess_returns_claims_with_evidence_and_limit(onsv_rows, tmp_path):
    """Toda afirmación debe evidencia Y límite conocido: sin límite,
    un veredicto alto se lee como garantía absoluta."""
    res = R.assess("onsv", onsv_rows, settings=SETTINGS, runs_dir=tmp_path)
    assert res["claims"], "debe producir afirmaciones"
    for c in res["claims"]:
        assert c["id"] and c["axis"] and c["question"]
        assert c["verdict"] in RULES["verdicts"]
        assert isinstance(c["evidence"], dict) and c["evidence"]
        assert c["limit"], f"la afirmación {c['id']} no declara su límite"


def test_assess_does_not_produce_a_single_reliability_score(onsv_rows, tmp_path):
    """Regresión de diseño: NO debe existir un 'índice de confiabilidad'.

    Un número único repetiría el error que hace malinterpretable el DQS.
    """
    res = R.assess("onsv", onsv_rows, settings=SETTINGS, runs_dir=tmp_path)
    assert "confiabilidad" not in res
    assert "score" not in res
    assert "indice" not in res


def test_assess_verdict_summary_counts_all_claims(onsv_rows, tmp_path):
    res = R.assess("onsv", onsv_rows, settings=SETTINGS, runs_dir=tmp_path)
    total = sum(res["resumen_veredictos"].values())
    assert total == len(res["claims"])


def test_save_assessment_writes_json(onsv_rows, tmp_path, monkeypatch):
    from src.utils import paths as P

    monkeypatch.setattr(P, "REPORTS", tmp_path / "reports")
    res = R.assess("onsv", onsv_rows, settings=SETTINGS, runs_dir=tmp_path)
    p = R.save_assessment(res, "onsv")
    assert p.exists()
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["claims"] and d["dqs"]["dqs"] > 0
