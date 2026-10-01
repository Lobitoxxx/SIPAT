# -*- coding: utf-8 -*-
"""Perfilado (sección 4 y 28): métrica/estadísticas por columna ANTES y DESPUÉS del proceso.

Salidas: reports/profiling/<dataset>_<stage>_profile.json/.csv y HTML autocontenido.
Se calcula: dtype, no nulos, nulos, % nulos, únicos, nulos en %, min/max/mean para numéricos,
top valores para categóricos.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.utils import paths
from src.utils.logging_util import get_logger

logger = get_logger("etl.profiling")


def _profile_frame(df: pd.DataFrame, max_categories: int = 10) -> Dict[str, Any]:
    total = len(df)
    out: Dict[str, Any] = {}
    for col in df.columns:
        s = df[col]
        non_null = s.notna().sum()
        pct_null = round(100 * (1 - non_null / total), 2) if total else 0.0
        base = {
            "dtype": str(s.dtype),
            "non_null": int(non_null),
            "nulls": int(total - non_null),
            "null_pct": pct_null,
            "uniques": int(s.nunique(dropna=True)),
        }
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            base.update(
                {
                    "min": None if non_null == 0 else _round(s.min()),
                    "max": None if non_null == 0 else _round(s.max()),
                    "mean": None if non_null == 0 else _round(s.mean(), 4),
                    "q25": None if non_null == 0 else _round(s.quantile(0.25)),
                    "q75": None if non_null == 0 else _round(s.quantile(0.75)),
                }
            )
        if base["uniques"] <= max_categories * 2:
            vc = s.value_counts(dropna=False).head(max_categories)
            base["top_values"] = {str(k): int(v) for k, v in vc.items()}
        out[col] = base
    return out


def _round(v, nd=2):
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


def profile(
    df: pd.DataFrame,
    dataset: str,
    stage: str,
    run_id: str | None = None,
    report_dir: Path | None = None,
) -> Dict[str, Any]:
    report_dir = report_dir or paths.reports_dir("profiling")
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": dataset,
        "stage": stage,
        "run_id": run_id,
        "rows": len(df),
        "cols": df.shape[1],
        "columns": _profile_frame(df),
    }
    (report_dir / f"{dataset}_{stage}_profile.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    pdf = pd.DataFrame(payload["columns"]).T.reset_index().rename(columns={"index": "column"})
    pdf.to_csv(report_dir / f"{dataset}_{stage}_profile.csv", index=False, encoding="utf-8")
    (report_dir / f"{dataset}_{stage}_profile.html").write_text(
        _html(dataset, stage, payload, _comparative_figure(dataset, stage, report_dir)),
        encoding="utf-8",
    )
    return payload


def _comparative_figure(
    dataset: str, stage: str, report_dir: Path
) -> str:
    """Figura antes/después en base64, solo en el perfil `after`.

    Es el único punto del pipeline donde ambas fotos coexisten: al perfilar
    `after` ya está escrito el JSON de `before`. Se dibuja en memoria, así que no
    crea ningún PNG suelto en `docs/figuras/etl/`.

    Devuelve "" si falta el perfil `before`, si la etapa no es `after` o si no
    hay matplotlib: el HTML se genera siempre.
    """
    if stage != "after":
        return ""
    before_path = report_dir / f"{dataset}_before_profile.json"
    if not before_path.exists():
        return ""
    try:
        import json as _json

        from src.quality import figures as F

        if not F.available():
            return ""
        before = _json.loads(before_path.read_text(encoding="utf-8"))
        after = _json.loads(
            (report_dir / f"{dataset}_after_profile.json").read_text(encoding="utf-8")
        )
        return F.html_nulls_before_after(before, after, dataset)
    except Exception as exc:  # pragma: no cover - degradar, no romper
        logger.warning("no se pudo incrustar la figura comparativa en el perfil: %s", exc)
        return ""


def _html(dataset: str, stage: str, payload: Dict[str, Any], figure: str = "") -> str:
    rows = ""
    for col, m in payload["columns"].items():
        rows += (
            "<tr><td><code>%s</code></td><td>%s</td><td>%d</td><td>%d</td><td>%.1f%%</td>"
            "<td>%d</td><td>%s</td></tr>"
        ) % (col, m["dtype"], m["non_null"], m["nulls"], m["null_pct"], m["uniques"],
             m.get("mean", "-"))
    return f"""<html><head><meta charset="utf-8"><title>{dataset} - {stage}</title>
<style>body{{font-family:system-ui;margin:2rem}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #cbd5e1;padding:6px 10px;font-size:13px;text-align:left}}
th{{background:#eef2ff;color:#3730a3}} code{{background:#f1f5f9;padding:2px 5px;border-radius:4px}}</style>
</head><body><h2>{dataset} <span style="color:#6366f1">[{stage}]</span></h2>
<p>filas: {payload['rows']} · columnas: {payload['cols']} · run_id: {payload.get('run_id','-')}</p>
{figure}
<table><thead><tr><th>columna</th><th>dtype</th><th>non_null</th><th>nulls</th><th>%null</th>
<th>únicos</th><th>mean</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""