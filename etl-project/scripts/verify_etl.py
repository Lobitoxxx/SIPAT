# -*- coding: utf-8 -*-
"""Verificación del proyecto: importa módulos, comprueba configs YAML y ejecuta smoke test.

Uso: python scripts/verify_etl.py
Devuelve 0 solo si todo es correcto (estructura, configs, imports, contrato cínico).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK = "\u2713"
FAIL = "\u2717"


def check(name: str, fn) -> bool:
    try:
        fn()
        print(f"  {OK} {name}")
        return True
    except Exception as exc:
        print(f"  {FAIL} {name}: {exc}")
        return False


def main() -> int:
    print("SIPAT-ETL — verificación")
    good = []

    def tree(path: Path, depth: int = 2):
        codes = []
        for p in sorted(path.glob("*")):
            if p.name.startswith((".", "_")) and p.name != "__init__.py":
                continue
            if p.is_dir():
                codes.append(p.name + "/")
        return codes

    def check_structure():
        for req in ("config", "data", "src", "tests", "scripts", "docs", "artifacts", "reports", "notebooks"):
            assert (ROOT / req).exists(), f"falta {req}/"
        for pkg in ("utils", "extract", "profiling", "validation", "cleaning", "transform",
                    "quality", "load", "lineage", "sql_engine", "orchestration", "ml", "reports"):
            assert (ROOT / "src" / pkg / "__init__.py").exists(), f"falta src/{pkg}/__init__.py"

    good.append(check("Estructura de carpetas", check_structure))

    def check_configs():
        import yaml

        from src.utils.configloader import load_settings
        s = load_settings()
        assert set(s["datasets"]) == {"onsv", "cinemometros"}
        assert abs(sum(s["quality"]["weights"].values()) - 1.0) < 1e-9

    good.append(check("Configs YAML válidos", check_configs))

    def check_imports():
        import importlib

        for mod in ("src.profiling.profile", "src.quality.dimensions", "src.quality.gates",
                    "src.cleaning.clean", "src.transform.features", "src.load.silver",
                    "src.load.gold", "src.orchestration.flow", "src.reports.report",
                    "src.sql_engine.engine", "src.utils.versioning", "src.validation.contract"):
            importlib.import_module(mod)

    good.append(check("Imports de módulos", check_imports))

    def check_smoke_contract():
        import pandas as pd

        from src.utils.configloader import load_contract, load_settings
        from src.validation.contract import validate_contract
        s = load_settings()
        for ds in s["datasets"]:
            c = load_contract(ds, s)
            df = pd.DataFrame({col: [] for col in c["contract"]["columns"]})
            res = validate_contract(df, c)
            assert isinstance(res, dict) and "valid" in res

    good.append(check("Validador de contrato (smoke)", check_smoke_contract))

    print(f"\nResultado: {sum(good)}/{len(good)} checks OK")
    return 0 if all(good) else 1


if __name__ == "__main__":
    raise SystemExit(main())
