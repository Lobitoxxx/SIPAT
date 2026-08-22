"""Pestaña «Viaja seguro»: el producto principal de SIPAT."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from theme import AMBAR, INDIGO, MORADO, ROJO, VERDE, banner, card, estilo_plotly, nivel_riesgo, pill

RUTAS_POPULARES = [
    ("Lima → Huancayo", "Lima", "Huancayo"),
    ("Lima → Cusco", "Lima", "Cusco"),
    ("Lima → Trujillo", "Lima", "Trujillo"),
    ("Lima → Arequipa", "Lima", "Arequipa"),
    ("Trujillo → Chiclayo", "Trujillo", "Chiclayo"),
    ("Arequipa → Puno", "Arequipa", "Puno"),
]


@st.cache_data(show_spinner=False)
def analizar_ruta(ori, dest, salida):
    from ruta_segura import analizar
    return analizar(ori, dest, salida=salida)


def _set_pop():
    nombre = st.session_state.get("pop")
    for n, o, d in RUTAS_POPULARES:
        if n == nombre:
            st.session_state["in_origen"] = o
            st.session_state["in_destino"] = d


def render(res_global=None):
    st.markdown("### Planifica tu viaje en 10 segundos")
    st.caption("Elige origen y destino (o una ruta popular). Antes de salir verás cada accidente "
               "ocurrido en la ruta, el riesgo histórico y previsto por IA, el clima y las alertas.")

    st.pills("🚏 Rutas populares", [r[0] for r in RUTAS_POPULARES], key="pop", on_change=_set_pop)

    c_o, c_d, c_f, c_h, c_b = st.columns([2.3, 2.3, 1.25, 1.0, 1.25])
    origen = c_o.text_input("📍 Origen", value="Lima", key="in_origen")
    destino = c_d.text_input("🏁 Destino", value="Huancayo", key="in_destino")
    fecha = c_f.date_input("📅 Fecha de salida", value=datetime.now().date(), key="in_fecha")
    hora = c_h.time_input("⏰ Hora", value=datetime.now().time().replace(minute=0, second=0,
                                                                        microsecond=0), key="in_hora")
    calc = c_b.button("🔎 Analizar mi ruta", type="primary", width='stretch')
    salida = f"{fecha:%Y-%m-%d} {hora:%H:%M}"

    res = st.session_state.get("ruta_res")
    if calc:
        with st.spinner("Geocodificando · calculando rutas alternativas · cruzando 51 mil "
                        "accidentes · prediciendo riesgo · consultando clima…"):
            try:
                res = analizar_ruta(origen.strip(), destino.strip(), salida)
                st.session_state["ruta_res"] = res
                st.session_state.pop("reporte_bytes", None)
            except Exception as e:
                st.error(f"No se pudo calcular la ruta: {e}")
                res = None

    if res is None:
        st.markdown("""<div class="banner-warn">👋 <b>Escribe tu origen y destino y pulsa
        «Analizar mi ruta»</b>. En unos segundos tendrás el mapa de tu viaje con cada accidente
        ocurrido, los tramos peligrosos y qué puede pasar.</div>""", unsafe_allow_html=True)
        return

    r0 = res["rutas"][0]
    pr0 = r0.get("prediccion") or {}
    n_hist, _ = nivel_riesgo(r0["score_km_penalizado"], 4.0, 8.0)
    n_pred, _ = nivel_riesgo(pr0.get("pred_siniestros_km", 0), 0.5, 1.2)
    rk = res["ranking"]
    ri = rk["segura"][0] if rk["segura"] else 0
    ti = r0.get("tipos_incidente") or {}
    geo0 = r0.get("geometry")

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        h = int(r0["duration_min"] // 60)
        mnt = int(r0["duration_min"] % 60)
        st.markdown(card("🕰️", f'{r0["distance_km"]:.0f} km', "Distancia del viaje",
                         f"≈ {h}h {mnt:02d} min"), unsafe_allow_html=True)
    with k2:
        st.markdown(card("📚", n_hist, "Riesgo histórico",
                         f'score {r0["score_km_penalizado"]} sini/km',
                         {"Bajo": VERDE, "Medio": AMBAR, "Alto": ROJO}[n_hist]), unsafe_allow_html=True)
    with k3:
        st.markdown(card("🔮", n_pred, "Riesgo previsto (IA)",
                         f'{pr0.get("pred_siniestros_km", 0)} sini/km esperados',
                         {"Bajo": VERDE, "Medio": AMBAR, "Alto": ROJO}[n_pred]), unsafe_allow_html=True)
    with k4:
        rapida = rk["rapida"][0] if rk["rapida"] else 0
        st.markdown(card("🛟", f"R{ri}", "Tu ruta más segura",
                         f"vs R{rapida} que es la más rápida", VERDE), unsafe_allow_html=True)
    with k5:
        st.markdown(card("⚠️", f"{ti.get('total', 0):,}", "Accidentes en esta ruta",
                         f"{ti.get('fallecidos', 0)} fallecidos · {ti.get('heridos', 0)} heridos",
                         ROJO), unsafe_allow_html=True)

    st.markdown(banner(n_hist,
                       f"<b>Riesgo histórico de tu ruta {pill(n_hist)}</b> &nbsp;·&nbsp; "
                       f"score {r0['score_km_penalizado']} sini/km (accidentes pasados + alertas + tráfico) "
                       f"&nbsp;·&nbsp; riesgo previsto {pill(n_pred)} &nbsp;·&nbsp; "
                       f"factor horario ×{res['factor_temporal']}"), unsafe_allow_html=True)

    st.markdown("#### 🗺️ Tu ruta, punto por punto")
    st.caption("Cada punto es un accidente real — clic para ver fecha, tipo, causa y clima. "
               "La línea va de verde (tranquilo) a rojo (peligroso).")
    try:
        from ruta_segura import mapa as mapa_ruta
        mapa_ruta(res, "dashboard/_map_ruta.html")
        st.iframe(src=Path("dashboard/_map_ruta.html"), height=640)
    except Exception as e:
        st.warning(f"No se pudo renderizar el mapa: {e}")

    cp, ct = st.columns([1.05, 1])
    with cp:
        st.markdown("**📶 ¿Dónde está lo peligroso?** Perfil km a km")
        figp = go.Figure()
        colores_r = [INDIGO, ROJO, VERDE, AMBAR]
        for i, r in enumerate(res["rutas"]):
            p = r.get("perfil") or []
            if not p:
                continue
            xs = [(s["km0"] + s["km1"]) / 2 for s in p]
            figp.add_trace(go.Scatter(
                x=xs, y=[s["score_km"] for s in p], mode="lines",
                name=("Tu ruta ⭐" if i == ri else f"Alternativa R{i}"),
                line=dict(color=(VERDE if i == ri else colores_r[i % 4]),
                          width=3.2 if i == ri else 1.8)))
            seg = (r.get("prediccion") or {}).get("segmentos") or []
            if seg and i == ri:
                figp.add_trace(go.Scatter(
                    x=[(s["km0"] + s["km1"]) / 2 for s in seg],
                    y=[s["pred_siniestros_km"] for s in seg], mode="lines",
                    name="Previsto (IA)", line=dict(color=MORADO, width=1.6, dash="dot"),
                    yaxis="y2"))
        figp.update_layout(xaxis_title="Kilómetro del viaje", yaxis_title="Riesgo histórico /km",
                           yaxis2=dict(title="Previsto", overlaying="y", side="right"))
        st.plotly_chart(estilo_plotly(figp, 400), width='stretch')

    with ct:
        st.markdown("**❓ ¿Qué puede pasar?** Histórico real de esta ruta")
        if ti.get("total"):
            b1, b2, b3 = st.columns(3)
            b1.metric("Accidentes", f"{ti['total']:,}")
            b2.metric("Fallecidos", f"{ti['fallecidos']:,}")
            b3.metric("Heridos", f"{ti['heridos']:,}")
            df_ti = pd.DataFrame(ti.get("top_tipos", []))
            if len(df_ti):
                st.dataframe(df_ti.rename(columns={"valor": "Tipo más frecuente", "n": "N",
                                                   "pct": "%"}).head(6),
                             width='stretch', hide_index=True)
        else:
            st.info("Sin accidentes históricos registrados cerca de la ruta ✅")

    st.markdown("#### 🌦️ Clima, avisos y emergencias para tu salida")
    force_clima = st.button("🔄 Actualizar ahora", key="force_clima")
    if geo0:
        cc1, cc2, cc3 = st.columns(3)
        from clima import (avisos_en_ruta, avisos_senamhi, emergencias_coen,
                           emergencias_en_ruta, pronostico_openmeteo)
        with cc1:
            st.markdown("**Pronóstico del trayecto**")
            try:
                pr = pronostico_openmeteo(geo0, force=force_clima)
                if pr:
                    st.success(f"🌡️ {pr['tmin_c']} – {pr['tmax_c']} °C\n\n"
                               f"🌧️ Lluvia {pr['precip_prob_max']}% · 💨 viento {pr['viento_max_kmh']} km/h\n\n"
                               f"📅 {pr['fecha']}")
                else:
                    st.caption("No disponible.")
            except Exception:
                st.caption("No disponible.")
        with cc2:
            st.markdown("**Avisos SENAMHI en tu ruta**")
            try:
                av = avisos_en_ruta(avisos_senamhi(force=force_clima), geo0)
                if av:
                    for a in av[:4]:
                        st.warning(f"**{a['nivel']}** · {a['fecha']}")
                else:
                    st.success("Ninguno en el trayecto ✅")
            except Exception:
                st.caption("No disponibles.")
        with cc3:
            st.markdown("**Emergencias activas cerca (COEN)**")
            try:
                ems = emergencias_en_ruta(emergencias_coen(force=force_clima), geo0)
                if ems:
                    for e in ems[:4]:
                        st.error(f"**{e['tipo']}** · {e['lugar']} · a {e['dist_km']} km")
                else:
                    st.success("Ninguna en los últimos 7 días ✅")
            except Exception:
                st.caption("No disponibles.")

    from reportes_ciudadanos import listar_reportes, reportes_en_ruta
    rep_todos = listar_reportes(dias=60)
    rep_ruta = reportes_en_ruta(rep_todos or [], geo0, radio_km=10)
    st.markdown("#### 👥 Lo que reportan otros viajeros cerca de tu ruta")
    if rep_ruta:
        for rp in rep_ruta[:6]:
            st.markdown(f"- **{rp['tipo']}** ({rp['severidad']}) a {rp['dist_km']} km · "
                        f"{rp['descripcion'][:90]} · _{str(rp['ts'])[:16]}_")
    else:
        st.caption("Aún no hay reportes ciudadanos cerca de esta ruta.")

    with st.expander("📋 Comparación detallada de rutas alternativas"):
        rows = []
        for i, r in enumerate(res["rutas"]):
            rows.append({
                "Ruta": ("⭐ " if i == ri else "") + f"R{i}",
                "km": round(r["distance_km"], 1),
                "horas": round(r["duration_min"] / 60, 1),
                "Score /km": round(r["score_km_penalizado"], 2),
                "ONSV": r["riesgo"]["accidentes_onsv"],
                "SUTRAN": r["riesgo"]["accidentes_sutran"],
                "OSITRAN": r["riesgo"]["accidentes_ositran"],
                "Alertas hist.": r["riesgo"]["alertas_hist_buffer"],
                "En vivo": len(r["alertas_en_vivo"]),
                "Peajes": r["riesgo"]["peajes_buffer"],
                "Predicción /km": round((r.get("prediccion") or {}).get("pred_siniestros_km", 0), 2)})
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    al_rows = []
    for i, r in enumerate(res["rutas"]):
        for a in r["alertas_en_vivo"]:
            al_rows.append({"ruta": f"R{i}", "estado": a["estado"], "motivo": a["motivo"],
                            "km": a["km"], "dist_km": a["dist_km"], "evento": a.get("evento", "")})
    if al_rows:
        st.markdown("#### 📢 Alertas SUTRAN en vivo (±2 km del trayecto)")
        estados = sorted({a["estado"] for a in al_rows})
        filtro = st.multiselect("Estado", estados, default=estados, key="filtro_al")
        st.dataframe(pd.DataFrame([a for a in al_rows if a["estado"] in filtro]),
                     width='stretch', hide_index=True)

    st.markdown("#### 📄 Lleva tu reporte de viaje")
    rb1, rb2, _rb3 = st.columns([1, 1, 2])
    with rb1:
        if st.button("🧾 Generar reporte HTML", key="btn_reporte"):
            with st.spinner("Armando el reporte…"):
                try:
                    from reporte_ruta import reporte_desde_resumen
                    ruta_html = reporte_desde_resumen(res, "data/processed/dashboard/reporte_ruta.html")
                    st.session_state["reporte_bytes"] = ruta_html.read_bytes()
                    st.session_state["reporte_nombre"] = f"reporte_sipat_{res['salida'] or 'viaje'}.html"
                except Exception as e:
                    st.error(f"No se pudo generar: {e}")
    with rb2:
        if "reporte_bytes" in st.session_state:
            st.download_button("⬇️ Descargar reporte", st.session_state["reporte_bytes"],
                               file_name=st.session_state.get("reporte_nombre", "reporte_sipat.html"),
                               mime="text/html", type="primary")
