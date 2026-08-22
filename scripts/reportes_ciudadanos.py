"""Reportes ciudadanos del SIPAT.

Los usuarios reportan incidentes viales desde el dashboard: tipo, severidad,
descripcion, ubicacion (coordenadas o km de la ruta calculada) y una foto.

Almacenamiento:
  data/processed/dashboard/reportes_ciudadanos.json   (lista append-only)
  data/processed/dashboard/reportes_fotos/<id>.<ext>  (fotos)

Uso:
    from reportes_ciudadanos import agregar_reporte, listar_reportes, reportes_en_ruta
"""

import io
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "processed" / "dashboard"
P_JSON = OUT_DIR / "reportes_ciudadanos.json"
P_FOTOS = OUT_DIR / "reportes_fotos"

TIPOS = {
    "Accidente": {"emoji": "💥", "color": "#d64545"},
    "Congestión / cola": {"emoji": "🚗", "color": "#e69138"},
    "Obra vial": {"emoji": "🚧", "color": "#3c78d8"},
    "Derrumbe / piedra": {"emoji": "⛰️", "color": "#8e6a3a"},
    "Inundación / lluvia": {"emoji": "🌧️", "color": "#2b7bb9"},
    "Animal en la vía": {"emoji": "🐄", "color": "#7f6000"},
    "Vía interrumpida": {"emoji": "⛔", "color": "#cc0000"},
    "Otro peligro": {"emoji": "⚠️", "color": "#777777"},
}
SEVERIDADES = {"Leve": "#2e8b57", "Moderado": "#d4a017", "Grave": "#b02a2a"}


def _load():
    if P_JSON.exists():
        try:
            return json.loads(P_JSON.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(reps):
    P_JSON.parent.mkdir(parents=True, exist_ok=True)
    P_JSON.write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")


def _limpiar(texto, maxlen):
    return re.sub(r"\s+", " ", str(texto)).strip()[:maxlen]


def agregar_reporte(tipo, descripcion, lat, lon, foto=None, autor="",
                    severidad="Moderado", ref="", cuando=None):
    """Registra un reporte. foto = bytes de imagen o None.
    Devuelve (ok, mensaje, reporte_dict|None)."""
    if tipo not in TIPOS:
        return False, f"Tipo invalido: {tipo}", None
    if severidad not in SEVERIDADES:
        severidad = "Moderado"
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False, "Ubicacion invalida.", None
    if not (-18.6 <= lat <= -0.04 and -82.0 <= lon <= -68.6):
        return False, "La ubicacion esta fuera del Peru.", None
    desc = _limpiar(descripcion, 500)
    if len(desc) < 5:
        return False, "Describe brevemente lo que ves (minimo 5 caracteres).", None

    rep_id = f"R{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    foto_nombre = ""
    if foto:
        P_FOTOS.mkdir(parents=True, exist_ok=True)
        ext = "jpg"
        if isinstance(foto, (bytes, bytearray)) and foto[:4] == b"\x89PNG":
            ext = "png"
        foto_nombre = f"{rep_id}.{ext}"
        try:
            (P_FOTOS / foto_nombre).write_bytes(foto)
        except Exception:
            foto_nombre = ""

    rep = {
        "id": rep_id,
        "tipo": tipo,
        "severidad": severidad,
        "descripcion": desc,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "ref": _limpiar(ref, 120),
        "autor": _limpiar(autor, 60) or "Anónimo",
        "foto": foto_nombre,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "epoch": int(time.time()),
    }
    reps = _load()
    # dedupe simple: mismo tipo+ubicacion (<150m) en los ultimos 10 min
    for r in reps[-20:]:
        try:
            if r["tipo"] == tipo and abs(r["lat"] - lat) < 0.0015 and abs(r["lon"] - lon) < 0.0015 \
                    and rep["epoch"] - r.get("epoch", 0) < 600:
                return False, "Ya existe un reporte igual hace pocos minutos.", None
        except Exception:
            continue
    reps.append(rep)
    _save(reps)
    return True, f"Reporte {rep_id} registrado. ¡Gracias por ayudar!", rep


def listar_reportes(dias=30):
    """DataFrame de reportes recientes (mas nuevos primero)."""
    reps = _load()
    if not reps:
        return None
    corte = (datetime.now() - timedelta(days=dias)).timestamp()
    recientes = [r for r in reps if r.get("epoch", 0) >= corte]
    recientes.sort(key=lambda r: r.get("epoch", 0), reverse=True)
    return recientes


def reportes_en_ruta(reportes, geometry, radio_km=8.0):
    """Filtra reportes a <= radio_km de la geometria [[lon,lat],...]."""
    if not geometry or not reportes:
        return []
    import math

    def hav(lat1, lon1, lat2, lon2):
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = p2 - p1
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    paso = max(1, len(geometry) // 300)
    pts = geometry[::paso]
    out = []
    for r in reportes:
        d = min(hav(r["lat"], r["lon"], pt[1], pt[0]) for pt in pts)
        if d <= radio_km:
            rr = dict(r)
            rr["dist_km"] = round(d, 1)
            out.append(rr)
    out.sort(key=lambda x: x["dist_km"])
    return out


def punto_en_km(geometry, km_objetivo, km_total):
    """Interpola un punto [lon,lat] de la geometria a X km del inicio."""
    if not geometry or km_total <= 0:
        return None
    frac = max(0.0, min(1.0, km_objetivo / km_total))
    idx = int(frac * (len(geometry) - 1))
    return geometry[idx][1], geometry[idx][0]  # (lat, lon)


def estadisticas():
    """Conteos para cabecera de la pestaña."""
    reps = _load()
    hoy = datetime.now().date().isoformat()
    return {
        "total": len(reps),
        "hoy": sum(1 for r in reps if str(r.get("ts", "")).startswith(hoy)),
        "con_foto": sum(1 for r in reps if r.get("foto")),
    }
