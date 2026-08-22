"""Pestaña «Reporta un incidente»: reportes ciudadanos con foto y contexto."""

from pathlib import Path

import folium
import streamlit as st

from theme import VERDE

TIPOS_REPORTE = {
    "💥 Accidente": "Accidente",
    "🚗 Congestión": "Congestión / cola",
    "🚧 Obra vial": "Obra vial",
    "⛰️ Derrumbe / piedra": "Derrumbe / piedra",
    "🌧️ Inundación / lluvia": "Inundación / lluvia",
    "🐄 Animal en la vía": "Animal en la vía",
    "⛔ Vía interrumpida": "Vía interrumpida",
    "⚠️ Otro peligro": "Otro peligro",
}
SEVERIDADES = ["Leve", "Moderado", "Grave"]


def foto_b64(nombre):
    p = Path("data/processed/dashboard/reportes_fotos") / nombre
    if not nombre or not p.exists():
        return ""
    import base64
    data = base64.b64encode(p.read_bytes()).decode()
    mime = "image/png" if str(nombre).endswith(".png") else "image/jpeg"
    return f'<img src="data:{mime};base64,{data}" style="max-width:220px;border-radius:8px;margin-top:6px">'


def mapa_reportes(reps, out_path="dashboard/_map_reportes.html"):
    m = folium.Map(location=[-9.8, -75.5], zoom_start=5, tiles="CartoDB voyager")
    for r in reps[:300]:
        sev = r.get("severidad", "")
        color_hex = {"Grave": "#dc2626", "Moderado": "#d97706", "Leve": "#059669"}.get(sev, "#64748b")
        html = (f"<b>{r.get('tipo', '?')}</b> · {sev}<br>{r.get('descripcion', '')}<br>"
                f"<small>👤 {r.get('autor', 'Anónimo')} · 🕒 {str(r.get('ts', ''))[:16]}"
                + (f" · 📍 {r['ref']}" if r.get("ref") else "") + "</small>"
                + foto_b64(r.get("foto", "")))
        folium.Marker(
            [r["lat"], r["lon"]],
            icon=folium.DivIcon(html=(
                f'<div style="background:{color_hex};color:white;border-radius:50%;'
                f'width:26px;height:26px;text-align:center;line-height:26px;font-size:13px;'
                f'box-shadow:0 2px 6px rgba(0,0,0,.35);font-weight:700">!</div>')),
            popup=folium.Popup(html, max_width=280),
            tooltip=f"{r.get('tipo', '?')} ({sev})").add_to(m)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(m._repr_html_())
    return Path(out_path)


def _ubicacion_actual():
    """Devuelve (lat, lon) según la ruta calculada o None."""
    from reportes_ciudadanos import punto_en_km
    res = st.session_state.get("ruta_res")
    if not res:
        return None
    r0 = res["rutas"][0]
    geo = r0.get("geometry")
    km_total = r0["distance_km"]
    if not geo:
        return None
    km = st.slider("📍 Kilómetro de tu ruta donde estás", 0.0, round(float(km_total), 1), 0.0, 0.5,
                   help="Mueve el deslizador al punto aproximado del incidente")
    p = punto_en_km(geo, km, km_total)
    if p:
        st.caption(f"Ubicación: {p[0]:.4f}, {p[1]:.4f} (km {km:.0f} de la ruta)")
    return p


def render():
    from reportes_ciudadanos import agregar_reporte, estadisticas, listar_reportes

    st.markdown("### 📣 Ayuda a los demás viajeros")
    st.caption("¿Viste un accidente, un derrumbe o una congestión? Repórtalo con una foto en menos "
               "de un minuto. Tu reporte aparece en los mapas de quienes planean pasar por ahí.")

    est = estadisticas()
    s1, s2, s3, _s4 = st.columns(4)
    s1.metric("Reportes totales", est["total"])
    s2.metric("Hoy", est["hoy"])
    s3.metric("Con foto", est["con_foto"])

    cf, cm = st.columns([1.05, 1])

    with cf:
        with st.container(border=True):
            tipo_ui = st.selectbox("🚨 ¿Qué pasó?", list(TIPOS_REPORTE.keys()))
            severidad = st.radio("Nivel de gravedad", SEVERIDADES, horizontal=True,
                                 help="Leve = cuidado pero pasable · Grave = peligro serio")
            descripcion = st.text_area(
                "📝 Cuéntanos qué ves", height=80,
                placeholder="Ej: choque entre camión y auto, carril derecho bloqueado, tránsito lento…")
            foto_up = st.file_uploader("📸 Foto (opcional)", type=["jpg", "jpeg", "png"])
            autor = st.text_input("👤 Tu nombre (opcional)", placeholder="Anónimo")

            tiene_ruta = bool(st.session_state.get("ruta_res"))
            if tiene_ruta:
                modo = st.radio("📍 ¿Dónde?",
                                ["En un punto de mi ruta calculada",
                                 "Escribir referencia (distrito / peaje / km)"], index=0)
            else:
                modo = "Escribir referencia (distrito / peaje / km)"
                st.info("💡 Tip: si primero calculas tu ruta en «Viaja seguro», podrás ubicar el "
                        "incidente por kilómetro.")

            ref_txt = ""
            lat = lon = None
            if modo.startswith("En un punto"):
                p = _ubicacion_actual()
                if p:
                    lat, lon = p
            else:
                ref_txt = st.text_input("🏙️ Referencia del lugar",
                                        placeholder="Ej: peaje Pucusana, distrito de Chosica, km 45 PE-1S")

            enviar = st.button("✅ Enviar reporte", type="primary", width='stretch')

            if enviar:
                if lat is None and ref_txt.strip():
                    try:
                        from ruta_segura import geocode
                        lon, lat, nombre = geocode(ref_txt.strip())
                        st.caption(f"Lugar reconocido: {nombre}")
                    except Exception as e:
                        st.error(f"No se pudo ubicar «{ref_txt}»: {e}")
                if lat is None:
                    st.error("Indica dónde ocurrió: usa tu ruta calculada o escribe una referencia.")
                else:
                    ok, msg, _rep = agregar_reporte(
                        TIPOS_REPORTE[tipo_ui], descripcion, lat, lon,
                        foto=foto_up.getvalue() if foto_up else None,
                        autor=autor, severidad=severidad, ref=ref_txt)
                    if ok:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)

    with cm:
        reps = listar_reportes(dias=30) or []
        st.markdown(f"**🗺️ Reportes de los últimos 30 días** ({len(reps)})")
        if reps:
            mapa_reportes(reps)
            st.iframe(src=Path("dashboard/_map_reportes.html"), height=420)
            with st.expander("📃 Ver lista detallada"):
                for rp in reps[:15]:
                    icono = {"Grave": "🔴", "Moderado": "🟠", "Leve": f"🟢"}[rp.get("severidad", "")] \
                        if rp.get("severidad") in ("Grave", "Moderado", "Leve") else "⚪"
                    st.markdown(f"{icono} **{rp['tipo']}** · {str(rp['ts'])[:16]} · "
                                f"{rp['descripcion'][:100]}")
                    if rp.get("foto"):
                        fpath = Path("data/processed/dashboard/reportes_fotos") / rp["foto"]
                        if fpath.exists():
                            st.image(str(fpath), width=200)
        else:
            st.info("Aún no hay reportes. ¡Sé el primero en ayudar! 💪")
