"""Regresiones de fiabilidad de fuentes.

Cada test documenta por qué un test sintético **no** detectaba el fallo real.
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
# Coordenadas compartidas no son duplicados
# --------------------------------------------------------------------------


def test_puntos_repetidos_no_se_confunden_con_duplicados():
    """El fallo: contar como duplicados filas que comparten coordenada.

    En SUTRAN la coordenada viene del km del tramo, no de un GPS del lugar del
    accidente, así que 12 accidentes distintos del mismo km comparten punto. Un
    test con datos sintéticos donde cada fila tiene coordenada propia nunca ve
    esto: da 0 duplicados y parece correcto.
    """
    n = 200
    sutran = pd.DataFrame(
        {
            "LATITUD_GEO": [-12.0] * n,  # todos el mismo km
            "LONGITUD_GEO": [-77.0] * n,
            "FECHA_DT": pd.date_range("2021-01-01", periods=n, freq="D"),
            "MODALIDAD": ["CHOQUE", "DESPISTE"] * (n // 2),
        }
    )
    onsv = pd.DataFrame({"lat": [-13.0], "lon": [-78.0], "fecha": pd.to_datetime(["2021-01-01"])})

    res = ff.calidad_coordenadas(onsv, sutran)

    # Todas las filas comparten coordenada, pero ninguna repite día, así que
    # coincidencias de km+fecha deben ser 0.
    assert res["SUTRAN"]["puntos_repetidos"] == n - 1
    assert res["SUTRAN"]["coincidencias_mismo_km_fecha"] == 0


def test_misma_modalidad_acentua_el_candidato_a_duplicado():
    """Con Modalidad, el conteo se estrecha: menos candidatos a doble reporte."""
    fecha = pd.Timestamp("2021-03-10")
    base = {
        "LATITUD_GEO": [-12.0, -12.0, -13.0, -13.0],
        "LONGITUD_GEO": [-77.0, -77.0, -78.0, -78.0],
        "FECHA_DT": [fecha, fecha, fecha, fecha],
        "MODALIDAD": ["CHOQUE", "DESPISTE", "CHOQUE", "CHOQUE"],
    }
    sutran = pd.DataFrame(base)
    onsv = pd.DataFrame({"lat": [-14.0], "lon": [-79.0], "fecha": pd.to_datetime(["2021-01-01"])})

    res = ff.calidad_coordenadas(onsv, sutran)

    # km+fecha: 2 coincidencias (los dos primeros, los dos últimos)
    assert res["SUTRAN"]["coincidencias_mismo_km_fecha"] == 2
    # +modalidad: solo 1, porque el primer par difiere en modalidad
    assert res["SUTRAN"]["coincidencias_misma_modalidad"] == 1


# --------------------------------------------------------------------------
# OSITRAN: la columna de unión
# --------------------------------------------------------------------------


def test_cobertura_ositran_no_usa_siglas():
    """El fallo: unir OSITRAN con la red por `siglas` en vez de por `ruta`.

    OSITRAN trae dos identificadores: `siglas` (16 valores, código corto de
    concesión: ASO, BAC...) y `ruta` (103 valores, identificador de tramo MTC).
    La red vial usa el formato MTC. Unir por `siglas` da **cero** coincidencias y
    la cobertura sale 0%: no es que OSITRAN no toque la red, es que se cruzaron
    códigos de dos sistemas distintos, y el número 0% parece un hallazgo.
    """
    ositran = pd.DataFrame(
        {
            "siglas": ["ASO", "ASO", "BAC"],
            "ruta": ["030A", "030A", "100"],
            "cant_accidentes": [5, 3, 7],
        }
    )
    red = pd.DataFrame({"ruta": ["030A", "100", "PE-02", "PE-04"]})

    cov = ff.cobertura_ositran(ositran, red)

    assert cov["rutas_comunes"] == 2
    assert cov["pct_rutas_comunes"] == 50.0
    # Si alguien cambiara el default a `siglas`, esto da 0 y el test falla.
    assert cov["rutas_comunes"] > 0
    assert cov["columna_union"] == "ruta"


# --------------------------------------------------------------------------
# Lincoln-Petersen
# --------------------------------------------------------------------------


def test_lp_devuelve_intervalo_sobre_log():
    """El estimador lleva su IC en escala logarítmica, que es como se deriva."""
    lp = ff.lincoln_petersen(993, 3932, 26)

    assert lp["estimable"] is True
    # N = n_a * n_b / n_ab
    assert lp["n_estimado"] == pytest.approx(993 * 3932 / 26, rel=1e-3)
    assert lp["ic95_low"] < lp["n_estimado"] < lp["ic95_high"]
    # El IC se construye sobre log(N), así que los multiplicadores hacia abajo y
    # hacia arriba son exp(-1.96·se) y exp(+1.96·se): iguales entre sí en escala
    # lineal, y NO un ±5% simétrico. Ese es el rasgo que distingue un IC
    # log-transformado de uno construido a ojo sobre N.
    mult = 1.96 * lp["se_log_n"]
    # `se_log_n` viene redondeado a 4 decimales en la salida publicada, así que
    # la comprobación usa esa versión redondeada y no la interna.
    assert lp["n_estimado"] / lp["ic95_low"] == pytest.approx(np.exp(mult), rel=1e-3)
    assert lp["ic95_high"] / lp["n_estimado"] == pytest.approx(np.exp(mult), rel=1e-3)
    # Y un IC lineal ingenuo sería mucho más estrecho por arriba que este.
    se_lineal = np.sqrt(lp["n_estimado"]) / 2
    assert lp["ic95_high"] - lp["n_estimado"] > 1.96 * se_lineal


def test_lp_no_estimable_sin_solape():
    """n_ab = 0 significa que las fuentes nunca coinciden: no hay estimador.

    Dividir por cero devolvería `inf`, que al serializar a JSON se vuelve un
    número enorme o un `Infinity` que ningún lector de JSON acepta.
    """
    lp = ff.lincoln_petersen(993, 3932, 0)

    assert lp["estimable"] is False
    assert "n_ab" in lp["motivo"]
    assert "n_estimado" not in lp


def test_supuesto_de_independencia_detecta_ambitos_distintos():
    """El veredicto NO ESTIMABLE depende del supuesto, no del tamaño de n_ab.

    Este es el punto que más fácil se malinterpreta: con n_ab=26 el intervalo de
    Lincoln-Petersen **no** es tan ancho (SE(log N) ≈ 0.29, un factor ~1.3), así
    que el veredicto no puede apoyarse en "la muestra es pequeña". Se apoya en
    que las fuentes no son dos vistas de la misma población.
    """
    onsv = pd.DataFrame(
        {
            "COD CARRETERA": ["PE-01", "PE-02", "PE-03", "PE-04"],
            "fecha": pd.to_datetime(
                ["2021-01-05", "2021-02-05", "2021-03-05", "2021-04-05"]
            ),
        }
    )
    sutran = pd.DataFrame(
        {
            "CODIGO_VIA": ["PE-90", "PE-91", "PE-92", "PE-93"],
            "FECHA_DT": pd.to_datetime(
                ["2021-05-05", "2021-06-05", "2021-07-05", "2021-08-05"]
            ),
        }
    )

    sup = ff.supuesto_independencia(onsv, sutran)

    assert sup["supuesto_razonable"] is False
    assert sup["pct_rutas_no_comunes"] == 100.0
    assert sup["pct_meses_no_comunes"] == 100.0


def test_supuesto_razonable_cuando_las_fuentes_si_coinciden():
    """El caso contrario: mismo ámbito y misma ventana → supuesto razonable."""
    fechas = pd.to_datetime(["2021-01-05", "2021-02-05", "2021-03-05", "2021-04-05"])
    onsv = pd.DataFrame({"COD CARRETERA": ["PE-01", "PE-02", "PE-03", "PE-04"], "fecha": fechas})
    sutran = pd.DataFrame({"CODIGO_VIA": ["PE-01", "PE-02", "PE-03", "PE-04"], "FECHA_DT": fechas})

    sup = ff.supuesto_independencia(onsv, sutran)

    assert sup["supuesto_razonable"] is True
    assert sup["pct_rutas_no_comunes"] == 0.0


# --------------------------------------------------------------------------
# Sensitividad
# --------------------------------------------------------------------------


def test_sensibilidad_incluye_el_caso_limite_sin_tolerancia():
    """Radio 0 km / 0 días es "el mismo accidente en el mismo sitio el mismo día".

    Si esa casilla no está en la rejilla no se puede saber cuánto del solape
    depende de ser permisivo con la fecha.
    """
    fechas = pd.to_datetime(["2021-01-05", "2021-02-05", "2021-01-05", "2021-03-05"])
    onsv = pd.DataFrame(
        {
            "COD CARRETERA": ["PE-01", "PE-02", "PE-01", "PE-03"],
            "km_red": [10.0, 20.0, 10.0, 30.0],
            "lat": [-12.0, -13.0, -12.0, -14.0],
            "lon": [-77.0, -78.0, -77.0, -79.0],
            "fecha": fechas,
            "fallecidos": [1, 0, 1, 2],
        }
    )
    sutran = pd.DataFrame(
        {
            "CODIGO_VIA": ["PE-01", "PE-02", "PE-01", "PE-04"],
            "KM": [10.0, 20.0, 10.05, 40.0],
            "LATITUD_GEO": [-12.0, -13.0, -12.001, -80.0],
            "LONGITUD_GEO": [-77.0, -78.0, -77.001, -80.0],
            "FECHA_DT": fechas,
            "FALLECIDOS": [1, 0, 1, 1],
            "HERIDOS": [0, 1, 0, 0],
        }
    )

    filas = ff.sensitividad_matching(onsv, sutran)

    combinaciones = {(f["radio_km"], f["tolerancia_dias"]) for f in filas}
    assert (0.1, 0) in combinaciones
    assert (1.0, 7) in combinaciones
    # La unión nunca puede ser mayor que la suma ingenua: deduplicar resta o iguala.
    for f in filas:
        assert f["n_unico_total"] <= f["suma_naiva"]


def test_tabla_de_afirmaciones_no_incluye_indice_unico():
    """El fallo: colapsar los veredictos en una nota de 0 a 100.

    El proyecto lo prohíbe explícitamente (`AGENTS.md`): combinar exigiría
    decidir cuánto pesa cada riesgo, y esa decisión no sale de estos datos. Un
    test sintético que solo mira "que devuelva algo" no lo pilla.
    """
    coords = {
        "ONSV": {
            "filas": 100, "sin_coordenada": 0, "pct_sin_coordenada": 0.0,
            "fuera_de_peru": 0, "puntos_repetidos": 0,
            "coincidencias_mismo_km_fecha": 0, "coincidencias_misma_modalidad": 0,
        },
        "SUTRAN": {
            "filas": 100, "sin_coordenada": 10, "pct_sin_coordenada": 10.0,
            "fuera_de_peru": 0, "puntos_repetidos": 50,
            "coincidencias_mismo_km_fecha": 3, "coincidencias_misma_modalidad": 1,
        },
    }
    cov = {
        "rutas_comunes": 26, "rutas_red": 150, "pct_rutas_comunes": 17.3,
        "accidentes_totales": 41833.0, "columna_union": "ruta",
    }
    lp = ff.lincoln_petersen(993, 3932, 26)
    sup = {"supuesto_razonable": False, "pct_rutas_no_comunes": 56.1, "pct_meses_no_comunes": 87.5}
    resumen = {"n_ambos": 26}
    sens = [
        {"n_ambos": 20, "n_unico_total": 5000, "radio_km": 0.1, "tolerancia_dias": 0},
        {"n_ambos": 30, "n_unico_total": 5100, "radio_km": 1.0, "tolerancia_dias": 7},
    ]

    filas = ff.tabla_afirmaciones(coords, cov, lp, sup, resumen, sens)

    assert len(filas) >= 4
    # Cada afirmación lleva veredicto, evidencia y límite: nada de una nota suelta.
    for fila in filas:
        assert set(fila) == {"afirmacion", "veredicto", "evidencia", "limite"}
        assert all(isinstance(v, str) and v.strip() for v in fila.values())
    # La subnotificación debe salir NO ESTIMABLE, no "no concluyente".
    sub = [f for f in filas if "subnotificación" in f["afirmacion"]]
    assert sub and sub[0]["veredicto"] == "NO ESTIMABLE"
    # Y ninguna clave que huela a índice agregado.
    assert not any(k in fila for fila in filas for k in ("indice", "score", "nota", "puntaje"))


# --------------------------------------------------------------------------
# Contrato de la salida publicada
# --------------------------------------------------------------------------


def test_calidad_coordenadas_devuelve_tipos_json_serializables():
    """np.int64 no es serializable; el JSON tiene que salir limpio.

    El fallo real: `df.duplicated().sum()` devuelve np.int64, y `json.dumps`
    lanza TypeError justo al final, después de todo el análisis ya hecho. Un
    test sintético que solo comprueba los valores con `==` no lo detecta,
    porque np.int64(3) == 3 es True.
    """
    import json

    onsv = pd.DataFrame(
        {
            "lat": [-12.0, -13.0, -12.0],
            "lon": [-77.0, -78.0, -77.0],
            "fecha": pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-01"]),
        }
    )
    sutran = pd.DataFrame(
        {
            "LATITUD_GEO": [-12.0, -13.0],
            "LONGITUD_GEO": [-77.0, -78.0],
            "FECHA_DT": pd.to_datetime(["2021-01-01", "2021-01-02"]),
            "MODALIDAD": ["CHOQUE", "CHOQUE"],
        }
    )

    res = ff.calidad_coordenadas(onsv, sutran)

    # Debe serializar sin conversores: si aparece un np.int64, json lo lanza.
    json.dumps(res)
    for fuente, vals in res.items():
        for clave, valor in vals.items():
            assert type(valor) in (int, float, str, type(None)), (
                f"{fuente}.{clave} es {type(valor).__name__}, no un tipo nativo"
            )