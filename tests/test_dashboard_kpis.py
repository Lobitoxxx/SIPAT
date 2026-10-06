# -*- coding: utf-8 -*-
"""Regresiones del KPI unionado que `build_dashboard_data.py` publica.

El bug que estos tests fijan: `build_dashboard_data.py` **prometia** en un
comentario una columna `siniestros_union_comun` y nunca la creaba. El comentario
describia un trabajo que no existia, y el dashboard publicaba `siniestros_total`
—una suma de tres fuentes con periodos distintos y sin deduplicar— como si fuera
el total de siniestros de la red.

Cada test documenta por que un test sintetico no detectaba el fallo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import panel_anual  # noqa: E402
from deduplicacion_eventos import (  # noqa: E402
    resumen_unificacion,
    unificar_onsv_sutran,
)

DASH = ROOT / "data" / "processed" / "dashboard"


@pytest.fixture(scope="module")
def tramos_json():
    f = DASH / "tramos_geo.json"
    if not f.exists():
        pytest.skip("falta data/processed/dashboard/tramos_geo.json")
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def meta_json():
    f = DASH / "tramos_geo_meta.json"
    if not f.exists():
        pytest.skip("falta data/processed/dashboard/tramos_geo_meta.json")
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# El contrato: la columna prometida existe y la suma ingenua ya no se llama "total"
# --------------------------------------------------------------------------
def test_la_columna_prometida_existe_de_verdad(tramos_json):
    """`siniestros_union_comun` estaba en el comentario del script y no en el JSON.

    El comentario decia "Se conservan las dos cifras, con nombres que dicen cuál
    es cuál" y solo existia una. Estos tests no podian existir porque el JSON no
    traia la columna que se pretendia comprobar.
    """
    assert tramos_json, "tramos_geo.json vacio"
    for t in tramos_json[:50]:
        assert "siniestros_union_comun" in t
        assert "fallecidos_union_comun" in t
        assert "siniestros_union_comun_km" in t


def test_suma_ingenua_ya_no_se_llama_total(tramos_json):
    """`siniestros_total` se leia como total; ahora se llama por lo que es.

    Un nombre no es cosmetico: quien lea el mapa ve "siniestros_total" y lo
    entiende como la cifra de siniestros de la red, cuando mezcla la ventana de
    ONSV (2021-2025) con la de SUTRAN (2020-2021Q3) y cuenta dos veces cada
    emparejado.
    """
    for t in tramos_json[:50]:
        assert "siniestros_total" not in t
        assert "siniestros_suma_fuentes" in t
        assert "siniestros_suma_fuentes_km" in t


def test_meta_documenta_el_significado_de_cada_columna(meta_json):
    """El JSON es una lista de tramos y no admite metadatos: van aparte."""
    cols = meta_json["columnas_de_conteo"]
    for c in ("siniestros_suma_fuentes", "siniestros_union_comun",
              "siniestros_union_comun_km", "fallecidos_union_comun"):
        assert c in cols
        assert len(cols[c]) > 20, f"columna {c} sin explicacion util"
    assert len(meta_json["por_que_no_hay_un_total"]) > 80
    assert "fiabilidad_fuentes" in meta_json["por_que_no_hay_un_total"]


# --------------------------------------------------------------------------
# La identidad contable: la union es el recuento del modulo de dedup
# --------------------------------------------------------------------------
def test_la_union_es_menor_que_la_suma_ingenua(tramos_json):
    """Si la union igualase o superase la suma, no habria deduplicado nada."""
    uni = sum(t.get("siniestros_union_comun", 0) for t in tramos_json)
    suma = sum(t.get("siniestros_suma_fuentes", 0) for t in tramos_json)
    onsv = sum(t.get("onsv_n", 0) for t in tramos_json)
    sutran = sum(t.get("sutran_n", 0) for t in tramos_json)
    assert uni > 0
    assert uni < suma
    # Y tiene que ser menor que la suma de ONSV y SUTRAN, que es lo que
    # deliberadamente no se deduplica.
    assert uni <= onsv + sutran


def test_la_union_coincide_con_el_modulo_de_dedup(tramos_json, meta_json, data_dir):
    """Reconciliacion exacta contra `resumen_unificacion`.

    La suma de `siniestros_union_comun` en el JSON mas los eventos que caen
    fuera de la red de estudio tiene que ser exactamente `n_unico_total` del
    modulo de deduplicacion. Si no cuadra, el KPI del dashboard cuenta otra cosa
    que el modelo.
    """
    onsv = pd.read_csv(data_dir / "onsv_nacional_geocod.csv")
    sutran = pd.read_csv(data_dir / "sutran_accidentes_geocod.csv")
    res = resumen_unificacion(onsv, sutran)
    n_unico = int(res["n_unico_total"])

    uni = sum(t.get("siniestros_union_comun", 0) for t in tramos_json)
    sin_tramo = int(meta_json["union_onsv_sutran"]["n_sin_tramo_asignable"])

    assert uni + sin_tramo == n_unico
    assert meta_json["union_onsv_sutran"]["n_unicos_ventana_comun"] == n_unico
    # Los marginales que se publican tienen que ser los inclusivos de LP.
    assert meta_json["union_onsv_sutran"]["n_onsv_exclusivo"] == int(res["n_onsv"])
    assert meta_json["union_onsv_sutran"]["n_sutran_exclusivo"] == int(res["n_sutran"])
    assert meta_json["union_onsv_sutran"]["n_vistos_por_ambas"] == int(res["n_ambos"])


def test_la_asignacion_es_la_canonica_por_ruta_y_km(meta_json, repo_root):
    """`asignar_por_km_red`, no el emparejamiento por centroides.

    Con el metodo de centroides 1.183 de los 3.750 tramos cambiaban de conteo, y
    entonces el mapa y `dataset_modelo.csv` marcaban dos cosas distintas sobre el
    mismo tramo. Aqui se comprueba que el script usa la asignacion canonica y que
    su firma es la de `panel_anual`, que es la que replica `features_tramos`.
    """
    import inspect

    fuente = (repo_root / "scripts" / "build_dashboard_data.py").read_text(encoding="utf-8")
    assert "asignar_por_km_red(unif" in fuente
    sig = inspect.signature(panel_anual.asignar_por_km_red)
    assert sig.parameters["col_ruta"].default == "ruta"
    assert sig.parameters["col_km"].default == "km_red"
    # El criterio de emparejamiento queda publicado, no buried en el script.
    crit = meta_json["union_onsv_sutran"]["criterio"]
    assert "radio" in crit and "dia" in crit


def test_la_ventana_de_la_union_es_la_comun_y_es_corta(meta_json):
    """La union tiene ventana; la suma por fuente no la tiene y no se inventa una."""
    v = meta_json["ventana_comun_onsv_sutran"]
    assert v["inicio"] and v["fin"]
    assert v["inicio"] < v["fin"]
    assert 8.0 <= v["meses"] <= 9.5
    # La ventana comun termina en 2021-09 mientras ONSV llega a 2025-12: por eso
    # la union no se puede presentar como el total de la red.
    assert v["fin"].startswith("2021-09")
    assert v["inicio"].startswith("2021-01")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
