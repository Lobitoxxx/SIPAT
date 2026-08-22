"""Capa predictiva: modelo NegBin de Fase 1 aplicado a rutas OSRM.

- `RiesgoPredictivo`: re-entrena el NegBin de Fase 1 sobre `dataset_modelo.csv`
  (3,750 tramos; misma especificacion que `modelo_glm.py`), predice siniestros
  por tramo y empalma una ruta OSRM a los tramos modelados (cKDTree) para dar
  un riesgo predictivo por km y por segmentos de 5 km.
- `tipos_incidente`: composicion historica (tipo/causa/clima/gravedad) de los
  accidentes en el buffer de la ruta -> el aviso "que puede pasar".

Uso:
  from prediccion import get_predictor, tipos_incidente
  p = get_predictor()
  res = p.predecir_ruta(geometry)        # geometry: lista de [lon, lat]
"""

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from riesgo_red import _xy, _haversine

P_MODELO = ROOT / "data" / "processed" / "dataset_modelo.csv"


def _features(df):
    """Replica la especificacion de features de Fase 1 (modelo_glm.py)."""
    d = df.copy()
    med_vel = d["vel_proy"].median()
    med_car = d["carriles"].median()
    d["vel_proy"] = d["vel_proy"].fillna(med_vel)
    d["carriles"] = d["carriles"].fillna(med_car)
    d["sinuosidad"] = d["sinuosidad"].clip(upper=d["sinuosidad"].quantile(0.99))
    d["log_ingemmet"] = np.log1p(d["dist_ingemmet_km"])
    d["log_peajes"] = np.log1p(d["dist_peajes_km"])
    d["log_cine"] = np.log1p(d["dist_cinemometros_km"])
    reg = pd.get_dummies(d["region"], prefix="reg", drop_first=True)
    top = pd.get_dummies(d["topografia"], prefix="top", drop_first=True)
    X = pd.concat([reg, top], axis=1).astype(float)
    X["carriles"] = d["carriles"]
    X["vel_proy"] = d["vel_proy"]
    X["sinuosidad"] = d["sinuosidad"]
    X["log_ingemmet"] = d["log_ingemmet"]
    X["log_peajes"] = d["log_peajes"]
    X["log_cine"] = d["log_cine"]
    X["cinemometros_c10km"] = d["cinemometros_c10km"]
    X["sup_buena"] = d["sup_buena"]
    X["es_panamericana"] = d["es_panamericana"]
    return X


@lru_cache(maxsize=1)
def _fit():
    """Entrena NegBin (Fase 1) y devuelve (modelo, pred por tramo)."""
    d = pd.read_csv(P_MODELO, low_memory=False)
    X = _features(d)
    y = d["y_onsv"].values.astype(float)
    expo = np.log(d["expo_km"].values)
    Xc = sm.add_constant(X)
    m = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=1.0), offset=expo).fit()
    alpha = m.scale
    m2 = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=alpha), offset=expo).fit()
    pred = m2.predict(Xc, offset=expo)
    return m2, pred


class RiesgoPredictivo:
    def __init__(self, max_dist_km=2.0):
        self.max_dist_km = max_dist_km
        self.modelo, pred = _fit()
        d = pd.read_csv(P_MODELO, low_memory=False)
        self.tramos = d
        # tasa esperada por km por tramo modelado
        long = d["long_km"].replace(0, np.nan).fillna(1.0)
        self.tasa = pred / long.values
        lon = d["lon_mid"].values
        lat = d["lat_mid"].values
        self.xy = np.column_stack(_xy(lon, lat))
        self.tree = cKDTree(self.xy)

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

    def _snap(self, sample):
        """Tasa predictiva (siniestros/km) para cada punto muestreado de la ruta."""
        sx, sy = _xy(sample[:, 0], sample[:, 1])
        pts = np.stack([sx, sy], axis=1)
        r = self.tree.query(pts, k=1, workers=-1)
        dist_m, idx = r
        ok = dist_m <= self.max_dist_km * 1000
        tasas = np.where(ok, self.tasa[idx], np.nan)
        return tasas, idx, ok

    def predecir_ruta(self, geometry, segment_km=5.0):
        """Riesgo predictivo del modelo NegBin a lo largo de una ruta.

        Devuelve tasa media predictiva (siniestros/km), cobertura de la red
        modelada y tasa por segmentos de ~segment_km (alineado al perfil).
        """
        sample = self._sample(geometry)
        if len(sample) < 2:
            return {"cobertura_pct": 0.0, "pred_siniestros_km": 0.0, "n_tramos": 0, "segmentos": []}
        tasas, idx, ok = self._snap(sample)
        cobertura = float(np.mean(ok)) * 100.0 if len(ok) else 0.0
        segs = []
        dist = np.zeros(len(sample))
        for i in range(1, len(sample)):
            dist[i] = dist[i - 1] + _haversine(sample[i - 1, 0], sample[i - 1, 1], sample[i, 0], sample[i, 1])
        total = dist[-1]
        n_seg = max(1, int(np.ceil(total / (segment_km * 1000.0))))
        for k in range(n_seg):
            lo = k * segment_km * 1000.0
            hi = min((k + 1) * segment_km * 1000.0, total)
            mask = (dist >= lo) & (dist <= hi)
            t = tasas[mask]
            if not len(t):
                continue
            t_ok = t[~np.isnan(t)]
            segs.append({
                "km0": float(round(lo / 1000.0, 1)),
                "km1": float(round(hi / 1000.0, 1)),
                "pred_siniestros_km": float(round(t_ok.mean(), 4)) if len(t_ok) else 0.0,
                "cobertura": float(round(np.mean(~np.isnan(t)) * 100.0, 0)),
            })
        medio = float(np.nanmean(tasas)) if np.any(~np.isnan(tasas)) else 0.0
        return {
            "cobertura_pct": round(cobertura, 1),
            "pred_siniestros_km": round(medio, 4),
            "n_tramos": int(len(np.unique(idx[ok]))) if ok.any() else 0,
            "segmentos": segs,
        }


@lru_cache(maxsize=1)
def get_predictor():
    return RiesgoPredictivo()


def tipos_incidente(accidentes):
    """Composicion historica de los accidentes en el buffer de la ruta."""
    if not accidentes:
        return {"total": 0, "fallecidos": 0, "heridos": 0,
                "top_tipos": [], "top_causas": [], "top_climas": []}
    df = pd.DataFrame(accidentes)
    n = len(df)

    def _top(col, k, dropna=True):
        s = df[col].astype(str).str.strip()
        if dropna:
            s = s[s.str.len() > 0]
        vc = s.value_counts().head(k)
        return [{"valor": str(x), "n": int(c), "pct": round(100 * c / n, 1)} for x, c in vc.items()]

    return {
        "total": n,
        "fallecidos": int(pd.to_numeric(df.get("fallecidos", 0), errors="coerce").fillna(0).sum()),
        "heridos": int(pd.to_numeric(df.get("lesionados", 0), errors="coerce").fillna(0).sum()),
        "top_tipos": _top("tipo", 5),
        "top_causas": _top("causa", 5),
        "top_climas": _top("clima", 3),
    }


if __name__ == "__main__":
    p = get_predictor()
    print(f"modelo NegBin ok | {len(p.tramos)} tramos | "
          f"tasa media={p.tasa.mean():.4f} sini/km")
    test = [(-77.02824, -12.04637), (-76.5, -11.9), (-76.0, -12.0), (-75.5, -12.1), (-75.20452, -12.06513)]
    import json
    print(json.dumps(p.predecir_ruta(test), indent=1, ensure_ascii=False))
