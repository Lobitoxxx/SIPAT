"""Pestañas analíticas: Mapa nacional, Puntos negros y Tendencias."""

from pathlib import Path

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from theme import AZUL, PALETA, ROJO, VERDE, estilo_plotly

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _color_ramp(v):
    v = min(v / 2.0, 1.0)
    if v <= 0.2:
        return "#fde68a"
    if v <= 0.4:
        return "#fbbf24"
    if v <= 0.6:
        return "#f97316"
    if v <= 0.8:
        return "#ef4444"
    return "#991b1b"


def tab_mapa(tramos_f, puntos, alertas_hist):
    st.markdown("### 🗺️ Red vial nacional según siniestros")
    st.caption("Gris = sin siniestros → amarillo → rojo (más peligroso). "
               "Activa las capas para ver puntos negros y alertas SUTRAN.")
    m = folium.Map(location=[-11.5, -74.5], zoom_start=5, tiles="CartoDB positron", prefer_canvas=True)
    fg_tramos = folium.FeatureGroup(name="Tramos con siniestros")
    fg_puntos = folium.FeatureGroup(name="Puntos negros")
    fg_alertas = folium.FeatureGroup(name="Alertas históricas SUTRAN")

    for t in tramos_f:
        sini = t.get("siniestros_total", t.get("onsv_n", 0))
        if sini <= 0:
            continue
        col = _color_ramp(t.get("siniestros_total_km", t.get("siniestros_km", 0)))
        popup_html = (f"<b>{t['ruta']} km {t['km0']:.1f}-{t['km1']:.1f}</b> ({t['region']})<br>"
                      f"{sini} siniestros | {t.get('fallecidos_total', 0)} fallecidos | "
                      f"{t.get('siniestros_total_km', t.get('siniestros_km', 0)):.2f} sini/km<br>"
                      f"ONSV: {t.get('onsv_n', 0)} | SUTRAN: {t.get('sutran_n', 0)} | "
                      f"OSITRAN: {t.get('ositran_n', 0)}")
        folium.PolyLine(t["coords"], color=col, weight=2.5, opacity=.85,
                        popup=folium.Popup(popup_html, max_width=300)).add_to(fg_tramos)

    for p in puntos:
        exceso = p.get("exceso_eb", p.get("residual", 0))
        exceso = exceso if isinstance(exceso, (int, float)) else 0
        folium.CircleMarker([p["lat"], p["lon"]], radius=6 + min(exceso, 3), color="black",
                            fill=True, fill_color="red", fill_opacity=.85,
                            popup=folium.Popup(
                                f"<b>PUNTO NEGRO</b><br>{p['ruta']} km {p['km0']}-{p['km1']}<br>"
                                f"{p.get('siniestros', 0)} siniestros | exceso {exceso:.2f}<br>"
                                f"ONSV:{p.get('onsv_n', 0)} SUTRAN:{p.get('sutran_n', 0)} "
                                f"OSITRAN:{p.get('ositran_n', 0)}<br>"
                                f"Fuente dominante: {p.get('fuente_dominante', '?')}",
                                max_width=300),
                            tooltip=f"PN {p['ruta']} km {p['km0']:.0f}").add_to(fg_puntos)

    for a in alertas_hist:
        if "lat" in a and "lon" in a:
            color = {"INTERRUMPIDO": "#dc2626", "RESTRINGIDO": "#d97706"}.get(a["estado"], "#888")
            folium.CircleMarker([float(a["lat"]), float(a["lon"])], radius=5, color=color,
                                fill=True, fill_color=color, fill_opacity=.7,
                                tooltip=f"{a['estado']} | {a['fecha_evento']} | {a['motivo']}").add_to(fg_alertas)

    fg_tramos.add_to(m)
    fg_puntos.add_to(m)
    fg_alertas.add_to(m)
    folium.TileLayer(tiles="OpenStreetMap", name="OSM").add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    with open("dashboard/_map_siniestros.html", "w", encoding="utf-8") as f:
        f.write(m._repr_html_())
    st.iframe(src=Path("dashboard/_map_siniestros.html"), height=640)


def tab_puntos(puntos):
    st.markdown("### ⚠️ Puntos negros del país")
    st.caption("Tramos con exceso de siniestros detectado por Empirical Bayes (Hauer), "
               "percentil 95 regional y residuos del modelo.")
    cm1, cm2 = st.columns(2)
    with cm1:
        m2 = folium.Map(location=[-9.5, -76.5], zoom_start=5, tiles="CartoDB positron")
        color_map = {"ONSV": "#7c3aed", "SUTRAN": "#f97316", "OSITRAN": "#0d9488"}
        for p in puntos:
            col = color_map.get(p.get("fuente_dominante", "ONSV"), "#dc2626")
            folium.CircleMarker([p["lat"], p["lon"]], radius=6 + min(p.get("exceso_eb", 0), 3),
                                color="black", fill=True, fill_color=col, fill_opacity=.85,
                                popup=folium.Popup(
                                    f"<b>{p['ruta']} km {p['km0']:.0f}-{p['km1']:.0f}</b><br>"
                                    f"{p.get('siniestros', 0)} siniestros | exceso EB {p.get('exceso_eb', '?')}<br>"
                                    f"ONSV:{p.get('onsv_n', 0)} SUTRAN:{p.get('sutran_n', 0)} "
                                    f"OSITRAN:{p.get('ositran_n', 0)}",
                                    max_width=300),
                                tooltip=f"{p['ruta']} km {p['km0']:.0f} ({p.get('siniestros', 0)})").add_to(m2)
        with open("dashboard/_map_puntos.html", "w", encoding="utf-8") as f:
            f.write(m2._repr_html_())
        st.iframe(src=Path("dashboard/_map_puntos.html"), height=560)
    with cm2:
        df_pn = pd.DataFrame(puntos).sort_values("exceso_eb", ascending=False)
        cols_show = [c for c in ["ruta", "km0", "km1", "region", "siniestros", "fallecidos_total",
                                 "exceso_eb", "fuente_dominante"] if c in df_pn.columns]
        st.dataframe(df_pn[cols_show].head(50), width='stretch', hide_index=True)
        st.download_button("⬇️ Descargar puntos negros (CSV)",
                           df_pn.to_csv(index=False).encode("utf-8-sig"),
                           file_name="puntos_negros.csv", mime="text/csv")


def tab_tendencias(ev_data):
    st.markdown("### 📈 Tendencias de siniestralidad")
    df_all = []
    if "ONSV" in ev_data and len(ev_data["ONSV"]):
        e = ev_data["ONSV"].copy()
        e["fuente"] = "ONSV"
        df_all.append(e.rename(columns={"CANTIDAD DE LESIONADOS": "les"}))
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
    df_ev = df_ev[df_ev.get("fal", pd.Series(0, index=df_ev.index)).notna()]

    c1, c2 = st.columns(2)
    with c1:
        g = df_ev.groupby(["anio", "fuente"]).size().unstack(fill_value=0).sort_index()
        fig = px.bar(g, barmode="group", color_discrete_sequence=PALETA,
                     title="Siniestros por año y fuente")
        st.plotly_chart(estilo_plotly(fig), width='stretch')
    with c2:
        g2 = (df_ev[df_ev["anio"] < 2026].groupby(["mes", "fuente"]).size()
              .unstack(fill_value=0).sort_index())
        fig2 = px.line(g2, markers=True, color_discrete_sequence=PALETA,
                       title="Siniestros por mes (2019-2025)")
        fig2.update_layout(xaxis_title="Mes")
        st.plotly_chart(estilo_plotly(fig2), width='stretch')

    c3, c4 = st.columns(2)
    with c3:
        dow_col = "dia_semana" if "dia_semana" in df_ev.columns else "DIA_SEMANA"
        dow = (df_ev.groupby([dow_col, "fuente"]).size().unstack(fill_value=0)
               .reindex(range(7), fill_value=0))
        cols_d = [c for c in ["ONSV", "SUTRAN", "OSITRAN"] if c in dow.columns]
        if cols_d:
            fig3 = px.bar(x=DIAS, y=[dow[c].values for c in cols_d], barmode="group",
                          color_discrete_sequence=PALETA[:len(cols_d)],
                          title="¿Qué día hay más siniestros?")
            st.plotly_chart(estilo_plotly(fig3), width='stretch')
    with c4:
        if "hora3" in df_ev.columns:
            h = df_ev.groupby(["hora3", "fuente"]).size().unstack(fill_value=0)
            h_cols = [c for c in ["ONSV", "SUTRAN", "OSITRAN"] if c in h.columns]
            if h_cols:
                fig4 = px.line(x=[f"{int(x):02d}:00" for x in h.index],
                               y=[h[c].values for c in h_cols], markers=True,
                               color_discrete_sequence=PALETA[:len(h_cols)],
                               title="¿A qué hora hay más siniestros?")
                fig4.update_layout(xaxis_title="Hora")
                st.plotly_chart(estilo_plotly(fig4), width='stretch')

    g = df_ev.groupby(["anio", "fuente"]).agg(fal=("fal", "sum"), n=("fecha", "size")).reset_index()
    g["gravedad"] = g["fal"] / g["n"].replace(0, 1)
    fig5 = px.line(g, x="anio", y="gravedad", color="fuente", markers=True,
                   color_discrete_sequence=PALETA,
                   title="Gravedad: fallecidos por siniestro")
    st.plotly_chart(estilo_plotly(fig5), width='stretch')
