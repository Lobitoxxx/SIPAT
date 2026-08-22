"""Capa de clima y emergencias para 'ruta segura'.

- avisos_senamhi(): avisos meteorologicos de 24 h del WFS publico de SENAMHI
  (geometrias MultiPolygon + nivel/descripcion/recomendaciones), cache 1 h.
- avisos_en_ruta(avisos, geometry): avisos que intersectan la ruta (shapely).
- pronostico_openmeteo(geometry): pronostico de temperatura/precipitacion/
  viento a lo largo de la ruta (Open-Meteo, sin API key), cache 1 h.
- emergencias_coen(): reportes recientes de emergencia del portal INDECI/COEN
  (titulo -> tipo + distrito + departamento, geocodificados con Photon), cache 6 h.
- emergencias_en_ruta(emergencias, geometry, radio_km): emergencias cerca de la ruta.

Uso:
  from clima import avisos_senamhi, avisos_en_ruta, pronostico_openmeteo, \
                   emergencias_coen, emergencias_en_ruta
"""

import html
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "data" / "processed" / "dashboard"
DASH.mkdir(parents=True, exist_ok=True)

SENAMHI_WFS = ("https://idesep.senamhi.gob.pe/geoserver/g_prono_pp_24h/ows"
               "?service=WFS&version=1.0.0&request=GetFeature"
               "&typeName=g_prono_pp_24h:view_aviso24h&outputFormat=application/json")
COEN_URL = "https://portal.indeci.gob.pe/emergencias/"
OPENMETEO = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
             "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
             "wind_speed_10m_max&forecast_days=3&timezone=auto")

CACHE = {
    "avisos_senamhi": ("avisos_senamhi.json", 1.0),
    "coen_emergencias": ("coen_emergencias.json", 6.0),
    "coen_geocode": ("coen_geocode.json", 24.0 * 30),
}


def _cached(name):
    file, _ttl = CACHE[name]
    p = DASH / file
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - d.get("_ts", 0) < _ttl * 3600:
                return d.get("data")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save(name, data):
    file, _ttl = CACHE[name]
    (DASH / file).write_text(json.dumps({"_ts": time.time(), "data": data},
                                        ensure_ascii=False), encoding="utf-8")


def _descargar(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SIPAT/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _anillos(geom):
    """Aplana una geometria MultiPolygon/Polygon de lon/lat a anillos [lon,lat]."""
    if not geom or geom.get("type") == "Point":
        return None
    coords = geom.get("coordinates") or []
    rings = []
    polys = coords if geom.get("type") == "MultiPolygon" else [coords]
    for poly in polys:
        if poly and isinstance(poly[0], list) and isinstance(poly[0][0], list):
            rings.append([[float(x), float(y)] for x, y in poly[0]])
    return rings or None


def avisos_senamhi(force=False):
    if not force:
        c = _cached("avisos_senamhi")
        if c is not None:
            return c
    try:
        gj = json.loads(_descargar(SENAMHI_WFS))
        out = []
        for f in gj.get("features", []):
            props = f.get("properties", {}) or {}
            rings = _anillos(f.get("geometry"))
            if not rings:
                continue
            out.append({
                "nivel": str(props.get("nivel") or ""),
                "fecha": str(props.get("fecha") or ""),
                "descripcion": str(props.get("descripcio") or props.get("descripcion") or ""),
                "recomendaciones": str(props.get("recomendac") or ""),
                "responsable": str(props.get("respons") or ""),
                "poligono": rings[0],
            })
        if out:
            _save("avisos_senamhi", out)
        return out
    except Exception:
        c = _cached("avisos_senamhi")
        return c if c is not None else []


def _avisos_cerca_puntos(avisos, geometry, buffer_km):
    """Fallback sin shapely: caja de la ruta ampliada."""
    lons = [p[0] for p in geometry]
    lats = [p[1] for p in geometry]
    d = buffer_km / 111.0
    x0, x1 = min(lons) - d, max(lons) + d
    y0, y1 = min(lats) - d, max(lats) + d
    return [a for a in avisos
            if any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in a["poligono"])]


def avisos_en_ruta(avisos, geometry, buffer_km=5.0):
    if not avisos:
        return []
    try:
        from shapely.geometry import LineString, Polygon
    except ImportError:
        return _avisos_cerca_puntos(avisos, geometry, buffer_km)
    ruta = LineString(geometry).buffer(buffer_km / 111.0)
    out = []
    for a in avisos:
        try:
            if Polygon(a["poligono"]).intersects(ruta):
                out.append(a)
        except Exception:
            continue
    return out


def pronostico_openmeteo(geometry, force=False):
    sub = geometry[::max(1, len(geometry) // 8)]
    clave = hashlib.md5(json.dumps(sub).encode()).hexdigest()[:10]
    p = DASH / f"openmeteo_{clave}.json"
    if not force and p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - d.get("_ts", 0) < 3600:
                return d.get("data")
        except (json.JSONDecodeError, OSError):
            pass
    try:
        n = min(4, len(geometry))
        idxs = np.linspace(0, len(geometry) - 1, n).astype(int)
        tmin, tmax, pop, viento = [], [], [], []
        for i in idxs:
            lon, lat = geometry[i]
            url = OPENMETEO.format(lat=lat, lon=lon)
            data = json.loads(_descargar(url, timeout=30))
            daily = data.get("daily", {})
            if daily.get("time"):
                tmin.append(min(daily["temperature_2m_min"]))
                tmax.append(max(daily["temperature_2m_max"]))
                pop.append(max(daily.get("precipitation_probability_max", [0])))
                viento.append(max(daily.get("wind_speed_10m_max", [0])))
        if not tmin:
            return None
        out = {
            "fecha": daily.get("time", [""])[0],
            "tmin_c": round(float(min(tmin)), 1),
            "tmax_c": round(float(max(tmax)), 1),
            "precip_prob_max": int(max(pop)),
            "viento_max_kmh": round(float(max(viento)), 1),
            "puntos": int(n),
        }
        p.write_text(json.dumps({"_ts": time.time(), "data": out}, ensure_ascii=False),
                     encoding="utf-8")
        return out
    except Exception:
        return None


_TIPOS_COEN = [
    (r"lluvias? intensas|lluvias|precipitaciones|huaico|aluvion", "Lluvias/Huaicos"),
    (r"vientos? fuertes", "Vientos fuertes"),
    (r"helada|descenso de temperatura|bajas temperaturas|friaje", "Frio/Helada"),
    (r"sismo|terremoto", "Sismo"),
    (r"incendio", "Incendio"),
    (r"deslizamiento|derrumbe|movimiento de masa|reptacion|socavon", "Movimiento de masa"),
    (r"granizada|nevada|granizo", "Nieve/Granizo"),
    (r"inundacion|desborde", "Inundacion"),
    (r"derrame", "Derrame"),
    (r"colapso", "Colapso"),
]


def _clasificar_tipo(texto):
    t = texto.lower()
    for pat, cat in _TIPOS_COEN:
        if re.search(pat, t):
            return cat
    return texto.strip()[:60]


def _parsear_titulo(titulo):
    """De 'REPORTE ... (Reporte N.° 67) SISMO ... DISTRITO DE X – JUNIN' extrae campos."""
    m_fecha = re.search(r"(\d{1,2}/\d{1,2}/20\d{2})", titulo)
    m_hora = re.search(r"(\d{1,2}:\d{2})\s*HORAS", titulo)
    resto = re.sub(r"^.*?\)\s*", "", titulo)
    resto = re.sub(r"^\s*", "", resto)
    if " – " in resto:
        evento, depto = resto.rsplit(" – ", 1)
    elif " - " in resto:
        evento, depto = resto.rsplit(" - ", 1)
    else:
        evento, depto = resto, ""
    m_dis = re.search(r"(?:EN EL DISTRITO|EN EL DISTRITO DEL|EN EL DISTRITO DE)\s+(.+?)\s*$", evento, re.I)
    m_pro = re.search(r"EN LA PROVINCIA DE\s+(.+?)\s*$", evento, re.I)
    lugar = ""
    tipo_raw = evento
    if m_dis:
        lugar = "DISTRITO " + m_dis.group(1).strip().title()
        tipo_raw = evento[:m_dis.start()].strip()
    elif m_pro:
        lugar = "PROVINCIA " + m_pro.group(1).strip().title()
        tipo_raw = evento[:m_pro.start()].strip()
    return {
        "fecha": m_fecha.group(1) if m_fecha else "",
        "hora": m_hora.group(1) if m_hora else "",
        "tipo": _clasificar_tipo(tipo_raw),
        "tipo_raw": tipo_raw[:80],
        "lugar": lugar,
        "departamento": depto.strip().upper(),
    }


def _geocodificar(place):
    g = _cached("coen_geocode") or {}
    if place in g:
        return g[place]
    urls = [
        ("https://photon.komoot.io/api/?q=" + urllib.parse.quote(place) + "&limit=1"),
        ("https://nominatim.openstreetmap.org/search?q=" + urllib.parse.quote(place)
         + "&format=json&limit=1"),
    ]
    for url in urls:
        try:
            data = json.loads(_descargar(url, timeout=20))
            fts = data.get("features") if isinstance(data, dict) else data
            if fts:
                if isinstance(data, dict):
                    lon, lat = fts[0]["geometry"]["coordinates"]
                else:
                    lon, lat = float(fts[0]["lon"]), float(fts[0]["lat"])
                g[place] = [lon, lat]
                _save("coen_geocode", g)
                return g[place]
        except Exception:
            continue
    return None


def emergencias_coen(force=False, dias=7):
    if not force:
        c = _cached("coen_emergencias")
        if c is not None:
            return c
    try:
        contenido = _descargar(COEN_URL, timeout=60)
    except Exception:
        c = _cached("coen_emergencias")
        return c if c is not None else []
    pares = re.findall(r'<h2>\s*<a href="([^"]+)">\s*([^<]+?)\s*</a>', contenido, re.S)
    hoy = time.time()
    out, vistos = [], set()
    for url, titulo in pares:
        titulo = html.unescape(titulo)
        campos = _parsear_titulo(titulo)
        fecha = campos["fecha"]
        if fecha:
            try:
                d = datetime.strptime(fecha, "%d/%m/%Y")
                if (hoy - d.timestamp()) > dias * 86400:
                    continue
            except ValueError:
                pass
        if not campos["lugar"]:
            continue
        q = f"{campos['lugar']}, {campos['departamento']}" if campos["departamento"] else campos["lugar"]
        coord = _geocodificar(q)
        if not coord:
            continue
        clave = (campos["tipo"], q)
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append({
            "tipo": campos["tipo"],
            "fecha": fecha,
            "hora": campos["hora"],
            "lugar": campos["lugar"].title(),
            "departamento": campos["departamento"],
            "lon": coord[0],
            "lat": coord[1],
            "url": url,
        })
    if out:
        _save("coen_emergencias", out)
    return out


def emergencias_en_ruta(emergencias, geometry, radio_km=25.0):
    if not emergencias:
        return []
    lons = np.array([p[0] for p in geometry])
    lats = np.array([p[1] for p in geometry])
    out = []
    for e in emergencias:
        dlat = (e["lat"] - lats) * 111.0
        dlon = (e["lon"] - lons) * 111.0 * np.cos(np.radians(lats))
        d = np.sqrt(dlat ** 2 + dlon ** 2)
        if d.min() <= radio_km:
            out.append({**e, "dist_km": round(float(d.min()), 1)})
    return out


if __name__ == "__main__":
    import json as _json
    av = avisos_senamhi()
    print(f"avisos SENAMHI: {len(av)}")
    if av:
        a = av[0]
        print("  ejemplo:", {k: (a[k] if k != "poligono" else f"{len(a[k])} pts") for k in a})
    em = emergencias_coen()
    print(f"emergencias COEN (7d): {len(em)}")
    if em:
        print("  ejemplo:", {k: em[0][k] for k in ("tipo", "fecha", "lugar", "departamento", "lon", "lat")})
    geo = [(-77.02824, -12.04637), (-77.06415, -11.99207)]
    pr = pronostico_openmeteo(geo)
    print("pronostico Open-Meteo:", pr)
