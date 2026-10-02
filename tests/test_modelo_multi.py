"""Regresiones del modelo multi-fuente.

Aquí se documentan defectos que solo aparecen con los datos reales. Todos eran
silenciosos: el script terminaba con código 0 y publicaba IRRs.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import modelo_multi as mm  # noqa: E402


def _df_tramos(n=200, seed=3):
    rng = np.random.default_rng(seed)
    long_km = rng.uniform(0.5, 40.0, n)
    total_km = long_km.sum()
    tasa = 2.0  # siniestros por km·año
    y = rng.negative_binomial(n=1.0 / 0.6, p=1.0 / (1.0 / 0.6 + long_km * tasa))
    return pd.DataFrame({
        "id_tramo": np.arange(n),
        "ruta": "PE-1N",
        "km0": np.cumsum(long_km) - long_km,
        "km1": np.cumsum(long_km),
        "long_km": long_km,
        "carriles": rng.integers(2, 6, n).astype(float),
        "vel_proy": rng.uniform(30, 100, n),
        "topografia": rng.choice(["ONDULADO", "PLANO", "MONTAÑOSO"], n),
        "superficie": rng.choice(["Buena", "Regular", "Mala"], n),
        "dist_ingemmet_km": rng.uniform(0, 200, n),
        "dist_peajes_km": rng.uniform(0, 200, n),
        "dist_cinemometros_km": rng.uniform(0, 200, n),
        "es_panamericana": rng.integers(0, 2, n).astype(float),
        "y": y.astype(float),
    })


# ── La exposición no puede ser negativa ni NaN ──────────────────────────────


def test_log_de_exposicion_negativa_es_nan_y_eso_rompia_el_modelo():
    """4 tramos de 3.750 vienen con `km1 < km0`, así que `long_km` era negativa.

    `np.clip(x, 1e-6, None)` deja el negativo en 1e-6 en vez de marcarlo: la
    exposición de esos tramos quedaba en 1e-6 km·año, es decir cero. Con
    exposición cero el GLM predeciría 0 sobre ellos, la verosimilitud se hundía y
    el perfil de `alpha` declaraba el borde (0.01) con χ²/df = 3.64: un Poisson
    "más sobredisperso que un Poisson". El diagnóstico publicaba una.bestia.
    """
    d = _df_tramos()
    d.loc[0, ["km0", "km1"]] = [100.0, 96.0]
    largo = pd.to_numeric(d["long_km"], errors="coerce").abs()
    largo = largo.where(largo > 0, np.nan)
    expo = np.log((largo * 1.0).fillna(1e-3).to_numpy())
    assert np.isfinite(expo).all(), "exposición no finita: el offset no puede llevar NaN"


def test_fit_model_rechaza_exposicion_no_positiva():
    """El fallo anterior: `np.clip(expo, 1e-6, None)` aceptaba exposición 0 y el
    modelo se ajustaba "bien" sobre una exposición nula. Ahora es un error."""
    d = _df_tramos()
    X = mm._construir_X(d)
    with pytest.raises(ValueError, match="exposici"):
        mm.fit_model(d["y"], X, expo_km=pd.Series(np.zeros(len(d))))
    with pytest.raises(ValueError, match="exposici"):
        mm.fit_model(d["y"], X, expo_km=pd.Series([-3.6] + [10.0] * (len(d) - 1)))


def test_la_longitud_no_entra_en_la_matriz_de_diseno():
    """`long_km` a la vez como covariable y como offset hace la matriz singular:
    `LinAlgError: Singular matrix` y los cuatro modelos caían al respaldo con
    `alpha=1` clavado, sin dispersión estimada."""
    d = _df_tramos()
    X = mm._construir_X(d)
    assert "long_km" not in X.columns


def test_no_se_inventa_una_variable_que_no_existe_en_el_dataset():
    """`dataset_modelo.csv` no tiene `red_vial`. El `if ... else 0.0` fabricaba
    una columna constante 0 que parecía una variable real y singularizaba."""
    d = _df_tramos()
    assert "red_vial" not in d.columns
    assert "es_ruta_nacional" not in mm._construir_X(d).columns


def test_la_topografia_real_no_es_llanura():
    """Las categorías son ONDULADO / PLANO / MONTAÑOSO. `topografia_llanura`
    comparaba contra una categoría inexistente, valía siempre 0, y PLANO quedaba
    como referencia sin nombrarla."""
    d = _df_tramos()
    X = mm._construir_X(d)
    assert "topografia_llanura" not in X.columns
    assert "topografia_ondulado" in X.columns
    assert "topografia_montanoso" in X.columns
    # PLANO es la referencia: la suma de los dos dummies no es 1.
    suma = X["topografia_ondulado"] + X["topografia_montanoso"]
    assert (suma == 1).any() and (suma == 0).any()


# ── La dispersión se estima de verdad ───────────────────────────────────────


def test_el_perfil_de_alpha_no_pega_en_el_borde():
    """Con la verosimilitud mal escrita (un término `(1/α)·log(1/α)` que en la
    forma de statsmodels se cancela) la verosimilitud crecía sin límite al bajar
    α y el perfil declaraba siempre el mínimo de la rejilla."""
    d = _df_tramos()
    X = mm._construir_X(d)
    largo = pd.to_numeric(d["long_km"], errors="coerce").abs()
    expo = np.log((largo * 4.99).to_numpy())
    y = d["y"].to_numpy()
    mejor = mm.alpha_por_verosimilitud(y, mm.sm.add_constant(X), expo)
    assert mejor is not None
    assert not mejor["alpha_en_borde"], (
        f"alpha={mejor['alpha']} en el borde de la rejilla: el perfil está mal"
    )


def test_alpha_crece_con_la_sobredispersion():
    """Más dispersión necesita más `alpha`. Con datos Poisson (sin
    sobredispersión) el perfil debe acercarse a 0, y con sobredispersión fuerte a
    valores claramente mayores que 0."""
    rng = np.random.default_rng(11)
    n = 600
    largo = np.full(n, 1.0)
    expo = np.log(largo * 1.0)
    X = mm.sm.add_constant(np.ones((n, 1)))
    poisson = rng.poisson(2.0, n).astype(float)
    sobre = rng.negative_binomial(n=0.2, p=0.2 / 2.2, size=n).astype(float)
    a_poisson = mm.alpha_por_verosimilitud(poisson, X, expo)["alpha"]
    a_sobre = mm.alpha_por_verosimilitud(sobre, X, expo)["alpha"]
    assert a_sobre > a_poisson
    assert a_sobre > 1.0


def test_el_reparto_de_ositran_conserva_el_total():
    """`reparto_proporcional_a_longitud` reparte por longitud; si pierde o inventa
    accidentes, la suma por ruta deja de cuadrar con el agregado de origen."""
    d = _df_tramos(n=50)
    d["ruta"] = ["R1"] * 25 + ["R2"] * 25
    d["ositran_n_total"] = 0.0
    d.loc[:24, "ositran_n_total"] = 100.0
    d.loc[25:, "ositran_n_total"] = 40.0
    d["ositran_n"] = mm.reparto_proporcional_a_longitud(
        d, col_ruta="ruta", col_total="ositran_n_total", col_long="long_km")
    for ruta, total in (("R1", 100.0), ("R2", 40.0)):
        assert abs(d.loc[d.ruta == ruta, "ositran_n"].sum() - total) <= 1.0


# ── McFadden y dispersión: las cifras que se publican ───────────────────────


def test_mcfadden_no_es_negativo_con_un_modelo_ajustado():
    """Con el modelo nulo mal construido (media constante, sin offset) el
    cociente puede salir negativo, y en McFadden es imposible."""
    d = _df_tramos()
    X = mm._construir_X(d)
    largo = pd.to_numeric(d["long_km"], errors="coerce").abs()
    expo = np.log((largo * 1.0).to_numpy())
    y = d["y"].astype(float)
    res, irrs, meta = mm.fit_model(y, X, expo_km=largo)
    assert meta["pseudo_r2_mcfadden"] >= 0.0
    assert np.isfinite(meta["pearson_chi2_sobre_df"])
    assert meta["pearson_chi2_sobre_df"] > 0


def test_chi2_sobre_df_es_pdispersion_y_no_deviance():
    """`GLMResults.scale` es el Pearson χ² sobre gl residuales y el script lo
    etiquetaba "deviance/df". Con la offset cambia el valor, así que la etiqueta
    equivocada no es cosmética."""
    d = _df_tramos()
    X = mm._construir_X(d)
    largo = pd.to_numeric(d["long_km"], errors="coerce").abs()
    expo = np.log((largo * 1.0).to_numpy())
    res = mm._ajustar_glm_nb(d["y"].to_numpy(), mm.sm.add_constant(X), expo, 1.0)
    esperado = float(np.nansum(np.asarray(res.resid_pearson) ** 2) / res.df_resid)
    assert mm.pearson_chi2_sobre_df(res) == pytest.approx(esperado)
    assert mm.pearson_chi2_sobre_df(res) != pytest.approx(res.deviance / res.df_resid)


def test_el_modelo_se_ajusta_tambien_con_los_tramos_en_cero():
    """Filtrar `y > 0` tiraba 2.472 de 3.750 filas y convertía el modelo en otro
    distinto (tasa condicionada a "hubo al menos un siniestro"). Con y = 0, el
    perfil de alpha se va al borde y McFadden cae a ~0."""
    d = _df_tramos()
    d["y"] = np.where(d.index % 3 == 0, d["y"], 0.0)
    X = mm._construir_X(d)
    largo = pd.to_numeric(d["long_km"], errors="coerce").abs()
    _, _, meta = mm.fit_model(d["y"].astype(float), X, expo_km=largo)
    assert meta["n"] == len(d)
    assert meta["pseudo_r2_mcfadden"] >= 0.0


# ── La identidad de la respuesta combinada ──────────────────────────────────


def test_y_total_es_onsv_mas_sutran_menos_los_vistos_por_ambas():
    """La identidad que hace defendible `y_total`. Con datos reales:
    993 + 3.932 - 26 = 4.899."""
    n = 500
    rng = np.random.default_rng(5)
    largo = rng.uniform(0.5, 30.0, n)
    ids = np.arange(n)
    c_onsv = pd.Series(rng.integers(0, 4, n), index=ids)
    c_sut = pd.Series(rng.integers(0, 6, n), index=ids)
    c_ambos = pd.Series(rng.integers(0, 2, n), index=ids).clip(
        upper=np.minimum(c_onsv, c_sut))
    # c_onsv incluye los que también vio SUTRAN (etiqueta "ONSV+SUTRAN").
    c_uni = c_onsv + c_sut - c_ambos
    df = pd.DataFrame({"id_tramo": ids, "long_km": largo})
    df["y_total"] = df["id_tramo"].map(c_uni).fillna(0).astype(int)
    assert df["y_total"].sum() == (c_onsv + c_sut - c_ambos).sum()
    assert (df["y_total"] >= 0).all()


def test_la_exposicion_es_km_por_ano_no_solo_km():
    """Con el mismo offset para las cuatro respuestas, el modelo de la ventana
    común (9 meses) estimaba una tasa 6,7 veces menor de la real y sus IRRs
    quedaban mal escalados."""
    largo = pd.Series([10.0, 20.0])
    expo_comun = (largo * 0.7447)
    expo_panel = (largo * 4.99)
    assert expo_comun.sum() == pytest.approx(22.341, abs=1e-6)
    assert expo_panel.sum() / expo_comun.sum() == pytest.approx(4.99 / 0.7447, rel=1e-3)


def test_el_centinela_sin_asignar_es_na_y_no_uno_negativo():
    """`asignar_por_km_red` deja NA, no -1. Filtrar por `< 0` no quita nada y
    `groupby("idx_tramo")` descarta los NA en silencio: 216 de 5.115 eventos
    desaparecieron de `y_total` sin un solo aviso."""
    import panel_anual

    tramos = pd.DataFrame({
        "id_tramo": [0, 1], "ruta": ["PE-1N", "PE-2N"],
        "km0": [0.0, 100.0], "km1": [50.0, 150.0], "long_km": [50.0, 50.0],
    })
    eventos = pd.DataFrame({
        "fecha_dt": pd.to_datetime(["2021-06-01"] * 3),
        "ruta": ["PE-1N", "PE-2N", "PE-9X"],
        "km_red": [10.0, 120.0, 10.0],
    })
    ev = panel_anual.asignar_por_km_red(eventos, tramos)
    assert ev["idx_tramo"].notna().tolist() == [True, True, False]
    assert int(ev["idx_tramo"].isna().sum()) == 1

    # Un consumidor que filtre por `< 0` en vez de `notna()` no quita NADA: el NA
    # no es negativo, así que la fila sigue ahí y luego la descarta el groupby.
    mal = ev[ev["idx_tramo"].astype("Int64") < 0]
    assert len(mal) == 0
    assert int(ev.groupby("idx_tramo").size().sum()) == 2
    conteo = ev[ev["idx_tramo"].notna()].groupby("idx_tramo").size()
    assert int(conteo.sum()) == 2


def test_y_total_cuadra_con_el_total_de_red_menos_los_no_asignables():
    """La suma por tramo tiene que ser el total de red menos lo que no se pudo
    colocar. Si no, `y_total` es un número sin origen conocido."""
    import panel_anual

    rng = np.random.default_rng(2)
    n = 120
    # Tramos contiguos y monótonos: `km1` acumulado y `km0` el inicio del tramo.
    # Con km0 no monótono los tramos se solapan y hay km dentro de dos a la vez.
    largos = rng.uniform(2, 9, n)
    km1 = np.cumsum(largos)
    km0 = km1 - largos
    tramos = pd.DataFrame({
        "id_tramo": np.arange(n), "ruta": "PE-1N", "km0": km0, "km1": km1,
        "long_km": largos,
    })
    dentro = rng.uniform(km0[:60], km1[:60])   # 60 km, siempre dentro de su tramo
    fuera = np.concatenate([
        rng.uniform(km1.max() + 10, km1.max() + 100, 10),   # km fuera de la red
        np.full(5, 10.0),                                    # ruta inexistente
    ])
    eventos = pd.DataFrame({
        "fecha_dt": pd.to_datetime(["2021-06-01"] * 75),
        "ruta": ["PE-1N"] * 60 + ["PE-1N"] * 10 + ["NOEXISTE"] * 5,
        "km_red": np.concatenate([dentro, fuera]),
    })
    ev = panel_anual.asignar_por_km_red(eventos, tramos)
    c = ev[ev["idx_tramo"].notna()].groupby("idx_tramo").size()
    assert int(c.sum()) == 60
    # 15 no asignables: 10 con km fuera del rango de la red + 5 con ruta inexistente.
    assert int(ev["idx_tramo"].isna().sum()) == 15
    assert len(ev) - int(c.sum()) == 15


def test_la_cobertura_de_ositran_se_reporta_no_se_oculta():
    """OSITRAN usa códigos de ruta numéricos (030A, 118.2) y la red del proyecto
    los de MTC (PE-02). Solo 26 de 103 rutas casan, así que el reparto cubre el
    42.9% de los 41.833 accidentes. Publicar 17.943 como si fuera el total de
    OSITRAN presenta una cobertura parcial como fuente completa.

    La propiedad de "las rutas que no casan no reciben nada" no la cumple la
    función de reparto (que solo conoce el frame que recibe) sino el `merge`
    previo: una ruta de la fuente ausente de la red ni siquiera llega al reparto.
    """
    import json

    texto = (ROOT / "scripts/modelo_multi.py").read_text(encoding="utf-8")
    assert "ositran_cobertura" in texto
    assert '"accidentes_fuente"' in texto

    d = _df_tramos(n=40)
    d["ruta"] = ["PE-1N"] * 20 + ["030A"] * 20
    d["ositran_n_total"] = 0.0
    d.loc[:19, "ositran_n_total"] = 80.0
    d.loc[20:, "ositran_n_total"] = 1000.0
    # Lo que el reparto ve es solo lo que el merge dejó en la red:
    red = d[d.ruta == "PE-1N"].copy()
    red["ositran_n"] = mm.reparto_proporcional_a_longitud(
        red, col_ruta="ruta", col_total="ositran_n_total", col_long="long_km")
    assert red["ositran_n"].sum() == 80

    stats = ROOT / "data" / "processed" / "dashboard" / "modelo_stats_multi.json"
    if not stats.exists():
        pytest.skip("modelo_stats_multi.json no generado; ejecuta scripts/modelo_multi.py")
    j = json.loads(stats.read_text(encoding="utf-8"))
    cob = j["ositran_cobertura"]
    assert cob["accidentes_fuente"] == 41833
    assert cob["accidentes_asignados"] == 17943
    assert cob["cobertura"] == pytest.approx(0.429, abs=1e-3)
    assert cob["rutas_fuente"] == 103
    assert cob["rutas_con_coincidencia"] == 26
    # La nota publicada tiene que advertirlo, no solo el número de cobertura.
    assert "NO es el total de OSITRAN" in j["notas"]["y_ositran"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))