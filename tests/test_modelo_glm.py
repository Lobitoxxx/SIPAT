"""Tests de las regresiones corregidas en `scripts/modelo_glm.py`.

Cada test fija una propiedad real del modelo de Fase 1. Se prefieren
comprobaciones NUMÉRICAS sobre el texto fuente: un test que busca una cadena se
dispara con el docstring que documenta el defecto, y una comprobación de
comportamiento no se puede esquivar reescribiendo el comentario.
"""
import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "modelo_glm.py"


def _codigo_sin_comentarios():
    """Texto del módulo con docstrings y comentarios eliminados.

    Permite afirmar sobre lo que se EJECUTA y no sobre lo que se escribe
    acerca a lo que se ejecutó.
    """
    arbol = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    lineas = SCRIPT.read_text(encoding="utf-8").splitlines()
    fuera = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(nodo, clean=False)
            if doc is not None:
                primero = nodo.body[0]
                fuera.update(range(primero.lineno, primero.end_lineno + 1))
    return "\n".join(
        l for i, l in enumerate(lineas, start=1)
        if i not in fuera and not l.lstrip().startswith("#")
    )


def _datos():
    d = pd.read_csv(ROOT / "data" / "processed" / "dataset_modelo.csv")
    y = d["y_onsv"].values.astype(float)
    X = sm.add_constant(pd.DataFrame({
        "carriles": d["carriles"].fillna(d["carriles"].median()),
        "sup_buena": d["sup_buena"].fillna(0),
    }).astype(float))
    return d, y, X


# ── Defecto 1: alpha nunca ajustado ─────────────────────────────────────────
def test_el_codigo_ya_no_usa_scale_como_alpha():
    """El script hacía `alpha2 = m2.scale`. Con alpha fijo, `GLMResults.scale`
    de statsmodels vale exactamente 1.0 porque no se estima, así que `alpha2`
    era 1.0 siempre y el refit con ese alpha era idéntico al original: un no-op
    disfrazado de ajuste."""
    codigo = _codigo_sin_comentarios()
    assert ".scale" not in codigo or "pearson" in codigo
    # Ningún `.scale` puede alimentar un alpha.
    assert not re_asigna_escala_a_alpha(codigo)


def re_asigna_escala_a_alpha(codigo):
    arbol = ast.parse(codigo)
    for asign in ast.walk(arbol):
        if not isinstance(asign, ast.Assign):
            continue
        for tgt in asign.targets:
            if isinstance(tgt, ast.Name) and tgt.id == "alpha2":
                if "scale" in ast.unparse(asign.value):
                    return True
    return False


def test_estimar_alpha_por_verosimilitud_mejora_el_ajuste():
    """Comprobación numérica del defecto: con el alpha fijo 1.0 la dispersión de
    Pearson era 2.17; con el alpha estimado por ML baja a ~1.11."""
    d, y, X = _datos()
    off = np.log(d["expo_km_anio"])
    fijo = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=1.0), offset=off).fit()
    chi2_fijo = float(np.sum(fijo.resid_pearson ** 2) / fijo.df_resid)

    sys.path.insert(0, str(ROOT / "scripts"))
    from modelo_multi import alpha_por_verosimilitud

    mejor = alpha_por_verosimilitud(y, X, off)
    assert mejor is not None
    chi2_est = float(np.sum(mejor["resultado"].resid_pearson ** 2) / mejor["resultado"].df_resid)

    assert mejor["alpha"] != pytest.approx(1.0), "si sale 1.0 no se ha estimado nada"
    assert chi2_est < chi2_fijo, "el alpha estimado debe acercar la dispersión a 1"
    assert 0.8 < chi2_est < 1.4


# ── Defecto 2: offset sin años ──────────────────────────────────────────────
def test_el_offset_es_el_que_incluye_los_anos():
    d, y, X = _datos()
    assert "expo_km_anio" in _codigo_sin_comentarios()
    assert np.log(d["expo_km_anio"]).max() > np.log(d["expo_km"]).max()


def test_el_offset_sin_anos_no_arrasna_las_predicciones():
    """Corrección de una lectura equivocada: un factor constante en el offset lo
    absorbe el intercepto, así que usar `expo_km` en vez de `expo_km_anio` NO
    cambia las predicciones ni los residuales. Lo único que cambia es el
    intercepto, en un factor exactamente igual al de los años.

    Este test existe para que nadie vuelva a "arreglar" el offset creyendo que
    arregla predicciones, y para dejar constancia de por qué el cambio es de
    escala y no de exactitud."""
    d, y, X = _datos()
    o1, o2 = np.log(d["expo_km"]), np.log(d["expo_km_anio"])
    r1 = sm.GLM(y, X, family=sm.families.Poisson(), offset=o1).fit()
    r2 = sm.GLM(y, X, family=sm.families.Poisson(), offset=o2).fit()
    assert np.allclose(r1.predict(X, offset=o1), r2.predict(X, offset=o2))
    # Los coeficientes de riesgo tampoco se mueven.
    assert np.allclose(r1.params.drop("const"), r2.params.drop("const"))
    # Solo el intercepto, y justo en -log(años): un offset mayor exige un
    # intercepto menor para dejar la misma media.
    assert r2.params["const"] - r1.params["const"] == pytest.approx(-np.log(5), rel=1e-6)


# ── Defecto 3: dispersión Poisson ───────────────────────────────────────────
def test_scale_de_poisson_es_constante_y_no_sirve_de_diagnostico():
    """El script imprimía "dispersion Poisson (deviance/df): 1.00". El `.scale`
    de la familia Poisson es 1.0 fijo: no informa de nada. La sobredispersión
    real del modelo es 3.26."""
    d, y, X = _datos()
    p = sm.GLM(y, X, family=sm.families.Poisson(), offset=np.log(d["expo_km_anio"])).fit()
    assert p.scale == pytest.approx(1.0)
    real = float(np.sum(p.resid_pearson ** 2) / p.df_resid)
    assert real > 2.0
    # Y el código ejecutado tiene que medir Pearson, no scale.
    codigo = _codigo_sin_comentarios()
    assert "pearson_chi2_sobre_df" in codigo
    assert "deviance/df" not in codigo


# ── Defecto estructural: dos scripts escribían el mismo archivo ─────────────
def test_ya_no_pisa_el_puntos_negros_canonico():
    """Este script y `build_puntos_negros.py` escribían el mismo
    `puntos_negros.csv` con definiciones distintas (residuo de Pearson vs
    Empirical Bayes). El último en ejecutarse pisaba al anterior sin aviso."""
    codigo = _codigo_sin_comentarios()
    assert 'OUT_PUNTOS = ROOT / "data" / "processed" / "puntos_negros.csv"' not in codigo
    assert "puntos_negros_legacy_residuales.csv" in codigo
    # Y declara cuál es la vía canónica.
    assert "eb_tramos.py" in SCRIPT.read_text(encoding="utf-8")


def test_el_script_completo_corre_y_reporta_alpha_estimado():
    # `errors="replace"`: el subproceso escribe en la codificacion de la consola
    # de Windows (cp1252) y las "ñ" de su salida no son utf-8 validas. Sin esto
    # la lectura del pipe revienta con UnicodeDecodeError, `stdout` queda en
    # None y el fallo se reporta como TypeError en la linea siguiente, que
    # esconde la causa real.
    r = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=3600)
    assert r.returncode == 0, r.stderr[-3000:]
    salida = r.stdout or ""
    assert "log(expo_km_anio)" in salida
    assert "alpha estimado" in salida
    assert "LEGADO" in salida
    # La sobredispersión reportada debe ser la real, no la constante 1.00.
    assert "Pearson chi2/df) = 3.2" in salida or "Pearson chi2/df) = 3.3" in salida
    assert "alpha estimado = 1.000" not in salida


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))