# -*- coding: utf-8 -*-
"""Reporte de calidad / pipeline (sección 28): HTML autocontenido por dataset+run."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.utils import paths
from src.utils.logging_util import get_logger

logger = get_logger("etl.report")

_ESCAPE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})


def _esc(v: Any) -> str:
    return str(v).translate(_ESCAPE)


def _figures_html(dataset: str, dqs: Optional[dict]) -> str:
    """Figuras embebidas en base64 para el reporte.

    Se dibujan en memoria: los PNG del pipeline NO se escriben en
    `docs/figuras/etl/`, porque ahí viven las figuras comparativas que genera
    `scripts/graficos_etl.py` (con los dos datasets). Si el reporte escribiera
    `dqs_dimensiones.png` con un único dataset, pisaría la comparativa.

    Sin matplotlib (o sin `dqs`) devuelve cadena vacía: el reporte se sigue
    generando en HTML puro. Una figura que no se puede dibujar nunca debe
    tumbar un ETL.
    """
    if not dqs:
        return ""
    try:
        from src.quality import figures as F

        if not F.available():
            return ""
        before_profile, after_profile = _profiles(dataset)
        bloques = [
            F.html_dqs_dimensions({dataset: dqs}),
            F.html_nulls_before_after(before_profile, after_profile, dataset),
        ]
        return "".join(b for b in bloques if b)
    except Exception as exc:  # pragma: no cover - degradar, no romper
        logger.warning("no se pudieron incrustar figuras en el reporte: %s", exc)
        return ""


def _profiles(dataset: str):
    """(perfil_antes, perfil_después) desde reports/profiling/, o ({}, {})."""
    import json as _json

    base = paths.reports_dir("profiling")
    salida = []
    for stage in ("before", "after"):
        p = base / f"{dataset}_{stage}_profile.json"
        try:
            salida.append(_json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            salida.append({})
    return tuple(salida)


def generate_quality_report(
    dataset: str,
    run_id: str,
    gate: dict,
    profile_before: Optional[dict] = None,
    profile_after: Optional[dict] = None,
    transform_log: Optional[dict] = None,
    out_dir: Optional[Path] = None,
    dqs: Optional[dict] = None,
) -> Path:
    out_dir = out_dir or paths.reports_dir("quality")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    gate_html = "".join(
        f"<tr><td>{_esc(k)}</td><td>{_esc(v)}</td></tr>" for k, v in gate.items()
    )
    dqs_html = ""
    if profile_before and profile_after:
        cols = sorted(set(profile_before["columns"]) | set(profile_after["columns"]))
        rows = []
        for c in cols:
            b = profile_before["columns"].get(c, {})
            a = profile_after["columns"].get(c, {})
            rows.append(
                "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s→%s</td><td>%.2f%%→%.2f%%</td></tr>"
                % (c, b.get("dtype", "-"), a.get("dtype", "-"),
                   b.get("non_null", "-"), a.get("non_null", "-"),
                   b.get("null_pct", 0.0) or 0.0, a.get("null_pct", 0.0) or 0.0)
            )
        dqs_html = (
            "<h3>Columnas — evolución de nulos</h3><table><thead><tr>"
            "<th>columna</th><th>dtype antes</th><th>dtype después</th>"
            "<th>non_null</th><th>%%null antes → después</th></tr></thead><tbody>%s</tbody></table>"
        ) % "".join(rows)

    tlog_html = ""
    if transform_log:
        ops = transform_log.get("operations", [])
        rows = "".join(
            "<tr><td>%s</td><td>%s</td><td>%d</td><td>%s</td></tr>"
            % (_esc(o.get("operation")), _esc(o.get("column", "-")),
               o.get("records_affected", 0), _esc(o.get("strategy", "")))
            for o in ops
        )
        tlog_html = (
            "<h3>TransformationLog (%d operaciones)</h3>"
            "<table><thead><tr><th>operación</th><th>columna</th><th>registros</th>"
            "<th>estrategia</th></tr></thead><tbody>%s</tbody></table>"
        ) % (len(ops), rows)

    # Las figuras se dibujan en memoria y se embeben en base64.
    figs_html = _figures_html(dataset, dqs)
    figs_html = f"<h2>Figuras</h2>{figs_html}" if figs_html else ""

    status_color = {"PASSED": "#16a34a", "WARNING": "#d97706", "FAILED": "#dc2626"}.get(
        gate.get("status", "FAILED"), "#dc2626"
    )

    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Reporte de calidad — {dataset} (run {run_id})</title>
<style>
body{{font-family:system-ui,-apple-system;margin:2rem;color:#0f172a;background:#fff}}
h1{{font-size:1.4rem}} h2{{font-size:1.1rem;margin-top:2rem}} h3{{font-size:.95rem}}
table{{border-collapse:collapse;width:100%;margin-top:.5rem}}
th,td{{border:1px solid #cbd5e1;padding:6px 9px;font-size:13px;text-align:left}}
th{{background:#eef2ff;color:#312e81}} code{{background:#f1f5f9;padding:1px 4px;border-radius:4px}}
.badge{{color:#fff;padding:4px 10px;border-radius:999px;font-weight:600;font-size:13px}}
.mono{{font-family:ui-monospace,monospace;font-size:12px;color:#475569}}
</style></head><body>
<h1>Reporte de calidad — <code>{_esc(dataset)}</code>
<span class="badge" style="background:{status_color}">{_esc(gate.get('status','?'))}</span></h1>
<p class="mono">run_id: {_esc(run_id)} · generado: {ts} · metodología: Kanban + CRISP-DM</p>
<h2>Quality Gate</h2><table><tbody>{gate_html}</tbody></table>
{dqs_html}
{figs_html}
{tlog_html}
<p class="mono">Ver también: reports/profiling/{_esc(dataset)}_*_profile.html · manifest en artifacts/runs/{_esc(run_id)}/</p>
</body></html>"""

    out = out_dir / f"{dataset}_{run_id}.html"
    out.write_text(html, encoding="utf-8")
    return out