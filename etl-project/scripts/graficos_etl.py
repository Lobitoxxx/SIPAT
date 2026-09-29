# -*- coding: utf-8 -*-
"""Genera las figuras del ETL en docs/figuras/etl/.

Se ejecuta desde artefactos ya existentes (no reejecuta el pipeline):
    python scripts/graficos_etl.py                    # ambos datasets
    python scripts/graficos_etl.py --dataset onsv
    python scripts/graficos_etl.py --skip-reliability # sin recalcular la tabla

Es el equivalente ETL de `scripts/graficos.py` del SIPAT raíz.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.quality import figures as F
from src.utils.configloader import load_settings
from src.utils.logging_util import get_logger

logger = get_logger("etl.graficos")


def _silver_path(dataset: str, version: str) -> Path:
    return ROOT / "data" / "silver" / f"{dataset}_silver_{version}.parquet"


def main() -> int:
    ap = argparse.ArgumentParser(description="Figuras del ETL en docs/figuras/etl/.")
    ap.add_argument("--dataset", default=None, help="Filtrar datasets (coma separada).")
    ap.add_argument("--skip-reliability", action="store_true",
                    help="No recalcular la tabla de confiabilidad (usa la última si existe).")
    args = ap.parse_args()

    if not F.available():
        print("ERROR: matplotlib no está disponible; no se pueden generar figuras.")
        return 1

    settings = load_settings()
    datasets = [d.strip() for d in args.dataset.split(",") if d.strip()] if args.dataset \
        else list(settings["datasets"])

    # Silver de todos (para comparativas y cross-dataset).
    frames: dict[str, pd.DataFrame] = {}
    for ds in datasets:
        p = _silver_path(ds, settings["datasets"][ds]["version"])
        if p.exists():
            frames[ds] = pd.read_parquet(p)
        else:
            logger.warning("sin Silver para '%s': ejecuta el pipeline primero (%s)", ds, p)
    if not frames:
        print("ERROR: no hay Silver. Ejecuta primero: python scripts/run_pipeline.py")
        return 1

    total = 0
    # Tabla de confiabilidad de TODOS los datasets primero: la figura de
    # dimensiones necesita el DQS completo (con sus 6 dimensiones) de cada uno.
    from src.quality import reliability as R

    assessments: dict[str, dict] = {}
    for ds, df in frames.items():
        if args.skip_reliability:
            cached = _last_reliability(ds)
            if cached:
                assessments[ds] = cached
                print(f"  {ds}: confiabilidad (caché, {len(cached['claims'])} afirmaciones)")
            continue
        others = {k: v for k, v in frames.items() if k != ds}
        rel = R.assess(ds, df, settings=settings, other_frames=others)
        R.save_assessment(rel, ds)
        assessments[ds] = rel
        print(f"  {ds}: confiabilidad {len(rel['claims'])} afirmaciones · "
              f"{rel['resumen_veredictos']}")

    # Figura comparativa de dimensiones (una sola, con todos los datasets).
    dqs_map = {ds: rel["dqs"] for ds, rel in assessments.items() if rel.get("dqs")}
    if dqs_map:
        p = F.plot_dqs_dimensions(dqs_map, F.figures_dir())
        if p:
            print(f"  [ok] dqs_dimensiones: {p.name}")

    for ds, df in frames.items():
        print(f"\n=== {ds} ({len(df):,} filas x {df.shape[1]} columnas) ===")
        rel = assessments.get(ds)
        rutas = F.build_all(ds, df, reliability=rel, other_silver={}, root=ROOT)
        for nombre, ruta in rutas.items():
            print(f"  [ok] {nombre}: {Path(ruta).name}")
            total += 1

        # Informe HTML autocontenido con las figuras embebidas.
        if rel:
            from pathlib import Path as _P
            from src.quality import reliability_report as RR

            figs = {k: _P(v) for k, v in rutas.items()}
            figs["confiabilidad_veredictos"] = _P(
                F.figures_dir() / f"{ds}_confiabilidad_veredictos.png"
            ) if (F.figures_dir() / f"{ds}_confiabilidad_veredictos.png").exists() else figs.get(
                "confiabilidad_veredictos", _P("none"))
            html_path = RR.generate_reliability_report(rel, ds, figs)
            print(f"  [ok] informe HTML: {html_path.name}")

    # Contexto de negocio (solo con Silver, sin depender de confiabilidad).
    for ds, df in frames.items():
        for col, titulo, nombre in _negocio(ds):
            if col in df.columns:
                p = F.plot_top_categories(df, col, titulo, nombre, F.figures_dir())
                if p:
                    print(f"  [ok] {ds}: {p.name}")
                    total += 1
        fecha = (settings["datasets"][ds].get("freshness_column"))
        if fecha and fecha in df.columns:
            p = F.plot_temporal(
                df, fecha, f"{ds}_evolucion_anual.png",
                f"{ds}: registros por año",
                F.figures_dir(),
                by=_stacked_by(ds),
            )
            if p:
                print(f"  [ok] {ds}: {p.name}")
                total += 1

    print(f"\nTotal de figuras generadas: {total} en {F.figures_dir()}")
    return 0


def _negocio(ds: str):
    if ds == "onsv":
        return [
            ("departamento", "ONSV: siniestros por departamento (top 15)", "onsv_top_departamentos.png"),
            ("clase", "ONSV: siniestros por clase", "onsv_top_clases.png"),
        ]
    if ds == "cinemometros":
        return [
            ("region", "Cinemómetros: detecciones por región", "cinemometros_top_regiones.png"),
            ("carretera", "Cinemómetros: detecciones por carretera", "cinemometros_top_carreteras.png"),
        ]
    return []


def _stacked_by(ds: str):
    return "clase" if ds == "onsv" else "region"


def _last_reliability(dataset: str):
    """Reutiliza la última evaluación de confiabilidad guardada en disco."""
    saved = sorted((ROOT / "reports" / "reliability").glob(f"{dataset}_reliability_*.json"),
                   reverse=True)
    for p in saved:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


if __name__ == "__main__":
    raise SystemExit(main())
