"""Capa de incidentes en vivo: SUTRAN 'Mapa interactivo de alertas'.

Endpoint publico: gis.sutran.gob.pe/alerta_sutran/script_cgm/carga_xlsx.php
  ?tipo=MAPA           -> alertas actuales (normal/restringido/interrumpido)
  ?tipo=HISTORICO_MAPA -> historico completo

Uso:
  from alertas_sutran import get_alertas, alertas_en_ruta
  alerts = get_alertas()                    # con cache TTL de 15 min
  cerca = alertas_en_ruta(alerts, geometry) # alerts en buffer de la ruta
"""

import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "processed" / "dashboard" / "sutran_alertas.json"
HIST_CACHE = ROOT / "data" / "processed" / "dashboard" / "sutran_alertas_historico.json"
URL = "http://gis.sutran.gob.pe/alerta_sutran/script_cgm/carga_xlsx.php"
TTL_S = 15 * 60

LAT0 = -10.0
M_LAT = 110574.0
M_LON = 111320.0 * np.cos(np.radians(LAT0))

PATRONES_MOTIVO = [
    ("ACCIDENTE", re.compile(r"choque|accidente|colisi|volcadur|despiste|atropell|choques", re.I)),
    ("FENOMENO", re.compile(r"derrumb|huayco|huaico|lluvia|nevad|deslizam|inundac|crecid|alud|piedras|rocas|erosi", re.I)),
    ("INFRAESTRUCTURA", re.compile(r"mantenimiento|obra|conservacion|pavimento|puente|plataforma|señal|senal|asfalto|construccion", re.I)),
    ("HUMANO", re.compile(r"bloqueo|cierre|manifest|protesta|piquete|poblador|paro", re.I)),
]


def _motivo(evento):
    for nombre, pat in PATRONES_MOTIVO:
        if pat.search(evento or ""):
            return nombre
    return "OTRO"


def _num_km(afectacion):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:\.\d+)?", afectacion or "")
    if not m:
        return None
    km = float(m.group(1))
    return int(km) if km == int(km) else km


def _fetch(tipo="MAPA"):
    url = f"{URL}?tipo={tipo}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8-sig", errors="replace")
    return json.loads(raw)


def normalizar(raw):
    out = []
    for estado, feats in (("NORMAL", raw.get("normal", [])),
                          ("RESTRINGIDO", raw.get("restringido", [])),
                          ("INTERRUMPIDO", raw.get("interrumpido", []))):
        for f in feats:
            geo = f.get("geometry", {})
            coords = geo.get("coordinates") or []
            p = f.get("properties", {}) or {}
            out.append({
                "item": p.get("item", ""),
                "estado": p.get("estado", estado),
                "motivo": _motivo(p.get("evento", "")),
                "evento": p.get("evento", ""),
                "afectacion": p.get("afectacion", ""),
                "km": _num_km(p.get("afectacion", "")),
                "ubigeo": p.get("ubigeo", ""),
                "fecha_evento": p.get("fecha_evento", ""),
                "fecha_actualizacion": p.get("fecha_actualizacion", ""),
                "tipo_alerta": p.get("tipo_alerta_", ""),
                "lon": coords[0] if coords else float(p.get("longitud", 0) or 0),
                "lat": coords[1] if coords else float(p.get("latitud", 0) or 0),
            })
    return out


def get_alertas(force=False, tipo="MAPA", archivar=True):
    """Alertas actuales de SUTRAN con cache TTL 15 min en disco.

    Si `archivar`, cada descarga nueva se anexa (deduplicada) al historico
    `sutran_alertas_historico.json`, acumulando senal de incidentes recurrentes.
    """
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not force and CACHE.exists():
        try:
            blob = json.loads(CACHE.read_text(encoding="utf-8"))
            if time.time() - blob.get("ts", 0) < TTL_S:
                return blob["alertas"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    raw = _fetch(tipo)
    alertas = normalizar(raw)
    blob = {"ts": time.time(), "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "actualizacion_sutran": raw.get("fecha_hora_actualizacion", ""),
            "numeros": raw.get("numeros", {}), "alertas": alertas}
    CACHE.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    if archivar:
        _archivar(alertas, blob["fecha"])
    return alertas


def _archivar(alertas, fecha_descarga):
    """Anexa alertas nuevas al historico (dedupe por item + fecha_actualizacion)."""
    HIST_CACHE.parent.mkdir(parents=True, exist_ok=True)
    try:
        hist = json.loads(HIST_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        hist = []
    vistos = {f"{a['item']}|{a['fecha_actualizacion']}" for a in hist}
    nuevos = 0
    for a in alertas:
        clave = f"{a['item']}|{a['fecha_actualizacion']}"
        if clave not in vistos:
            hist.append(dict(a, primera_vista=fecha_descarga))
            vistos.add(clave)
            nuevos += 1
    if nuevos:
        hist.sort(key=lambda a: a.get("primera_vista", ""))
        HIST_CACHE.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    return nuevos


def get_historico():
    """Alertas archivadas historicamente (acumuladas en disco)."""
    try:
        return json.loads(HIST_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _dist_km(lon, lat, sample):
    x = (lon - sample[:, 0]) * M_LON
    y = (lat - sample[:, 1]) * M_LAT
    return np.sqrt(x * x + y * y)


def alertas_en_ruta(alertas, geometry, radio_km=2.0):
    """Alertas a menos de radio_km de la polilinea de la ruta (geometry: [(lon,lat)])."""
    if not geometry or not alertas:
        return []
    pts = np.asarray(geometry, dtype=float)
    n = max(2, min(2000, int(len(pts) * 0.5)))
    idx = np.linspace(0, len(pts) - 1, n).astype(int)
    sample = pts[idx]
    cerca = []
    for a in alertas:
        d = _dist_km(a["lon"], a["lat"], sample).min()
        if d <= radio_km:
            a = dict(a)
            a["dist_km"] = round(float(d), 2)
            cerca.append(a)
    return sorted(cerca, key=lambda x: x["dist_km"])


if __name__ == "__main__":
    a = get_alertas(force=True)
    print(f"{len(a)} alertas | numeros: normal/restringido/interrumpido")
    for x in a[:6]:
        print(f"  [{x['estado']:12s}] {x['motivo']:13s} km={x['km']} {x['ubigeo']} | {x['evento'][:60]}")
