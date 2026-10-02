"""Empirical Bayes (Hauer) para tramos: cuánto de un exceso es real y cuánto es ruido.

POR QUÉ ESTE MÓDULO EXISTE
---------------------------
`build_puntos_negros.py` usaba `siniestros_total_km` —el observado— como
"predicción" del Empirical Bayes:

    pred_km = obs_km
    w_eb    = pred_total / (pred_total + 1)
    eb_km   = w_eb * obs_km + (1 - w_eb) * pred_km   ==   obs_km

O sea `eb_km == obs_km` para toda fila, `exceso_eb == 0` para toda fila, y los
criterios `exceso_eb > 1` y `(obs-pred)/pred > 2` **nunca se cumplían**. Dos de los
tres criterios de punto negro eran código muerto.

EL MODELO QUE SÍ DICE ALGO
---------------------------
Gamma-Poisson (Hauer, el esquema de ASHAT / Danish Road Directorate):

    y_i | λ_i ~ Poisson(λ_i · km_i)          # dispersión de Poisson: es real
    λ_i      ~ Gamma(shape=k, rate=k/μ_g)    # prior del grupo g: media μ_g, var μ_g²/k

La posterior de la tasa del tramo i es

    post_km = (y_i + k·μ_g) / (km_i + k)
            = w · obs_km + (1 - w) · μ_g        con   w = km_i / (km_i + k)

`w` es el peso de la observación sobre el prior: un tramo largo pesa más que uno
corto, y `k` es la "fuerza" del prior medida en kilómetros. Si `k → ∞` no hay
contracción (no se detecta sobredispersión) y `post_km = obs_km`; si `k → 0` todo
se va al promedio del grupo. Ese es el comportamiento correcto, no el bug.

El prior se estima **leave-one-out** (sin el propio tramo): usar la tasa media de
la región *incluyendo* el tramo que se quiere juzgar filtra el propio dato y
subestima el exceso. Con una sola observación eso es exactamente la regresión a la
media que Bayes aplica a propósito, y sin dejar fuera el tramo el sesgo se va a 0.

Nada aquí está hardcodeado: `prior_strength_km` sale de la sobredispersión medida
en los datos y la estrategia de días/tolerancias vive en `deduplicacion_eventos.py`.
"""
from __future__ import annotations

import warnings
from typing import Optional, Tuple

import numpy as np
import pandas as pd

__all__ = [
    "prior_por_grupo_loo",
    "prior_strength_km",
    "contraccion_eb",
    "eb_sobre_tramos",
]

_EPS = 1e-12


def prior_por_grupo_loo(
    df: pd.DataFrame,
    grupo: str,
    col_conteo: str = "siniestros_total",
    col_km: str = "long_km",
) -> pd.Series:
    """Tasa previa por grupo, dejando fuera el tramo evaluado (leave-one-out).

    Devuelve sigmoidos/km. Cuando el grupo tiene un único tramo (o su km residual
    es ~0) cae al prior global leave-one-out, para que nunca sea NaN.
    """
    obs = df[col_conteo].to_numpy(dtype=float)
    km = np.maximum(df[col_km].to_numpy(dtype=float), _EPS)

    obs_g = df.groupby(grupo)[col_conteo].transform("sum").to_numpy(dtype=float)
    km_g = df.groupby(grupo)[col_km].transform("sum").to_numpy(dtype=float)
    obs_t = obs_g.sum()
    km_t = km_g.sum()

    loo_num = obs_g - obs
    loo_den = km_g - km
    # Grupo degenerado (un solo tramo): prior global LOO.
    loo_num = np.where(loo_den > _EPS, loo_num, obs_t - obs)
    loo_den = np.where(loo_den > _EPS, loo_den, km_t - km)

    return pd.Series(loo_num / np.maximum(loo_den, _EPS), index=df.index, name="prior_km")


def prior_strength_km(
    tasa_km: np.ndarray,
    km: np.ndarray,
    prior_km: np.ndarray,
    min_km: float = 1.0,
) -> Tuple[float, float, float]:
    """Fuerza del prior `k` (en km) por el estimador de momentos de Gamma-Poisson.

    El modelo marginal, para un tramo de longitud `km_i` con prior de grupo
    `μ_i`, es

        y_i ~ NegBin(mu = μ_i·km_i,  var = μ_i·km_i + μ_i²·km_i²/k)

    y en **unidades de tasa** (por km), que es donde vive el `exceso_eb`:

        r_i = y_i/km_i,   E[r_i] = μ_i,   Var[r_i] = μ_i/km_i + μ_i²/k

    El término `μ_i/km_i` es la parte de Poisson (ruido puro de conteo) y el
    `μ_i²/k` es la sobredispersión que el prior tiene que portada. La `k` que
    buscamos es la que iguala la varianza medida con esa suma:

        k = <μ_i²> / ( <r_i − μ_i>²_ponderado  −  <μ_i/km_i> )

    Se mide la dispersión **alrededor del prior**, no alrededor de la media
    global: si se midiera alrededor de la media global, el `k`estimator absorbería
    las diferencias entre regiones y saldría inflado.

    Devuelve (k, varianza medida, varianza de Poisson esperada). Si la varianza
    medida no supera la de Poisson, no hay evidencia de sobredispersión y se
    devuelve `inf` → no se contrae nada. Esa es la respuesta honesta, no un parche.
    """
    tasa_km = np.asarray(tasa_km, dtype=float)
    km = np.asarray(km, dtype=float)
    prior_km = np.asarray(prior_km, dtype=float)

    validas = (
        np.isfinite(tasa_km)
        & np.isfinite(km)
        & np.isfinite(prior_km)
        & (km >= min_km)
        & (prior_km > 0)
    )
    if validas.sum() < 2:
        return float("inf"), float("nan"), float("nan")

    w = km[validas]          # peso = exposición: la tasa de un tramo corto es ruido
    mu = prior_km[validas]
    r = tasa_km[validas]
    sw = w.sum()

    resid = r - mu
    var_obs = float((w * resid**2).sum() / sw)
    var_pois = float((w * (mu / km[validas])).sum() / sw)
    media_mu2 = float((w * mu**2).sum() / sw)

    exceso = var_obs - var_pois
    if exceso <= _EPS:
        return float("inf"), var_obs, var_pois
    return media_mu2 / exceso, var_obs, var_pois


def contraccion_eb(
    obs_total: np.ndarray,
    km: np.ndarray,
    prior_km: np.ndarray,
    k: float,
) -> dict:
    """Contracción Gamma-Poisson. Devuelve peso, EB total/km y exceso relativo."""
    obs_total = np.asarray(obs_total, dtype=float)
    km = np.maximum(np.asarray(km, dtype=float), _EPS)
    prior_km = np.asarray(prior_km, dtype=float)

    w = km / (km + k)                       # peso de la observación
    # Posterior de la tasa: (y + k·μ) / (km + k) ≡ w·(y/km) + (1-w)·μ
    eb_km = (obs_total + k * prior_km) / (km + k)
    eb_total = eb_km * km
    exceso_rel = np.where(prior_km > _EPS, (eb_km - prior_km) / prior_km, 0.0)

    return {
        "w_eb": w,
        "eb_total": eb_total,
        "eb_km": eb_km,
        "exceso_rel": exceso_rel,
    }


def eb_sobre_tramos(
    df: pd.DataFrame,
    grupo: str = "region",
    col_conteo: str = "siniestros_total",
    col_km: str = "long_km",
    prefijo: str = "",
    min_km: float = 1.0,
    k_override: Optional[float] = None,
) -> pd.DataFrame:
    """Aplica prior LOO + contracción EB y devuelve `df` con las columnas EB.

    Columnas añadidas: `{p}prior_km`, `{p}k`, `{p}w_eb`, `{p}eb_total`, `{p}eb_km`,
    `{p}exceso_eb`, más `{p}var_obs` y `{p}var_poisson` para poder auditar el `k`.

    `k_override` permite fijar la fuerza del prior (tests, sensibilidad).

    Si `k` sale `inf` o NaN la salida **queda degenerada** (todo el prior o toda la
    observación). No es un detalle: se avisa con `warnings.warn` porque un
    `exceso_eb` idénticamente cero se lee como "no hay puntos negros" cuando en
    realidad es que el estimador no pudo medir nada.
    """
    out = df.copy()
    prior = prior_por_grupo_loo(out, grupo, col_conteo=col_conteo, col_km=col_km)
    km = np.maximum(out[col_km].to_numpy(dtype=float), _EPS)
    obs_total = out[col_conteo].to_numpy(dtype=float)

    k_auto, var_obs, var_pois = prior_strength_km(
        obs_total / km, km, prior.to_numpy(), min_km=min_km
    )
    k = float(k_override) if k_override is not None else k_auto

    if k_override is None and (not np.isfinite(k) or k <= 0):
        warnings.warn(
            "prior_strength_km no pudo estimar k (finito y > 0): "
            f"k={k}, var_obs={var_obs:.6g}, var_poisson={var_pois:.6g}. "
            "La salida EB es degenerada; revisa que haya más de un tramo por "
            "grupo con km >= min_km y con siniestros en el grupo.",
            RuntimeWarning,
            stacklevel=2,
        )

    eb = contraccion_eb(obs_total, km, prior.to_numpy(), k)

    out[f"{prefijo}prior_km"] = prior
    out[f"{prefijo}k"] = k
    out[f"{prefijo}var_obs"] = var_obs
    out[f"{prefijo}var_poisson"] = var_pois
    out[f"{prefijo}w_eb"] = eb["w_eb"]
    out[f"{prefijo}eb_total"] = eb["eb_total"]
    out[f"{prefijo}eb_km"] = eb["eb_km"]
    out[f"{prefijo}exceso_eb"] = eb["exceso_rel"]
    return out