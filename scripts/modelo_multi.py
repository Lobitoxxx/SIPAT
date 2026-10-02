#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modelos NegBin multi-fuente para el dashboard (tab5).

DEFECTOS CORREGIDOS (ver tests/test_modelo_multi.py)
---------------------------------------------------
1. **`y_total` sumaba universos incomparables.** Era
   `y_onsv + y_sutran + y_ositran`, pero las tres fuentes cubren ventanas
   temporales distintas (medidas sobre los datos reales):
   ONSV 2021-01-01→2025-12-28, SUTRAN 2020-01-01→2021-09-30, OSITRAN 2019→2026.
   Sumarlas mezclaba periodos y además contaba dos veces el mismo accidente,
   que ONSV y SUTRAN reportan por separado. Ahora `y_total` es la **unión
   deduplicada dentro de la ventana común** (`deduplicacion_eventos.py`).
2. **OSITRAN no se puede deduplicar**: `ositran_accidentes.csv` es un agregado
   por ruta/año/mes/causa, sin fecha de evento ni coordenadas. Por eso sale
   fuera de `y_total` y se modela como respuesta propia, con su cobertura
   declarada. Antes se colaba en el "total" sin poder defenderlo.
3. **Reparto de OSITRAN uniforme** con `round(total / n_tramos)`, cuando el
   comentario decía "proporcionalmente según su longitud". Ahora es
   proporcional a la longitud, con reparto por resto mayor para que la suma
   cuadre exactamente (antes se perdían accidentes por redondeo).
4. **`pseudo_r2` siempre `null`**: `result.prsquared` no existe en `GLMResults`.
   Ahora se calcula McFadden (1 − llf/llnull), que sí está, y se anota que es
   McFadden y no el pseudo-R² de Cox-Snell de los modelos discretos.
5. **Fallback silencioso**: si `sm.NegativeBinomial` fallaba, se caía a un
   `GLM(NegativeBinomial(alpha=1))` **con offset 0**, es decir sin exposición en
   km. Ahora el fallback conserva el offset y ambos caminos quedan registrados en
   la salida.
6. **Código muerto**: `offset` calculado y descartado; `sutran_by_ruta`
   calculado y nunca usado; `es_ruta_nacional` con una rama que comparaba una
   Serie vacía.

Salidas: `irrs_multi.csv`, `modelo_stats_multi.json`.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import deduplicacion_eventos as dedup
import panel_anual

DATASET = ROOT / "data" / "processed" / "dataset_modelo.csv"
OUT_DIR = ROOT / "data" / "processed" / "dashboard"

# Un NegBin con 13 covariables necesita un mínimo de observaciones con eventos;
# por debajo, la matriz de diseño no es identificable y los IRRs son ruido.
MIN_TRAMOS_CON_EVENTOS = 50

# Rejilla de `alpha` (NB2) para el maximum likelihood. Geométrica porque alpha es
# un parámetro de escala: el orden de magnitud importa más que el decimal.
ALPHA_GRID_MIN = 0.01
ALPHA_GRID_MAX = 50.0
ALPHA_GRID_PUNTOS = 60


def reparto_proporcional_a_longitud(
    tramos: pd.DataFrame,
    col_ruta: str,
    col_total: str,
    col_long: str = "long_km",
) -> pd.Series:
    """Reparte el total de cada ruta entre sus tramos **proporcional a longitud**.

    Redondeo por resto mayor: `round(total/n)` pierde accidentes (con 17
    repartidos en 5 tramos, `round(3.4)` deja 15 y el total no cuadra), y un
    reparto que no cuadra hace que la suma del agregado difiera del original.
    Con resto mayor la suma es exactamente el total y la asignación sigue siendo
    monótona en longitud: tramo más largo → más accidentes.
    """
    out = pd.Series(0, index=tramos.index, dtype=int)
    long = pd.to_numeric(tramos[col_long], errors="coerce").fillna(0).clip(lower=0)

    for ruta, idx in tramos.groupby(col_ruta).groups.items():
        total = float(pd.to_numeric(tramos.loc[idx, col_total], errors="coerce").fillna(0).iloc[0])
        if total <= 0:
            continue
        long_ruta = long.loc[idx]
        if long_ruta.sum() <= 0:
            largos = pd.Series(1.0, index=idx)
        else:
            largos = long_ruta
        exacto = total * (largos / largos.sum())
        base = np.floor(exacto).astype(int)
        resto = int(total - base.sum())
        if resto > 0:
            # Los decimales más grandes se llevan el redondeo que falta.
            orden = (exacto - base).sort_values(ascending=False).index[:resto]
            base.loc[orden] += 1
        out.loc[base.index] = base
    return out


def _llf(result) -> float:
    """Log-verosimilitud del modelo, tal cual la calcula statsmodels.

    Se usa la de statsmodels y **no** una fórmula NB2 escrita a mano. La versión
    propia tenía un término constante sobrante (`(1/α)·log(1/α)`, que en la forma
    `size·log(prob) + y·log(1-prob)` se cancela con `(1/α)·log α`). Como no se
    cancelaba, la verosimilitud **crecía sin límite al bajar α** y el perfil
    declaraba `alpha = 0.01` (el borde de la rejilla) con `χ²/df = 3.64`: un
    Poisson "más sobredisperso que un Poisson", que no significa nada. El bug
    estaba en el diagnóstico, no en los datos, y por eso era invisible.
    """
    try:
        return float(result.llf)
    except Exception:  # pragma: no cover
        return float("nan")


def r2_mcfadden(result, alpha, y) -> float:
    """McFadden (1 − llf/llnull), con el modelo nulo con offset.

    `prsquared` es el pseudo-R² de Cox-Snell de los modelos *discretos*
    (`sm.NegativeBinomial`), no del GLM: leerlo por `hasattr` devolvía `None` y el
    dashboard publicaba `null` sin decir por qué.

    El modelo nulo es `mu = t·e` (solo intercepto, mismo offset). Con un nulo de
    media constante se comparan dos modelos distintos y el cociente puede salir
    negativo, que en McFadden es imposible.

    McFadden mide verosimilitud, **no** error de predicción: un valor bajo no
    significa que el modelo predeciría mal. Para eso está
    `scripts/validez_predictiva.py`, fuera de muestra.
    """
    llf = _llf(result)
    try:
        n = int(result.nobs)
        expo = np.asarray(getattr(result.model, "offset", np.zeros(n)), dtype=float)
        nulos = _ajustar_glm_nb(np.asarray(y, dtype=float), np.ones((n, 1)), expo, alpha)
        llnull = _llf(nulos)
    except Exception:  # pragma: no cover
        return float("nan")
    if not np.isfinite(llf) or not np.isfinite(llnull) or llnull == 0:
        return float("nan")
    return float(1.0 - llf / llnull)


def pearson_chi2_sobre_df(result) -> float:
    """Pearson χ² / gl residuales. Es **dispersión**, no deviance.

    `GLMResults.scale` es el Pearson χ² sobre los gl residuales, y el script lo
    etiquetaba como "deviance/df". No son lo mismo: con sobredispersión la
    deviance también crece, y confundirlas cambia el diagnóstico.
    """
    try:
        r = np.asarray(result.resid_pearson, dtype=float)
        return float(np.nansum(r**2) / result.df_resid)
    except Exception:  # pragma: no cover
        return float("nan")


def _ajustar_glm_nb(y, X_c, expo, alpha):
    return sm.GLM(
        y, X_c, family=sm.families.NegativeBinomial(alpha=alpha), offset=expo
    ).fit(maxiter=300)


def alpha_por_verosimilitud(y, X_c, expo, rejilla=None):
    """Estima `alpha` (NB2) por maximum likelihood sobre una rejilla.

    Por qué rejilla y no `sm.NegativeBinomial`: la verosimilitud NB2 de statsmodels
    para el modelo discreto se evalúa como `size·log(prob) + endog·log(1-prob)`, y
    con `endog > 0` y `mu` grande `1-prob` cae a cero. En este dataset el ajuste
    discreto por ML (lbfgs) divergió: `alpha` a 13.6, hessiana no invertible,
    `χ²/df = 0.13` y oleadas de `RuntimeWarning` en cada iteración. Publicar eso
    es peor que no estimar la dispersión.

    Con `alpha` fijo, el GLM de statsmodels no da el MLE de los betas: usa
    cuasi-verosimilitud, que los sesga al alza. Es la práctica estándar de
    cuasi-verosimilitud con dispersión estimada, y aquí gana en estabilidad y
    reproducibilidad. El sesgo se documenta en `docs/validez_predictiva.md`; la
    cobertura de intervalos sale de ahí, no del `conf_int()` del GLM.
    """
    if rejilla is None:
        rejilla = np.geomspace(ALPHA_GRID_MIN, ALPHA_GRID_MAX, ALPHA_GRID_PUNTOS)
    y = np.asarray(y, dtype=float)
    mejor = None
    for a in rejilla:
        try:
            # La verosimilitud NB2 evaluada en `mu` muy pequeño produce
            # log(0) y divisiones por cero. Son ruido del numerico, no un
            # fallo del ajuste: esos valores de la rejilla se descartan igual
            # por no ser finitos, asi que el warning solo ensucia la salida.
            # `errstate` restaura la configuracion previa al salir; asignar a
            # mano `np.seterr` dejaria el estado global cambiado.
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                res = _ajustar_glm_nb(y, X_c, expo, float(a))
                ll = _llf(res)
        except Exception:  # pragma: no cover - rejilla robusta
            continue
        if np.isfinite(ll) and (mejor is None or ll > mejor["ll"]):
            mejor = {"alpha": float(a), "ll": float(ll), "resultado": res}
    if mejor is not None:
        mejor["alpha_en_borde"] = bool(
            mejor["alpha"] <= ALPHA_GRID_MIN * 1.001 or mejor["alpha"] >= ALPHA_GRID_MAX * 0.999
        )
    return mejor


def fit_model(y, X, expo_km):
    """Ajusta GLM NegBin con `alpha` por ML y offset en km. Devuelve
    (resultado, IRRs, metadatos).

    `long_km` va **solo** en el offset. Antes también estaba en la matriz de
    diseño, y una variable que es exactamente el offset hace la matriz singular:
    `sm.NegativeBinomial` reventaba con `LinAlgError: Singular matrix` y los
    cuatro modelos caían al GLM de respaldo con `alpha=1` clavado, es decir sin
    dispersión estimada. El coste era silencioso: los IRRs se publicaban igual.

    Los dos caminos conservan la exposición. Antes el fallback usaba
    `offset=log(1)`, o sea cero: el modelo pasaba de "siniestros por km" a
    "siniestros por tramo" sin avisar.
    """
    y = pd.Series(y).astype(float)
    X = pd.DataFrame(X).astype(float)

    # La exposición se valida en lugar de recortarse. Con `np.clip(x, 1e-6, None)`
    # un tramo con `long_km` negativa (4 de 3.750 vienen con km1 < km0) quedaba
    # con exposición 1e-6 km·año, es decir cero: el GLM predeciría 0 ahí, la
    # verosimilitud se hundía y el perfil de alpha declaraba el borde. Todo ello
    # con código de salida 0 y los IRRs publicados. Mejor un fallo ruidoso.
    expo_raw = pd.Series(expo_km, index=X.index).astype(float)
    malos = ~np.isfinite(expo_raw.to_numpy()) | (expo_raw.to_numpy() <= 0)
    if malos.any():
        raise ValueError(
            f"exposición no positiva o no finita en {int(malos.sum())} de {len(X)} "
            f"tramos (min={np.nanmin(expo_raw.to_numpy()):.6g}). "
            "La exposición debe ser km·año > 0. Revisa long_km (tramos con km1 < km0 "
            "salen negativos) antes de ajustar."
        )
    expo = np.log(expo_raw.to_numpy())

    # Una columna constante dentro del subconjunto de ajuste también singulariza.
    variables = [c for c in X.columns if X[c].nunique(dropna=False) > 1]
    constantes = [c for c in X.columns if c not in variables]
    X = X[variables]
    if constantes:
        print(f"     [nota] columnas constantes en este subconjunto, omitidas: {constantes}")

    X_c = sm.add_constant(X)
    meta = {"exposicion": "offset=log(long_km)", "variables": list(X.columns)}
    mejor = alpha_por_verosimilitud(np.asarray(y, dtype=float), X_c, expo)
    if mejor is None:  # pragma: no cover - solo si la rejilla entera falla
        result = _ajustar_glm_nb(np.asarray(y, dtype=float), X_c, expo, 1.0)
        meta["estimador"] = "sm.GLM(NegativeBinomial)"
        meta["alpha"] = 1.0
        meta["alpha_estimado"] = False
        meta["aviso_fallback"] = "la rejilla de alpha no produjo ninguna verosimilitud finita"
    else:
        result = mejor["resultado"]
        meta["estimador"] = "sm.GLM(NegativeBinomial) + alpha por ML en rejilla"
        meta["alpha"] = mejor["alpha"]
        meta["alpha_estimado"] = True
        meta["alpha_rejilla"] = [ALPHA_GRID_MIN, ALPHA_GRID_MAX, ALPHA_GRID_PUNTOS]
        if mejor.get("alpha_en_borde"):
            meta["aviso_fallback"] = (
                f"el perfil de verosimilitud peaking en el borde de la rejilla "
                f"(alpha={mejor['alpha']:.4g}); ampliar ALPHA_GRID_MIN/MAX"
            )

    meta["pseudo_r2_mcfadden"] = r2_mcfadden(result, meta["alpha"], y)
    meta["pearson_chi2_sobre_df"] = pearson_chi2_sobre_df(result)
    meta["llf"] = _llf(result)
    meta["aic"] = float(result.aic)
    meta["n"] = int(result.nobs)
    return result, _irrs(result), meta


def _irrs(result):
    params = result.params
    conf = result.conf_int()
    pvalues = result.pvalues

    labels_map = {
        "const": "Intercepto",
        "alpha": "alpha (dispersion)",
        "carriles": "Carriles (+1)",
        "vel_proy": "Vel. proyecto (+10 km/h)",
        "topografia_ondulado": "Terreno ondulado",
        "topografia_montanoso": "Terreno montañoso",
        "topografia_llanura": "Terreno llano",
        "topografia_lplan": "Terreno plano (ref)",
        "sup_buena": "Superficie buena",
        "sup_regular": "Superficie regular",
        "sup_mala": "Superficie mala (ref)",
        "dist_ingemmet_km_log": "Dist. INGEMMET (log)",
        "dist_peajes_km_log": "Dist. peaje (log)",
        "dist_cinemometros_km_log": "Dist. cinemómetro (log)",
        "es_panamericana": "Vía panamericana",
        "es_ruta_nacional": "Red nacional",
    }

    irrs = []
    for var in params.index:
        conf_fila = conf.loc[var]
        irrs.append(
            {
                "variable": var,
                "label": labels_map.get(var, var),
                # alpha es un parámetro de dispersión, no un efecto: su "IRR" no
                # significa una tasa relativa y no debe leerse como una.
                "irr": float(np.exp(params[var])),
                "irr_low": float(np.exp(conf_fila.iloc[0])),
                "irr_high": float(np.exp(conf_fila.iloc[1])),
                "p": float(pvalues[var]),
                "coef": float(params[var]),
                "es_alpha": var == "alpha",
            }
        )
    return irrs


def _construir_X(df):
    """Matriz de diseño del modelo. Nótese qué NO va aquí:

    - `long_km`: es el offset. Como covariable hace la matriz singular.
    - `es_ruta_nacional`: `dataset_modelo.csv` no tiene columna `red_vial`, así
      que el `if ... else 0.0` de antes fabricaba una columna **constante 0** que
      parecía una variable real y solo servía para singularizar. Si la columna no
      está, la variable no existe: no se inventa.
    - `topografia`: las categorías reales son ONDULADO / PLANO / MONTAÑOSO. El
      dummy `topografia_llanura` comparaba contra "LLANURA", que no existe en los
      datos, así que valía siempre 0 y PLANO quedaba como categoría base sin
      nombrarla. Se codifica con PLANO como referencia explícita.
    """
    X = pd.DataFrame(index=df.index)
    X["carriles"] = df["carriles"].astype(float)
    X["vel_proy"] = df["vel_proy"].astype(float)
    X["topografia_ondulado"] = (df["topografia"] == "ONDULADO").astype(float)
    X["topografia_montanoso"] = (df["topografia"] == "MONTAÑOSO").astype(float)
    X["sup_buena"] = (df["superficie"] == "Buena").astype(float)
    X["sup_regular"] = (df["superficie"] == "Regular").astype(float)
    X["dist_ingemmet_km_log"] = np.log1p(df["dist_ingemmet_km"].fillna(0))
    X["dist_peajes_km_log"] = np.log1p(df["dist_peajes_km"].fillna(0))
    X["dist_cinemometros_km_log"] = np.log1p(df["dist_cinemometros_km"].fillna(0))
    X["es_panamericana"] = df["es_panamericana"].fillna(0)
    if "red_vial" in df.columns:
        X["es_ruta_nacional"] = (df["red_vial"] == "NACIONAL").astype(float)
    return X


def main():
    print("[1/5] Cargando dataset modelo + SUTRAN/OSITRAN en tramos...")
    df = pd.read_csv(DATASET)
    print(f"     Tramos: {len(df)}, y_onsv>0: {(df.y_onsv > 0).sum()}")

    # ── SUTRAN: asignación por (ruta, km), la misma que features_tramos.py ──
    print("[2/5] Asignando SUTRAN por (ruta, km)...")
    sutran = pd.read_csv(ROOT / "data" / "processed" / "sutran_accidentes_geocod.csv")
    if "GEOCODIFICADO" in sutran.columns:
        sutran = sutran[sutran["GEOCODIFICADO"] == 1].copy()
    sutran["fecha_dt"] = pd.to_datetime(sutran["FECHA_DT"], errors="coerce")
    sutran["fallecidos"] = pd.to_numeric(sutran["FALLECIDOS"], errors="coerce")
    sutran["km_red"] = pd.to_numeric(
        sutran["KM"] if "KM" in sutran.columns else sutran["KILOMETRO"], errors="coerce"
    )
    col_ruta_su = "CODIGO_VIA" if "CODIGO_VIA" in sutran.columns else "CODIGO_VÍA"
    sutran = panel_anual.asignar_por_km_red(
        sutran, df[["id_tramo", "ruta", "km0", "km1", "long_km"]], col_ruta=col_ruta_su,
        col_km="km_red",
    )

    # ── OSITRAN: agregado sin fecha ni coordenadas → reparto por longitud ──
    print("[3/5] Repartiendo OSITRAN por longitud de tramo...")
    ositran_acc = pd.read_csv(ROOT / "data" / "processed" / "ositran_accidentes.csv")
    ositran_acc["ruta"] = ositran_acc["ruta"].astype(str).str.strip()
    df["ruta"] = df["ruta"].astype(str).str.strip()
    total_fuente = pd.to_numeric(ositran_acc["cant_accidentes"], errors="coerce").fillna(0).sum()

    ositran_by_ruta = ositran_acc.groupby("ruta").agg(
        ositran_n_total=("cant_accidentes", "sum")
    ).reset_index()
    df = df.merge(ositran_by_ruta, on="ruta", how="left")
    df["ositran_n_total"] = pd.to_numeric(df["ositran_n_total"], errors="coerce").fillna(0)

    df["ositran_n"] = reparto_proporcional_a_longitud(
        df, col_ruta="ruta", col_total="ositran_n_total", col_long="long_km",
    )
    df["y_ositran"] = df["ositran_n"].astype(int)
    _verificar_reparto(df, "ositran_n")

    n_asignado = int(df.y_ositran.sum())
    # OSITRAN usa codigos de ruta numericos (030A, 118.2) y la red del proyecto
    # usa los de MTC (PE-02). Sin una tabla de equivalencias, solo 26 de las 103
    # rutas casan y el 57% de los accidentes se queda fuera. Publicar el total
    # repartido sin decir esto presenta una cobertura parcial como si fuera la
    # fuente completa.
    rutas_fuente = set(ositran_acc["ruta"])
    rutas_red = set(df["ruta"])
    cobertura = n_asignado / total_fuente if total_fuente else float("nan")
    ositran_cobertura = {
        "accidentes_fuente": int(total_fuente),
        "accidentes_asignados": n_asignado,
        "cobertura": float(cobertura),
        "rutas_fuente": len(rutas_fuente),
        "rutas_con_coincidencia": len(rutas_fuente & rutas_red),
        "rutas_sin_coincidencia": len(rutas_fuente - rutas_red),
        "ejemplos_rutas_sin_coincidencia": sorted(rutas_fuente - rutas_red)[:10],
    }
    print(f"     OSITRAN: {n_asignado} accidentes repartidos sobre {len(df)} tramos")
    print(f"     Cobertura OSITRAN: {n_asignado}/{int(total_fuente)} = "
          f"{cobertura*100:.1f}% "
          f"({ositran_cobertura['rutas_con_coincidencia']}/{rutas_fuente.__len__()} rutas "
          "casan con la red; los códigos OSITRAN son numéricos y los del proyecto MTC)")

    # ── Respuesta combinada: unión deduplicada en la ventana común ─────────
    print("[4/5] Unificando ONSV ∪ SUTRAN (deduplicado, ventana común)...")
    onsv = pd.read_csv(ROOT / "data" / "processed" / "onsv_nacional_geocod.csv")
    unif = dedup.unificar_onsv_sutran(onsv, sutran)
    resumen = dedup.resumen_unificacion(onsv, sutran, unif=unif)
    ventanas = dedup.ventanas_de_fuente(onsv, sutran)
    ini, fin = dedup.ventana_comun(ventanas)
    if ini is None or fin is None:
        # Sin ventana común no existe `y_total`: no se puede restar el doble
        # conteo sin comparar las dos fuentes en el mismo periodo. Fallar aquí es
        # mejor que publicar `y_total = 0` con otro nombre.
        raise SystemExit(
            "ABORTADO: ONSV y SUTRAN no comparten ventana temporal, así que no hay "
            f"respuesta combinada defendible. Ventanas: "
            + ", ".join(f"{k}={v[0].date()}→{v[1].date()}" for k, v in ventanas.items())
        )
    print(f"     Ventana común: {ini.date()} → {fin.date()}")
    print(f"     {resumen}")

    # El reparto por tramo sale de la MISMA unión que el total de red. Antes se
    # contaba la unión (para el resumen) y luego se repartían las dos fuentes por
    # separado (para `y_total`): el total de red salía correcto y la columna que se
    # publicaba seguía sumando los duplicados. Error invisible desde fuera.
    ev_u = panel_anual.asignar_por_km_red(
        unif, df[["id_tramo", "ruta", "km0", "km1", "long_km"]],
        col_ruta="ruta", col_km="km_red",
    )
    df["y_onsv_comun"] = 0
    df["y_sutran_comun"] = 0
    df["y_ambos_comun"] = 0

    def _contar(ev, etiqueta=None):
        # `asignar_por_km_red` deja **NA** (no -1) en `idx_tramo` cuando el
        # (ruta, km) no cae dentro de ningún tramo. Filtrar por `< 0` no los
        # quita, y `groupby` los descarta en silencio: 216 de 5.115 eventos
        # desaparecieron de `y_total` sin aviso. Hay que mirar `isna()`.
        ev = ev[ev["idx_tramo"].notna()]
        if etiqueta is not None:
            ev = ev[ev["fuentes"].isin(etiqueta)]
        return ev.groupby("idx_tramo").size()

    c_uni = _contar(ev_u)
    c_onsv = _contar(ev_u, {"ONSV", "ONSV+SUTRAN"})
    c_sut = _contar(ev_u, {"SUTRAN", "ONSV+SUTRAN"})
    c_ambos = _contar(ev_u, {"ONSV+SUTRAN"})
    for col, serie in (("y_total", c_uni), ("y_onsv_comun", c_onsv),
                       ("y_sutran_comun", c_sut), ("y_ambos_comun", c_ambos)):
        df[col] = df["id_tramo"].map(serie).fillna(0).astype(int)

    sin_asignar = int(ev_u["idx_tramo"].isna().sum())
    n_dedup = int(resumen["n_ambos"])
    # La diferencia entre el total de red y el total asignado a tramos tiene DOS
    # causas distintas y sumarlas en una sola cifra invite a concluir que se
    # perdieron accidentes: 26 duplicados reales y N eventos sin tramo asignable.
    print(f"     y_total: {df.y_total.sum()} siniestros únicos en la ventana común")
    print(f"       = red {resumen['n_unico_total']} - sin tramo asignable {sin_asignar}")
    print(f"       (doble conteo evitado: {n_dedup}; "
          f"la suma ingenua de las dos fuentes habría dado {resumen['suma_naiva']})")
    print(f"     onsv_comun={df.y_onsv_comun.sum()} (todo el periodo: {df.y_onsv.sum()}), "
          f"sutran_comun={df.y_sutran_comun.sum()}, "
          f"vistos por ambas={df.y_ambos_comun.sum()}, "
          f"ositran={df.y_ositran.sum()} (FUERA de y_total)")
    if sin_asignar:
        print(f"     [aviso] {sin_asignar} eventos únicos sin tramo asignado "
              "(km_red o ruta no recognized); no entran en ningún modelo")

    # ── Features ────────────────────────────────────────────────────────────
    X = _construir_X(df)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    # `long_km` NO entra en X: es el offset. Meterlo en ambos sitio singulariza.
    long_km = pd.to_numeric(df["long_km"], errors="coerce").abs()
    long_km = long_km.where(long_km > 0, np.nan)

    def exposicion(anos):
        """km·año. El offset tiene que ser el del periodo de ESA respuesta.

        Con un offset único (los 5 años del panel) el modelo de la ventana común
        (9 meses)ava a estimar una tasa 6,7 veces menor de la real, y sus IRRs
        quedan mal escalados aunque el signo y la significación no cambien.
        """
        return (long_km * anos).fillna(np.nan).fillna(1e-3)

    anos_onsv = (ventanas["ONSV"][1] - ventanas["ONSV"][0]).days / 365.25
    anos_comun = (fin - ini).days / 365.25
    anos_ositran = float(
        (pd.to_datetime(ositran_acc["ANIO"].astype(str) + "-12-31", errors="coerce").max()
         - pd.to_datetime(ositran_acc["ANIO"].astype(str) + "-01-01", errors="coerce").min()
         ).days / 365.25
    ) if "ANIO" in ositran_acc.columns else anos_onsv
    print(f"     Exposición (km·año): onsv={anos_onsv:.2f} años, "
          f"común={anos_comun:.2f} años, ositran={anos_ositran:.2f} años")

    print("[5/5] Ajustando NegBin ONSV / SUTRAN / combinado / OSITRAN...")
    respuestas = {
        "onsv": (df["y_onsv"], exposicion(anos_onsv), anos_onsv),
        "sutran": (df["y_sutran_comun"], exposicion(anos_comun), anos_comun),
        "total": (df["y_total"], exposicion(anos_comun), anos_comun),
        "ositran": (df["y_ositran"], exposicion(anos_ositran), anos_ositran),
    }

    todos_irrs, meta_out = [], {}
    for nombre, (y, expo_r, anos_r) in respuestas.items():
        mask = y.notna()
        # Se usan TODOS los tramos, también los de y = 0. Filtrar y > 0 tira
        # 2.472 de 3.750 filas y convierte un modelo de conteos con offset en otro
        # distinto (la tasa se condiciona a "hubo al menos un siniestro"), con otro
        # intercepto y otras pendientes; los IRRs ya no son comparables entre las
        # cuatro respuestas ni con la verosimilitud calculada.
        if int(mask.sum()) < MIN_TRAMOS_CON_EVENTOS:
            print(f"     [aviso] '{nombre}': solo {int(mask.sum())} tramos; "
                  f"no se ajusta (mínimo {MIN_TRAMOS_CON_EVENTOS})")
            meta_out[nombre] = {"n_tramos": int(mask.sum()), "ajustado": False}
            continue
        resultado, irrs, meta = fit_model(y[mask], X[mask], expo_km=expo_r[mask])
        print(f"     {nombre}: n={meta['n']} (con y=0: {int((y == 0).sum())}), "
              f"alpha={meta['alpha']:.3f}, "
              f"R2_McFadden={meta['pseudo_r2_mcfadden']:.4f}, "
              f"pearson_chi2/df={meta['pearson_chi2_sobre_df']:.2f}")
        if meta.get("aviso_fallback"):
            print(f"        [aviso] alpha no estimado: {meta['aviso_fallback']}")
        for r in irrs:
            r["fuente"] = nombre
        todos_irrs.extend(irrs)
        meta["n_tramos"] = int(mask.sum())
        meta["n_tramos_con_eventos"] = int((y > 0).sum())
        meta["n_eventos"] = int(y.sum())
        meta["anos_exposicion"] = round(float(anos_r), 4)
        meta["ajustado"] = True
        meta_out[nombre] = meta

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(todos_irrs).to_csv(OUT_DIR / "irrs_multi.csv", index=False, encoding="utf-8-sig")
    print(f"     Guardado: {OUT_DIR / 'irrs_multi.csv'} ({len(todos_irrs)} rows)")

    stats_out = {
        "respuestas": meta_out,
        "ventanas": {
            k: [str(v[0].date()), str(v[1].date())] for k, v in ventanas.items()
        } | {"ventana_comun": [str(ini.date()), str(fin.date())]},
        "deduplicacion": resumen,
        "ositran_cobertura": ositran_cobertura,
        "notas": {
            "y_total": (
                "Unión deduplicada ONSV ∪ SUTRAN dentro de la ventana común "
                f"{ini.date()}→{fin.date()}. OSITRAN queda fuera: es un agregado "
                "sin fecha ni coordenadas y no se puede deduplicar."
            ),
            "seudo_r2": "McFadden (1 - llf/llnull) sobre la verosimilitud NB2, con el "
            "modelo nulo con offset. Es verosimilitud, NO error de prediccion: "
            "para eso esta scripts/validez_predictiva.py.",
            "exposicion": "offset = log(long_km × años de esa respuesta); cada "
                          "respuesta usa la duración de SU periodo, no la del panel.",
            "y_onsv": "Recuento ONSV del periodo completo de ONSV.",
            "y_sutran": "SUTRAN recortado a la ventana común.",
            "y_ositran": (
                "Reparto proporcional a la longitud DENTRO de las rutas que casan "
                f"con la red del proyecto: {ositran_cobertura['cobertura']*100:.1f}% de "
                f"los {ositran_cobertura['accidentes_fuente']} accidentes de la fuente "
                f"({ositran_cobertura['rutas_con_coincidencia']} de "
                f"{ositran_cobertura['rutas_fuente']} rutas). NO es el total de OSITRAN. "
                "Los codigos OSITRAN son numericos (030A, 118.2) y los del proyecto "
                "son de MTC (PE-02); sin tabla de equivalencias, el resto no se puede "
                "ubicar. Ver `ositran_cobertura`."
            ),
            "filas": "Modelos ajustados sobre los 3.750 tramos, incluidos los de "
                     "y = 0 (no se filtra por y > 0).",
        },
        "features": list(X.columns),
    }
    with open(OUT_DIR / "modelo_stats_multi.json", "w", encoding="utf-8") as f:
        json.dump(stats_out, f, ensure_ascii=False, indent=2)
    print(f"     Guardado: {OUT_DIR / 'modelo_stats_multi.json'}")
    print("\n[OK] Modelos multi-fuente completados")


def _verificar_reparto(df, col):
    """El reparto tiene que cuadrar con el total de la fuente, ruta a ruta."""
    suma_rep = df.groupby("ruta")[col].sum()
    esperado = df.groupby("ruta")["ositran_n_total"].first()
    esperado = esperado[esperado > 0]
    comunes = suma_rep.index.intersection(esperado.index)
    desajuste = (suma_rep.loc[comunes] - esperado.loc[comunes]).abs()
    if (desajuste > 0).any():
        rutas = desajuste[desajuste > 0].index.tolist()[:5]
        raise SystemExit(
            f"El reparto proporcional de '{col}' no cuadra en {len(desajuste[desajuste>0])} "
            f"rutas (ejemplos: {rutas}). El agregado ya no reconcilia con la fuente."
        )


if __name__ == "__main__":
    main()