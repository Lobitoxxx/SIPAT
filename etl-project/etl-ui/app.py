"""SIPAT-ETL — Dashboard de observabilidad (Streamlit).

Capa mínima de observabilidad: solo LEE artefactos ya generados por el pipeline
(manifests, quality gates, perfiles, silver/gold, lineage). NO contiene lógica
de negocio ni de extracción: el pipeline se ejecuta por CLI
(`python scripts/run_pipeline.py`), no desde la interfaz.

Ejecución:  streamlit run etl-ui/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from src.utils.configloader import load_settings  # noqa: E402

st.set_page_config(page_title="SIPAT-ETL · Observabilidad", page_icon="🧪", layout="wide")
SETTINGS = load_settings()
DATASETS = list(SETTINGS["datasets"])
WEIGHTS = SETTINGS["quality"]["weights"]

STATUS_ICON = {"PASSED": "✅", "WARNING": "⚠️", "FAILED": "❌", "ERROR": "⛔"}


@st.cache_data
def load_manifests() -> list[dict]:
    runs_dir = ROOT / "artifacts" / "runs"
    if not runs_dir.exists():
        return []
    out = []
    for d in sorted(runs_dir.glob("run-*"), reverse=True):
        mf = d / "manifest.json"
        if mf.exists():
            try:
                out.append(json.loads(mf.read_text(encoding="utf-8")))
            except Exception:
                continue
    return out


@st.cache_data
def read_silver(dataset: str, version: str):
    p = ROOT / "data" / "silver" / f"{dataset}_silver_{version}.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)


@st.cache_data
def read_profile(dataset: str, stage: str) -> dict:
    p = ROOT / "reports" / "profiling" / f"{dataset}_{stage}_profile.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@st.cache_data
def read_lineage() -> pd.DataFrame:
    db = ROOT / "artifacts" / "lineage" / "sipat_lineage.duckdb"
    if not db.exists():
        return pd.DataFrame()
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(
            "SELECT dataset, layer, run_id, rows, cols, created_at FROM dataset_lines "
            "ORDER BY created_at DESC LIMIT 200"
        ).df()
    finally:
        con.close()


st.title("🧪 SIPAT-ETL · Observabilidad del pipeline")
st.caption(
    f"Metodología **{SETTINGS['project']['methodology']}** · v{SETTINGS['project']['version']} · "
    "Interfaz de solo lectura sobre los artefactos del pipeline."
)

manifests = load_manifests()
if not manifests:
    st.warning(
        "No hay corridas todavía. Ejecuta primero:\n\n"
        "```bash\npython scripts/run_pipeline.py\n```"
    )
    st.stop()

# --- Overview: último run ---
latest = manifests[0]
run_id = latest["run_id"]
c1, c2, c3 = st.columns([2, 1, 1])
c1.metric("Último run_id", run_id)
c2.metric("Estado global", f"{STATUS_ICON.get(latest['status'], '?')} {latest['status']}")
c3.metric("Fecha", str(latest.get("finished_at", ""))[:19])

# --- Gates por dataset ---
st.subheader("Quality gates del run")
cols = st.columns(len(DATASETS))
for i, ds in enumerate(DATASETS):
    ds_data = (latest.get("datasets") or {}).get(ds, {})
    gate = ds_data.get("gate", "-")
    dqs = ds_data.get("dqs")
    with cols[i]:
        st.metric(f"{ds} · DQS", "n/d" if dqs is None else round(dqs, 2))
        st.write(f"{STATUS_ICON.get(gate, '?')} **{gate}**")

# --- DQS por dimensión: radar (plotly) + evolución por corrida ---
st.subheader("Data Quality Score")
st.caption("DQS = indicador interno ponderado de calidad (NO es una probabilidad de verdad de los datos).")

# Lectura del último assessment de confiabilidad (contiene el desglose por dimensión).
@st.cache_data
def load_reliability(dataset: str):
    saved = sorted((ROOT / "reports" / "reliability").glob(f"{dataset}_reliability_*.json"), reverse=True)
    if not saved:
        return None
    return json.loads(saved[0].read_text(encoding="utf-8"))


g1, g2 = st.columns([1, 1.2])

with g1:
    rel_map = {ds: load_reliability(ds) for ds in DATASETS}
    if any(rel_map.values()):
        try:
            import plotly.graph_objects as go

            fig = go.Figure()
            palette = ["#4f46e5", "#059669", "#d97706", "#dc2626"]
            for i, (ds, rel) in enumerate(rel_map.items()):
                if not rel:
                    continue
                d = rel["dqs"]
                dims = [k for k in WEIGHTS if k in d]
                fig.add_trace(go.Scatterpolar(
                    r=[d[k] for k in dims] + [d[dims[0]]],
                    theta=[k[:10] for k in dims] + [dims[0][:10]],
                    fill="toself", name=ds,
                    line=dict(color=palette[i % len(palette)], width=2),
                ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=True, height=380,
                title="Dimensiones del DQS (0-100)",
                margin=dict(l=40, r=40, t=50, b=20),
            )
            st.plotly_chart(fig, width="stretch")
        except Exception as exc:
            st.caption(f"Gráfico no disponible: {exc}")

with g2:
    if any(load_reliability(ds) for ds in DATASETS):
        serie = []
        for ds in DATASETS:
            rel = load_reliability(ds)
            if rel:
                for s in rel["detalle"]["drift"]["serie"]:
                    if s["dataset"] == ds:
                        serie.append(s)
        if serie:
            import plotly.graph_objects as go

            fig = go.Figure()
            palette = ["#4f46e5", "#059669"]
            for i, ds in enumerate(DATASETS):
                xs = sorted([s for s in serie if s["dataset"] == ds], key=lambda r: r["run_id"])
                if xs:
                    fig.add_trace(go.Scatter(
                        x=list(range(len(xs))), y=[s["dqs"] for s in xs],
                        mode="lines+markers", name=ds,
                        line=dict(color=palette[i % len(palette)], width=2),
                    ))
            fig.update_layout(
                title="Evolución del DQS por corrida", height=380,
                xaxis_title="Corridas (orden temporal)", yaxis_title="DQS",
                yaxis_range=[0, 100], margin=dict(l=40, r=20, t=50, b=40),
            )
            st.plotly_chart(fig, width="stretch")
            st.caption("Una línea plana es la evidencia de determinismo del pipeline.")

# --- Tabla de confiabilidad (resumen) ---
with st.expander("Confiabilidad de las métricas (¿cuánta confianza merecen?)", expanded=False):
    st.caption(
        "El DQS mide el DATO. Esto mide la CONFIANZA en las métricas. "
        "No se colapsa en un número único a propósito."
    )
    for ds in DATASETS:
        rel = load_reliability(ds)
        if not rel:
            st.info(f"{ds}: sin evaluación de confiabilidad. Ejecuta scripts/graficos_etl.py")
            continue
        st.markdown(f"**{ds}** — DQS {rel['dqs']['dqs']}")
        st.dataframe(
            pd.DataFrame([
                {"Id": c["id"], "Eje": c["axis"], "Veredicto": c["verdict"],
                 "Evidencia": json.dumps(c["evidence"], ensure_ascii=False)[:180],
                 "Límite conocido": c["limit"]}
                for c in rel["claims"]
            ]),
            width="stretch",
        )
        st.caption(f"Veredictos: {rel['resumen_veredictos']}")

# --- Silver datasets ---
st.subheader("Datasets Silver (contrato canónico)")
for ds in DATASETS:
    version = SETTINGS["datasets"][ds]["version"]
    with st.expander(f"{ds} — silver v{version}", expanded=False):
        df = read_silver(ds, version)
        if df is None:
            st.info("Silver no generado todavía.")
            continue
        st.write(f"**{len(df):,} filas × {df.shape[1]} columnas**")
        st.dataframe(df.head(50), width="stretch")
        num = df.select_dtypes("number").columns.tolist()
        if num:
            st.bar_chart(df[num].describe().T[["mean", "min", "max"]])
# --- Perfiles antes/después ---
st.subheader("Perfilado de datos (antes → después)")
for ds in DATASETS:
    with st.expander(f"Perfil {ds}", expanded=False):
        before = read_profile(ds, "before")
        after = read_profile(ds, "after")
        if not after:
            st.info("Sin perfil generado.")
            continue
        rows = []
        for col, m in after.get("columns", {}).items():
            b = before.get("columns", {}).get(col, {})
            rows.append(
                {
                    "columna": col,
                    "dtype_after": m.get("dtype"),
                    "nulls_before": b.get("nulls", "n/d"),
                    "nulls_after": m.get("nulls"),
                    "uniques_after": m.get("uniques"),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch")

# --- Lineage ---
st.subheader("Lineage (DuckDB)")
lin = read_lineage()
if not lin.empty:
    st.dataframe(lin, width="stretch")
else:
    st.caption("Sin registros de lineage todavía.")

# --- Historial de runs ---
with st.expander("Historial completo de corridas", expanded=False):
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "run_id": m["run_id"],
                    "estado": m.get("status"),
                    "onsv": (m.get("datasets") or {}).get("onsv", {}).get("dqs"),
                    "cinemometros": (m.get("datasets") or {}).get("cinemometros", {}).get("dqs"),
                    "finalizado": m.get("finished_at", "")[:19],
                }
                for m in manifests
            ]
        ),
        width="stretch",
    )
