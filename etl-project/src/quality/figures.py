# -*- coding: utf-8 -*-
"""Figuras del ETL (matplotlib + seaborn, backend Agg).

Antes de este módulo, `matplotlib` y `plotly` estaban declaradas en
requirements.txt pero NO se usaban en ninguna parte: el ETL no tenía ni una
figura. Estas funciones cierran ese hueco, y siguen el patrón del SIPAT raíz
(`scripts/graficos.py` -> `docs/figuras/`), escribiendo en
`docs/figuras/etl/`.

Todas las funciones devuelven la ruta del PNG y son idempotentes. Si falta
`seaborn` o `matplotlib`, se degradan con un aviso en vez de romper el
pipeline: una figura que no se puede dibujar nunca debe tumbar un ETL.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.utils.logging_util import get_logger

logger = get_logger("etl.figures")

FIGS_DIRNAME = "etl"
FIGS_SUBDIR = "docs/figuras"

# Paleta coherente con el tema del SIPAT (indigo/verde/ámbar/rojo).
PALETTE = ["#4f46e5", "#059669", "#d97706", "#dc2626", "#0891b2", "#7c3aed"]
VERDICT_COLORS = {
    "alta": "#059669",
    "media": "#d97706",
    "baja": "#dc2626",
    "no_verificable": "#94a3b8",
}

# Sin ventana: obligatorio en Streamlit/CI/segundos pasos.
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _MPL = True
except Exception as exc:  # pragma: no cover
    plt = None  # type: ignore
    _MPL = False
    logger.warning("matplotlib no disponible: %s", exc)

try:
    import seaborn as sns

    _SNS = True
except Exception:  # pragma: no cover
    sns = None  # type: ignore
    _SNS = False


def available() -> bool:
    return _MPL


def figures_dir(root: Optional[Path] = None) -> Path:
    """docs/figuras/etl/ (creada si no existe)."""
    from src.utils import paths as P

    base = (root or P.ROOT) / FIGS_SUBDIR / FIGS_DIRNAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def _style() -> None:
    if _SNS:
        sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 110,
            "savefig.bbox": "tight",
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "axes.axisbelow": True,
            "figure.facecolor": "white",
        }
    )


def _save(fig, name: str, out_dir: Path) -> Path:
    p = out_dir / name
    fig.savefig(p, format="png")
    plt.close(fig)
    return p


def fig_to_base64(fig, fmt: str = "png") -> str:
    """Serializa una figura a base64 para incrustarla en un HTML autocontenido."""
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def fig_file_to_base64(path: Path) -> str:
    """Base64 de un PNG ya escrito en disco, para incrustarlo sin redibujar."""
    try:
        return base64.b64encode(Path(path).read_bytes()).decode("ascii")
    except Exception:
        return ""


def fig_tag(path: Path, alt: str = "", caption: str = "") -> str:
    """Devuelve un <img> base64 listo para un HTML autocontenido."""
    b64 = fig_file_to_base64(path)
    if not b64:
        return ""
    img = f'<img src="data:image/png;base64,{b64}" alt="{alt}" style="max-width:100%;border:1px solid #e2e8f0;border-radius:8px;">'
    cap = f'<p style="font-size:0.85rem;color:#475569;margin:0.4rem 0 1.4rem">{caption}</p>' if caption else ""
    return f'<figure style="margin:0 0 1rem">{img}{cap}</figure>'


# --------------------------------------------------------------------------
# 1) Nulos antes / después: la prueba visual de que la limpieza funcionó
# --------------------------------------------------------------------------
def plot_nulls_before_after(
    before: Dict[str, Any],
    after: Dict[str, Any],
    dataset: str,
    out_dir: Optional[Path] = None,
    top: int = 18,
) -> Optional[Path]:
    """Barras horizontales de % nulos por columna, antes y después de limpiar.

    El perfil "antes" usa los nombres CRUDOS (`'CÓDIGO SINIESTRO'`) y el
    "después" los canónicos (`codigo`). Sin alinear ambos por el mapa `rename`
    de settings, la intersección sería casi vacía y la figura no se podría
    dibujar: por eso se alinean aquí.
    """
    if not _MPL:
        return None
    fig = _fig_nulls_before_after(before, after, dataset)
    if fig is None:
        return None
    return _save(fig, f"{dataset}_nulos_antes_despues.png", out_dir or figures_dir())


def _fig_nulls_before_after(
    before: Dict[str, Any], after: Dict[str, Any], dataset: str, top: int = 18
):
    """Construye (sin guardar) la figura de nulos. Devuelve None si no hay datos."""
    b_cols = (before or {}).get("columns", {})
    a_cols = (after or {}).get("columns", {})
    if not b_cols or not a_cols:
        return None

    # Alinea por el mapa de renombrado declarado en settings.
    ren = _rename_map(dataset)
    alineado: Dict[str, Dict[str, Any]] = {}
    for raw_name, meta in b_cols.items():
        canon = ren.get(raw_name, raw_name)
        if canon in a_cols:
            alineado[canon] = {"antes": meta, "despues": a_cols[canon]}

    cols = list(alineado)
    if not cols:
        logger.warning("sin columnas comparables antes/después para '%s'", dataset)
        return None

    antes = np.array([float(alineado[c]["antes"].get("null_pct", 0.0)) for c in cols])
    despues = np.array([float(alineado[c]["despues"].get("null_pct", 0.0)) for c in cols])
    # Ordenar por el nulos "antes" descendente: es donde estaba el problema.
    order = np.argsort(-antes)[:top]
    cols = [cols[i] for i in order]
    antes, despues = antes[order], despues[order]

    _style()
    fig, ax = plt.subplots(figsize=(10, max(4, 0.34 * len(cols))))
    y = np.arange(len(cols))
    h = 0.38
    ax.barh(y + h / 2, antes, h, label="Antes (crudo)", color="#94a3b8")
    ax.barh(y - h / 2, despues, h, label="Después (Silver)", color=PALETTE[0])
    ax.set_yticks(y)
    ax.set_yticklabels(cols, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("% de valores nulos")
    ax.set_title(f"{dataset}: nulos por columna, antes y después de la limpieza")
    ax.legend(loc="lower right")

    n_resueltos = int((antes > 0).sum() - (despues > 0).sum())
    # Aviso explícito de las columnas que la limpieza NO pudo arreglar: si una
    # columna sigue casi vacía, el dato de origen no la trae y no hay nada que
    # imputar. Se declara en vez de dejar que pase desapercibida.
    casi_vacias = [cols[i] for i, v in enumerate(despues) if v >= 50]
    texto = (f"columnas con nulos: {(antes > 0).sum()} → {(despues > 0).sum()}"
             f"   |   nulos resueltos: {n_resueltos}")
    if casi_vacias:
        texto += f"   |   siguen casi vacías en Silver: {len(casi_vacias)}"
    ax.text(
        0.015, 0.02, texto,
        transform=ax.transAxes, ha="left", va="bottom", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", fc="#eef2ff", ec="#c7d2fe"),
    )
    if casi_vacias:
        ax.text(
            0.015, 0.075, "casi vacías: " + ", ".join(casi_vacias[:4]),
            transform=ax.transAxes, ha="left", va="bottom", fontsize=7.5,
            color="#b45309",
        )
    return fig


def html_nulls_before_after(
    before: Dict[str, Any], after: Dict[str, Any], dataset: str
) -> str:
    """`<figure>` en base64 con la figura de nulos, para el HTML del pipeline.

    No escribe ningún PNG en disco: los reportes del pipeline se embeben a
    memoria, así que no aparece un `dqs_dimensiones.png` de un solo dataset
    conviviendo con el comparativo de `scripts/graficos_etl.py`."""
    if not _MPL:
        return ""
    fig = _fig_nulls_before_after(before, after, dataset)
    if fig is None:
        return ""
    b64 = fig_to_base64(fig)
    return (
        f'<figure style="margin:0 0 1rem">'
        f'<img src="data:image/png;base64,{b64}" '
        f'alt="Nulos por columna antes y después de la limpieza" '
        f'style="max-width:100%;border:1px solid #e2e8f0;border-radius:8px;">'
        f"<figcaption style=\"font-size:.85rem;color:#475569;margin-top:.35rem\">"
        f"Qué resolvió la limpieza y qué no: las columnas que siguen casi vacías no las "
        f"arregla ningún <code>fillna</code>, sencillamente la fuente no las trae."
        f"</figcaption></figure>"
    )


def _rename_map(dataset: str) -> Dict[str, str]:
    """Mapa crudo -> canónico desde settings.datasets.<dataset>.rename."""
    from src.utils import paths as P
    from src.utils.configloader import load_yaml

    try:
        d = load_yaml(P.CONFIG / "settings.yaml") or {}
        return dict(((d.get("datasets") or {}).get(dataset) or {}).get("rename") or {})
    except Exception:
        return {}


# --------------------------------------------------------------------------
# 2) DQS por dimensión, con los pesos dibujados
# --------------------------------------------------------------------------
def plot_dqs_dimensions(
    dqs_by_dataset: Dict[str, Dict[str, Any]],
    out_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Las seis dimensiones del DQS por dataset, con el peso de cada una encima."""
    if not _MPL or not dqs_by_dataset:
        return None
    fig = _fig_dqs_dimensions(dqs_by_dataset)
    if fig is None:
        return None
    return _save(fig, "dqs_dimensiones.png", out_dir or figures_dir())


def html_dqs_dimensions(dqs_by_dataset: Dict[str, Dict[str, Any]]) -> str:
    """`<figure>` en base64 con las dimensiones del DQS, para el HTML del reporte."""
    if not _MPL or not dqs_by_dataset:
        return ""
    fig = _fig_dqs_dimensions(dqs_by_dataset)
    if fig is None:
        return ""
    b64 = fig_to_base64(fig)
    return (
        f'<figure style="margin:0 0 1rem">'
        f'<img src="data:image/png;base64,{b64}" '
        f'alt="Dimensiones del DQS con su peso" '
        f'style="max-width:100%;border:1px solid #e2e8f0;border-radius:8px;">'
        f'<figcaption style="font-size:.85rem;color:#475569;margin-top:.35rem">'
        f"El DQS es una media ponderada de estas seis dimensiones. Mirarlas por separado "
        f"explica mucho más que el número final: la frescura es baja porque la fuente es "
        f"histórica, no por un defecto del proceso."
        f"</figcaption></figure>"
    )


def _fig_dqs_dimensions(dqs_by_dataset: Dict[str, Dict[str, Any]]):
    if not _MPL or not dqs_by_dataset:
        return None
    from src.quality.auditoria import DIMS

    _style()
    datasets = list(dqs_by_dataset)
    ncols = max(len(datasets), 1)
    fig, axes = plt.subplots(1, ncols, figsize=(6.2 * ncols, 4.6), squeeze=False)
    for ax, ds in zip(axes[0], datasets):
        d = dqs_by_dataset[ds]
        valores = [float(d.get(k, 0.0)) for k in DIMS]
        pesos = [float((d.get("weights") or {}).get(k, 0.0)) for k in DIMS]
        colores = [VERDICT_COLORS.get(_verdict(v), PALETTE[0]) for v in valores]
        barras = ax.bar([k[:9] for k in DIMS], valores, color=colores)
        for b, v, w in zip(barras, valores, pesos):
            ax.text(
                b.get_x() + b.get_width() / 2, v + 1.2,
                f"{v:.0f}\n×{w:.2f}",
                ha="center", va="bottom", fontsize=8,
            )
        ax.set_ylim(0, 118)
        ax.set_ylabel("Puntaje 0-100")
        ax.set_title(f"{ds} · DQS {float(d.get('dqs', 0)):.2f}")
        ax.tick_params(axis="x", rotation=40)
    fig.suptitle(
        "DQS por dimensión (etiqueta superior: valor · peso)", y=1.04, fontweight="bold",
    )
    fig.tight_layout()
    return fig


def _verdict(v: float) -> str:
    if v >= 99.9:
        return "alta"
    if v >= 80:
        return "media"
    return "baja"


# --------------------------------------------------------------------------
# 3) Evolución del DQS entre corridas
# --------------------------------------------------------------------------
def plot_dqs_evolution(
    serie: List[Dict[str, Any]],
    out_dir: Optional[Path] = None,
    dataset: Optional[str] = None,
) -> Optional[Path]:
    """Línea del DQS por corrida.

    Una línea PLANA es la evidencia visual del determinismo: mismo input, mismo
    resultado. Los saltos se explican por un cambio en la medición (huella).
    """
    if not _MPL or not serie:
        return None
    _style()
    fig, ax = plt.subplots(figsize=(11, 4.4))
    por_ds: Dict[str, List[Dict[str, Any]]] = {}
    for s in serie:
        por_ds.setdefault(s["dataset"], []).append(s)

    for i, (ds, xs) in enumerate(sorted(por_ds.items())):
        xs = sorted(xs, key=lambda r: r.get("run_id", ""))
        y = [float(r["dqs"]) for r in xs]
        x = range(len(y))
        ax.plot(x, y, marker="o", ms=4, lw=1.6, color=PALETTE[i % len(PALETTE)],
                label=f"{ds} (n={len(y)})")
        if y:
            ax.axhline(float(np.mean(y)), ls="--", lw=1, alpha=0.5,
                       color=PALETTE[i % len(PALETTE)])
    ax.set_xlabel("Corridas (en orden temporal)")
    ax.set_ylabel("DQS")
    ax.set_title("Evolución del DQS por corrida — una línea plana demuestra determinismo")
    ax.legend()
    # Nombre por dataset: si no, el segundo dataset sobrescribe al primero.
    nombre = f"dqs_evolucion_{dataset}.png" if dataset else "dqs_evolucion.png"
    return _save(fig, nombre, out_dir or figures_dir())


# --------------------------------------------------------------------------
# 4) Sensibilidad a los pesos
# --------------------------------------------------------------------------
def plot_weight_sensitivity(
    sens: Dict[str, Any],
    out_dir: Optional[Path] = None,
    dataset: Optional[str] = None,
) -> Optional[Path]:
    """Histograma del DQS perturbando los pesos + escenarios declarados.

    Responde a la crítica más fácil contra un DQS: "ese número sale de los pesos
    que elegiste tú".
    """
    if not _MPL or not sens or not sens.get("enabled"):
        return None
    valores = sens.get("distribucion_valores") or []
    if not valores:
        return None
    _style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))

    ax1.hist(valores, bins=28, color=PALETTE[0], edgecolor="white", alpha=0.9)
    cfg = sens.get("dqs_config")
    if cfg is not None:
        ax1.axvline(float(cfg), color=VERDICT_COLORS["baja"], lw=2,
                    label=f"DQS configurado: {float(cfg):.2f}")
    d = sens["distribucion"]
    ax1.axvline(d["p05"], ls=":", color="#64748b", lw=1.5, label=f"p05 = {d['p05']}")
    ax1.axvline(d["p95"], ls=":", color="#64748b", lw=1.5, label=f"p95 = {d['p95']}")
    ax1.set_xlabel("DQS bajo pesos perturbados aleatoriamente")
    ax1.set_ylabel("Frecuencia")
    ax1.set_title(
        f"Sensibilidad a los pesos (spread p05-p95 = {sens['spread_p05_p95']:.2f})"
    )
    ax1.legend(fontsize=8)

    esc = sens.get("scenarios") or []
    if esc:
        nombres = [e["name"] for e in esc]
        valores_e = [float(e["dqs"]) for e in esc]
        barras = ax2.barh(range(len(nombres)), valores_e,
                          color=[VERDICT_COLORS[_verdict(v)] for v in valores_e])
        ax2.set_yticks(range(len(nombres)))
        ax2.set_yticklabels(nombres, fontsize=9)
        ax2.invert_yaxis()
        if cfg is not None:
            ax2.axvline(float(cfg), color=VERDICT_COLORS["baja"], ls="--", lw=1.5)
        for b, v in zip(barras, valores_e):
            ax2.text(v + 0.6, b.get_y() + b.get_height() / 2, f"{v:.1f}", va="center", fontsize=9)
        ax2.set_xlabel("DQS con esos pesos")
        ax2.set_title("Escenarios de pesos alternativos (línea = configuración)")
    fig.tight_layout()
    nombre = (f"{dataset}_sensibilidad_pesos.png" if dataset else "sensibilidad_pesos.png")
    return _save(fig, nombre, out_dir or figures_dir())


# --------------------------------------------------------------------------
# 5) Distribución de la frescura
# --------------------------------------------------------------------------
def plot_freshness_distribution(
    dates: pd.Series,
    window_days: int,
    out_dir: Optional[Path] = None,
    bins: int = 40,
    dataset: Optional[str] = None,
) -> Optional[Path]:
    """Histograma de fechas con la ventana de frescura marcada.

    Explica por qué la dimensión 'frescura' vale 12: los datos son históricos.
    """
    if not _MPL:
        return None
    s = pd.to_datetime(dates, errors="coerce").dropna()
    if s.empty:
        return None
    _style()
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.hist(s.dt.to_pydatetime(), bins=bins, color=PALETTE[0], edgecolor="white")
    corte = pd.Timestamp.now().normalize() - pd.Timedelta(days=window_days)
    ax.axvline(corte, color=VERDICT_COLORS["baja"], lw=2,
               label=f"Ventana de frescura: últimos {window_days} días")
    ax.set_xlabel("Fecha del registro")
    ax.set_ylabel("Número de registros")
    ax.set_title(
        f"{dataset or ''} Distribución temporal: {s.min().date()} a {s.max().date()} — "
        f"fuera de ventana: {int((s < corte).sum()):,} de {len(s):,}"
    )
    ax.legend()
    fig.autofmt_xdate()
    nombre = (f"{dataset}_frescura_distribucion.png" if dataset
              else "frescura_distribucion.png")
    return _save(fig, nombre, out_dir or figures_dir())


# --------------------------------------------------------------------------
# 6) Intervalos de confianza del DQS (forest plot)
# --------------------------------------------------------------------------
def plot_bootstrap_ci(
    boot: Dict[str, Any],
    out_dir: Optional[Path] = None,
    dataset: Optional[str] = None,
) -> Optional[Path]:
    """Forest plot: estimador puntual e IC por dimensión y global."""
    if not _MPL or not boot or not boot.get("enabled"):
        return None
    from src.quality.auditoria import DIMS

    claves = [k for k in list(DIMS) + ["dqs"] if k in boot]
    puntos = [float(boot[k]["punto"]) for k in claves]
    lo = [float(boot[k]["ic_inf"]) for k in claves]
    hi = [float(boot[k]["ic_sup"]) for k in claves]

    _style()
    fig, ax = plt.subplots(figsize=(9, 0.62 * len(claves) + 1.8))
    y = np.arange(len(claves))
    for yi, p, l, h in zip(y, puntos, lo, hi):
        ax.plot([l, h], [yi, yi], lw=3, color=PALETTE[0], solid_capstyle="round")
        ax.plot(p, yi, "o", ms=7, color=VERDICT_COLORS["baja"], zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels([k for k in claves], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 100.5)
    ax.set_xlabel("Puntaje 0-100")
    ci_pct = int(float(boot.get("ci", 0.95)) * 100)
    ax.set_title(
        f"DQS por dimensión con IC {ci_pct}% (bootstrap, "
        f"{boot.get('n_resamples')} remuestreos)\n"
        f"unicidad e integridad se fijan: no dependen del muestreo de filas"
    )
    nombre = (f"{dataset}_dqs_ic_bootstrap.png" if dataset else "dqs_ic_bootstrap.png")
    return _save(fig, nombre, out_dir or figures_dir())


# --------------------------------------------------------------------------
# 7) Afirmaciones de confiabilidad
# --------------------------------------------------------------------------
def plot_auditoria_claims(
    claims: List[Dict[str, Any]],
    out_dir: Optional[Path] = None,
    dataset: Optional[str] = None,
) -> Optional[Path]:
    """Resumen visual de los veredictos: cuántos ejes por nivel de confianza."""
    if not _MPL or not claims:
        return None
    _style()
    orden = ["alta", "media", "baja", "no_verificable"]
    conteo = {v: sum(1 for c in claims if c["verdict"] == v) for v in orden}
    etiquetas = [v.replace("_", " ") for v in orden]
    valores = [conteo[v] for v in orden]
    colores = [VERDICT_COLORS[v] for v in orden]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={"width_ratios": [1, 1.5]})
    barras = ax1.bar(etiquetas, valores, color=colores)
    for b, v in zip(barras, valores):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.06, str(v), ha="center", fontsize=10)
    ax1.set_ylabel("Número de afirmaciones")
    ax1.set_title("Veredictos por nivel")
    ax1.set_ylim(0, max(valores + [1]) + 1)

    cols = [VERDICT_COLORS.get(c["verdict"], "#94a3b8") for c in claims]
    ax2.barh(range(len(claims)), [1] * len(claims), color=cols)
    ax2.set_yticks(range(len(claims)))
    ax2.set_yticklabels([f"{c['id']} {c['axis'][:26]}" for c in claims], fontsize=8)
    ax2.invert_yaxis()
    ax2.set_xticks([])
    ax2.set_title("Cada eje de la tabla de confiabilidad")
    fig.tight_layout()
    nombre = (f"{dataset}_confiabilidad_veredictos.png" if dataset
              else "confiabilidad_veredictos.png")
    return _save(fig, nombre, out_dir or figures_dir())


# --------------------------------------------------------------------------
# 8) Negros: contexto de negocio desde las agregaciones Gold
# --------------------------------------------------------------------------
def plot_top_categories(
    df: pd.DataFrame, column: str, title: str, name: str,
    out_dir: Optional[Path] = None, top: int = 15,
) -> Optional[Path]:
    """Barras horizontales de las categorías más frecuentes."""
    if not _MPL or column not in df.columns:
        return None
    _style()
    conteo = df[column].dropna().astype(str).value_counts().head(top)
    if conteo.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, max(3.2, 0.32 * len(conteo))))
    colores = [PALETTE[0]] + [PALETTE[2]] * (len(conteo) - 1)
    ax.barh(range(len(conteo))[::-1], conteo.values, color=colores)
    ax.set_yticks(range(len(conteo))[::-1])
    ax.set_yticklabels(conteo.index, fontsize=9)
    ax.set_xlabel("Registros")
    ax.set_title(title)
    return _save(fig, name, out_dir or figures_dir())


def plot_temporal(
    df: pd.DataFrame, date_col: str, name: str, title: str,
    out_dir: Optional[Path] = None, by: Optional[str] = None,
) -> Optional[Path]:
    """Evolución temporal; opcionalmente apilada por una categórica."""
    if not _MPL or date_col not in df.columns:
        return None
    d = df[[date_col]].copy()
    d["_y"] = pd.to_datetime(d[date_col], errors="coerce").dt.year
    d = d.dropna(subset=["_y"])
    if d.empty:
        return None
    _style()
    fig, ax = plt.subplots(figsize=(10, 4.4))
    if by and by in df.columns:
        tabla = (
            d.assign(_cat=df[by].astype(str))
            .groupby(["_y", "_cat"]).size().unstack(fill_value=0)
        )
        tabla = tabla.loc[:, tabla.sum().sort_values(ascending=False).index[:6]]
        ax = tabla.plot(kind="bar", stacked=True, ax=ax, width=0.8)
        ax.legend(title=by[:24], fontsize=8, ncol=2)
    else:
        d.groupby("_y").size().plot(kind="bar", ax=ax, color=PALETTE[0], width=0.6)
    ax.set_xlabel("Año")
    ax.set_ylabel("Registros")
    ax.set_title(title)
    return _save(fig, name, out_dir or figures_dir())


# --------------------------------------------------------------------------
# Orquestador
# --------------------------------------------------------------------------
def build_all(
    dataset: str,
    silver: pd.DataFrame,
    auditoria: Optional[Dict[str, Any]] = None,
    other_silver: Optional[Dict[str, pd.DataFrame]] = None,
    root: Optional[Path] = None,
) -> Dict[str, str]:
    """Genera todas las figuras aplicables a un dataset. Devuelve {nombre: ruta}."""
    out = figures_dir(root)
    rutas: Dict[str, str] = {}

    def _try(name: str, fn):
        try:
            p = fn()
            if p:
                rutas[name] = str(p)
        except Exception as exc:  # pragma: no cover
            logger.warning("figura '%s' falló: %s", name, exc)

    # Nulos antes/después (perfilados)
    prof_dir = (root or _root()) / "reports" / "profiling"
    before = _read_json(prof_dir / f"{dataset}_before_profile.json")
    after = _read_json(prof_dir / f"{dataset}_after_profile.json")
    _try("nulos_antes_despues", lambda: plot_nulls_before_after(before, after, dataset, out))

    if auditoria:
        d = auditoria.get("detalle", {})
        _try("confiabilidad_veredictos",
             lambda: plot_auditoria_claims(auditoria.get("claims", []), out, dataset))
        # `assess` guarda la distribución de la sensibilidad FUERA del detalle
        # (para no duplicarla en el JSON); la figura la necesita, así que se
        # reinyecta antes de dibujar.
        sens = dict(d.get("weight_sensitivity", {}))
        vals = auditoria.get("detalle", {}).get("weight_sensitivity_distribucion")
        if vals and sens.get("enabled"):
            sens["distribucion_valores"] = vals
        _try("sensibilidad_pesos", lambda: plot_weight_sensitivity(sens, out, dataset))
        _try("dqs_ic_bootstrap", lambda: plot_bootstrap_ci(d.get("bootstrap", {}), out, dataset))

    # Evolución del DQS
    serie = (auditoria or {}).get("detalle", {}).get("drift", {}).get("serie", [])
    _try("dqs_evolucion", lambda: plot_dqs_evolution(serie, out, dataset) if serie else None)

    # Frescura
    cfg = (root or _root()) / "config" / "settings.yaml"
    fresh_col, window = _freshness_config(cfg, dataset)
    if fresh_col and fresh_col in silver.columns:
        _try("frescura_distribucion",
             lambda: plot_freshness_distribution(
                 silver[fresh_col], window, out, dataset=dataset))

    return rutas


def _root() -> Path:
    from src.utils import paths as P

    return P.ROOT


def _read_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _freshness_config(settings_yaml: Path, dataset: str) -> Tuple[Optional[str], int]:
    try:
        import yaml

        d = yaml.safe_load(settings_yaml.read_text(encoding="utf-8")) or {}
        col = ((d.get("datasets") or {}).get(dataset) or {}).get("freshness_column")
        window = int((d.get("quality") or {}).get("freshness_window_days", 365))
        return col, window
    except Exception:
        return None, 365
