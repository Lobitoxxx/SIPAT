"""Regresiones de la unificación ONSV ∪ SUTRAN.

Cada test documenta un defecto real: ninguno se habría detectado con datos
sintéticos "bonitos" porque el fallo solo aparece con las coordenadas, fechas y
nombres de columna que usan los CSV reales.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import deduplicacion_eventos as dedup  # noqa: E402


def _onsv(filas):
    return pd.DataFrame(
        {
            "fecha": [f[0] for f in filas],
            "lat": [f[1] for f in filas],
            "lon": [f[2] for f in filas],
            "fallecidos": [f[3] for f in filas],
            "COD CARRETERA": [f[4] for f in filas],
            "km_red": [f[5] for f in filas],
        }
    )


def _sutran(filas):
    return pd.DataFrame(
        {
            "FECHA_DT": [f[0] for f in filas],
            "LATITUD_GEO": [f[1] for f in filas],
            "LONGITUD_GEO": [f[2] for f in filas],
            "FALLECIDOS": [f[3] for f in filas],
            "CODIGO_VIA": [f[4] for f in filas],
            "KM": [f[5] for f in filas],
        }
    )


D = "2021-06-15"

# ── La aritmética de la unión ───────────────────────────────────────────────


def test_un_evento_visto_por_las_dos_fuentes_se_cuenta_una_sola_vez():
    o = _onsv([(D, -12.05, -77.05, 2, "PE-1N", 1050.0)])
    s = _sutran([(D, -12.05, -77.05, 2, "PE-1N", 1050.0)])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 1
    assert u.iloc[0]["fuentes"] == "ONSV+SUTRAN"


def test_eventos_en_lugares_distintos_no_se_fusionan():
    # Separados 0.01° (~1.1 km) con el mismo código de ruta: si el emparejamiento
    # ignorara la distancia, los contaría como uno.
    o = _onsv([(D, -12.05, -77.05, 1, "PE-1N", 1050.0)])
    s = _sutran([(D, -12.04, -77.05, 1, "PE-1N", 1051.5)])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 2
    assert set(u["fuentes"]) == {"ONSV", "SUTRAN"}


def test_el_emparejamiento_respeta_la_tolerancia_de_dias():
    """3 días de diferencia con tolerancia_dias=1 no es el mismo evento.

    Los eventos de relleno están para que las ventanas de las dos fuentes sí se
    solapen. Con solo los dos eventos test, la intersección de las ventanas
    empezaría en el segundo de ellos y uno de los dos quedaría fuera: el test
    pasaría por la ventana y no por la tolerancia.
    """
    X = (D, -12.05, -77.05, 1, "PE-1N", 1050.0)
    o = _onsv([
        ("2021-01-05", -11.0, -70.0, 1, "PE-9N", 10.0),
        ("2021-06-20", *X[1:]),
        ("2021-09-25", -13.0, -71.0, 1, "PE-9N", 20.0),
    ])
    s = _sutran([
        ("2021-01-10", -14.0, -72.0, 1, "PE-8N", 40.0),
        ("2021-06-23", *X[1:]),
        ("2021-12-20", -15.0, -73.0, 1, "PE-7N", 50.0),
    ])
    ini, fin = dedup.ventana_comun(dedup.ventanas_de_fuente(o, s))
    assert (ini, fin) == (pd.Timestamp("2021-01-10"), pd.Timestamp("2021-09-25"))

    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 4
    assert int((u["fuentes"] == "ONSV+SUTRAN").sum()) == 0

    # Con tolerancia de 4 días el mismo par sí se empareja: el resultado depende
    # del parámetro, no de un accidento enterrado en el código.
    holgado = dedup.ParametrosEmparejamiento(radio_km=0.25, tolerancia_dias=4)
    u2 = dedup.unificar_onsv_sutran(o, s, params=holgado)
    assert int((u2["fuentes"] == "ONSV+SUTRAN").sum()) == 1


def test_ventana_invertida_no_devuelve_un_conjunto_vacio_en_silencio():
    """Sin solape temporal hay que decirlo, no devolver 0 eventos."""
    o = _onsv([(D, -12.05, -77.05, 1, "PE-1N", 1050.0)])
    s = _sutran([("2021-06-19", -12.05, -77.05, 1, "PE-1N", 1050.0)])
    ini, fin = dedup.ventana_comun(dedup.ventanas_de_fuente(o, s))
    assert ini is None and fin is None
    assert len(dedup.unificar_onsv_sutran(o, s)) == 0


def test_el_emparejamiento_es_uno_a_uno():
    """Dos eventos de SUTRAN en el mismo punto y día NO pueden absorber los dos
    registros de ONSV. Si el emparejamiento no fuera injectivo, `n_ambos` sería
    2 y el recuento de la unión perdería un siniestro real."""
    o = _onsv([
        (D, -12.05, -77.05, 1, "PE-1N", 1050.0),
        (D, -12.05, -77.05, 1, "PE-1N", 1050.1),
    ])
    s = _sutran([(D, -12.05, -77.05, 1, "PE-1N", 1050.0)])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 2
    assert int((u["fuentes"] == "ONSV+SUTRAN").sum()) == 1


def test_los_fallecidos_se_toman_como_maximo_y_no_como_suma():
    """El mismo evento con 1 muerto en ONSV y 3 en SUTRAN es un evento con 3
    muertos. Sumar daría 4 víctimas de un solo accidente."""
    o = _onsv([(D, -12.05, -77.05, 1, "PE-1N", 1050.0)])
    s = _sutran([(D, -12.05, -77.05, 3, "PE-1N", 1050.0)])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 1
    assert u.iloc[0]["fallecidos"] == 3


# ── Lo que hace posible repartir por tramo ───────────────────────────────────


def test_la_union_arrastra_ruta_y_km_para_poder_asignar_a_tramos():
    """Sin `ruta`/`km_red` el total de red se puede calcular pero no repartir: el
    reparto por tramo seguiría sumando las dos fuentes y el doble conteo quedaría
    escondido en la columna que se publica."""
    o = _onsv([
        ("2021-01-05", -11.0, -70.0, 1, "PE-9N", 10.0),
        ("2021-06-15", -12.05, -77.05, 1, "PE-1N", 1050.0),
        ("2021-08-20", -13.0, -71.0, 1, "PE-9N", 20.0),
    ])
    s = _sutran([
        ("2021-02-10", -14.0, -72.0, 1, "PE-8N", 40.0),
        ("2021-07-02", -12.20, -76.90, 0, "PE-3N", 100.0),
    ])
    u = dedup.unificar_onsv_sutran(o, s)
    assert {"ruta", "km_red"} <= set(u.columns)
    # Ventana común: [2021-02-10, 2021-07-02] (inclusiva en ambos extremos).
    por_ruta = dict(zip(u["ruta"], u["km_red"]))
    assert por_ruta["PE-1N"] == 1050.0
    assert por_ruta["PE-3N"] == 100.0
    # Los dos rellenos de ONSV (2021-01-05 y 2021-08-20) caen fuera del solape.
    assert "PE-9N" not in por_ruta
    assert len(u) == 3


def test_en_un_par_emparejado_manda_la_ruta_de_onsv():
    o = _onsv([(D, -12.05, -77.05, 1, "PE-1N", 1050.0)])
    s = _sutran([(D, -12.05, -77.05, 1, "PE-1NX", 999.0)])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 1
    assert u.iloc[0]["ruta"] == "PE-1N"
    assert u.iloc[0]["km_red"] == 1050.0


# ── La ventana común ────────────────────────────────────────────────────────


def test_fuera_de_la_ventana_comun_no_entra_nada():
    """El defecto que motiva el módulo: `y_total` sumaba los 2020 de SUTRAN con
    los 2022-2025 de ONSV, dos periodos distintos en la misma columna."""
    o = _onsv([
        ("2021-06-15", -12.05, -77.05, 1, "PE-1N", 1050.0),   # en la ventana
        ("2021-03-15", -12.30, -77.30, 1, "PE-2N", 200.0),    # antes de SUTRAN
    ])
    s = _sutran([
        ("2021-07-01", -12.20, -76.90, 1, "PE-3N", 100.0),
        ("2020-05-01", -12.40, -77.40, 1, "PE-4N", 50.0),      # antes de ONSV
    ])
    u = dedup.unificar_onsv_sutran(o, s)
    ini, fin = dedup.ventana_comun(dedup.ventanas_de_fuente(o, s))
    # ONSV [2021-03-15, 2021-06-15] ∩ SUTRAN [2020-05-01, 2021-07-01]
    assert ini == pd.Timestamp("2021-03-15")
    assert fin == pd.Timestamp("2021-06-15")
    assert ((u["fecha_dt"] >= ini) & (u["fecha_dt"] <= fin)).all()
    # Solo entran los dos eventos de ONSV: el de SUTRAN en 2021-07-01 y el de
    # SUTRAN en 2020-05-01 quedan fuera de la ventana común.
    assert len(u) == 2
    assert set(u["ruta"]) == {"PE-1N", "PE-2N"}
    assert set(u["fuentes"]) == {"ONSV"}


def test_sin_interseccion_devuelve_vacio_y_no_una_excepcion():
    o = _onsv([("2021-06-15", -12.05, -77.05, 1, "PE-1N", 1050.0)])
    s = _sutran([("2019-01-05", -12.05, -77.05, 1, "PE-1N", 1050.0)])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) == 0


# ── El resumen ──────────────────────────────────────────────────────────────


def test_el_resumen_cuadra_con_lo_que_devuelve_la_union():
    rng = np.random.default_rng(7)
    o = _onsv([(D, -12.0 + rng.normal(0, 0.1), -77.0 + rng.normal(0, 0.1),
                1, "PE-1N", 1000.0 + i) for i in range(40)])
    s = _sutran([(D, -12.0 + rng.normal(0, 0.1), -77.0 + rng.normal(0, 0.1),
                  1, "PE-1N", 1000.0 + i) for i in range(40)])
    u = dedup.unificar_onsv_sutran(o, s)
    r = dedup.resumen_unificacion(o, s, unif=u)
    assert r["n_unico_total"] == len(u)
    assert r["n_ambos"] == int((u["fuentes"] == "ONSV+SUTRAN").sum())
    assert r["doble_conteo_evitado"] == r["n_ambos"]
    # La suma ingenua de las fuentes en la ventana común debe exceder al único.
    assert r["suma_naiva"] == r["n_unico_total"] + r["n_ambos"]


def test_coordenadas_invalidas_no_rompen_el_emparejamiento():
    """NaT/NaN en lat-lon viene de los CSV reales (siniestros sin coordenada). Si
    `cKDTree` los traga, `cKDTree` lanza ValueError y el pipeline entero muere."""
    o = _onsv([
        (D, -12.05, -77.05, 1, "PE-1N", 1050.0),
        (D, np.nan, np.nan, 1, "PE-1N", 1051.0),
        ("no-es-una-fecha", -12.06, -77.06, 1, "PE-1N", 1052.0),
    ])
    s = _sutran([
        (D, -12.05, -77.05, 1, "PE-1N", 1050.0),
        (D, np.nan, -77.10, 1, "PE-1N", 1053.0),
    ])
    u = dedup.unificar_onsv_sutran(o, s)
    assert len(u) >= 1
    assert int((u["fuentes"] == "ONSV+SUTRAN").sum()) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))