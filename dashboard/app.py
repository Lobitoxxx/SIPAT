"""Dashboard SIPAT — Prevención antes de viajar + analítica de siniestralidad vial (Perú).

Ejecutar:  streamlit run dashboard/app.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="SIPAT · Viaja Seguro", page_icon="🛡️",
                   layout="wide", initial_sidebar_state="expanded")

from theme import css, hero

BASE = "data/processed/dashboard"


@st.cache_data
def load():
    events = pd.read_csv(f"{BASE}/onsv_events.csv", parse_dates=["fecha"])
    sutran_events = pd.read_csv(f"{BASE}/sutran_events.csv", parse_dates=["fecha"])
    ositran_events = pd.read_csv(f"{BASE}/ositran_events.csv", parse_dates=["fecha"])
    with open(f"{BASE}/tramos_geo.json", encoding="utf-8") as f:
        tramos = json.load(f)
    with open(f"{BASE}/puntos_negros.json", encoding="utf-8") as f:
        puntos = json.load(f)
    irrs = pd.read_csv(f"{BASE}/irrs_multi.csv")
    with open(f"{BASE}/modelo_stats_multi.json", encoding="utf-8") as f:
        stats_modelo = json.load(f)
    with open(f"{BASE}/sutran_alertas_historico.json", encoding="utf-8") as f:
        alertas_hist = json.load(f)
    return (events, sutran_events, ositran_events, tramos, puntos, irrs,
            stats_modelo, alertas_hist)


(events, sutran_events, ositran_events, tramos, puntos, irrs,
 stats_modelo, alertas_hist) = load()

css()
hero(len(events) + len(sutran_events) + len(ositran_events),
     sum(t["km1"] - t["km0"] for t in tramos), len(puntos))

with st.sidebar:
    st.markdown("## ⚙️ Filtros de análisis")
    st.caption("Aplican a Mapa, Puntos negros, Tendencias y Rutas críticas.")
    regiones = sorted({str(t["region"]) for t in tramos if t["region"] is not None
                       and not (isinstance(t["region"], float) and np.isnan(t["region"]))})
    sel_region = st.multiselect("Región geográfica", regiones, default=regiones)
    rutas_all = sorted({t["ruta"] for t in tramos})
    sel_rutas = st.multiselect("Rutas específicas", rutas_all, default=[], help="Vacío = todas")
    max_sin = max(t.get("siniestros_total_km", t.get("siniestros_km", 0)) for t in tramos)
    umbral = st.slider("Tramos con siniestros/km ≥", 0.0, round(max_sin, 1), 0.0, 0.1)
    deptos = sorted({str(d) for d in pd.concat([
        events.get("DEPARTAMENTO", pd.Series(dtype="object")),
        sutran_events.get("depto", pd.Series(dtype="object"))]).dropna().unique()})
    sel_depto = st.multiselect("Departamentos (eventos)", deptos, default=[])
    anios_all = sorted({int(a) for a in set(events["anio"].dropna())
                        | set(sutran_events.get("anio", pd.Series()).dropna())
                        | set(ositran_events["anio"].dropna()) if pd.notna(a)})
    sel_anios = st.multiselect("Años", anios_all, default=anios_all)
    fuentes_on = st.multiselect("Fuentes", ["ONSV", "SUTRAN", "OSITRAN"],
                                default=["ONSV", "SUTRAN", "OSITRAN"])
    st.caption("ONSV 2021-2025 · SUTRAN 2020-2021 · OSITRAN 2019-2025")

tramos_f = [t for t in tramos if t["region"] in sel_region
            and t.get("siniestros_total_km", t.get("siniestros_km", 0)) >= umbral]
if sel_rutas:
    tramos_f = [t for t in tramos_f if t["ruta"] in sel_rutas]

ev_data = {}
if "ONSV" in fuentes_on:
    ev = events.copy()
    if sel_depto and "DEPARTAMENTO" in ev.columns:
        ev = ev[ev["DEPARTAMENTO"].isin(sel_depto)]
    if sel_anios:
        ev = ev[ev["anio"].isin(sel_anios)]
    ev_data["ONSV"] = ev
if "SUTRAN" in fuentes_on:
    ev_s = sutran_events.copy()
    if sel_depto and "depto" in ev_s.columns:
        ev_s = ev_s[ev_s["depto"].isin(sel_depto)]
    if sel_anios:
        ev_s = ev_s[ev_s["anio"].isin(sel_anios)]
    ev_data["SUTRAN"] = ev_s
if "OSITRAN" in fuentes_on:
    ev_o = ositran_events.copy()
    if sel_anios:
        ev_o = ev_o[ev_o["anio"].isin(sel_anios)]
    ev_data["OSITRAN"] = ev_o

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["🧭 Viaja seguro", "📣 Reporta un incidente", "🗺️ Mapa nacional", "⚠️ Puntos negros",
     "📈 Tendencias", "🏆 Rutas críticas", "📊 Modelo"])

import analitica
import modelo_tab
import reporta
import viaja_seguro

with tab1:
    viaja_seguro.render()

with tab2:
    reporta.render()

with tab3:
    analitica.tab_mapa(tramos_f, puntos, alertas_hist)

with tab4:
    analitica.tab_puntos(puntos)

with tab5:
    analitica.tab_tendencias(ev_data)

with tab6:
    modelo_tab.tab_rutas_criticas(ev_data)

with tab7:
    modelo_tab.tab_modelo(irrs, stats_modelo, tramos_f, sel_rutas)
