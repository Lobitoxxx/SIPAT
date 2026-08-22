"""Reporte HTML estatico autónomo del módulo 'Ruta segura'.

Genera un documento autocontenido (mapa folium + grafico de perfil de riesgo
embebido en base64) para un par origen-destino.

Uso:
  python scripts/reporte_ruta.py "Lima" "Huancayo" --salida "2026-08-15 19:30"
  python scripts/reporte_ruta.py "Trujillo" "Chiclayo" --out out/reporte.html
"""

import argparse
import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ruta_segura import analizar, resumen_analisis, _popup_accidente
import folium

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f5f7fa; color: #222; }
.wrap { max-width: 1000px; margin: 0 auto; padding: 16px; }
header { background: linear-gradient(120deg, #1f3a5f, #2a5298); color: #fff; padding: 22px 28px; border-radius: 10px; }
header h1 { margin: 0 0 6px; font-size: 22px; }
header p { margin: 2px 0; opacity: .92; font-size: 13px; }
.cards { display: flex; gap: 14px; flex-wrap: wrap; margin: 18px 0; }
.card { flex: 1; min-width: 180px; background: #fff; border-radius: 10px; padding: 14px 18px;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); border-left: 5px solid #2a5298; }
.card b { font-size: 22px; display: block; }
.card span { font-size: 12px; color: #666; }
section { background: #fff; border-radius: 10px; padding: 16px 20px; margin: 14px 0; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border-bottom: 1px solid #e3e6ea; padding: 7px 9px; text-align: left; }
th { background: #f0f3f7; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; color: #fff; }
.b-green { background: #2e8b57; } .b-red { background: #c0392b; } .b-orange { background: #e67e22; }
.tag { font-size: 11px; color: #666; margin-top: 8px; }
iframe { width: 100%; height: 560px; border: 0; border-radius: 8px; }
footer { text-align: center; font-size: 12px; color: #888; margin: 20px 0; }
"""


def _chart_perfil(resumen):
    fig, ax = plt.subplots(figsize=(9, 3.2), dpi=110)
    colores = ["#2a5298", "#c0392b", "#2e8b57", "#e67e22"]
    for i, r in enumerate(resumen["rutas"]):
        p = r["perfil"]
        if not p:
            continue
        xs = [(s["km0"] + s["km1"]) / 2 for s in p]
        ys = [s["score_km"] for s in p]
        ax.plot(xs, ys, lw=2, label=f"R{i}", color=colores[i % 4])
    ax.set_xlabel("Kilometro del trayecto")
    ax.set_ylabel("Riesgo /km")
    ax.set_title("Perfil de riesgo a lo largo de la ruta")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _tabla_rutas(resumen):
    filas = []
    for i, r in enumerate(resumen["rutas"]):
        sc = r["riesgo"]
        tags = [k for k, ix in resumen["ranking"].items() if i in ix]
        filas.append(
            f"<tr><td><b>Ruta {i}</b></td><td>{r['distance_km']} km</td><td>{r['duration_min']:.0f} min</td>"
            f"<td>{r['score_km_penalizado']}</td><td>{sc['accidentes_onsv']} / {sc['accidentes_sutran']} / {sc['accidentes_ositran']}</td>"
            f"<td>{sc['alertas_hist_buffer']}</td><td>{len(r['alertas_en_vivo'])}</td>"
            f"<td>{sc['trafico_km']} ({sc['peajes_buffer']} peajes, AADT {sc['aadt_max']})</td>"
            f"<td>{' '.join(f'<span class=\"badge b-green\">{t}</span>' for t in tags)}</td></tr>")
    return ("<table><tr><th>Ruta</th><th>Distancia</th><th>Duracion</th><th>Score (penalizado)</th>"
            "<th>Acc. ONSV/SUTRAN/OSITRAN</th><th>Alertas historicas</th><th>Alertas en vivo</th>"
            "<th>Trafico (peajes/AADT)</th><th>Ranking</th></tr>"
            + "".join(filas) + "</table>")


def _mapa_html(resumen):
    o = resumen["origen"]
    d = resumen["destino"]
    geo = resumen["rutas"][0].get("geometry")
    lat0 = (o["lat"] + d["lat"]) / 2
    lon0 = (o["lon"] + d["lon"]) / 2
    m = folium.Map(location=[lat0, lon0], zoom_start=8, tiles="CartoDB positron")
    folium.Marker([o["lat"], o["lon"]], popup="Origen", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([d["lat"], d["lon"]], popup="Destino", icon=folium.Icon(color="red")).add_to(m)
    colores = {0: "#2a5298", 1: "#c0392b", 2: "#2e8b57", 3: "#e67e22"}
    vmax = max((r["score_km_penalizado"] for r in resumen["rutas"]), default=1.0)
    for i, r in enumerate(resumen["rutas"]):
        g = r.get("geometry") or geo
        if not g:
            continue
        pts = [(p[1], p[0]) for p in g]
        c = colores.get(i, "#444")
        folium.PolyLine(pts, color=c, weight=5, opacity=0.9,
                        popup=f"Ruta {i}: {r['distance_km']} km, {r['duration_min']:.0f} min, score {r['score_km_penalizado']}").add_to(m)
    g_hist = folium.FeatureGroup(name="Accidentes historicos")
    cf = {"ONSV": "purple", "SUTRAN": "orange", "OSITRAN": "teal"}
    for r in resumen["rutas"]:
        for a in r["accidentes_hist"]:
            folium.CircleMarker([a["lat"], a["lon"]], radius=3, color=cf.get(a["fuente"], "blue"),
                                fill=True, fill_opacity=0.85,
                                popup=folium.Popup(_popup_accidente(a), max_width=340)).add_to(g_hist)
    g_hist.add_to(m)
    g_live = folium.FeatureGroup(name="Alertas SUTRAN en vivo")
    for r in resumen["rutas"]:
        for a in r["alertas_en_vivo"]:
            folium.Marker([a["lat"], a["lon"]], icon=folium.Icon(color="darkred", icon="info-sign"),
                          popup=f"<b>{a['estado']}</b><br>{a['evento']}<br>{a['ubigeo']}").add_to(g_live)
    g_live.add_to(m)
    folium.LayerControl().add_to(m)
    return m.get_root().render()


def _alertas_html(resumen):
    filas = []
    for i, r in enumerate(resumen["rutas"]):
        for a in r["alertas_en_vivo"]:
            filas.append(f"<tr><td>R{i}</td><td>{a['estado']}</td><td>{a['motivo']}</td>"
                         f"<td>KM {a['km']}</td><td>{a['ubigeo']}</td><td>{a['dist_km']} km</td></tr>")
    if not filas:
        return "<p>Sin alertas SUTRAN en vivo dentro de ±2 km del trayecto.</p>"
    return ("<table><tr><th>Ruta</th><th>Estado</th><th>Motivo</th><th>KM</th><th>Ubigeo</th><th>Distancia</th></tr>"
            + "".join(filas) + "</table>")


def _tipos_html(resumen):
    ti = resumen["rutas"][0].get("tipos_incidente", {}) or {}
    if not ti.get("total"):
        return "<p>Sin accidentes historicos en el buffer (±1 km) de la ruta.</p>"
    def _lista(items, sep=" · "):
        return sep.join(f"<b>{t['valor']}</b> {t['pct']}%" for t in items[:4])
    return (f"<p><b>{ti['total']}</b> accidentes historicos en el buffer (±1 km): "
            f"<b>{ti['fallecidos']}</b> fallecidos, <b>{ti['heridos']}</b> heridos.</p>"
            f"<p><b>Tipos:</b> {_lista(ti['top_tipos']) or 's/d'}</p>"
            f"<p><b>Causas:</b> {_lista(ti['top_causas']) or 's/d'}</p>")


def _prediccion_html(resumen):
    pr = resumen["rutas"][0].get("prediccion", {}) or {}
    if not pr:
        return "<p>Sin cobertura del modelo predictivo para esta ruta.</p>"
    cov = pr.get("cobertura_pct", 0.0)
    color = "b-green" if cov >= 50 else "b-orange"
    return (f"<p>Modelo NegBin (Fase 1) aplicado a la ruta: <b>{pr.get('pred_siniestros_km', 0):.3f} "
            f"siniestros/km</b> esperados sobre <b>{pr.get('n_tramos', 0)}</b> tramos modelados.</p>"
            f"<p>Cobertura de la red modelada: <span class='badge {color}'>{cov:.0f}%</span></p>")


def _clima_html(resumen):
    from clima import (avisos_senamhi, avisos_en_ruta, pronostico_openmeteo,
                       emergencias_coen, emergencias_en_ruta)
    geo = resumen["rutas"][0].get("geometry")
    if not geo:
        return "<p>Sin geometria de ruta.</p>"
    partes = []
    try:
        avisos = avisos_senamhi()
        en_ruta = avisos_en_ruta(avisos, geo)
        if en_ruta:
            items = "".join(f"<li><b>{a['nivel']}</b> ({a['fecha']}) — {a['responsable'] or 'SENAMHI'}</li>"
                            for a in en_ruta)
            partes.append(f"<p><b>Avisos SENAMHI en la ruta:</b> {len(en_ruta)}</p><ul>{items}</ul>")
        else:
            partes.append(f"<p><b>Avisos SENAMHI en la ruta:</b> ninguno (de {len(avisos)} avisos activos).</p>")
    except Exception:
        partes.append("<p><b>Avisos SENAMHI:</b> no disponibles.</p>")
    try:
        pr = pronostico_openmeteo(geo)
        if pr:
            partes.append(f"<p><b>Pronostico:</b> {pr['tmin_c']}–{pr['tmax_c']} °C · probabilidad de lluvia "
                          f"{pr['precip_prob_max']}% · viento hasta {pr['viento_max_kmh']} km/h.</p>")
    except Exception:
        pass
    try:
        ems = emergencias_en_ruta(emergencias_coen(), geo)
        if ems:
            items = "".join(f"<li><b>{e['tipo']}</b> — {e['lugar']}, {e['departamento']} ({e['fecha']}) "
                            f"a {e['dist_km']} km</li>" for e in ems[:6])
            partes.append(f"<p><b>Emergencias COEN cerca de la ruta:</b> {len(ems)}</p><ul>{items}</ul>")
        else:
            partes.append("<p><b>Emergencias COEN cerca de la ruta:</b> ninguna registrada (ultimos 7 dias).</p>")
    except Exception:
        partes.append("<p><b>Emergencias COEN:</b> no disponibles.</p>")
    return "<br>".join(partes)


def reporte_desde_resumen(resumen, out_path=None):
    if out_path is None:
        out_path = ROOT / "data" / "processed" / "dashboard" / "reporte_ruta.html"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mapa = _mapa_html(resumen)
    chart = _chart_perfil(resumen)
    fct = resumen["factor_temporal"]
    fac = (f"x{fct} <span class='badge b-orange'>factor temporal</span>"
           if fct > 1.0 else "<span class='badge b-green'>factor temporal neutro (x1.0)</span>")
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    best = min(r["score_km_penalizado"] for r in resumen["rutas"])

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>SIPAT · Ruta segura — {resumen["origen"]["nombre"]} → {resumen["destino"]["nombre"]}</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>SIPAT · Prevención antes de viajar</h1>
<p><b>{resumen["origen"]["nombre"]}</b> → <b>{resumen["destino"]["nombre"]}</b></p>
<p>Generado: {fecha} · Salida: {resumen["salida"] or "no especificada"} · {fac}</p></header>
<div class="cards">
<div class="card"><b>{resumen["rutas"][0]["distance_km"]} km</b><span>Ruta mas corta</span></div>
<div class="card"><b>{min(r["duration_min"] for r in resumen["rutas"]):.0f} min</b><span>Ruta mas rapida</span></div>
<div class="card"><b>{best}</b><span>Menor riesgo (score /km)</span></div>
<div class="card"><b>{len(resumen["rutas"])}</b><span>Alternativas OSRM</span></div></div>
<section><h2>Mapa de la ruta y accidentes historicos</h2>{mapa}
<p class="tag">Colores de ruta: azul/rojo/verde/naranja = R0/R1/R2/R3. Accidentes clicables: morado ONSV, naranja SUTRAN, teal OSITRAN.</p></section>
<section><h2>¿Qué puede pasar? Perfil historico</h2>{_tipos_html(resumen)}</section>
<section><h2>Riesgo predictivo (modelo NegBin)</h2>{_prediccion_html(resumen)}</section>
<section><h2>Comparativa de rutas</h2>{_tabla_rutas(resumen)}</section>
<section><h2>Perfil de riesgo por segmento (cada 5 km)</h2>
<img src="data:image/png;base64,{chart}" style="width:100%;border-radius:8px"></section>
<section><h2>Clima y emergencias</h2>{_clima_html(resumen)}</section>
<section><h2>Alertas SUTRAN en vivo cerca del trayecto</h2>{_alertas_html(resumen)}</section>
<footer>SIPAT — Siniestralidad Vial en la Red Vial Nacional. Riesgo = accidentes ONSV/SUTRAN/OSITRAN
en buffer ±1 km ponderados por gravedad + alertas historicas SUTRAN + exposicion de trafico OSITRAN
(AADT/100 000 por peaje a ≤15 km), penalizado por alertas en vivo (interrumpido +5, restringido +1).</footer>
</div></body></html>"""
    out_path.write_text(html, encoding="utf-8")
    return out_path


def reporte(origin, dest, salida=None, out_path=None):
    res = analizar(origin, dest, salida=salida)
    resumen = resumen_analisis(res, include_geometry=True)
    return reporte_desde_resumen(resumen, out_path=out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("origin")
    ap.add_argument("dest")
    ap.add_argument("--salida", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ruta = reporte(a.origin, a.dest, salida=a.salida, out_path=a.out)
    print(f"Reporte: {ruta}")


if __name__ == "__main__":
    main()
