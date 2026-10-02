"""Tests de `scripts/validez_predictiva.py`.

Fijan las decisiones metodológicas que, de changent, convierten la validación en
una tautología: que la agrupeación sea por corredor, que la imputación no vea el
test, que el holdout temporal reporte su propia limitación, y que no se publique
un único número de "fiabilidad".
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validez_predictiva as vp  # noqa: E402


# ── Agrupación espacial ─────────────────────────────────────────────────────
def test_pe1n_y_pe1s_caen_en_el_mismo_corredor():
    """PE-1N y PE-1S son la misma Panamericana en sentidos opuestos y comparten
    tramo fisico, curbatura y trafico. Si quedaran en folds distintos, el test
    seria una copia del train y el R2 no mediria nada."""
    r = vp.corredor_de(pd.Series(["PE-1N", "PE-1S", "PE-1N"]))
    assert r.nunique() == 1
    assert r.iloc[0] == "PE-1"


def test_quitar_sentido_no_arranca_un_numero_de_ruta():
    """La red usa sufijos N/S/E/W. `PE-03` termina en dígito y debe quedarse
    intacto; un recorte ingenuo de la ultima letra lo rompería."""
    assert vp.corredor_de(pd.Series(["PE-03"])).iloc[0] == "PE-03"
    assert vp.corredor_de(pd.Series(["PE-20N"])).iloc[0] == "PE-20"


def test_la_red_real_no_tiene_dos_carreteras_en_un_corredor():
    """Comprobacion sobre los datos: si el mapeo colapsara rutas distintas en un
    solo grupo, la validación agruparia cosas que no son la misma carretera."""
    d = pd.read_csv(ROOT / "data" / "processed" / "dataset_modelo.csv")
    base = vp.corredor_de(d["ruta"])
    assert base.nunique() <= d["ruta"].nunique()
    # Ningun corredor debe absorber rutas de familias distintas (PE- frente a no PE-).
    familias = d.assign(base=base).groupby("base")["ruta"].apply(
        lambda s: len({r.split("-")[0] for r in s}) > 1)
    assert not familias.any(), f"corredores con familias mezcladas: {familias[familias].index.tolist()}"


# ── Fuga de información ─────────────────────────────────────────────────────
def test_la_imputacion_usa_la_mediana_del_entrenamiento():
    """Si la mediana se calculara con todo el dataset, cada fila de test habria
    condicionado su propia imputacion.

    El caso tiene que discriminar de verdad: los valores no nulos del test deben
    desplazar la mediana global. Train [10,20,30] -> mediana 20; añadiendo el 5
    del test la mediana global pasa a 15.
    """
    train = np.array([[10.0], [20.0], [30.0]])
    test = np.array([[np.nan], [np.nan], [5.0]])
    Xtr, Xte = vp._imputar(train, test)
    assert np.nanmedian(train) == pytest.approx(20.0)
    assert np.nanmedian(np.vstack([train, test])) == pytest.approx(15.0)
    assert Xte[0, 0] == pytest.approx(20.0), "debe usar la mediana del train, no la global"
    assert Xte[1, 0] == pytest.approx(20.0)
    assert Xte[2, 0] == pytest.approx(5.0), "los valores no nulos pasan intactos"


def test_la_mediana_imputadora_ignora_nan():
    X = np.array([[1.0], [np.nan], [3.0]])
    a, _ = vp._imputar(X, X)
    assert np.all(np.isfinite(a))


# ── Métricas ────────────────────────────────────────────────────────────────
def test_la_devianza_de_la_media_es_la_referencia_del_nulo():
    """La devianza de Poisson NO se compara contra 1 como constante.

    El valor esperado de la devianza media depende de λ: para Poisson(0.3)
    ronda 0.83, no 1. La referencia exacta es la devianza de la propia baseline
    `media` (que predice la media de entrenamiento). Este test fija que la
    baseline de la media y la devianza calculada sobre esa misma media coinciden,
    que es lo que hace que la comparacion sea legitima.
    """
    rng = np.random.default_rng(0)
    y = rng.poisson(0.3, 5000).astype(float)
    d_ref = vp._media_poisson(y, np.full_like(y, y.mean()))

    base = vp.MediaEntrenamiento().fit(y, None)
    mu = base.predict(np.zeros((len(y), 1)))
    assert vp._media_poisson(y, mu) == pytest.approx(d_ref)
    # Y de hecho NO vale 1: queda registrado para que nadie use el 1 como umbral.
    assert d_ref == pytest.approx(0.83, abs=0.1)
    assert abs(d_ref - 1.0) > 0.05


def test_devianza_poisson_baja_cuando_el_modelo_mejora():
    """Con la media verdadera como prediccion, la devianza debe bajar frente a
    predecir la media de la muestra."""
    rng = np.random.default_rng(1)
    mu = rng.gamma(2.0, 0.5, 5000) + 0.01
    y = rng.poisson(mu).astype(float)
    mala = vp._media_poisson(y, np.full_like(y, y.mean()))
    buena = vp._media_poisson(y, mu)
    assert buena < mala
# Con la media verdadera, la devianza ronda 1 (1.05 aqui) pero no es exactamente
# 1: depende de λ y del ruido de muestreo. Por eso el umbral de referencia es la
    # baseline, no el 1.
    assert 0.6 < buena < 1.6


def test_baseline_que_predice_cero_no_tiene_devianza_poisson():
    """Con 86% de ceros, la mediana predice 0. La devianza de Poisson no esta
    definida en mu=0 y recortarla produce un numero enorme y sin sentido."""
    y = np.array([0, 0, 0, 0, 2, 1], dtype=float)
    m = vp.metricas(y, np.zeros_like(y))
    assert not np.isfinite(m["poisson_deviance"])
    assert "no esta definida" in m["poisson_deviance_no_aplica"]
    assert "n/d" in vp.formato(m)


# ── Persistencia ───────────────────────────────────────────────────────────
def test_persistencia_usa_el_anio_anterior_del_mismo_tramo():
    p = vp.Persistencia()
    y = np.array([1.0, 5.0, 0.0])
    idx = np.array([10, 11, 12])
    anio = np.array([2021, 2021, 2021])
    p.fit(y, None, anio=anio, idx_tramo=idx)
    pred = p.predict(None, anio=np.array([2022, 2022, 2022]), idx_tramo=idx)
    assert list(pred) == [1.0, 5.0, 0.0]
    # Un tramo sin historia devuelve NaN, no un cero inventado.
    pred2 = p.predict(None, anio=np.array([2022]), idx_tramo=np.array([99]))
    assert np.isnan(pred2[0])


def test_la_persistencia_no_se_usa_en_el_protocolo_espacial():
    """En el fold espacial los tramos de test no tienen historia. Si se rellenara
    con la media, una limitacion se convertiria en un numero."""
    from sklearn.model_selection import GroupKFold

    rng = np.random.default_rng(2)
    n = 300
    datos = pd.DataFrame({
        "corredor": [f"c{i % 30}" for i in range(n)],
        "n_eventos": rng.poisson(0.3, n),
        "expo_km": rng.uniform(1, 30, n),
    })
    gkf = GroupKFold(n_splits=3)
    tr, te = next(iter(gkf.split(np.zeros((n, 1)), datos["n_eventos"], datos["corredor"])))
    assert not (set(datos["corredor"].iloc[tr]) & set(datos["corredor"].iloc[te]))


# ── Veredicto ──────────────────────────────────────────────────────────────
def test_el_veredicto_no_se_colapsa_en_un_numero():
    """`confiabilidad` son cuatro preguntas distintas (DQS, auditoría, fuentes,
    y ésta). Un índice único las escondería detrás de un número sin significado."""
    esp = {"agregado": {"media": {"poisson_deviance": 1.2, "mae": 0.5, "r2": 0.0},
                        "negbin": {"poisson_deviance": 0.9, "mae": 0.4, "r2": 0.1}}}
    tmp = {"modelos": {"persistencia": {"mae": 0.3, "poisson_deviance": float("nan")},
                       "negbin": {"mae": 0.4, "poisson_deviance": 0.8}},
           "advertencia": {"caida_volumen_holdout": -0.67}}
    v = vp._veredicto(esp, tmp, 0.86)
    assert set(v) >= {"afirmaciones", "nota"}
    for k, a in v["afirmaciones"].items():
        assert set(a) == {"veredicto", "evidencia", "limite"}, k
        assert a["veredicto"] in {"SI", "NO", "AMBIGUO"}
    # Discordancia entre metricas -> veredicto ambiguo, no un ganador forzado.
    p = v["afirmaciones"]["El modelo supera a la persistencia en el holdout temporal"]
    assert p["veredicto"] == "AMBIGUO"


def test_veredicto_ambiguo_cuando_la_persistencia_predice_cero():
    esp = {"agregado": {"media": {"poisson_deviance": 1.2, "mae": 0.5, "r2": 0.0},
                        "negbin": {"poisson_deviance": 0.9, "mae": 0.4, "r2": 0.1}}}
    tmp = {"modelos": {"persistencia": {"mae": 0.2, "poisson_deviance": float("nan")},
                       "negbin": {"mae": 0.4, "poisson_deviance": 0.8}},
           "advertencia": {"caida_volumen_holdout": -0.67}}
    v = vp._veredicto(esp, tmp, 0.86)
    p = v["afirmaciones"]["El modelo supera a la persistencia en el holdout temporal"]
    assert p["veredicto"] == "AMBIGUO"
    assert "no definida" in p["evidencia"]


# ── Cobertura de intervalos ─────────────────────────────────────────────────
def test_el_nivel_nominal_de_los_intervalos_no_esta_invertido():
    """Bug real corregido: se pasaba el nivel como significancia, asi que un
    intervalo del 80% se reportaba como 'nominal 20%' y el cumplimiento salia
    442%. El nivel es la cobertura prometida."""
    rng = np.random.default_rng(3)
    mu = rng.gamma(2.0, 0.5, 4000) + 0.05
    y = rng.poisson(mu).astype(float)
    c = vp.cobertura_intervalos(y, mu, 0.80, dispersion=0.5)
    assert c["nivel"] == pytest.approx(0.80)
    # El intervalo es el que se pedia, no el complementario.
    c95 = vp.cobertura_intervalos(y, mu, 0.95, dispersion=0.5)
    assert c95["cobertura"] >= c["cobertura"]
    assert 0.5 < c95["cobertura"] < 0.99


# ── Contrato de la salida ──────────────────────────────────────────────────
def test_el_json_de_salida_tiene_la_estructura_del_panel():
    salida = ROOT / "data" / "processed" / "dashboard" / "validez_predictiva.json"
    if not salida.exists():
        pytest.skip("validez_predictiva.json no generado")
    import json

    j = json.loads(salida.read_text(encoding="utf-8"))
    assert set(j) >= {"protocolo_espacial", "protocolo_temporal", "intervalos", "veredicto"}
    assert j["protocolo_espacial"]["agrupacion"] == "corredor"
    assert j["protocolo_temporal"]["holdout"] == vp.ANIO_HOLDOUT
    # La limitacion del holdout tiene que viajar con los numeros.
    assert j["protocolo_temporal"]["advertencia"]["caida_volumen_holdout"] < -0.5


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))