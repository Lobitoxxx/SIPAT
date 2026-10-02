"""Regresión NegBin/Poisson para siniestros fatales ONSV por tramo.

MODELO LEGADO DE FASE 1 — superado por `modelo_multi.py`.

Qué sigue siendo útil: el contraste Poisson vs NegBin sobre `y_onsv` con las
variables de diseño de Fase 1 (región, topografía, velocidad, sinuosidad,
proximidad a servicios), y la tabla de residuales para inspección manual.

Qué ya no es la vía canónica:
  - Los IRR por fuente y con `alpha` estimado están en `modelo_multi.py`.
  - Los puntos negros están en `eb_tramos.py` + `build_puntos_negros.py`, que
    usan Empirical Bayes. Este script sigue escribiendo un
    `puntos_negros.csv` por residuales SOLO por compatibilidad; se marca como
    legado en la salida y no debe usarse para decisiones.

Defectos reales corregidos aquí (y por qué importan):

1. **Offset sin años: cambio de escala, no de exactitud.** Usaba `log(expo_km)` y
   `expo_km` es solo `long_km`, pero `y_onsv` cuenta 5 años, así que el
   intercepto salía con otra escala. Importante: esto NO cambiaba las
   predicciones ni los residuales — un factor constante en el offset lo absorbe
   el intercepto, y se comprobó que `predict()` da números idénticos con ambos
   offsets. Los otros coeficientes tampoco se mueven. Lo único que cambia es que
   `exp(const)` queda 5× más grande y deja de ser comparable con el de
   `modelo_multi.py`. Ahora el offset es `log(expo_km_anio)` = `log(long_km ×
   años)`, que además hace que el "por año" sea explícito en el código. Un test
   lo fija: si alguna vez se cambia, el intercepto tiene que explicar el factor.

2. **`alpha` nunca se ajustaba.** El código hacía
   `alpha2 = m2.scale` y refitaba con `alpha=alpha2`. Con `alpha` fijo,
   statsmodels GLM devuelve `scale == 1.0` exactamente (no lo estima), así que
   `alpha2` era siempre 1.0 y el refit era idéntico al original: un no-op que
   parecía un ajuste. Este sí es un defecto con consecuencias: con alpha=1 la
   dispersión de Pearson era 2.17 y con el alpha estimado (1.56) baja a 1.11.
   Ahora `alpha` se estima por máxima verosimilitud sobre rejilla
   (`alpha_por_verosimilitud`, importada de `modelo_multi.py`).

3. **"dispersión Poisson (deviance/df) = 1.00".** `GLMResults.scale` de la
   familia Poisson es una constante: imprimirlo como diagnóstico de dispersión
   es vacío. La sobredispersión real es 3.26. Se reporta Pearson χ²/gl
   residuales, que sí es diagnóstico.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modelo_multi import (  # noqa: E402
    alpha_por_verosimilitud,
    pearson_chi2_sobre_df,
    r2_mcfadden,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_PUNTOS = ROOT / "data" / "processed" / "puntos_negros_legacy_residuales.csv"

d = pd.read_csv(ROOT / "data" / "processed" / "dataset_modelo.csv")

# ── Imputación ─────────────────────────────────────────────────────────────
# La mediana se calcula una vez y se registra: sin registrar, "no hay nulos"
# es una afirmación no verificable.
med_vel = d["vel_proy"].median()
med_car = d["carriles"].median()
n_imputados = int(d["vel_proy"].isna().sum() + d["carriles"].isna().sum())
d["vel_proy"] = d["vel_proy"].fillna(med_vel)
d["carriles"] = d["carriles"].fillna(med_car)
for c in ("sup_buena", "es_panamericana"):
    d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
corte_sinuosidad = d["sinuosidad"].quantile(0.99)
n_sinuosidad_recortada = int((d["sinuosidad"] > corte_sinuosidad).sum())
d["sinuosidad"] = d["sinuosidad"].clip(upper=corte_sinuosidad)

# ── Transformaciones ───────────────────────────────────────────────────────
d["log_ingemmet"] = np.log1p(d["dist_ingemmet_km"])
d["log_peajes"] = np.log1p(d["dist_peajes_km"])
d["log_cine"] = np.log1p(d["dist_cinemometros_km"])

# ── Diseño ─────────────────────────────────────────────────────────────────
# `region` y `topografia` son categorias: si se pasan enteros, el modelo los
# leería como magnitudes y estimaría un "efecto por unidad de código".
for c in ("region", "topografia"):
    if c in d.columns:
        d[c] = d[c].astype(str).str.strip()

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

y = d["y_onsv"].values.astype(float)

# ── Offset: longitud × años del periodo de la respuesta ───────────────────
# `expo_km` es `long_km` pelado; `expo_km_anio` es `long_km × años`. Un factor
# constante en el offset lo absorbe el intercepto, así que esto NO cambia las
# predicciones ni los residuales (comprobado): lo que corrige es la escala del
# intercepto y que "por año" quede explícito en el código.
if "expo_km_anio" in d.columns and "n_anios_cubiertos" in d.columns:
    expo_raw = pd.to_numeric(d["expo_km_anio"], errors="coerce").to_numpy(float)
    anos = float(np.nanmedian(d["n_anios_cubiertos"]))
    offset_desc = f"log(expo_km_anio) = log(long_km × {anos:g} años)"
else:  # pragma: no cover - solo si el dataset pierde las columnas
    expo_raw = pd.to_numeric(d["expo_km"], errors="coerce").to_numpy(float)
    anos = 1.0
    offset_desc = "log(expo_km) = log(long_km)  [SIN años: predicciones 5x bajas]"
if np.any(~np.isfinite(expo_raw)) or np.any(expo_raw <= 0):
    raise ValueError("La exposición debe ser finita y positiva en todos los tramos.")
expo = np.log(expo_raw)

Xc = sm.add_constant(X)

print(f"[1/5] n={len(d)} tramos, y_onsv={int(y.sum())} siniestros en {anos:g} años")
print(f"      offset = {offset_desc}")
print(f"      imputadas {n_imputados} celdas (mediana vel={med_vel:g}, carriles={med_car:g}); "
      f"{n_sinuosidad_recortada} sinuosidades recortadas al P99={corte_sinuosidad:.2f}")


def report(m, name, alpha_ci=0.05):
    ci = m.conf_int(alpha=alpha_ci)
    res = pd.DataFrame({
        "IRR": np.exp(m.params),
        "IRR_low": np.exp(ci.iloc[:, 0]),
        "IRR_high": np.exp(ci.iloc[:, 1]),
        "p": m.pvalues,
    }).round(3)
    print(f"\n##### {name} #####")
    print(res.to_string())
    print(f"AIC={m.aic:.1f}  n={int(m.nobs)}")
    return res


# ── 1. Poisson (referencia) ────────────────────────────────────────────────
print("\n[2/5] Poisson (referencia)...")
m1 = sm.GLM(y, Xc, family=sm.families.Poisson(), offset=expo).fit()
disp_poisson = pearson_chi2_sobre_df(m1)
report(m1, "Poisson")
print(f"    dispersion REAL (Pearson chi2/df) = {disp_poisson:.2f}"
      f"   [antes el script imprimia GLMResults.scale = {m1.scale:.2f}, una constante]")

# ── 2. NegBin con alpha estimado por ML ────────────────────────────────────
print("\n[3/5] NegBin: alpha por maxima verosimilitud sobre rejilla...")
mejor = alpha_por_verosimilitud(y, Xc, expo)
if mejor is None:
    raise RuntimeError("Ningun alpha de la rejilla produjo una verosimilitud finita.")
alpha2 = mejor["alpha"]
m2 = mejor["resultado"]
if mejor["alpha_en_borde"]:
    print(f"    [aviso] alpha quedo en el borde de la rejilla; ampliar el rango antes de publicarlo")
print(f"    alpha estimado = {alpha2:.4f}   [antes: 1.000 fijo porque GLM scale==1 con alpha fijo]")
print(f"    dispersion (Pearson chi2/df) = {pearson_chi2_sobre_df(m2):.2f}")
print(f"    R2 McFadden = {r2_mcfadden(m2, alpha2, y):.4f}   (verosimilitud, no error de prediccion)")
report(m2, "NegBin (alpha por ML)")

# ── 3. Errores agrupados por ruta ──────────────────────────────────────────
# Los tramos de una misma ruta comparten clima, curvas y estado del firme: sus
# residuales no son independientes. Sin agrupar, los IC salen demasiado estrechos.
m3 = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=alpha2), offset=expo).fit(
    cov_type="cluster", cov_kwds={"groups": d["ruta"]})
print("\n[4/5] NegBin con IC agrupados por ruta...")
print(f"    {d['ruta'].nunique()} grupos (rutas) con {len(d)} tramos")
ci3 = m3.conf_int()
comp = pd.DataFrame({
    "IRR": np.exp(m3.params),
    "IRR_naive": np.exp(m2.params),
    "IC_low_cluster": np.exp(ci3.iloc[:, 0]),
    "IC_high_cluster": np.exp(ci3.iloc[:, 1]),
    "p_cluster": m3.pvalues,
}).round(3)
comp["ratio_IC"] = (np.exp(ci3.iloc[:, 1]) - np.exp(ci3.iloc[:, 0])).round(3)
print(comp.to_string())
print(f"\n    Poisson dispersion={disp_poisson:.2f} | NegBin alpha={alpha2:.3f} "
      f"| NB pearson_chi2/df={pearson_chi2_sobre_df(m2):.2f}")

# ── 4. Residuales ──────────────────────────────────────────────────────────
# Con offset corregido, `pred` ya esta en la misma escala que `y_onsv`.
d["pred"] = np.asarray(m3.predict(Xc, offset=expo), dtype=float)
var_pred = d["pred"] + d["pred"] ** 2 / alpha2
d["pearson"] = (y - d["pred"]) / np.sqrt(var_pred)

cols_ver = ["ruta", "km0", "km1", "y_onsv", "pred", "pearson",
            "region", "topografia", "vel_proy", "sinuosidad"]
print("\n[5/5] Tramos con mayor residuo (mas siniestros de los esperados)...")
print(d.sort_values("pearson", ascending=False)[cols_ver].head(15).round(2).to_string(index=False))

cand = d[(d["y_onsv"] >= 5) & (d["pearson"] > 1.5)][
    ["ruta", "km0", "km1", "y_onsv", "pred", "pearson", "dist_ingemmet_km", "dist_peajes_km"]
].sort_values("pearson", ascending=False)
print("\n    Candidatos a punto negro por residual: "
      f"{len(cand)} tramos (maximo teorico por pearson>1.5 sobre {int((y >= 5).sum())} tramos con y>=5)")
print("    [legado] La lista canonica de puntos negros la produce "
      "build_puntos_negros.py con Empirical Bayes (eb_tramos.py); este criterio")
print("             por residual no corrige el efecto de la varianza del propio tramo.")
if len(cand):
    print(cand.head(15).round(2).to_string(index=False))

# Se escribe con nombre propio y marca de legado: antes dos scripts escribian
# `puntos_negros.csv` con definiciones distintas y la segunda pisaba a la
# primera sin que nadie lo notara.
cand.to_csv(OUT_PUNTOS, index=False, encoding="utf-8-sig")
print(f"\n[OK] {OUT_PUNTOS.name} guardado ({len(cand)} filas, LEGADO por residuales)")
print("     Los IRR multi-fuente estan en scripts/modelo_multi.py "
      "(irrs_multi.csv / modelo_stats_multi.json).")