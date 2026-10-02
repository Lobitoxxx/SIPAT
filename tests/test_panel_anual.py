"""Regresiones del panel tramo × año (`scripts/panel_anual.py`).

EL DEFECTO QUE ESTOS TESTS DOCUMENTAN
-------------------------------------
`dataset_modelo.csv` era un agregado por tramo sin ningún año, y su comentario
decía "variable objetivo estandarizada por año" mientras la exposición era
`expo_km = long_km`, o sea km y no km·año. La promesa no estaba implementada.

Dos consecuencias concretas que se comprueban aquí:

1. **No se puede validar en el tiempo.** Sin un eje de años no hay holdout
   temporal, así que cualquier "el modelo predice" es una afirmación sin
   prueba. `construir_panel` es lo que hace posible esa prueba.
2. **La exposición no era comparable.** Un tramo con cobertura de 5 años y otro
   de 1 They'd share denominator; `expo_km_anio` corrige eso.

Y un tercer defecto que solo aparece al integrar: la primera versión del panel
asignaba los eventos al **centroide** del tramo más cercano, mientras `onsv_n`
venía de la asignación por **(ruta, km en la red)** de `features_tramos.py`. Las
dos son defendibles por separado, pero juntas hacen que el panel y el dataset
digan números distintos para el mismo tramo: **1.183 de 3.750 tramos cambiaban**.
Por eso `asignar_por_km_red` replica la regla canónica y hay un test que exige
que panel y agregado coincidan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import panel_anual


def _eventos(coords, fechas):
    return pd.DataFrame(
        {
            "lat": [c[0] for c in coords],
            "lon": [c[1] for c in coords],
            "fecha_dt": pd.to_datetime(fechas),
            "fallecidos": np.ones(len(coords), dtype=int),
        }
    )


def _tramos():
    return pd.DataFrame(
        {
            "id_tramo": [0, 1, 2],
            "ruta": ["PE-1", "PE-1", "PE-5"],
            "km0": [0.0, 10.0, 0.0],
            "km1": [10.0, 20.0, 50.0],
            "long_km": [10.0, 10.0, 50.0],
        }
    )


class TestRejillaCompleta:
    def test_la_rejilla_incluye_los_ceros(self):
        """Un tramo sin siniestros en un año vale información: es una celda cero."""
        ev = _eventos([(-12.0, -77.0)], ["2021-05-01"])
        ev["ruta"] = "PE-1"
        ev["km_red"] = 5.0
        ev = panel_anual.asignar_por_km_red(ev, _tramos(), col_ruta="ruta", col_km="km_red")

        panel = panel_anual.construir_panel(
            ev, tramo_ids=[0, 1, 2], long_km=[10.0, 10.0, 50.0], anios=[2021, 2022]
        )

        assert len(panel) == 6, "3 tramos × 2 años deben salir aunque no haya eventos"
        assert (panel["n_eventos"] == 0).sum() == 5
        assert panel["n_eventos"].sum() == 1

    def test_la_exposicion_es_km_anio(self):
        ev = _eventos([(-12.0, -77.0)], ["2021-05-01"])
        ev["ruta"] = "PE-1"
        ev["km_red"] = 5.0
        ev = panel_anual.asignar_por_km_red(ev, _tramos(), col_ruta="ruta", col_km="km_red")

        panel = panel_anual.construir_panel(
            ev, tramo_ids=[0, 1, 2], long_km=[10.0, 10.0, 50.0], anios=[2021, 2022, 2023]
        )

        assert panel.loc[panel["idx_tramo"] == 0, "expo_km"].iloc[0] == 10.0
        assert panel.loc[panel["idx_tramo"] == 0, "expo_km_anio"].iloc[0] == 30.0

    def test_el_agregado_suma_el_panel(self):
        ev = _eventos(
            [(-12.0, -77.0), (-12.0, -77.0), (-12.0, -77.0)],
            ["2021-05-01", "2021-08-01", "2022-02-01"],
        )
        ev["ruta"] = "PE-1"
        ev["km_red"] = 5.0
        ev = panel_anual.asignar_por_km_red(ev, _tramos(), col_ruta="ruta", col_km="km_red")

        panel = panel_anual.construir_panel(
            ev, tramo_ids=[0, 1, 2], long_km=[10.0, 10.0, 50.0], anios=[2021, 2022]
        )
        agg = panel_anual.panel_a_agregado_tramo(panel)

        assert agg.loc[0, "y_total"] == 3
        assert agg.loc[0, "y_anios_con_evento"] == 2
        assert agg.loc[0, "y_anual_medio"] == pytest.approx(1.5)


class TestAsignacionPorKmRed:
    def test_replica_la_regla_de_features_tramos(self):
        ev = _eventos([(0.0, 0.0), (0.0, 0.0)], ["2021-01-01", "2021-01-01"])
        ev["ruta"] = ["PE-1", "PE-5"]
        ev["km_red"] = [5.0, 25.0]

        out = panel_anual.asignar_por_km_red(ev, _tramos(), col_ruta="ruta", col_km="km_red")

        assert list(out["idx_tramo"]) == [0, 2]

    def test_un_km_fuera_de_la_red_no_se_asigna(self):
        ev = _eventos([(0.0, 0.0)], ["2021-01-01"])
        ev["ruta"] = "PE-1"
        ev["km_red"] = 999.0

        out = panel_anual.asignar_por_km_red(ev, _tramos(), col_ruta="ruta", col_km="km_red")

        assert out["idx_tramo"].isna().all()

    def test_una_ruta_desconocida_no_se_asigna(self):
        ev = _eventos([(0.0, 0.0)], ["2021-01-01"])
        ev["ruta"] = "PE-999"
        ev["km_red"] = 5.0

        out = panel_anual.asignar_por_km_red(ev, _tramos(), col_ruta="ruta", col_km="km_red")

        assert out["idx_tramo"].isna().all()


class TestCoherenciaConDatasetModelo:
    """El panel y `dataset_modelo.csv` tienen que decir lo mismo del mismo tramo."""

    def test_el_panel_reproduce_onsv_n(self, eventos_onsv, tramos_modelo):
        ev = eventos_onsv.copy()
        ev["fecha_dt"] = pd.to_datetime(ev["fecha"], errors="coerce")
        ev["km_red"] = pd.to_numeric(ev["km_red"], errors="coerce")
        ev["fallecidos"] = pd.to_numeric(ev["fallecidos"], errors="coerce")

        tramos = tramos_modelo[["id_tramo", "ruta", "km0", "km1", "long_km"]]

        ev = panel_anual.asignar_por_km_red(
            ev, tramos, col_ruta="COD CARRETERA", col_km="km_red"
        )
        panel = panel_anual.construir_panel(
            ev,
            tramo_ids=tramos["id_tramo"],
            long_km=tramos["long_km"],
            anios=sorted(int(a) for a in ev["anio"].dropna().unique()),
        )
        agg = panel_anual.panel_a_agregado_tramo(panel, prefijo="p_")

        esperado = tramos_modelo.set_index("id_tramo")["y_onsv"].astype(int)
        real = agg["p_total"].reindex(esperado.index).fillna(0).astype(int)

        assert int((real != esperado).sum()) == 0, (
            "el panel y 'y_onsv' no coinciden: la asignación de eventos difiere"
        )

    def test_dataset_modelo_expone_km_anio_y_no_solo_km(self, tramos_modelo):
        """El dataset tiene que llevar la exposición en km·año, no solo en km."""
        assert "expo_km_anio" in tramos_modelo.columns
        assert "n_anios_cubiertos" in tramos_modelo.columns
        assert "densidad_anual" in tramos_modelo.columns
        assert (tramos_modelo["n_anios_cubiertos"] > 1).all(), (
            "un único año de cobertura no puede llamarse 'estandarizada por año'"
        )
        esperado = tramos_modelo["expo_km"] * tramos_modelo["n_anios_cubiertos"]
        assert np.allclose(tramos_modelo["expo_km_anio"], esperado)
        assert (tramos_modelo["expo_km_anio"] > tramos_modelo["expo_km"]).all()

    def test_la_exposicion_no_ignora_los_anos(self, tramos_modelo):
        """La densidad anual no puede ser el conteo bruto dividido por km pelado."""
        validos = (tramos_modelo["expo_km_anio"] > 0) & (tramos_modelo["y_onsv"] > 0)
        esperado = tramos_modelo["y_onsv"] / tramos_modelo["expo_km_anio"]
        con_km = tramos_modelo["y_onsv"] / tramos_modelo["expo_km"]

        assert np.allclose(tramos_modelo.loc[validos, "densidad_anual"], esperado[validos])
        assert (tramos_modelo.loc[validos, "densidad_anual"] < con_km[validos]).all()
        # Con km pelado la densidad sería `n_anios_cubiertos` veces mayor.
        ratio = con_km[validos] / tramos_modelo.loc[validos, "densidad_anual"]
        assert np.allclose(ratio, tramos_modelo.loc[validos, "n_anios_cubiertos"])