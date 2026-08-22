"""Motor 'ruta segura': geocoding Nominatim -> rutas OSRM -> score de riesgo + alertas SUTRAN.

Uso:
  python scripts/ruta_segura.py "Lima, Peru" "Huancayo, Peru" --out data/processed/dashboard/ruta_segura.html
  python scripts/ruta_segura.py "-12.046,-77.028" "-12.065,-75.204"   # o coordenadas directas

Genera: dataset con rutas rankeadas (segura/rapida/corta) y mapa folium.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import folium

from osrm_router import OSRMClient
from riesgo_red import get_index, factor_temporal
from alertas_sutran import get_alertas, alertas_en_ruta
from prediccion import get_predictor, tipos_incidente

GEO_CACHE = ROOT / "data" / "processed" / "dashboard" / "geocode_cache.json"

PENALTY_INTERRUMPIDO = 5.0
PENALTY_RESTRINGIDO = 1.0


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_km(km):
    try:
        f = float(km)
        return f"km {f:.1f}"
    except (TypeError, ValueError):
        return str(km or "").strip()


def _popup_accidente(a):
    """HTML del popup de un accidente historico (al hacer clic en el mapa)."""
    f = a.get("fuente", "")
    tipo = _esc(a.get("tipo"))
    fecha = _esc(a.get("fecha"))
    hora = _esc(a.get("hora"))
    ruta = _esc(a.get("ruta"))
    km = _fmt_km(a.get("km"))
    depto = _esc(a.get("depto"))
    prov = _esc(a.get("provincia"))
    dist = _esc(a.get("distrito"))
    try:
        fal = int(a.get("fallecidos") or 0)
        les = int(a.get("lesionados") or 0)
    except (TypeError, ValueError):
        fal, les = 0, 0
    causa = _esc(a.get("causa"))
    causa_esp = _esc(a.get("causa_especifica"))
    clima = _esc(a.get("clima"))
    sup = _esc(a.get("superficie"))
    via = _esc(a.get("via"))
    tramo = _esc(a.get("tramo"))
    total = a.get("total_tramo")

    ubic = " · ".join(x for x in [ruta and f"{ruta}", km, depto] if x)
    titulo = f"{tipo} ({f})" if tipo else f"Accidente ({f})"
    gravedad = []
    if fal:
        gravedad.append(f"<b>{fal} fallecido(s)</b>")
    if les:
        gravedad.append(f"{les} herido(s)")
    lines = []
    if fecha:
        lines.append(f"<b>Fecha:</b> {fecha}" + (f" {hora}" if hora else ""))
    if ubic:
        lines.append(f"<b>Ubicación:</b> {ubic}")
    if prov and dist and depto != dist:
        lines.append(f"<b>Lugar:</b> {dist} ({prov})")
    if gravedad:
        lines.append(f"<b>Gravedad:</b> {' · '.join(gravedad)}")
    if causa:
        lines.append(f"<b>Causa:</b> {causa}" + (f" — {causa_esp}" if causa_esp and causa_esp != causa else ""))
    extras = [x for x in [f"Clima: {clima}" if clima else "", f"Vía: {sup}" if sup else "",
                          f"Tipo de vía: {via}" if via else ""] if x]
    if extras:
        lines.append("<b>Entorno:</b> " + " · ".join(extras))
    if f == "OSITRAN" and total:
        lines.append(f"<b>Tramo {ruta}:</b> {total} accidentes 2019-2025" + (f" · {tramo}" if tramo else ""))
    return (f"<div style='min-width:230px'><b style='color:#b02a2a'>{_esc(titulo)}</b><br>"
            + "<br>".join(lines) + "</div>")


def _es_coordenadas(s):
    try:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 2:
            return False
        float(parts[0]), float(parts[1])
        return True
    except ValueError:
        return False


def _geocodificar_foton(place):
    q = urllib.parse.quote(place.replace(",", " ").strip())
    url = f"https://photon.komoot.io/api/?q={q}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "SIPAT-ruta-segura/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("features"):
        return None
    f = data["features"][0]
    lon, lat = f["geometry"]["coordinates"]
    p = f.get("properties", {})
    nombre = p.get("name", "") + ", " + p.get("state", "") + ", " + p.get("country", "Peru")
    return (float(lon), float(lat), nombre.strip(", "))


def _geocodificar_nominatim(place):
    q = urllib.parse.quote(place)
    url = f"https://nominatim.openstreetmap.org/search?q={q}&format=jsonv2&limit=1&countrycodes=pe&accept-language=es"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SIPAT-ruta-segura/1.0 (sipat@example.com)",
                 "Referer": "https://www.openstreetmap.org/"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data:
        return None
    hit = data[0]
    return (float(hit["lon"]), float(hit["lat"]), hit.get("display_name", place))


def geocode(place):
    """Retorna (lon, lat, nombre). Acepta 'lat,lon' directo, texto via Photon (fallback Nominatim)."""
    if _es_coordenadas(place):
        lat, lon = (float(x) for x in place.split(","))
        return lon, lat, place
    cache = {}
    if GEO_CACHE.exists():
        try:
            cache = json.loads(GEO_CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {}
    if place in cache:
        return cache[place]
    for fn in (_geocodificar_foton, _geocodificar_nominatim):
        try:
            out = fn(place)
            if out:
                cache[place] = out
                GEO_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                return out
        except Exception:
            continue
    raise ValueError(f"Geocoding sin resultado para: {place}")


def _penalizar(score, alerts, factor=1.0):
    p = 0.0
    for a in alerts:
        if a["estado"] == "TRANSITO INTERRUMPIDO":
            p += PENALTY_INTERRUMPIDO
        elif a["estado"] == "TRANSITO RESTRINGIDO":
            p += PENALTY_RESTRINGIDO
    return round(score * factor + p, 4)


def _parse_salida(salida):
    """Convierte str 'YYYY-MM-DD HH:MM' (o None) en datetime local."""
    if not salida:
        return None
    if isinstance(salida, str):
        from datetime import datetime
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(salida, fmt)
            except ValueError:
                continue
        raise ValueError(f"Formato de salida invalido: {salida} (use 'YYYY-MM-DD HH:MM')")
    return salida


def analizar(origin, dest, radio_alertas_km=2.0, salida=None, perfil_segmento_km=5.0):
    idx = get_index()
    alerts = get_alertas()
    o = geocode(origin)
    d = geocode(dest)
    salida_dt = _parse_salida(salida)
    factor = factor_temporal(salida_dt)
    cliente = OSRMClient()
    rutas = cliente.route([(o[0], o[1]), (d[0], d[1])], alternatives=3, steps=True)
    res = []
    for r in rutas:
        geo = r["geometry"]["coordinates"]
        score = idx.score_route(geo)
        cercanas = alertas_en_ruta(alerts, geo, radio_km=radio_alertas_km)
        score_p = _penalizar(score["score_km"], cercanas, factor)
        acc = idx.matched(geo)
        perfil = idx.perfil_segmentos(geo, segment_km=perfil_segmento_km)
        predictor = get_predictor()
        pred = predictor.predecir_ruta(geo, segment_km=perfil_segmento_km)
        tipos = tipos_incidente(acc)
        res.append({
            "distance_km": round(r["distance_m"] / 1000.0, 1),
            "duration_min": round(r["duration_s"] / 60.0, 0),
            "geometry": geo,
            "accidentes_hist": acc,
            "alertas_en_vivo": cercanas,
            "riesgo": score,
            "perfil": perfil,
            "prediccion": pred,
            "tipos_incidente": tipos,
            "factor_temporal": factor,
            "score_km_penalizado": score_p,
        })
    if not res:
        raise RuntimeError("OSRM no devolvio rutas")
    min_dist = min(r["distance_km"] for r in res)
    min_duracion = min(r["duration_min"] for r in res)
    min_riesgo = min(r["score_km_penalizado"] for r in res)
    ranking = {
        "corta": [i for i, r in enumerate(res) if r["distance_km"] == min_dist],
        "rapida": [i for i, r in enumerate(res) if r["duration_min"] == min_duracion],
        "segura": [i for i, r in enumerate(res) if r["score_km_penalizado"] == min_riesgo],
    }
    return {"origen": o, "destino": d, "rutas": res, "ranking": ranking, "factor_temporal": factor,
            "salida": salida_dt.strftime("%Y-%m-%d %H:%M") if salida_dt else None}


def resumen_analisis(resultado, include_geometry=True, max_acc_hist=500):
    """Version JSON-serializable y ligera del resultado para la API."""
    out = {
        "origen": {"lon": resultado["origen"][0], "lat": resultado["origen"][1], "nombre": resultado["origen"][2]},
        "destino": {"lon": resultado["destino"][0], "lat": resultado["destino"][1], "nombre": resultado["destino"][2]},
        "factor_temporal": resultado["factor_temporal"],
        "salida": resultado["salida"],
        "ranking": resultado["ranking"],
        "rutas": [],
    }
    for i, r in enumerate(resultado["rutas"]):
        acc = r["accidentes_hist"]
        if len(acc) > max_acc_hist:
            step = len(acc) / max_acc_hist
            acc = [acc[int(j * step)] for j in range(max_acc_hist)]
        out["rutas"].append({
            "indice": i,
            "distance_km": r["distance_km"],
            "duration_min": r["duration_min"],
            "score_km_penalizado": r["score_km_penalizado"],
            "factor_temporal": r["factor_temporal"],
            "riesgo": r["riesgo"],
            "perfil": r["perfil"],
            "prediccion": r["prediccion"],
            "tipos_incidente": r["tipos_incidente"],
            "alertas_en_vivo": [{k: a[k] for k in ("item", "estado", "motivo", "km", "ubigeo", "evento", "dist_km")} for a in r["alertas_en_vivo"]],
            "accidentes_hist": [{"lon": a["lon"], "lat": a["lat"], "fuente": a["fuente"],
                                 "fallecidos": a["fallecidos"], "lesionados": a["lesionados"],
                                 "fecha": a.get("fecha", ""), "tipo": a.get("tipo", ""),
                                 "ruta": a.get("ruta", ""), "km": a.get("km"),
                                 "depto": a.get("depto", ""), "causa": a.get("causa", ""),
                                 "clima": a.get("clima", ""), "tramo": a.get("tramo", "")} for a in acc],
        })
        if include_geometry:
            out["rutas"][-1]["geometry"] = r["geometry"]
    return out


def _color(score, vmax):
    t = min(score / max(vmax, 1e-9), 1.0)
    return f"#{int(255 * t):02x}{int(255 * (1 - t)):02x}00"


def mapa(resultado, out_path):
    m = resultado["rutas"][0]["geometry"]
    lon0 = sum(p[0] for p in m) / len(m)
    lat0 = sum(p[1] for p in m) / len(m)
    mapa_f = folium.Map(location=[lat0, lon0], zoom_start=9, tiles="OpenStreetMap")
    folium.Marker([resultado["origen"][1], resultado["origen"][0]], popup="Origen", icon=folium.Icon(color="green")).add_to(mapa_f)
    folium.Marker([resultado["destino"][1], resultado["destino"][0]], popup="Destino", icon=folium.Icon(color="red")).add_to(mapa_f)
    vmax = max((r["score_km_penalizado"] for r in resultado["rutas"]), default=1.0)
    for i, r in enumerate(resultado["rutas"]):
        pts = [(p[1], p[0]) for p in r["geometry"]]
        color = _color(r["score_km_penalizado"], vmax)
        folium.PolyLine(
            pts, color=color, weight=6, opacity=0.9,
            popup=f"Ruta {i}: {r['distance_km']} km, {r['duration_min']:.0f} min, riesgo {r['score_km_penalizado']}",
        ).add_to(mapa_f)
        mid = pts[len(pts) // 2]
        folium.Marker(mid, icon=folium.DivIcon(html=f'<b style="background:{color};color:#fff;padding:2px 6px">R{i} {r["score_km_penalizado"]}</b>')).add_to(mapa_f)
    g_hist = folium.FeatureGroup(name="Accidentes historicos")
    colores_fuente = {"ONSV": "purple", "SUTRAN": "orange", "OSITRAN": "teal"}
    for r in resultado["rutas"]:
        for a in r["accidentes_hist"]:
            c = colores_fuente.get(a["fuente"], "blue")
            folium.CircleMarker([a["lat"], a["lon"]], radius=4, color=c, fill=True,
                                fill_opacity=0.85,
                                popup=folium.Popup(_popup_accidente(a), max_width=340)).add_to(g_hist)
    g_hist.add_to(mapa_f)
    g_live = folium.FeatureGroup(name="Alertas SUTRAN en vivo")
    iconos = {"INTERRUMPIDO": "red", "RESTRINGIDO": "orange", "NORMAL": "green"}
    for r in resultado["rutas"]:
        for a in r["alertas_en_vivo"]:
            folium.Marker([a["lat"], a["lon"]], icon=folium.Icon(color=iconos.get(a["estado"], "blue"), icon="info-sign"),
                          popup=f"<b>{a['estado']}</b><br>{a['motivo']}<br>{a['evento']}<br>{a['ubigeo']}").add_to(g_live)
    g_live.add_to(mapa_f)
    folium.LayerControl().add_to(mapa_f)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mapa_f.save(str(out_path))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("origin", help="Origen (texto o 'lat,lon')")
    ap.add_argument("dest", help="Destino (texto o 'lat,lon')")
    ap.add_argument("--out", default=str(ROOT / "data" / "processed" / "dashboard" / "ruta_segura.html"))
    ap.add_argument("--json", action="store_true", help="solo imprimir ranking en JSON")
    ap.add_argument("--salida", default=None, help="fecha/hora de salida 'YYYY-MM-DD HH:MM' (factor temporal)")
    a = ap.parse_args()
    res = analizar(a.origin, a.dest, salida=a.salida)
    rank = {k: {"indices": v, "labels": [f"Ruta {i}" for i in v]} for k, v in res["ranking"].items()}
    if a.json:
        out = {"ranking": rank,
               "factor_temporal": res["factor_temporal"],
               "salida": res["salida"],
               "rutas": [{"indice": i,
                          **{k: r[k] for k in ("distance_km", "duration_min", "score_km_penalizado")},
                          "riesgo": r["riesgo"]} for i, r in enumerate(res["rutas"])]}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    for i, r in enumerate(res["rutas"]):
        print(f"Ruta {i}: {r['distance_km']} km | {r['duration_min']:.0f} min | riesgo={r['score_km_penalizado']} | "
              f"acc_hist={len(r['accidentes_hist'])} | alertas_live={len(r['alertas_en_vivo'])}")
    print("Ranking:", {k: [f'Ruta {i}' for i in v] for k, v in res["ranking"].items()})
    ruta = mapa(res, a.out)
    print(f"Mapa: {ruta}")


if __name__ == "__main__":
    main()
