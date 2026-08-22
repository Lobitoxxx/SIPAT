"""Capa de riesgo historico: accidentes geocodificados (ONSV + SUTRAN) sobre la red.

Provee un indice espacial (equirectangular local + scipy cKDTree) para contar
accidentes en un buffer alrededor de una geometria de ruta (OSRM) y calcular un
score de riesgo por km.

Uso:
  from riesgo_red import RiesgoIndex
  idx = RiesgoIndex()                 # carga una vez (cachea en memoria)
  res = idx.score_route(geometry)     # geometry: lista de [lon, lat]
"""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
P_ONSV = ROOT / "data" / "processed" / "onsv_nacional_geocod.csv"
P_SUTRAN = ROOT / "data" / "processed" / "sutran_accidentes_geocod.csv"
P_ALERTAS_HIST = ROOT / "data" / "processed" / "dashboard" / "sutran_alertas_historico.json"
P_OSITRAN = ROOT / "data" / "processed" / "ositran_tramos_geocod.csv"
P_OSITRAN_ACC = ROOT / "data" / "processed" / "ositran_accidentes.csv"
P_TRAFICO = ROOT / "data" / "processed" / "ositran_trafico.csv"
P_PEAJES = ROOT / "data" / "processed" / "ositran_peajes_geo.json"

LAT0 = -10.0  # latitud de referencia para la proyeccion equirectangular (Peru)
M_LAT = 110574.0
M_LON = 111320.0 * np.cos(np.radians(LAT0))

W_FALL = 3.0  # peso de gravedad: fallecidos
W_LES = 1.0   # peso de gravedad: lesionados

PESO_ALERTA_ESTADO = {"INTERRUMPIDO": 2.0, "RESTRINGIDO": 1.0, "NORMAL": 0.3}

RADIO_PEAJES_KM = 15.0      # radio para peajes con trafico OSITRAN
TRAFICO_MAX_PESO = 0.5      # tope de contribucion por peaje (aadt/100000)


def aadt_peajes():
    """Trafico medio diario (AADT) por peaje = ultimo anio disponible / 365."""
    if not P_TRAFICO.exists():
        return {}
    tra = pd.read_csv(P_TRAFICO, usecols=["anio", "peaje", "cant_vehiculos"], low_memory=False)
    tra["anio"] = pd.to_numeric(tra["anio"], errors="coerce").fillna(0)
    g = tra.groupby(["peaje", "anio"], as_index=False)["cant_vehiculos"].sum()
    g["aadt"] = g["cant_vehiculos"] / 365.0
    ult = g.sort_values("anio").groupby("peaje").tail(1)
    return dict(zip(ult["peaje"], ult["aadt"]))


def factor_temporal(dt=None):
    """Factor multiplicativo del riesgo segun dia/hora de salida (EDA ONSV).

    Pico de siniestros: sabados y ~18 h; nocturno mas peligroso.
    Si `dt` es None (o fuera de rango) devuelve 1.0 (factor neutro).
    """
    if dt is None:
        return 1.0
    try:
        f = 1.0
        if dt.weekday() == 5:      # sabado
            f *= 1.25
        elif dt.weekday() == 6:    # domingo
            f *= 1.10
        h = dt.hour + dt.minute / 60.0
        if h >= 19 or h < 5:       # noche (19h-05h)
            f *= 1.30
        elif 5 <= h < 8:           # madrugada de transito
            f *= 1.05
        return round(f, 3)
    except (AttributeError, TypeError, ValueError):
        return 1.0


def _xy(lon, lat):
    return ((lon - (-70.0)) * M_LON, (lat - LAT0) * M_LAT)


def _haversine(lon1, lat1, lon2, lat2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


class RiesgoIndex:
    def __init__(self, radius_km=1.0, include_alertas_hist=True, include_ositran=True,
                 include_trafico=True):
        self.radius_km = radius_km
        self.onsv = self._load_onsv()
        self.sutran = self._load_sutran()
        df = pd.concat([self.onsv, self.sutran], ignore_index=True)
        if include_ositran:
            ositran = self._load_ositran()
            if len(ositran):
                df = pd.concat([df, ositran], ignore_index=True)
        for c in ("fecha", "hora", "tipo", "ruta", "depto", "provincia", "distrito",
                  "clima", "causa", "causa_especifica", "superficie", "via", "red",
                  "tramo", "concesion"):
            df[c] = df[c].fillna("")
        df["x"], df["y"] = _xy(df["lon"], df["lat"])
        self.xy = df[["x", "y"]].to_numpy()
        self.acc = df.to_dict("records")
        self.tree = cKDTree(self.xy)
        self.alertas_hist = []
        self.alertas_hist_xy = np.empty((0, 2))
        self.alertas_hist_tree = None
        if include_alertas_hist:
            self._load_alertas_hist()
        self.trafico = []
        self.trafico_xy = np.empty((0, 2))
        self.trafico_tree = None
        if include_trafico:
            self._load_trafico()

    def _load_alertas_hist(self):
        try:
            hist = json.loads(P_ALERTAS_HIST.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, AttributeError):
            return
        rows = [a for a in hist if abs(a.get("lat", 0)) > 0.01 and abs(a.get("lon", 0)) > 0.01]
        if not rows:
            return
        self.alertas_hist = rows
        xy = np.stack([_xy(a["lon"], a["lat"]) for a in rows])
        self.alertas_hist_xy = xy
        self.alertas_hist_tree = cKDTree(xy)

    def _load_ositran(self):
        """Puntos sinteticos sobre corredores concesionados (accidentes OSITRAN).

        Distribuye un punto cada ~1 km a lo largo de cada tramo geocodificado;
        el peso reparte el total de accidentes del tramo entre sus puntos y cada
        punto lleva la descripcion agregada del tramo (tipo/causa/clima top).
        """
        if not P_OSITRAN.exists():
            return pd.DataFrame()
        tramos = pd.read_csv(P_OSITRAN)
        desc = {}
        if P_OSITRAN_ACC.exists():
            acc = pd.read_csv(P_OSITRAN_ACC, usecols=["siglas", "tramo", "tipo", "causa", "CLIMA"],
                              low_memory=False)
            def _moda(s):
                m = s.mode(dropna=True)
                return str(m.iloc[0]) if len(m) else ""
            g = (acc.groupby(["siglas", "tramo"])
                 .agg(total=("tipo", "size"), top_tipo=("tipo", _moda),
                      top_causa=("causa", _moda), clima_frecuente=("CLIMA", _moda))
                 .reset_index())
            desc = {(r["siglas"], r["tramo"]): r.to_dict() for _, r in g.iterrows()}
        rows = []
        for _, t in tramos.iterrows():
            n = max(1, int(t["longitud_km"]))
            lons = np.linspace(t["lon0"], t["lon1"], n + 1)[:-1]
            lats = np.linspace(t["lat0"], t["lat1"], n + 1)[:-1]
            peso = t["accidentes_2019_2025"] / n
            d = desc.get((t["siglas"], t["tramo"]), {})
            rows.append(pd.DataFrame({
                "lon": lons, "lat": lats, "peso": peso,
                "fuente": "OSITRAN", "fallecidos": 0, "lesionados": 0,
                "fecha": "", "tipo": d.get("top_tipo", ""),
                "ruta": t["siglas"], "km": "",
                "depto": "", "clima": d.get("clima_frecuente", ""),
                "causa": d.get("top_causa", ""), "via": "",
                "tramo": t["tramo"], "concesion": "",
                "total_tramo": int(d.get("total", t["accidentes_2019_2025"])),
            }))
        if not rows:
            return pd.DataFrame()
        return pd.concat(rows, ignore_index=True)

    def _load_onsv(self):
        df = pd.read_csv(P_ONSV, low_memory=False, usecols=[
            "lon", "lat", "CANTIDAD DE FALLECIDOS", "CANTIDAD DE LESIONADOS",
            "FECHA SINIESTRO", "HORA SINIESTRO", "CLASE SINIESTRO", "('ruta',)", "km_red",
            "DEPARTAMENTO", "PROVINCIA", "DISTRITO", "CONDICIÓN CLIMÁTICA",
            "CAUSA FACTOR PRINCIPAL", "CAUSA ESPECÍFICA", "SUPERFICIE DE CALZADA", "TIPO DE VÍA", "RED VIAL"])
        df = df.rename(columns={"CANTIDAD DE FALLECIDOS": "fallecidos",
                                "CANTIDAD DE LESIONADOS": "lesionados"})
        df = df.dropna(subset=["lon", "lat"]).copy()
        df["fuente"] = "ONSV"
        df["peso"] = df["fallecidos"].fillna(0) * W_FALL + df["lesionados"].fillna(0) * W_LES + 1.0
        for c, out in [("FECHA SINIESTRO", "fecha"), ("HORA SINIESTRO", "hora"),
                       ("CLASE SINIESTRO", "tipo"), ("('ruta',)", "ruta"),
                       ("km_red", "km"), ("DEPARTAMENTO", "depto"), ("PROVINCIA", "provincia"),
                       ("DISTRITO", "distrito"), ("CONDICIÓN CLIMÁTICA", "clima"),
                       ("CAUSA FACTOR PRINCIPAL", "causa"), ("CAUSA ESPECÍFICA", "causa_especifica"),
                       ("SUPERFICIE DE CALZADA", "superficie"), ("TIPO DE VÍA", "via"), ("RED VIAL", "red")]:
            df[out] = df[c].fillna("").astype(str).str.strip()
        df["km"] = pd.to_numeric(df["km"].replace("", np.nan), errors="coerce")
        return df[["lon", "lat", "peso", "fuente", "fallecidos", "lesionados", "fecha", "hora",
                   "tipo", "ruta", "km", "depto", "provincia", "distrito", "clima", "causa",
                   "causa_especifica", "superficie", "via", "red"]]

    def _load_sutran(self):
        df = pd.read_csv(P_SUTRAN, low_memory=False, usecols=[
            "LONGITUD_GEO", "LATITUD_GEO", "FALLECIDOS", "HERIDOS", "FECHA",
            "MODALIDAD", "DEPARTAMENTO", "CODIGO_VIA", "KILOMETRO"])
        df = df.rename(columns={"LONGITUD_GEO": "lon", "LATITUD_GEO": "lat",
                                "FALLECIDOS": "fallecidos", "HERIDOS": "lesionados"})
        df = df.dropna(subset=["lon", "lat"]).copy()
        df["fallecidos"] = pd.to_numeric(df["fallecidos"], errors="coerce").fillna(0)
        df["lesionados"] = pd.to_numeric(df["lesionados"], errors="coerce").fillna(0)
        df["fuente"] = "SUTRAN"
        df["peso"] = df["fallecidos"].fillna(0) * W_FALL + df["lesionados"].fillna(0) * W_LES + 1.0
        df["fecha"] = (pd.to_datetime(df["FECHA"].astype(str), format="%Y%m%d", errors="coerce")
                       .dt.strftime("%d/%m/%Y").fillna(""))
        for c, out in [("MODALIDAD", "tipo"), ("DEPARTAMENTO", "depto"),
                       ("CODIGO_VIA", "ruta"), ("KILOMETRO", "km")]:
            df[out] = df[c].fillna("").astype(str).str.strip()
        df["km"] = pd.to_numeric(df["km"].replace("", np.nan), errors="coerce")
        df["hora"] = ""
        df["provincia"] = ""
        df["distrito"] = ""
        df["clima"] = ""
        df["causa"] = ""
        df["via"] = ""
        df["superficie"] = ""
        df["red"] = ""
        return df[["lon", "lat", "peso", "fuente", "fallecidos", "lesionados", "fecha", "hora",
                   "tipo", "ruta", "km", "depto", "provincia", "distrito", "clima", "causa",
                   "superficie", "via", "red"]]

    def _sample(self, geometry, step_m=500.0):
        pts = np.asarray(geometry, dtype=float)
        if len(pts) < 2:
            return pts
        dist = np.zeros(len(pts))
        for i in range(1, len(pts)):
            dist[i] = dist[i - 1] + _haversine(pts[i - 1, 0], pts[i - 1, 1], pts[i, 0], pts[i, 1])
        n = max(2, int(dist[-1] // step_m) + 1)
        cuts = np.linspace(0, dist[-1], n)
        return np.stack([np.interp(cuts, dist, pts[:, 0]), np.interp(cuts, dist, pts[:, 1])], axis=1)

    def points_near_route(self, geometry):
        """Indices de accidentes dentro del buffer de la ruta."""
        sample = self._sample(geometry)
        sx, sy = _xy(sample[:, 0], sample[:, 1])
        cand = self.tree.query_ball_point(np.stack([sx, sy], axis=1), self.radius_km * 1000)
        return set(i for c in cand for i in c)

    def matched(self, geometry):
        """Lista de accidentes (dicts) dentro del buffer, para mapas."""
        out = []
        for i in sorted(self.points_near_route(geometry)):
            r = dict(self.acc[i])
            r["i"] = i
            out.append(r)
        return out

    def points_near_alertas_hist(self, geometry):
        """Indices de alertas historicas dentro del buffer de la ruta."""
        if self.alertas_hist_tree is None:
            return set()
        sample = self._sample(geometry)
        sx, sy = _xy(sample[:, 0], sample[:, 1])
        cand = self.alertas_hist_tree.query_ball_point(np.stack([sx, sy], axis=1), self.radius_km * 1000)
        return set(i for c in cand for i in c)

    def alertas_hist_matched(self, geometry):
        out = []
        for i in sorted(self.points_near_alertas_hist(geometry)):
            r = dict(self.alertas_hist[i])
            r["i"] = f"A{i}"
            out.append(r)
        return out

    def perfil_segmentos(self, geometry, segment_km=5.0, step_m=250.0):
        """Score local por tramos de ~segment_km a lo largo de la ruta.

        Devuelve lista de dicts: km0, km1, score_km, accidentes, lat, lon
        (centroide del segmento, para graficar el perfil).
        """
        sample = self._sample(geometry, step_m=step_m)
        if len(sample) < 2:
            return []
        dist = np.zeros(len(sample))
        for i in range(1, len(sample)):
            dist[i] = dist[i - 1] + _haversine(sample[i - 1, 0], sample[i - 1, 1], sample[i, 0], sample[i, 1])
        total = dist[-1]
        n_seg = max(1, int(np.ceil(total / (segment_km * 1000.0))))
        perfil = []
        for k in range(n_seg):
            lo = k * segment_km * 1000.0
            hi = min((k + 1) * segment_km * 1000.0, total)
            mask = (dist >= lo) & (dist <= hi)
            chunk = sample[mask]
            if len(chunk) < 2:
                continue
            sc = self.score_route(chunk)
            centro = chunk[len(chunk) // 2]
            perfil.append({
                "km0": round(lo / 1000.0, 1),
                "km1": round(hi / 1000.0, 1),
                "score_km": sc["score_km"],
                "accidentes": sc["accidentes_buffer"],
                "lat": round(float(centro[1]), 5),
                "lon": round(float(centro[0]), 5),
            })
        return perfil

    def _load_trafico(self):
        """Peajes con trafico vehicular (OSITRAN) como senal de exposicion.

        Guarda lat/lon + aadt (vehiculos/dia, ultimo anio disponible). El peso
        de exposicion es aadt/100000 con tope para no dominar el score.
        """
        try:
            peajes = json.loads(P_PEAJES.read_text(encoding="utf-8"))["peajes"]
        except (json.JSONDecodeError, OSError, AttributeError, KeyError):
            return
        aadt = aadt_peajes()
        rows = [p for p in peajes if abs(p.get("lat", 0)) > 0.01 and abs(p.get("lon", 0)) > 0.01]
        for p in rows:
            p["aadt"] = float(aadt.get(str(p["peaje"]), 0.0))
            p["peso_trafico"] = min(p["aadt"] / 100000.0, TRAFICO_MAX_PESO)
        rows = [p for p in rows if p["aadt"] > 0]
        if not rows:
            return
        self.trafico = rows
        self.trafico_xy = np.stack([_xy(p["lon"], p["lat"]) for p in rows])
        self.trafico_tree = cKDTree(self.trafico_xy)

    def points_near_trafico(self, geometry):
        """Indices de peajes (trafico) dentro de RADIO_PEAJES_KM de la ruta."""
        if self.trafico_tree is None:
            return set()
        sample = self._sample(geometry, step_m=1000.0)
        sx, sy = _xy(sample[:, 0], sample[:, 1])
        cand = self.trafico_tree.query_ball_point(np.stack([sx, sy], axis=1), RADIO_PEAJES_KM * 1000)
        return set(i for c in cand for i in c)

    def score_route(self, geometry, longitud_km=None):
        """Score de riesgo de una ruta (normalizado por km).

        Incluye accidentes historicos (ONSV+SUTRAN+OSITRAN), alertas SUTRAN
        archivadas (zonas de incidentes recurrentes) y el trafico vehicular
        (exposicion OSITRAN) como senal adicional.
        """
        if longitud_km is None:
            p = np.asarray(geometry, dtype=float)
            longitud_km = sum(
                _haversine(p[i - 1, 0], p[i - 1, 1], p[i, 0], p[i, 1]) for i in range(1, len(p))
            ) / 1000.0
        idx = self.points_near_route(geometry)
        n = len(idx)
        grav = sum(self.acc[i]["peso"] for i in idx)
        n_onsv = sum(1 for i in idx if self.acc[i]["fuente"] == "ONSV")
        n_sutran = sum(1 for i in idx if self.acc[i]["fuente"] == "SUTRAN")
        n_ositran = sum(1 for i in idx if self.acc[i]["fuente"] == "OSITRAN")
        score_km = (n + 0.5 * grav) / max(longitud_km, 1e-6)
        idx_a = self.points_near_alertas_hist(geometry)
        n_alertas_hist = len(idx_a)
        peso_alertas = sum(PESO_ALERTA_ESTADO.get(self.alertas_hist[i]["estado"], 0.5)
                           for i in idx_a)
        alertas_hist_km = peso_alertas / max(longitud_km, 1e-6)
        idx_t = self.points_near_trafico(geometry)
        aadts = [self.trafico[i]["aadt"] for i in idx_t]
        trafico_km = sum(self.trafico[i]["peso_trafico"] for i in idx_t) if idx_t else 0.0
        aadt_max = max(aadts) if aadts else 0.0
        return {
            "longitud_km": round(longitud_km, 2),
            "accidentes_buffer": n,
            "accidentes_onsv": n_onsv,
            "accidentes_sutran": n_sutran,
            "accidentes_ositran": n_ositran,
            "gravedad_ponderada": round(grav, 1),
            "alertas_hist_buffer": n_alertas_hist,
            "alertas_hist_km": round(alertas_hist_km, 4),
            "trafico_km": round(trafico_km, 4),
            "peajes_buffer": len(idx_t),
            "aadt_max": int(aadt_max),
            "score_km": round(score_km + alertas_hist_km + trafico_km, 4),
        }


@lru_cache(maxsize=1)
def get_index():
    return RiesgoIndex()


if __name__ == "__main__":
    idx = get_index()
    print(f"indice: {len(idx.xy)} accidentes en memoria")
    test = [(-77.02824, -12.04637), (-76.5, -11.9), (-76.0, -12.0), (-75.5, -12.1), (-75.20452, -12.06513)]
    print(idx.score_route(test))
