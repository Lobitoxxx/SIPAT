"""Pestañas Rutas críticas y Modelo NegBin."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from theme import INDIGO, MORADO, PALETA, ROJO, estilo_plotly


def tab_rutas_criticas(ev_data):
    st.markdown("### 🏆 ¿Dónde se concentra el peligro?")
    df_all = []
    if "ONSV" in ev_data and len(ev_data["ONSV"]):
        e = ev_data["ONSV"].copy()
        e["fuente"] = "ONSV"
        df_all.append(e.rename(columns={"fallecidos": "fal"}))
    if "SUTRAN" in ev_data and len(ev_data["SUTRAN"]):
        e = ev_data["SUTRAN"].copy()
        e["fuente"] = "SUTRAN"
        df_all.append(e)
    if "OSITRAN" in ev_data and len(ev_data["OSITRAN"]):
        e = ev_data["OSITRAN"].copy()
        e["fuente"] = "OSITRAN"
        e["fal"] = 0
        df_all.append(e)
    if not df_all:
        st.warning("No hay eventos para los filtros seleccionados.")
        return
    df_ev = pd.concat(df_all, ignore_index=True)

    c1, c2 = st.columns(2)
    with c1:
        g_r = df_ev.groupby(["ruta", "fuente"]).size().unstack(fill_value=0)
        for col in ["ONSV", "SUTRAN", "OSITRAN"]:
            if col not in g_r.columns:
                g_r[col] = 0
        g_r["Total"] = g_r[["ONSV", "SUTRAN", "OSITRAN"]].sum(axis=1)
        g_r = g_r.sort_values("Total", ascending=True).head(15).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=g_r["ONSV"], y=g_r["ruta"], name="ONSV", marker_color=ROJO,
                             orientation="h"))
        fig.add_trace(go.Bar(x=g_r["SUTRAN"], y=g_r["ruta"], name="SUTRAN", marker_color="#f59e0b",
                             orientation="h"))
        fig.add_trace(go.Bar(x=g_r["OSITRAN"], y=g_r["ruta"], name="OSITRAN", marker_color=INDIGO,
                             orientation="h"))
        fig.update_layout(barmode="group", xaxis_title="Siniestros", title="Top 15 rutas críticas")
        st.plotly_chart(estilo_plotly(fig, 460), width='stretch')
    with c2:
        dept_col = ("depto" if "depto" in df_ev.columns
                    else "DEPARTAMENTO" if "DEPARTAMENTO" in df_ev.columns else None)
        if dept_col:
            g = (df_ev.groupby(dept_col)["fal"].sum().sort_values(ascending=False).head(15))
            fig2 = px.bar(x=g.values[::-1], y=[str(i) for i in g.index[::-1]], orientation="h",
                          color_discrete_sequence=[MORADO], title="Top 15 departamentos (fallecidos)")
            fig2.update_layout(xaxis_title="Fallecidos")
            st.plotly_chart(estilo_plotly(fig2, 460), width='stretch')

    c3, c4 = st.columns(2)
    with c3:
        tipo_map = {"ONSV": "CLASE SINIESTRO", "SUTRAN": "modalidad", "OSITRAN": "tipo"}
        tipos = []
        for fuente, col in tipo_map.items():
            if fuente in ev_data and col in ev_data[fuente].columns:
                for k, v in ev_data[fuente][col].value_counts().head(8).items():
                    tipos.append({"Tipo": str(k), "N": v, "Fuente": fuente})
        if tipos:
            df_t = pd.DataFrame(tipos).sort_values("N", ascending=True)
            fig3 = px.bar(x=df_t["N"], y=df_t["Tipo"], orientation="h", color=df_t["Fuente"],
                          color_discrete_sequence=PALETA,
                          title="Tipos de siniestro más frecuentes")
            st.plotly_chart(estilo_plotly(fig3, 430), width='stretch')
    with c4:
        causas = []
        if "ONSV" in ev_data and "CAUSA FACTOR PRINCIPAL" in ev_data["ONSV"].columns:
            for k, v in ev_data["ONSV"]["CAUSA FACTOR PRINCIPAL"].value_counts().head(6).items():
                causas.append({"Causa": str(k), "N": v})
        if "OSITRAN" in ev_data and "causa" in ev_data["OSITRAN"].columns:
            for k, v in ev_data["OSITRAN"]["causa"].value_counts().head(6).items():
                causas.append({"Causa": str(k), "N": v})
        if causas:
            df_c = pd.DataFrame(causas).sort_values("N", ascending=True)
            fig4 = px.bar(x=df_c["N"], y=df_c["Causa"], orientation="h", color_discrete_sequence=[ROJO],
                          title="Causas principales")
            st.plotly_chart(estilo_plotly(fig4, 430), width='stretch')


def tab_modelo(irrs, stats_modelo, tramos_f, sel_rutas):
    st.markdown("### 📊 Modelo estadístico NegBin — factores de riesgo (IRR)")
    st.caption("IRR > 1 aumenta el riesgo de siniestros; IRR < 1 lo reduce. "
               "Rojo = significativo (p<0.05). Cambia la fuente para ver ONSV, SUTRAN o combinado.")
    c1, c2 = st.columns([1.05, 1])
    with c1:
        fuente_sel = st.segmented_control("Fuente del modelo", ["ONSV", "SUTRAN", "COMBINADO"],
                                          selection_mode="single", default="COMBINADO") or "COMBINADO"
        ir_f = irrs[irrs["fuente"] == fuente_sel].sort_values("irr", ascending=False)
        fig = go.Figure()
        fig.add_vline(x=1, line_dash="dash", line_color="gray")
        for _, r in ir_f.iterrows():
            col = ROJO if r["p"] < 0.05 else "#94a3b8"
            fig.add_trace(go.Bar(
                x=[r["irr"]], y=[r["label"]], orientation="h", marker_color=col,
                error_x=dict(type="data", symmetric=False,
                             array=[r["irr_high"] - r["irr"]],
                             arrayminus=[r["irr"] - r["irr_low"]]),
                text=[f"{r['irr']:.2f}"], textposition="outside"))
        st_m = stats_modelo.get(fuente_sel.lower(), {})
        fig.update_layout(xaxis_type="log", xaxis_title="IRR (escala log)",
                          title=f"Rojo = p<0.05 · {fuente_sel}: "
                                f"{st_m.get('n_tramos', '?')} tramos · "
                                f"{st_m.get('n_accidentes', '?')} siniestros")
        fig.update_xaxes(range=[np.log10(0.2), np.log10(6)])
        st.plotly_chart(estilo_plotly(fig, 520), width='stretch')
    with c2:
        st.markdown("**🔎 Explorador de tramos**")
        cols_sel = st.multiselect(
            "Columnas",
            ["ruta", "km0", "km1", "region", "topografia", "superficie", "onsv_n", "sutran_n",
             "ositran_n", "siniestros_total", "fallecidos_total", "siniestros_total_km",
             "vel_proy", "carriles", "sinuosidad", "alertas_hist_n", "es_panamericana"],
            default=["ruta", "km0", "km1", "region", "siniestros_total", "siniestros_total_km",
                     "vel_proy"])
        cols_sel = [c for c in cols_sel if tramos_f and c in tramos_f[0]]
        if cols_sel:
            df_t = pd.DataFrame([{k: t.get(k) for k in cols_sel} for t in tramos_f])
            if "ruta" in cols_sel and sel_rutas:
                df_t = df_t[df_t["ruta"].isin(sel_rutas)]
            sort_col = ("siniestros_total_km" if "siniestros_total_km" in cols_sel else cols_sel[0])
            df_t = df_t.sort_values(sort_col, ascending=False)
            st.dataframe(df_t.head(500), width='stretch', hide_index=True)
            st.download_button("⬇️ Descargar tramos (CSV)", df_t.to_csv(index=False).encode("utf-8-sig"),
                               file_name="tramos.csv", mime="text/csv")
