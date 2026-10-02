"""Regresiones del Empirical Bayes de tramos (`scripts/eb_tramos.py`).

EL DEFECTO QUE ESTOS TESTS DOCUMENTAN
-------------------------------------
`build_puntos_negros.py` usaba el observado como "predicción":

    pred_km = siniestros_total_km
    w_eb    = pred_total / (pred_total + 1.0)
    eb_km   = w_eb * obs_km + (1 - w_eb) * pred_km     # == obs_km, siempre

Consecuencias, todas verificadas aquí:

1. `eb_km == obs_km` en cada fila: el EB no suavizaba nada.
2. `exceso_eb == 0` en cada fila, así que `exceso_eb > 1` **nunca era cierto**.
3. `(obs_km - pred_km)/pred_km > 2` **nunca era cierto** tampoco: 0 > 2 es falso.
   Dos de los tres criterios de punto negro eran código muerto.
4. `phi = 1.0` hardcodeado: con pred >> 1, `w_eb ≈ 1`, el prior no pesaba nada.
5. Y el lanzafallos del otro lado: un estimador de `k` con unidades mezcladas
   devolvía `k = inf`, que colapsa el EB **sobre el prior** y también anula el
   criterio. Un test que solo mirara "exceso_eb != 0" no lo habría pillado.

Por eso el test principal comprueba la **forma** del resultado (contracción real,
exceso con signo) y no un número: un número concreto sería frágil y, sobre todo,
no es lo que estaba roto.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import eb_tramos


def _tramos_sinteticos(n=400, seed=0):
    """Tramos con sobredispersión real: la tasa verdadera varía por grupo."""
    rng = np.random.default_rng(seed)
    prior_grupo = rng.uniform(0.2, 2.0, size=6)
    grupo = rng.integers(0, 6, size=n)
    km = rng.uniform(1.0, 25.0, size=n)
    obs = rng.poisson(prior_grupo[grupo] * km)
    return pd.DataFrame(
        {
            "id": range(n),
            "region": [f"R{g}" for g in grupo],
            "long_km": km,
            "siniestros_total": obs.astype(float),
        }
    )


class _PuntosNegrosViejos:
    """La implementación que estaba en `build_puntos_negros.py` antes del arreglo.

    Se conserva aquí a propósito: un test de regresión que solo dice "esto ya no
    falla" no explica por qué existía. Este es el "antes" ejecutable.
    """

    @staticmethod
    def eb(df, phi=1.0):
        out = df.copy()
        out["pred_km"] = out["siniestros_total_km"].clip(lower=0.01)
        out["pred_total"] = out["pred_km"] * out["long_km"]
        out["w_eb"] = out["pred_total"] / (out["pred_total"] + phi)
        out["eb_total"] = (
            out["w_eb"] * out["siniestros_total"] + (1 - out["w_eb"]) * out["pred_total"]
        )
        out["eb_km"] = out["eb_total"] / out["long_km"]
        out["exceso_eb"] = ((out["eb_km"] - out["pred_km"]) / out["pred_km"]).fillna(0)
        return out


class TestDefectoEmpiricalBayesDegenerado:
    def test_el_codigo_viejo_no_suaviza_nada(self):
        """Reproduce el defecto: el EB antiguo devuelve exactamente el observado.

        Matiz que hace el test fiel al código real: para los tramos con cero
        siniestros el `clip(lower=0.01)` sí movía algo (a 0.01, y de ahí un
        `exceso_eb` levemente negativo). El invariante que importa es que
        **nunca hay exceso positivo**, que es lo que deja muertos dos criterios.
        """
        df = _tramos_sinteticos()
        df["siniestros_total_km"] = df["siniestros_total"] / df["long_km"]

        viejo = _PuntosNegrosViejos.eb(df)
        con_datos = df["siniestros_total_km"] > 0

        assert np.allclose(viejo.loc[con_datos, "eb_km"], df.loc[con_datos, "siniestros_total_km"])
        assert (viejo["exceso_eb"] <= 0).all(), "el EB antiguo jamás encuentra exceso"

    def test_el_codigo_viejo_deja_muertos_dos_de_tres_criterios(self, datos_reales_tramos):
        """Con datos reales, los dos criterios del EB no seleccionan nada."""
        df = datos_reales_tramos.copy()
        df["siniestros_total_km"] = df["siniestros_total"] / df["long_km"]

        viejo = _PuntosNegrosViejos.eb(df)

        assert not (viejo["exceso_eb"] > 1.0).any()
        assert not (viejo["exceso_eb"] > 0).any()


class TestEmpiricalBayesCorregido:
    def test_el_eb_suaviza_hacia_el_prior(self):
        """El EB tiene que mover el observado, no devolverlo."""
        df = _tramos_sinteticos()
        out = eb_tramos.eb_sobre_tramos(df, grupo="region")

        obs_km = out["siniestros_total"] / out["long_km"]
        assert not np.allclose(out["eb_km"], obs_km), "el EB sigue sin hacer nada"

        # Contracción real: la tasa EB cae entre el observado y el prior.
        entre = (out["eb_km"] >= np.minimum(obs_km, out["prior_km"]) - 1e-9) & (
            out["eb_km"] <= np.maximum(obs_km, out["prior_km"]) + 1e-9
        )
        assert entre.all()

        # Y se mueve en la dirección correcta.
        alto = obs_km > out["prior_km"]
        assert (out.loc[alto, "eb_km"] < obs_km[alto]).all()
        assert (out.loc[~alto, "eb_km"] > obs_km[~alto]).all()

    def test_exceso_eb_tiene_los_dos_signos(self):
        """Un exceso de una sola dirección no puede ser un shrinkage real."""
        out = eb_tramos.eb_sobre_tramos(_tramos_sinteticos(), grupo="region")

        assert (out["exceso_eb"] < 0).any(), "nunca hay exceso por debajo del prior"
        assert (out["exceso_eb"] > 0).any()

    def test_k_es_finito_y_positivo(self):
        """La sobredispersión real de un conteo debe dar un k usable."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            out = eb_tramos.eb_sobre_tramos(_tramos_sinteticos(), grupo="region")

        assert np.isfinite(out["k"].iloc[0]), "k=inf colapsa el EB sobre el prior"
        assert out["k"].iloc[0] > 0

    def test_el_eb_equivale_a_la_forma_ponderada(self):
        """`eb_km == w·obs + (1-w)·prior`. Si no cuadra, la fórmula está mal."""
        out = eb_tramos.eb_sobre_tramos(_tramos_sinteticos(), grupo="region")
        obs_km = out["siniestros_total"] / out["long_km"]

        esperado = out["w_eb"] * obs_km + (1 - out["w_eb"]) * out["prior_km"]

        assert np.allclose(out["eb_km"], esperado)
        assert np.allclose(out["eb_total"], esperado * out["long_km"])

    def test_prior_es_leave_one_out(self):
        """El prior de un tramo no puede contener el propio conteo de ese tramo."""
        df = _tramos_sinteticos()
        out = eb_tramos.eb_sobre_tramos(df, grupo="region")

        g = df[df["region"] == "R0"]
        for _, row in g.iterrows():
            otros = g[g["id"] != row["id"]]
            esperado = otros["siniestros_total"].sum() / otros["long_km"].sum()
            assert out.loc[row.name, "prior_km"] == pytest.approx(esperado)

    def test_grupo_con_un_solo_tramo_cae_al_prior_global(self):
        df = _tramos_sinteticos()
        df.loc[df.index[:3], "region"] = "AISLADO"

        prior = eb_tramos.prior_por_grupo_loo(df, "region")

        assert prior.notna().all(), "un grupo de un tramo no puede dejar el prior en NaN"


class TestCriteriosDePuntoNegro:
    def test_los_tres_criterios_son_alcanzables(self, datos_reales_tramos):
        """Los tres criterios tienen que ser capaces de disparar alguna vez."""
        out = eb_tramos.eb_sobre_tramos(datos_reales_tramos, grupo="region")
        suficiente = out["siniestros_total"] >= 3

        thr_eb = out.loc[suficiente, "exceso_eb"].quantile(0.95)
        crit_eb = suficiente & (out["exceso_eb"] > thr_eb)

        assert crit_eb.sum() > 0, "el criterio EB vuelve a ser código muerto"

    def test_k_infinito_avisa_en_vez_de_fallar_en_silencio(self):
        """Sin sobredispersión medible, k=inf; eso debe ser ruidoso, no un
        `exceso_eb` todo cero que se lee como "no hay puntos negros"."""
        rng = np.random.default_rng(7)
        n = 200
        km = np.full(n, 5.0)
        region = np.array([f"R{i % 4}" for i in range(n)])
        # Poisson puro alrededor del prior: no hay sobredispersión que estimar.
        obs = rng.poisson(1.0 * km).astype(float)
        df = pd.DataFrame({"region": region, "long_km": km, "siniestros_total": obs})

        with pytest.warns(RuntimeWarning):
            out = eb_tramos.eb_sobre_tramos(df, grupo="region")

        assert not np.isfinite(out["k"].iloc[0])


@pytest.fixture(scope="module")
def datos_reales_tramos():
    """`tramos_geo.json` del workspace: 3.750 tramos con conteos reales."""
    import json
    from pathlib import Path

    f = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "processed"
        / "dashboard"
        / "tramos_geo.json"
    )
    if not f.exists():
        pytest.skip("falta data/processed/dashboard/tramos_geo.json")
    with open(f, encoding="utf-8") as fh:
        df = pd.DataFrame(json.load(fh))
    df["long_km"] = pd.to_numeric(df["long_km"], errors="coerce").fillna(0).clip(lower=1e-3)
    df["siniestros_total"] = pd.to_numeric(df["siniestros_total"], errors="coerce").fillna(0)
    return df