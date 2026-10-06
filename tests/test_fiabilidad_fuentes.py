# -*- coding: utf-8 -*-
"""Regresiones de `scripts/fiabilidad_fuentes.py`.

Cada test documenta por que un test sintetico no detectaba el fallo. Si uno de
estos falla, no se arregla el test: se lee el comentario, porque el fallo esta
en una afirmacion del modulo que los datos contradicen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fiabilidad_fuentes as ff  # noqa: E402


# --------------------------------------------------------------------------
# Ventanas: "hay solape" y "solape vacio" son cosas distintas
# --------------------------------------------------------------------------
def _onsv(fechas, lat=-12.0, lon=-77.0):
    """Un-frame ONSV con las columnas que `unificar_onsv_sutran` exige.

    Los fixtures iniciales no traian `lat`/`lon`, asi que los tests de
    Lincoln-Petersen morian con `KeyError: 'lat'` antes de llegar al calculo que
    pretendian comprobar: el test no verificaba nada.
    """
    n = len(fechas)
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(fechas),
            "lat": [lat] * n,
            "lon": [lon] * n,
            "fallecidos": [0] * n,
            "COD CARRETERA": ["PE-1N"] * n,
            "km_red": [10.0] * n,
        }
    )


def _sutran(fechas, lat=-12.0, lon=-77.0):
    n = len(fechas)
    return pd.DataFrame(
        {
            "FECHA_DT": pd.to_datetime(fechas),
            "LATITUD_GEO": [lat] * n,
            "LONGITUD_GEO": [lon] * n,
            "FALLECIDOS": [0] * n,
            "CODIGO_VIA": ["PE-1N"] * n,
            "KM": [10.0] * n,
        }
    )


def test_ventanas_reportan_solape_real():
    v = ff.ventanas(
        _onsv(["2021-01-01", "2025-12-28"]), _sutran(["2020-01-01", "2021-09-30"])
    )
    c = v["comun_onsv_sutran"]
    assert c["hay_solape"] is True
    assert c["inicio"] == "2021-01-01"
    assert c["fin"] == "2021-09-30"
    # El solape real son ~9 meses. Un modulo querimpiese "21 meses" estaria
    # contando la ventana de una sola fuente.
    assert c["meses"] == pytest.approx(9, abs=1)


def test_sin_solape_temporal_no_inventa_ventana():
    v = ff.ventanas(_onsv(["2024-01-01"]), _sutran(["2020-01-01"]))
    c = v["comun_onsv_sutran"]
    assert c["hay_solape"] is False
    assert c["meses"] is None


# --------------------------------------------------------------------------
# Coordenadas
# --------------------------------------------------------------------------
def test_coordenadas_detectan_nulos_y_fuera_de_peru():
    d = pd.DataFrame(
        {
            "lat": [12.0, np.nan, 0.5, 45.0],
            "lon": [-77.0, -77.0, np.nan, -100.0],
        }
    )
    q = ff.calidad_coordenadas(d, "lat", "lon", "X")
    assert q["lat_nulos"] == 1
    assert q["lon_nulos"] == 1
    # 45/-100 esta fuera del Peru; el 0.5 de lat si esta dentro del rango.
    assert q["fuera_de_peru"] == 2


def test_duplicados_exactos_de_posicion_se_cuentan():
    # Sin este test, un agregado por posicion contaria dos veces el mismo
    # accidente. En SUTRAN es el 46% de las filas.
    d = pd.DataFrame({"lat": [-12.0] * 3 + [-13.0], "lon": [-77.0] * 3 + [-76.0]})
    q = ff.calidad_coordenadas(d, "lat", "lon", "X")
    assert q["duplicados_exactos_posicion"] == 2
    assert q["pct_duplicados"] == pytest.approx(50.0)


def test_coordenadas_no_dividen_por_cero():
    d = pd.DataFrame({"lat": [], "lon": []})
    q = ff.calidad_coordenadas(d, "lat", "lon", "X")
    assert q["n_eventos"] == 0
    assert q["pct_fuera_de_peru"] is None
    assert q["pct_duplicados"] is None


def test_nulos_de_lat_y_lon_no_se_suman_dos_veces():
    """`lat_nulos + lon_nulos` no es el numero de filas sin coordenada.

    En SUTRAN las 499 filas sin coordenada tienen las dos columnas vacias a la
    vez, asi que sumarlas daba 998 y duplicaba el defecto. Se reporta
    `sin_coordenada_usable`, que cuenta filas.
    """
    d = pd.DataFrame({"lat": [-12.0, np.nan, -13.0], "lon": [-77.0, np.nan, -76.0]})
    q = ff.calidad_coordenadas(d, "lat", "lon", "X")
    assert q["lat_nulos"] == 1 and q["lon_nulos"] == 1
    assert q["sin_coordenada_usable"] == 1
    assert q["pct_sin_coordenada"] == pytest.approx(100 / 3, abs=0.01)


def test_sin_coordenada_no_cuenta_como_fuera_de_peru():
    """Ausencia de dato y error de geocodificacion son defectos distintos.

    Una fila sin coordenada no esta mal situada: esta sin situar. Sumarlas al
    indicador de error de geocodificacion infla el defecto y hace que SUTRAN
    parezca peor de lo que es (0 filas realmente fuera del Peru).
    """
    d = pd.DataFrame({"lat": [np.nan, -12.0], "lon": [np.nan, -77.0]})
    q = ff.calidad_coordenadas(d, "lat", "lon", "X")
    assert q["sin_coordenada_usable"] == 1
    assert q["fuera_de_peru"] == 0
    assert q["pct_fuera_de_peru"] == 0.0


# --------------------------------------------------------------------------
# OSITRAN: el denominador de la cobertura
# --------------------------------------------------------------------------
def test_ositran_reporta_la_cobertura_sobre_los_dos_denominadores():
    """Si solo se publica 42,9%, el lector creera que se pierde el 57% de la fuente.

    La realidad es que el 39,5% viene como SIN INFO y no se le puede atribuir un
    tramo. Sobre lo utilizable la cobertura es 71%. Publicar una sola de las dos
    cifras induce a error en direccion opuesta a la real.
    """
    o = pd.DataFrame(
        {
            "ruta": ["SIN INFO", "PE-1N", "PE-1S", "PE-9X"],
            "siglas": ["PE"] * 4,
            "anio": [2021] * 4,
            "cant_accidentes": [50, 20, 20, 10],
        }
    )
    red = pd.DataFrame({"ruta": ["PE-1N", "PE-1S"]})
    r = ff.calidad_ositran(o, red)
    assert r["eventos_sin_info_ruta"] == 50
    assert r["pct_sin_info_ruta"] == pytest.approx(50.0)
    assert r["eventos_con_ruta"] == 50
    # 40 de 100 eventos caen en ruta de red.
    assert r["eventos_sobre_ruta_de_red"] == 40
    assert r["cobertura_pct_del_total"] == pytest.approx(40.0)
    assert r["cobertura_pct_de_los_con_ruta"] == pytest.approx(80.0)
    # Las dos cifras deben aparecer siempre y ser distintas cuando hay SIN INFO.
    assert r["cobertura_pct_del_total"] != r["cobertura_pct_de_los_con_ruta"]


# --------------------------------------------------------------------------
# Lincoln-Petersen: el calculo y, sobre todo, el veredicto
# --------------------------------------------------------------------------
def test_lincoln_petersen_reproduce_el_calculo_a_mano():
    """El estimador tiene que ser n_a * n_b / n_ab, sin factores ocultos.

    Con un unico evento en cada fuente que coincide: n_a = n_b = n_ab = 1, luego
    N = 1. Este test existia pero no podia detectar nada: los fixtures no traian
    `lat`/`lon` y el modulo reventaba con KeyError antes de calcular.
    """
    r = ff.solape_onsv_sutran(_onsv(["2021-01-01"]), _sutran(["2021-01-01"]))
    lp = r["lincoln_petersen"]
    assert lp["n_a"] == 1
    assert lp["n_b"] == 1
    assert lp["n_ab"] == 1
    assert lp["n_estimado_lincoln_petersen"] == pytest.approx(1.0, rel=0.01)
    # Con n_a = n_b = n_ab el intervalo tiene que ser estrecho, no enorme.
    assert lp["ic95_bajo"] <= 1.0 <= lp["ic95_alto"]


def test_lincoln_petersen_usa_marginales_inclusivos():
    """`n_a` de LP es el total que vio la fuente, no el exclusivo.

    `resumen_unificacion` etiqueta un evento emparejado como `ONSV+SUTRAN`, asi
    que nunca aparece en `n_onsv`. Tomar ese numero como `n_a` sube el estimador:
    con los datos reales daba 30x en vez de 25x, y el intervalo se desplazaba.
    """
    # El segundo evento de SUTRAN cae fuera de la ventana comun, asi que el
    # filtro por ventana no lo cuenta como exclusivo de SUTRAN.
    r = ff.solape_onsv_sutran(
        _onsv(["2021-01-01", "2021-01-02"]), _sutran(["2021-01-01", "2021-01-03"])
    )
    lp = r["lincoln_petersen"]
    # Un evento coincide; ONSV aporta otro que SUTRAN no vio.
    assert lp["n_ab"] == 1
    assert lp["n_a_exclusivo"] == 1
    assert lp["n_b_exclusivo"] == 0
    assert lp["n_a"] == lp["n_a_exclusivo"] + lp["n_ab"]
    assert lp["n_b"] == lp["n_b_exclusivo"] + lp["n_ab"]
    # El estimador se calcula con los inclusivos: 2 * 1 / 1 = 2.
    assert lp["n_estimado_lincoln_petersen"] == pytest.approx(2.0, rel=0.01)


def test_lincoln_petersen_no_inventa_estimador_sin_solape():
    """Con n_ab = 0 el estimador no existe (division por cero).

    Un modulo que devolviera N = 0 o NaN sin avisar publicaria "no hay
    subnotificacion" cuando en realidad no hay informacion para estimarla.
    """
    onsv = _onsv(["2021-01-01", "2021-02-01"])
    sutran = _sutran(["2021-03-01", "2021-04-01"])
    sutran["CODIGO_VIA"] = "PE-9X"
    sutran["KM"] = 500.0
    r = ff.solape_onsv_sutran(onsv, sutran)
    lp = r["lincoln_petersen"]
    if lp["n_ab"] == 0:
        assert "n_estimado_lincoln_petersen" not in lp


def test_el_modulo_no_declara_estimable_la_subnotificacion():
    """El fallo que mas caro sale: publicar un factor de 30x como subnotificacion.

    Con estos datos ONSV y SUTRAN recorren las mismas carreteras (Jaccard 0,44)
    pero solo coincide el 0,5% de los eventos. Lincoln-Petersen exige dos
    capturas independientes de la MISMA poblacion; aqui eso no se cumple y el
    estimador describes dos fuentes no comparables, no una poblacion oculta.
    """
    res = ff.analizar()
    a = {x["afirmacion"]: x for x in res["afirmaciones"]}
    sub = next(v for k, v in a.items() if "Lincoln-Petersen" in k)
    assert sub["veredicto"] == "NO ESTIMABLE"
    assert res["independencia"]["supuesto_independencia_verificable"] is False
    # Y el limite tiene que explicar el motivo, no solo decir "no".
    assert len(sub["limite"]) > 80


def test_el_solape_no_se_declara_estable_si_varia():
    """n_ab va de 13 a 95 segun el radio: afirmar que es estable seria falso."""
    res = ff.analizar()
    est = next(x for x in res["afirmaciones"] if "estable" in x["afirmacion"])
    n_ab = [f["n_ambos"] for f in res["sensibilidad_matching"] if "n_ambos" in f]
    if max(n_ab) > 2 * min(n_ab):
        assert est["veredicto"] == "NO"


# --------------------------------------------------------------------------
# Contrato de salida
# --------------------------------------------------------------------------
def test_salida_tiene_afirmaciones_con_veredicto_evidencia_y_limite():
    res = ff.analizar()
    assert len(res["afirmaciones"]) >= 4
    for a in res["afirmaciones"]:
        assert set(a) >= {"afirmacion", "veredicto", "evidencia", "limite"}
        assert a["evidencia"].strip()
        assert a["limite"].strip()


def test_ositran_pesa_accidentes_y_no_filas():
    """`n_eventos` debe significar accidentes.

    El modulo contaba filas. En la fuente real cada fila vale un accidente, asi
    que el numero coincidia y el defecto no se veia; con una fila que declara
    varios accidentes, contar filas daria una cobertura que no existe.
    """
    o = pd.DataFrame(
        {
            "ruta": ["SIN INFO", "PE-1N", "PE-9X"],
            "siglas": ["PE"] * 3,
            "anio": [2021] * 3,
            "cant_accidentes": [10, 5, 5],
        }
    )
    red = pd.DataFrame({"ruta": ["PE-1N"]})
    r = ff.calidad_ositran(o, red)
    assert r["n_eventos"] == 20
    assert r["n_filas"] == 3
    assert r["eventos_sin_info_ruta"] == 10
    assert r["eventos_con_ruta"] == 10
    assert r["eventos_sobre_ruta_de_red"] == 5
    assert r["cobertura_pct_del_total"] == pytest.approx(25.0)


def test_ositran_sin_columna_de_conteo_cuenta_una_por_fila():
    """Si no hay `cant_accidentes`, la unidad es la fila y se dice cual es."""
    o = pd.DataFrame({"ruta": ["PE-1N"], "siglas": ["PE"], "anio": [2021]})
    r = ff.calidad_ositran(o, pd.DataFrame({"ruta": ["PE-1N"]}))
    assert r["n_eventos"] == 1
    assert r["n_filas"] == 1


def test_afirmaciones_no_inventan_porcentajes_fuera_de_los_datos():
    """El texto del modulo tiene que derivar de `cal_sutran`, no de memoria.

    La primera version de `afirmaciones` decia "un 6% cae fuera del Peru"
    escrito a mano. Los datos reales dicen 0% fuera del Peru y 12,2% sin
    coordenada: la afirmacion era falsa y la evidencia de al lado la contradecia.
    """
    cal = ff.calidad_coordenadas(
        pd.DataFrame({"lat": [-12.0, np.nan], "lon": [-77.0, np.nan]}),
        "lat",
        "lon",
        "SUTRAN",
    )
    o = pd.DataFrame({"ruta": ["PE-1N"], "siglas": ["PE"], "anio": [2021]})
    sol = ff.solape_onsv_sutran(_onsv(["2021-01-01"]), _sutran(["2021-01-01"]))
    indep = ff._diagnostico_independencia(
        _onsv(["2021-01-01"]), _sutran(["2021-01-01"]), sol["lincoln_petersen"], pd.DataFrame({"ruta": ["PE-1N"]})
    )
    filas = ff.afirmaciones(
        sol,
        cal,
        cal,
        ff.calidad_ositran(o, pd.DataFrame({"ruta": ["PE-1N"]})),
        indep,
        ff.sensibilidad_matching(_onsv(["2021-01-01"]), _sutran(["2021-01-01"])),
    )
    txt = " ".join(
        f"{a['evidencia']} {a['limite']}" for a in filas if "coordenadas" in a["afirmacion"]
    )
    assert "50.0%" in txt  # el porcentaje real de filas sin coordenada
    assert "6% cae fuera" not in txt


def test_no_se_emite_indice_unico_de_confiabilidad():
    """Regla del proyecto: ponderar exigiria decidir el peso de cada riesgo.

    Si alguna vez se anade una clave tipo "indice" o "score", este test falla.
    """
    res = ff.analizar()
    assert "indice" not in res
    assert "score" not in res
    assert "confiabilidad" not in res