"""Modelo de regresion NegBin/Poisson para siniestros fatales ONSV por tramo."""
import numpy as np
import pandas as pd
import statsmodels.api as sm

d = pd.read_csv("data/processed/dataset_modelo.csv")

# imputacion
med_vel = d["vel_proy"].median()
med_car = d["carriles"].median()
d["vel_proy"] = d["vel_proy"].fillna(med_vel)
d["carriles"] = d["carriles"].fillna(med_car)
d["sinuosidad"] = d["sinuosidad"].clip(upper=d["sinuosidad"].quantile(0.99))

# transformaciones
d["log_ingemmet"] = np.log1p(d["dist_ingemmet_km"])
d["log_peajes"] = np.log1p(d["dist_peajes_km"])
d["log_cine"] = np.log1p(d["dist_cinemometros_km"])

# dummies
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
expo = np.log(d["expo_km"]).values

Xc = sm.add_constant(X)


def report(m, name, alpha=0.05):
    ci = m.conf_int(alpha=alpha)
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


print("== Modelo 1: Poisson (referencia) ==")
m1 = sm.GLM(y, Xc, family=sm.families.Poisson(), offset=expo).fit()
report(m1, "Poisson")

print("\n== Modelo 2: Negative Binomial ==")
m2 = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=1.0), offset=expo).fit()
# ajustar alpha
alpha2 = m2.scale
m2b = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=alpha2), offset=expo).fit()
report(m2b, "NegBin")

print("\n== Modelo 3: NegBin con errores cluster por ruta ==")
m3 = sm.GLM(y, Xc, family=sm.families.NegativeBinomial(alpha=alpha2), offset=expo).fit(
    cov_type="cluster", cov_kwds={"groups": d["ruta"]})
ci3 = m3.conf_int()
print(pd.DataFrame({
    "IRR": np.exp(m3.params), "IRR_low": np.exp(ci3.iloc[:, 0]), "IRR_high": np.exp(ci3.iloc[:, 1]), "p": m3.pvalues
}).round(3).to_string())

# dispersion: Poisson phi
print(f"\ndispersion Poisson (deviance/df): {m1.scale:.2f}")
print(f"alpha NegBin estimado: {alpha2:.3f}")

# prediccion: tramos esperados vs observados top
d["pred"] = np.exp(m3.predict(Xc, offset=expo))
d["pearson"] = (y - d["pred"]) / np.sqrt(d["pred"] + d["pred"] ** 2 / alpha2)
print("\n== Tramos con mayor residual (mas siniestros que lo esperado) ==")
topr = d.assign(**{c: X[c].values for c in X.columns})
topr["fecha_res"] = y
out = d.sort_values("pearson", ascending=False)[
    ["ruta", "km0", "km1", "y_onsv", "pred", "pearson", "region", "topografia", "vel_proy", "sinuosidad"]].head(15)
print(out.round(2).to_string(index=False))

print("\n== Tramos con exceso (top por tasa y residual alto) - candidatos a puntos negros ==")
cand = d[(d["y_onsv"] >= 5) & (d["pearson"] > 1.5)][
    ["ruta", "km0", "km1", "y_onsv", "pred", "pearson", "dist_ingemmet_km", "dist_peajes_km"]].sort_values(
    "pearson", ascending=False).head(15)
print(cand.round(2).to_string(index=False))
cand.to_csv("data/processed/puntos_negros.csv", index=False, encoding="utf-8-sig")
print("\npuntos_negros.csv guardado")
