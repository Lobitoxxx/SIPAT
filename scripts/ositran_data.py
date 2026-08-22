"""Datos OSITRAN: accidentes de transito y trafico vehicular en concesiones.

Fuentes (PNDA, OSITRAN):
  accidentes: 202603-PDE-REP-00204.csv  (16 concesiones, sin coordenadas)
  trafico:    202603-PDE-REP-00201.csv  (flujo vehicular por peaje)

Este script:
  1. Parsea y limpia ambos CSV (separador ';').
  2. Geocodifica extremos de tramo ('PEAJE A - PEAJE B') usando el GeoJSON de
     peajes MTC y Photon como respaldo (cacheado), generando tramos con coords.
  3. Agrega trafico por peaje y los ubica espacialmente.
  4. Exporta: ositran_accidentes.csv, ositran_trafico.csv,
     ositran_tramos_geocod.csv, ositran_peajes_geo.json.

Uso:
  python scripts/ositran_data.py
"""

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ositran"
PROC = ROOT / "data" / "processed"

P_ACC = RAW / "accidentes.csv"
P_TRA = RAW / "trafico.csv"
P_PEAJES = ROOT / "data" / "raw" / "mtc_flujo_peajes" / "unidades_peaje_2024-2025.geojson"

OUT_ACC = PROC / "ositran_accidentes.csv"
OUT_TRA = PROC / "ositran_trafico.csv"
OUT_TRAMOS = PROC / "ositran_tramos_geocod.csv"
OUT_PEAJES = PROC / "ositran_peajes_geo.json"

GEO_CACHE_FILE = PROC / "dashboard" / "geocode_cache.json"

# limites geograficos de Peru (generosos)
LON_MIN, LON_MAX = -85.0, -66.0
LAT_MIN, LAT_MAX = -20.5, 0.5
MAX_SEG_KM = 350.0


def _dentro_peru(lon, lat):
    return LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _load_peajes():
    gj = json.loads(P_PEAJES.read_text(encoding="utf-8"))
    out = {}
    for f in gj.get("features", []):
        p = f.get("properties") or {}
        name = p.get("NOMBRE") or p.get("nombre")
        c = f.get("geometry", {}).get("coordinates")
        if name and c:
            out[_norm(name)] = (float(c[0]), float(c[1]), str(name))
    return out


def _cargar_cache():
    try:
        return json.loads(GEO_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _guardar_cache(cache):
    GEO_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GEO_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _foton(place):
    q = urllib.parse.quote(place.replace(",", " ").strip())
    url = f"https://photon.komoot.io/api/?q={q}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "SIPAT-ositran/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("features"):
        return None
    coords = data["features"][0]["geometry"]["coordinates"]
    return (float(coords[0]), float(coords[1]))


def _extremos(tramo):
    """Devuelve lista de tokens candidatos a lugar de un tramo."""
    t = re.sub(r"sector\s*\d+\s*[:.-]*", "", str(tramo), flags=re.I)
    parts = re.split(r"[-–—:()]| y | e ", t)
    return [x.strip().rstrip(".") for x in parts if x.strip()]


def _coords_por_token(tokens, peajes, cache):
    """Geocodifica una vez cada token unico (peajes MTC -> Photon cacheado)."""
    sin_resolver = [t for t in tokens if t not in cache and _norm(t) not in peajes]

    def _resolver(t):
        for k in peajes:
            if _norm(t) in k or k in _norm(t):
                return t, peajes[k][:2]
        try:
            out = _foton(t)
        except Exception:
            out = None
        if out and not _dentro_peru(out[0], out[1]):
            out = None
        return t, out

    with ThreadPoolExecutor(max_workers=5) as ex:
        for t, out in ex.map(_resolver, sin_resolver):
            cache[t] = list(out) + [t] if out else None

    def _coord(t):
        n = _norm(t)
        if n in peajes:
            return peajes[n][:2]
        v = cache.get(t)
        if v and _dentro_peru(float(v[0]), float(v[1])):
            return (float(v[0]), float(v[1]))
        return None

    return {t: _coord(t) for t in tokens}


def _segmento(tramo, coords):
    """Geocodifica los 2 extremos del tramo; devuelve (lon0,lat0,lon1,lat1) o None."""
    toks = _extremos(tramo)
    pts = []
    for tk in toks:
        c = coords.get(tk)
        if c and _dentro_peru(c[0], c[1]):
            pts.append(c)
        if len(pts) >= 2:
            break
    if len(pts) < 2:
        return None
    lon0, lat0, lon1, lat1 = pts[0][0], pts[0][1], pts[1][0], pts[1][1]
    if abs(lon0 - lon1) < 0.02 and abs(lat0 - lat1) < 0.02:
        return None
    if _len_km(lon0, lat0, lon1, lat1) > MAX_SEG_KM:
        return None
    return lon0, lat0, lon1, lat1


def _len_km(lon0, lat0, lon1, lat1):
    p0, p1 = np.radians([lat0, lon0]), np.radians([lat1, lon1])
    a = np.sin((p1[0] - p0[0]) / 2) ** 2 + np.cos(p0[0]) * np.cos(p1[0]) * np.sin((p1[1] - p0[1]) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def _int(x):
    try:
        return int(float(str(x).replace('"', "").strip()))
    except (ValueError, TypeError):
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true", help="re-descargar CSVs de PNDA")
    a = ap.parse_args()

    if a.raw:
        import urllib.request as u
        for name, url in (
            ("accidentes.csv", "https://www.datosabiertos.gob.pe/sites/default/files/202603-PDE-REP-00204.csv"),
            ("trafico.csv", "https://www.datosabiertos.gob.pe/sites/default/files/202603-PDE-REP-00201.csv"),
        ):
            req = u.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with u.urlopen(req, timeout=180) as r:
                (RAW / name).write_bytes(r.read())
            print("descargado", name)

    acc = pd.read_csv(P_ACC, sep=";", low_memory=False)
    tra = pd.read_csv(P_TRA, sep=";", low_memory=False)

    acc["cant_accidentes"] = acc["CANTIDAD ACCIDENTES"].map(_int)
    acc["cant_afectados"] = acc["CANTIDAD AFECTADOS"].map(_int)
    acc["cant_vehinvolucrados"] = acc["CANTIDAD VEHINVOLUCRADOS"].map(_int)
    acc_clean = acc.rename(columns={
        "ANIO": "anio", "MES": "mes", "ENTIDAD_PRESTADORA": "entidad",
        "CONCESION": "concesion", "SIGLAS": "siglas", "TIPO_ACCIDENTE": "tipo",
        "CAUSA_ACCIDENTE": "causa", "TIPO_VIA": "tipo_via", "RUTA": "ruta",
        "TRAMO": "tramo"})
    acc_clean.to_csv(OUT_ACC, index=False, encoding="utf-8-sig")

    tra["cant_vehiculos"] = tra["CANTIDAD VEHICULOS"].map(_int)
    tra_clean = tra.rename(columns={
        "ANIO": "anio", "MES": "mes", "ENTIDAD_PRESTADORA": "entidad",
        "CONCESION": "concesion", "SIGLAS": "siglas", "PEAJE": "peaje",
        "CLASE_VEHICULO": "clase", "TIPO_VEHICULO": "tipo_vehiculo"})
    tra_clean.to_csv(OUT_TRA, index=False, encoding="utf-8-sig")

    peajes = _load_peajes()
    report = {}

    # --- trafico por peaje con coordenadas ---
    g_tra = tra_clean.groupby("peaje", as_index=False)["cant_vehiculos"].sum()
    peajes_geo = []
    n_match = 0
    for _, row in g_tra.iterrows():
        n = _norm(row["peaje"])
        c = peajes.get(n)
        if c is None:
            for k in peajes:
                if n in k or k in n:
                    c = peajes[k]
                    break
        if c:
            peajes_geo.append({"peaje": row["peaje"], "lon": c[0], "lat": c[1],
                               "vehiculos_2019_2025": int(row["cant_vehiculos"])})
            n_match += 1
    (PROC / "ositran_peajes_geo.json").write_text(
        json.dumps({"n_peajes": len(peajes_geo), "peajes": peajes_geo}, ensure_ascii=False), encoding="utf-8")
    report["trafico_peajes"] = {"n": len(g_tra), "con_coordenadas": n_match}

    # --- tramos de accidentes geocodificados ---
    g_tr = acc_clean.groupby(["siglas", "tramo"], as_index=False)["cant_accidentes"].sum()
    cache = _cargar_cache()
    n_bad = sum(1 for v in cache.values()
                if v and isinstance(v, (list, tuple)) and len(v) >= 2
                and not _dentro_peru(float(v[0]), float(v[1])))
    cache = {k: v for k, v in cache.items()
             if not (v and isinstance(v, (list, tuple)) and len(v) >= 2
                     and not _dentro_peru(float(v[0]), float(v[1])))}
    _guardar_cache(cache)
    report["cache_limpiada"] = n_bad
    tokens = {tk for t in g_tr["tramo"].dropna().unique() for tk in _extremos(t)}
    coords = _coords_por_token(list(tokens), peajes, cache)
    _guardar_cache(cache)
    report["tokens_geocod"] = {"n": len(tokens),
                               "resueltos": sum(1 for v in coords.values() if v)}
    rows = []
    n_ok = 0
    for _, row in g_tr.iterrows():
        seg = _segmento(row["tramo"], coords)
        if seg is None:
            continue
        lon0, lat0, lon1, lat1 = seg
        km = _len_km(lon0, lat0, lon1, lat1)
        rows.append({
            "siglas": row["siglas"], "tramo": row["tramo"],
            "accidentes_2019_2025": int(row["cant_accidentes"]),
            "lon0": round(lon0, 5), "lat0": round(lat0, 5),
            "lon1": round(lon1, 5), "lat1": round(lat1, 5),
            "longitud_km": round(float(km), 2),
        })
        n_ok += 1
    df_tr = pd.DataFrame(rows)
    df_tr.to_csv(OUT_TRAMOS, index=False, encoding="utf-8-sig")
    report["tramos"] = {"n": len(g_tr), "geocodificados": n_ok}
    report["accidentes_geocod"] = int(df_tr["accidentes_2019_2025"].sum()) if n_ok else 0

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("salidas:", OUT_ACC.name, OUT_TRA.name, OUT_TRAMOS.name, "ositran_peajes_geo.json")


if __name__ == "__main__":
    main()
