# -*- coding: utf-8 -*-
"""Genera el informe HTML de auditoría de la medición (autocontenido, con figuras base64)."

Complementa a `src/reports/report.py` (que informa de la CALIDAD del dato):
este informa de la CONFIANZA en las métricas. Son preguntas distintas y por eso
son informes distintos.

    python scripts/graficos_etl.py   # genera primero las figuras
    python -c "from src.quality.auditoria_report import ...; ..."
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.quality import figures as F
from src.utils import paths
from src.utils.logging_util import get_logger

logger = get_logger("etl.auditoria_report")

_ESC = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})

VERDICT_BADGE = {
    "alta": ("#059669", "#d1fae5", "ALTA"),
    "media": ("#d97706", "#fef3c7", "MEDIA"),
    "baja": ("#dc2626", "#fee2e2", "BAJA"),
    "no_verificable": ("#64748b", "#e2e8f0", "NO VERIFICABLE"),
}

CSS = """
* { box-sizing: border-box; }
body { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
       margin: 0; padding: 2rem 1.5rem; background: #f8fafc; color: #0f172a;
       line-height: 1.55; }
.wrap { max-width: 1080px; margin: 0 auto; }
h1 { font-size: 1.7rem; margin: 0 0 .2rem; letter-spacing: -.02em; }
h2 { font-size: 1.2rem; margin: 2.2rem 0 .8rem; padding-bottom: .4rem;
     border-bottom: 1px solid #e2e8f0; }
.sub { color: #64748b; font-size: .9rem; margin-bottom: 1.5rem; }
.lead { background: #eef2ff; border-left: 4px solid #4f46e5; padding: 1rem 1.2rem;
        border-radius: 0 8px 8px 0; margin-bottom: 1.5rem; font-size: .93rem; }
.lead strong { color: #3730a3; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: .86rem;
        border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
th { background: #f1f5f9; text-align: left; padding: .6rem .7rem; font-weight: 600;
     border-bottom: 1px solid #e2e8f0; }
td { padding: .6rem .7rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
tr:last-child td { border-bottom: none; }
code { background: #f1f5f9; padding: .1rem .35rem; border-radius: 4px; font-size: .82em; }
.badge { display: inline-block; padding: .18rem .5rem; border-radius: 999px;
         font-size: .7rem; font-weight: 700; letter-spacing: .03em; white-space: nowrap; }
.kpis { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.2rem 0; }
.kpi { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
       padding: .9rem 1.2rem; flex: 1 1 150px; }
.kpi .v { font-size: 1.5rem; font-weight: 700; }
.kpi .l { font-size: .76rem; color: #64748b; text-transform: uppercase;
          letter-spacing: .04em; margin-top: .15rem; }
.limit { color: #475569; font-size: .84rem; }
.warn { background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px;
        padding: .9rem 1.1rem; margin: 1.2rem 0; font-size: .88rem; }
.warn h3 { margin: 0 0 .4rem; font-size: .95rem; color: #92400e; }
.ok { background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px;
      padding: .9rem 1.1rem; margin: 1.2rem 0; font-size: .88rem; }
.ok h3 { margin: 0 0 .4rem; font-size: .95rem; color: #065f46; }
.figs { display: grid; gap: 1.2rem; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;
         color: #64748b; font-size: .8rem; }
"""


def _esc(v: Any) -> str:
    return str(v).translate(_ESC)


def _badge(verdict: str) -> str:
    fg, bg, txt = VERDICT_BADGE.get(verdict, VERDICT_BADGE["no_verificable"])
    return f'<span class="badge" style="color:{fg};background:{bg}">{txt}</span>'


def _fmt_evidence(ev: Dict[str, Any]) -> str:
    """Evidencia legible: los escalares van en tabla, las listas se resumen."""
    partes: List[str] = []
    for k, v in ev.items():
        if isinstance(v, dict):
            inner = ", ".join(
                f"{kk}={_fmt_evidence(vv) if isinstance(vv, dict) else _esc(vv)}"
                for kk, vv in list(v.items())[:8]
            )
            partes.append(f"<code>{_esc(k)}</code>: {inner}")
        elif isinstance(v, (list, tuple)):
            muestra = ", ".join(_esc(x) for x in list(v)[:6])
            extra = " …" if len(v) > 6 else ""
            partes.append(f"<code>{_esc(k)}</code>: {muestra}{extra}")
        elif v is None:
            continue
        else:
            partes.append(f"<code>{_esc(k)}</code>: {_esc(v)}")
    return "<br>".join(partes)


def generate_auditoria_report(
    result: Dict[str, Any],
    dataset: str,
    fig_paths: Optional[Dict[str, Path]] = None,
    out_dir: Optional[Path] = None,
) -> Path:
    """Informe HTML autocontenido: tabla de afirmaciones + figuras embebidas."""
    out_dir = out_dir or paths.reports_dir("auditoria")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fig_paths = fig_paths or {}

    claims = result.get("claims", [])
    resumen = result.get("resumen_veredictos", {})
    dqs = result.get("dqs", {})

    # --- KPIs ---
    kpis = [
        (f"{float(dqs.get('dqs', 0)):.2f}", "DQS del dato"),
        (str(len(claims)), "afirmaciones evaluadas"),
        (str(resumen.get("alta", 0)), "alta confianza"),
        (str(resumen.get("no_verificable", 0)), "no verificables"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="v">{_esc(v)}</div><div class="l">{_esc(l)}</div></div>'
        for v, l in kpis
    )

    # --- Tabla de afirmaciones ---
    rows = []
    for c in claims:
        rows.append(
            f"<tr><td><strong>{_esc(c['id'])}</strong></td>"
            f"<td>{_esc(c['axis'])}</td>"
            f"<td>{_esc(c['question'])}</td>"
            f"<td>{_badge(c['verdict'])}</td>"
            f"<td>{_fmt_evidence(c['evidence'])}</td>"
            f"<td class='limit'>{_esc(c['limit'])}</td></tr>"
        )
    tabla = (
        "<table><thead><tr><th>Id</th><th>Eje</th><th>Pregunta</th><th>Veredicto</th>"
        "<th>Evidencia</th><th>Límite conocido</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    # --- Figuras ---
    figs: List[str] = []
    for clave, titulo, caption in (
        ("auditoria_veredictos", "Veredictos por eje de la auditoría",
         "Cada eje del apartado, coloreado por su veredicto. No se colapsa en un "
         "número único a propósito."),
        ("nulos_antes_despues", "Nulos por columna, antes y después de la limpieza",
         "La prueba visual de que la limpieza funcionó, y de lo que NO pudo arreglar."),
        ("dqs_dimensiones", "DQS por dimensión",
         "Cada dimensión con su peso. Una dimensión a 0 es un defecto de medición, "
         "no del dato."),
        ("sensibilidad_pesos", "Sensibilidad del DQS a los pesos",
         "Izquierda: DQS al perturbar los pesos al azar. Derecha: escenarios "
         "plausibles de pesos declarados en config."),
        ("dqs_ic_bootstrap", "Incertidumbre del DQS (bootstrap)",
         "Estimador puntual e intervalo de confianza. Unicidad e integridad se "
         "fijan porque no dependen del muestreo de filas."),
        ("dqs_evolucion", "Evolución del DQS por corrida",
         "Una línea plana demuestra determinismo: mismo input, mismo resultado."),
        ("frescura_distribucion", "Distribución temporal y ventana de frescura",
         "Explica por qué la dimensión 'frescura' es baja: los datos son históricos."),
    ):
        p = fig_paths.get(clave)
        if not p or not Path(p).exists():
            continue
        tag = F.fig_tag(Path(p), alt=titulo, caption=caption)
        if tag:
            figs.append(f"<h2>{_esc(titulo)}</h2>{tag}")

    # --- Puntos fuertes de la evidencia ---
    det = result.get("detalle", {})
    ws = det.get("weight_sensitivity", {})
    boot = det.get("bootstrap", {}).get("dqs", {})
    dr = det.get("drift", {}).get("datasets", {}).get(dataset, {})
    esc = {s["name"]: float(s["dqs"]) for s in (ws.get("scenarios") or [])}

    alta = [c for c in claims if c["verdict"] == "alta"]
    baja = [c for c in claims if c["verdict"] in ("baja", "no_verificable")]

    resumen_html = f"""
    <div class="ok">
      <h3>Lo que SÍ se puede sostener (veredictos 'alta')</h3>
      <ul style="margin:.3rem 0 0 1.1rem;padding:0">
        {''.join(f'<li><strong>{_esc(c["axis"])}</strong>: {_esc(c["evidence"] and list(c["evidence"].items())[0][0])}</li>' for c in alta)}
      </ul>
      <p style="margin:.6rem 0 0">
        <strong>Incertidumbre medida:</strong> DQS {boot.get("punto", "n/d")} con IC
        {boot.get("ci", "n/d")*100 if isinstance(boot.get("ci"), float) else "n/d"}%
        [{_esc(boot.get("ic_inf"))}, {_esc(boot.get("ic_sup"))}] — amplitud
        {_esc(boot.get("amplitud"))} puntos. Es decir, el DQS es un estimador muy estable.
      </p>
    </div>
    <div class="warn">
      <h3>Lo que NO se puede sostener (veredictos 'baja' / 'no verificable')</h3>
      <ul style="margin:.3rem 0 0 1.1rem;padding:0">
        {''.join(f'<li><strong>{_esc(c["axis"])}</strong> — {_esc(c["limit"][:170])}</li>' for c in baja)}
      </ul>
      {f'<p style="margin:.6rem 0 0"><strong>El DQS depende de los pesos:</strong> con pesos "solo_contrato" sale {esc.get("solo_contrato", "n/d")}, con "frescura_crítica" sale {esc.get("frescura_critica", "n/d")}. El número refleja una decisión de configuración, no solo una propiedad del dato.</p>' if esc else ''}
    </div>
    """

    html_doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Auditoría de la medición -étricas — {_esc(dataset)}</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>Auditoría de la medición -étricas — {_esc(dataset)}</h1>
<p class="sub">Generado {_esc(ts)} · {_esc(result.get("generado", "")[:19])} ·
DQS {_esc(dqs.get("dqs"))} · {_esc(len(claims))} afirmaciones</p>

<div class="lead">
<strong>Este informe no es sobre la calidad del dato, sino sobre la confianza en las
métricas.</strong> El DQS (quality gate) mide propiedades del dato: nulos, rangos,
unicidad. Aquí se evalúa si ese DQS y las cifras derivadas resisten las preguntas
incómodas: ¿dependen de una decisión mía?, ¿cuánta incertidumbre tienen?, ¿qué parte
de la validación es tautológica? Por eso no se calcula un «índice de confiabilidad»:
un número único repetiría el error que hace malinterpretable el DQS.
</div>

<h2>Resumen</h2>
<div class="kpis">{kpi_html}</div>
{resumen_html}

<h2>Tabla de afirmaciones verificables</h2>
<p class="sub">Cada fila es una afirmación que se sostiene o no, con su evidencia
medible y su límite conocido. Un veredicto sin límite sería una garantía, y aquí
no hay garantías.</p>
{tabla}

<div class="figs">{''.join(figs)}</div>

<footer>
<p>Generado por <code>src/quality/auditoria.py</code> + <code>src/quality/auditoria_report.py</code>.
Umbrales y número de iteraciones en <code>config/quality/auditoria_rules.yaml</code> (nada hardcodeado).</p>
<p>Métodología CRISP-DM + KDD · SIPAT-ETL v1.0</p>
</footer>
</div></body></html>"""

    path = out_dir / f"{dataset}_auditoria_{ts.replace(':', '').replace(' ', '_')}.html"
    path.write_text(html_doc, encoding="utf-8")
    logger.info("informe de auditoría: %s", path)
    return path
