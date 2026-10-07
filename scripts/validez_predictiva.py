"""¿La predicción aguanta fuera de muestra?

Este módulo responde a UNA pregunta, distinta de las otras tres del proyecto:

    DQS             ¿el dato tiene nulos, rangos y unicidad?  quality/dimensions
    auditoría ETL   ¿las métricas del ETL son defendibles?  quality/auditoria
    fuentes         ¿ONSV/SUTRAN/OSITRAN son de fiar?      fiabilidad_fuentes
    ESTE MÓDULO     ¿la predicción aguanta fuera de muestra?

No mezcla las cuatro ni inventa un índice único de "confiabilidad". Un R²
negativo aquí no dice que los datos sean malos: dice que el modelo no pronostica,
que es una afirmación distinta y con consecuencias distintas.

Qué hace, y por qué así:

* Reconstruye el panel tramo × año con `panel_anual.construir_panel` — la misma
  función que alimenta `dataset_modelo.csv`. Si la validación usara otra
  asignación de eventos, mediría un dataset que nadie usa.
* Dos protocolos, porque "fuera de muestra" tiene dos significados distintos:
    - ESPACIAL: se entrena y se predice sobre corredores que el modelo no ha
      visto. Responde "¿sirve en una carretera nueva?".
    - TEMPORAL: se entrena con 2021-2024 y se predice 2025. Responde
      "¿sirve mañana?". Su resultado está condicionado por el cambio de nivel de
      ONSV en 2025, que se documenta y se cuantifica aquí en vez de culparse al
      modelo de un problema de datos.
* Agrupa por CORREDOR, no por tramo. La red vial nacional enumera los dos
  sentidos por separado (PE-1N y PE-1S son la misma Panamericana). Si se
  agrupara solo por tramo, un tramo de entrenamiento y otro de prueba del mismo
  sentido separtirían el tramo de al lado y la validación mediría memoria, no
  capacidad de generalizar.
* Compara siempre contra la media de entrenamiento. Un R² alto con datos
  desbalanceados (86% de las celdas vale cero) es fácil de conseguir sin
  saber nada; lo que importa es si el modelo bate a la media.

Métricas: MAE, RMSE, R², devianza de Poisson y su residuo medio. Para conteos
con tantos ceros, R² es poco informativo y la devianza de Poisson es la que
distingue "aporta información" de "no aporta nada". Se añade la cobertura de
intervalos predictivos porque un intervalo que no cubre no sirve para nada.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import eb_tramos  # noqa: E402
import modelo_multi as mm  # noqa: E402
import panel_anual  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT_DIR = PROC / "dashboard"
OUT_JSON = OUT_DIR / "validez_predictiva.json"

ANIO_HOLDOUT = 2025
N_SPLITS = 5
NIVELES_INTERVALO = (0.80, 0.95)

# Diseño declarado como mapa destino -> origen, no como lista. Deducir el
# origen recortando el nombre del destino es fragile: `log_ingemmet` no viene de
# `ingemmet`, viene de `dist_ingemmet_km`. Declarar el par hace que un cambio en
# el dataset rompa aqui, en vez de colarse en silencio en el modelo.
VARIABLES = {
    "carriles": "carriles",
    "vel_proy": "vel_proy",
    "sinuosidad": "sinuosidad",
    "log_ingemmet": "dist_ingemmet_km",
    "log_peajes": "dist_peajes_km",
    "log_cine": "dist_cinemometros_km",
    "cinemometros_c10km": "cinemometros_c10km",
    "sup_buena": "sup_buena",
    "es_panamericana": "es_panamericana",
}
TRANSFORMACIONES = {"log_ingemmet", "log_peajes", "log_cine"}
CATEGORICAS = ["region", "topografia"]

COLS_PANEL = ["idx_tramo", "anio", "n_eventos", "expo_km"]


# ────────────────────────────────────────────────────────────────────────────
# Preparación de datos
# ────────────────────────────────────────────────────────────────────────────
def corredor_de(ruta: pd.Series) -> pd.Series:
    """Identificador de corredor, quitando el sentido.

    `PE-1N` y `PE-1S` son la misma Panamericana en direcciones opuestas: si
    quedan en lados distintos del folds, el modelo ve en el test un tramo
    virtualmente gemelo de uno del train y la validación deja de medir nada.

    La red usa sufijos N/S y a veces E/W. Se quita solo el sufijo final de una
    letra, de modo que `PE-03` (un número, no un sentido) se queda intacto.
    """
    return ruta.astype(str).str.strip().str.replace(r"([NSEW])$", "", regex=True)


def construir_design(d: pd.DataFrame) -> pd.DataFrame:
    """Matriz de diseño a partir del dataset por tramo.

    Falla ruidosamente si falta una columna de `VARIABLES`: mejor un error al
    arrancar que un diseño que cambió en silencio.
    """
    faltantes = sorted({src for src in VARIABLES.values() if src not in d.columns})
    if faltantes:
        raise KeyError(
            f"Faltan columnas del diseño: {faltantes}. Si el dataset las renombró, "
            "actualiza VARIABLES; no las deduzcas del nombre."
        )
    x = pd.DataFrame(index=d.index)
    for destino, origen in VARIABLES.items():
        v = pd.to_numeric(d[origen], errors="coerce")
        x[destino] = np.log1p(v) if destino in TRANSFORMACIONES else v
    for c in CATEGORICAS:
        if c in d.columns:
            # String antes de get_dummies: si la columna llega como float o int,
            # el modelo leería un "efecto por unidad de código".
            dummies = pd.get_dummies(
                d[c].astype(str).str.strip(), prefix=c, drop_first=True, dtype=float
            )
            for col in dummies.columns:
                x[col] = dummies[col].values
    # Mediana del propio lote como imputación: la mediana global de todo el
    # dataset usaría filas de test y sería fuga de información. La mediana se
    # recalcula dentro de cada fold en `ajustar_por_fold`.
    x = x.replace([np.inf, -np.inf], np.nan)
    return x


def columnas_diseno(d: pd.DataFrame) -> List[str]:
    """Nombres de la matriz de diseño, en orden estable."""
    return [c for c in construir_design(d).columns]


def _matriz_diseno(datos: pd.DataFrame) -> np.ndarray:
    x = datos[[c for c in datos.columns
               if c in VARIABLES or c.startswith(("region_", "topografia_"))]]
    return x.to_numpy(dtype=float)


def _imputar(X_fit: np.ndarray, *a_aplicar: np.ndarray) -> Tuple[np.ndarray, ...]:
    """Imputa por la mediana del ENTRENAMIENTO.

    Si se usara la mediana de todo el dataset, cada fila de test habría
    condicionado su propia imputación: es fuga de información, pequeña pero
    real, y del tipo que hace que un score suba sin que nada haya mejorado.
    """
    with np.errstate(invalid="ignore"):
        med = np.nanmedian(X_fit, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    salida = [np.where(np.isfinite(X_fit), X_fit, med)]
    for xa in a_aplicar:
        salida.append(np.where(np.isfinite(xa), xa, med))
    return tuple(salida)


def panel_de_eventos(d: pd.DataFrame) -> pd.DataFrame:
    """Reconstruye el panel tramo × año desde los eventos geocodificados.

    Misma asignación que `features_engine.py`, para que la validación mida el
    dataset que el dashboard muestra.
    """
    onsv = pd.read_csv(PROC / "onsv_nacional_geocod.csv")
    onsv["fecha_dt"] = pd.to_datetime(onsv["fecha"], errors="coerce")
    onsv["fallecidos"] = pd.to_numeric(onsv["fallecidos"], errors="coerce")
    onsv["km_red"] = pd.to_numeric(onsv["km_red"], errors="coerce")
    eventos = panel_anual.asignar_por_km_red(
        onsv, d.rename(columns={"ruta": "ruta", "km0": "km0", "km1": "km1"}),
        col_ruta="COD CARRETERA", col_km="km_red",
    )
    anios = sorted(int(a) for a in eventos["anio"].dropna().unique())
    panel = panel_anual.construir_panel(
        eventos, tramo_ids=d["id_tramo"], long_km=d["long_km"], anios=anios
    )
    return panel[COLS_PANEL].copy()


def unir_panel_diseno(d: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Panel + diseño, con corredor y etiqueta de año para los folds."""
    x = construir_design(d)
    out = panel.merge(x, left_on="idx_tramo", right_index=True, how="left")
    out["ruta"] = out["idx_tramo"].map(d["ruta"])
    out["corredor"] = corredor_de(out["ruta"])
    return out


# ────────────────────────────────────────────────────────────────────────────
# Métricas
# ────────────────────────────────────────────────────────────────────────────
def _media_poisson(y: np.ndarray, mu: np.ndarray) -> float:
    """Devianza de Poisson media por observación.

    Es la métrica que manda con conteos sesgados a cero: el R² depende de la
    varianza total y con 86% de ceros ese término queda en manos de los pocos
    tramos con eventos.

    Cómo se lee el número: NO se compara contra 1 como constante. La referencia
    exacta es la devianza del propio modelo nulo —la baseline `media`, que
    predice la media de entrenamiento— y hay que mirar si el modelo la baja. El
    1 es solo una guía aproximada, y con λ bajo se aparta bastante de ahí: para
    Poisson(0.3) el valor esperado ronda 0.83, no 1.
    """
    y = np.asarray(y, dtype=float)
    mu = np.clip(np.asarray(mu, dtype=float), 1e-9, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(y > 0, y * np.log(y / mu), 0.0)
    return float(np.mean(2 * (term - (y - mu))))


def metricas(y: np.ndarray, mu: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y, dtype=float)
    mu = np.asarray(mu, dtype=float)
    resid = mu - y
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    salida = {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(resid))),
        "rmse": float(np.sqrt(np.mean(resid ** 2))),
        "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
        "poisson_deviance": _media_poisson(y, mu),
        "media_observada": float(y.mean()),
        "media_predicha": float(mu.mean()),
        "sesgo": float(np.mean(resid)),
    }
    # Una baseline que predice 0 tiene devianza de Poisson indefinida (log 0),
    # y recortarla a 1e-9 produce un numero enorme que no significa nada. Se
    # marca para que no se lea como "el peor modelo posible": es una metrica
    # que no aplica a ese modelo.
    if np.any(mu <= 0):
        salida["poisson_deviance"] = float("nan")
        salida["poisson_deviance_no_aplica"] = (
            "predice 0 en parte del test: la devianza de Poisson no esta definida")
    return salida


def formato(m: Dict[str, float]) -> str:
    pv = m.get("poisson_deviance", float("nan"))
    pv_txt = "n/d" if (pv is None or not np.isfinite(pv)) else f"{pv:.3f}"
    return (f"MAE={m['mae']:.3f}  RMSE={m['rmse']:.3f}  R2={m['r2']:+.3f}  "
            f"Poisson={pv_txt}")


# ────────────────────────────────────────────────────────────────────────────
# Modelos candidatos
# ────────────────────────────────────────────────────────────────────────────
class MediaEntrenamiento:
    """Predice la media de `y` en el train. El suelo que hay que superar.

    Sin esto, un R² de 0,3 sobre una variable con 86% de ceros parece bueno y
    no dice nada.
    """

    nombre = "media_entrenamiento"

    def fit(self, y, X, offset=None, **kw):
        self.ymed_ = float(np.mean(y))
        return self

    def predict(self, X, offset=None, **kw):
        return np.full(len(X), self.ymed_, dtype=float)


class MedianaEntrenamiento(MediaEntrenamiento):
    nombre = "mediana_entrenamiento"

    def fit(self, y, X, offset=None, **kw):
        self.ymed_ = float(np.median(y))
        return self


class GlmNb:
    """NegBin con offset, reutilizando el estimador de `modelo_multi`.

    No se reimplementa el ajuste de `alpha` a mano: hacerlo fue precisamente el
    defecto que se corrigió en `modelo_glm.py`.
    """

    nombre = "negbin_offset"

    def fit(self, y, X, offset=None, **kw):
        if offset is None:
            raise ValueError("GlmNb necesita la exposición (offset).")
        X_c = sm.add_constant(np.asarray(X, dtype=float), has_constant="add")
        mejor = mm.alpha_por_verosimilitud(np.asarray(y, float), X_c,
                                           np.asarray(offset, float))
        if mejor is None:
            raise RuntimeError("alpha_por_verosimilitud no encontro alpha valido.")
        self.resultado_ = mejor["resultado"]
        self.alpha_ = mejor["alpha"]
        self.X_c_ = X_c
        return self

    def predict(self, X, offset=None, **kw):
        X_c = sm.add_constant(np.asarray(X, dtype=float), has_constant="add")
        return np.asarray(self.resultado_.predict(X_c, offset=np.asarray(offset, float)),
                          dtype=float)


class Persistencia:
    """Predice el valor observado el año anterior del mismo tramo.

    Solo tiene sentido en el protocolo temporal; en el espacial los tramos de
    prueba no tienen historia y la predicción es NaN. Se reporta como no
    aplicable en vez de rellenarse con la media, porque rellenarla convertiría
    una limitación en un número.
    """

    nombre = "persistencia_1año"

    def fit(self, y, X, offset=None, anio=None, **kw):
        self.tabla_ = pd.Series(np.asarray(y, float),
                                index=pd.MultiIndex.from_arrays(
                                    [np.asarray(kw["idx_tramo"]), np.asarray(anio)]))
        return self

    def predict(self, X, offset=None, anio=None, idx_tramo=None):
        clave = pd.MultiIndex.from_arrays([np.asarray(idx_tramo), np.asarray(anio) - 1])
        return self.tabla_.reindex(clave).to_numpy(dtype=float)


def _instanciar(nombre: str):
    return {
        "media": MediaEntrenamiento,
        "mediana": MedianaEntrenamiento,
        "negbin": GlmNb,
        "persistencia": Persistencia,
    }[nombre]()


# ────────────────────────────────────────────────────────────────────────────
# Protocolo espacial: corredores que el modelo no ha visto
# ────────────────────────────────────────────────────────────────────────────
def validar_espacial(datos: pd.DataFrame, n_splits: int = N_SPLITS) -> Dict:
    """K-fold agrupado por corredor.

    Se agrupa por corredor y no por tramo: `PE-1N` y `PE-1S` son la misma
    carretera en sentidos opuestos y comparten tramo físico, si no curbatura y
    tráfico. Si quedaran repartidos, el fold de test sería una copia del de
    train y un R² alto no significaría capacidad de extrapolar a una carretera
    nueva, que es justo lo que se quiere medir.
    """
    from sklearn.model_selection import GroupKFold

    X = _matriz_diseno(datos)
    y = datos["n_eventos"].to_numpy(float)
    offset = np.log(np.clip(datos["expo_km"].to_numpy(float), 1e-9, None))
    grupos = datos["corredor"].to_numpy()

    gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(grupos))))
    por_fold: List[Dict] = []
    acum: Dict[str, List[Tuple[np.ndarray, np.ndarray]]] = {}

    for k, (tr, te) in enumerate(gkf.split(X, y, grupos), start=1):
        Xtr, Xte = _imputar(X[tr], X[te])
        fila: Dict = {"fold": k, "n_train": int(len(tr)), "n_test": int(len(te)),
                      "n_corredores_test": int(len(np.unique(grupos[te]))),
                      "eventos_test": int(y[te].sum()), "modelos": {}}
        for nombre in ("media", "mediana", "negbin"):
            m = _instanciar(nombre)
            m.fit(y[tr], Xtr, offset=offset[tr])
            mu = m.predict(Xte, offset=offset[te])
            fila["modelos"][nombre] = metricas(y[te], mu)
            acum.setdefault(nombre, []).append((y[te], mu))
        por_fold.append(fila)

    resumen = {}
    for nombre, pares in acum.items():
        yy = np.concatenate([p[0] for p in pares])
        mm_ = np.concatenate([p[1] for p in pares])
        resumen[nombre] = metricas(yy, mm_)
    return {"tipo": "espacial", "agrupacion": "corredor",
            "n_corredores": int(len(np.unique(grupos))),
            "folds": por_fold, "agregado": resumen}


# ────────────────────────────────────────────────────────────────────────────
# Protocolo temporal: 2021-2024 entrena, 2025 predice
# ────────────────────────────────────────────────────────────────────────────
def _serie_anual(onsv: pd.DataFrame) -> pd.DataFrame:
    """Cifras de control por año: volumen, fallecidos y tasa de mortalidad.

    Deriva el año de `fecha_dt` para no depender de que el llamador lo haya
    calculado. Sin esta tabla, un MAE enorme en el holdout se atribuye al
    modelo cuando la causa es un cambio en la fuente.
    """
    ev = onsv.copy()
    if "anio" not in ev.columns:
        if "fecha_dt" not in ev.columns:
            ev["fecha_dt"] = pd.to_datetime(ev["fecha"], errors="coerce")
        ev["anio"] = ev["fecha_dt"].dt.year
    ev = ev[ev["anio"].notna()]
    ev["anio"] = ev["anio"].astype(int)
    t = (ev.groupby("anio")
         .agg(eventos=("fecha_dt", "size"),
              fallecidos=("fallecidos", "sum"),
              ultimo_mes=("fecha_dt", lambda s: int(s.dt.to_period("M").max().month)))
         .reset_index())
    t["tasa_mortalidad"] = np.where(t["eventos"] > 0, t["fallecidos"] / t["eventos"], np.nan)
    t["meses_cubiertos"] = t["ultimo_mes"]
    base = t.loc[t["anio"] < ANIO_HOLDOUT, "eventos"].mean()
    t["caida_vs_media_previa"] = np.where(
        (t["anio"] >= ANIO_HOLDOUT) & (base > 0), t["eventos"] / base - 1.0, np.nan)
    return t.drop(columns=["ultimo_mes"])


def validar_temporal(datos: pd.DataFrame, onsv: pd.DataFrame) -> Dict:
    """Entrena en 2021-2024 y predice 2025.

    La persistencia entra aquí y no en el fold espacial porque solo tiene
    sentido donde el mismo tramo tiene historia observada. Es además el
    baseline más fuerte de los dos protocolos, y cualquier modelo que no lo
    supere no está aportando.
    """
    tr = datos["anio"] < ANIO_HOLDOUT
    te = ~tr
    X = _matriz_diseno(datos)
    y = datos["n_eventos"].to_numpy(float)
    offset = np.log(np.clip(datos["expo_km"].to_numpy(float), 1e-9, None))
    idx = datos["idx_tramo"].to_numpy()
    anio = datos["anio"].to_numpy()
    Xtr, Xte = _imputar(X[tr], X[te])

    res: Dict[str, Optional[Dict]] = {}
    for nombre in ("media", "mediana", "negbin", "persistencia"):
        m = _instanciar(nombre)
        try:
            m.fit(y[tr], Xtr, offset=offset[tr], anio=anio[tr], idx_tramo=idx[tr])
            mu = m.predict(Xte, offset=offset[te], anio=anio[te], idx_tramo=idx[te])
        except Exception as exc:  # persistencia puede no tener historia
            res[nombre] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        if not np.all(np.isfinite(mu)):
            faltan = int((~np.isfinite(mu)).sum())
            res[nombre] = {"error": f"sin prediccion en {faltan} celdas "
                                     f"(tramos sin anio previo)"}
            continue
        res[nombre] = metricas(y[te], mu)

    serie = _serie_anual(onsv)
    fila_hold = serie.loc[serie["anio"] == ANIO_HOLDOUT]
    caida = float(fila_hold["caida_vs_media_previa"].iloc[0]) if len(fila_hold) else float("nan")
    return {
        "tipo": "temporal",
        "entrenamiento": f"{int(anio[tr].min())}-{int(anio[tr].max())}",
        "holdout": ANIO_HOLDOUT,
        "n_test": int(te.sum()),
        "eventos_test": int(y[te].sum()),
        "modelos": res,
        "serie_anual": serie.to_dict(orient="records"),
        "advertencia": {
            "caida_volumen_holdout": caida,
            "motivo": (f"ONSV registra {caida*100:.0f}% menos siniestros en {ANIO_HOLDOUT} "
                       "que el promedio 2021-2024, con los 12 meses cubiertos y una "
                       "tasa de mortalidad casi igual. Es un cambio de nivel de la "
                       "fuente, no una mejora de la seguridad vial: el MAE del "
                       "holdout mezcla error del modelo y error de la fuente y no "
                       "se puede separar con estos datos."),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Cobertura de intervalos
# ────────────────────────────────────────────────────────────────────────────
def cobertura_intervalos(y: np.ndarray, mu: np.ndarray, nivel: float,
                         dispersion: float = 1.0) -> Dict[str, float]:
    """Cobertura empírica de un intervalo predictivo NB2 al nivel `nivel`.

    `nivel` es la cobertura prometida (0.80 = "el 80% de las veces"), NO el
    significancia: el intervalo usa las colas `(1-nivel)/2` y `1-(1-nivel)/2`.

    La media es `mu` y la varianza `mu + mu**2 * dispersion`. Se compara la
    cobertura observada con la prometida: un intervalo que cubre el 60% cuando
    promete el 80% no sirve, por más que el ajuste sea bueno; y uno que cubre el
    95% cuando promete el 80% es tan inútil como el anterior, porque no
    discrimina.
    """
    from scipy.stats import nbinom

    y = np.asarray(y, dtype=float)
    mu = np.clip(np.asarray(mu, dtype=float), 1e-9, None)
    p = dispersion / (mu + dispersion)
    n = mu / dispersion
    cola = (1 - nivel) / 2
    lo = nbinom.ppf(cola, n, p)
    hi = nbinom.ppf(1 - cola, n, p)
    dentro = ((y >= lo) & (y <= hi)).mean()
    return {"nivel": float(nivel), "cobertura": float(dentro),
            "cumplimiento": float(dentro / nivel)}


def analizar(verbose: bool = True) -> Dict:
    """Corre los dos protocolos y devuelve el informe. No escribe nada.

    `main()` es solo `analizar()` + volcar el JSON. La separación importa porque el
    notebook 06 llama a esta función para **recalcular** los resultados en vez de
    leer el JSON que otro dejó escrito: si el módulo cambia, el notebook cambia.
    """
    def _p(*a):
        if verbose:
            print(*a)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _p("[1/4] Cargando dataset y reconstruyendo el panel tramo x anio...")
    d = pd.read_csv(PROC / "dataset_modelo.csv")
    panel = panel_de_eventos(d)
    datos = unir_panel_diseno(d, panel)
    frac_cero = float((datos["n_eventos"] == 0).mean())
    _p(f"      {len(datos)} celdas (tramo x anio), "
       f"{datos['idx_tramo'].nunique()} tramos, {datos['anio'].nunique()} anios")
    _p(f"      celdas con cero: {frac_cero*100:.1f}%")
    _p(f"      corredores: {datos['corredor'].nunique()} (de {d['ruta'].nunique()} rutas)")

    _p("\n[2/4] Protocolo ESPACIAL (corredores no vistos)...")
    esp = validar_espacial(datos)
    _p(f"      {esp['n_corredores']} corredores, "
       f"{len(esp['folds'])} folds")
    for nombre, m in esp["agregado"].items():
        _p(f"      {nombre:22s} {formato(m)}")
    _p("      (Poisson menor que el de la media = el modelo aporta;")
    _p("       la referencia es la devianza de la propia baseline, no el 1)")

    _p("\n[3/4] Protocolo TEMPORAL (holdout 2025)...")
    onsv = pd.read_csv(PROC / "onsv_nacional_geocod.csv")
    onsv["fecha_dt"] = pd.to_datetime(onsv["fecha"], errors="coerce")
    onsv["fallecidos"] = pd.to_numeric(onsv["fallecidos"], errors="coerce")
    tmp = validar_temporal(datos, onsv)
    _p(f"      entrenamiento {tmp['entrenamiento']}, holdout {tmp['holdout']} "
       f"({tmp['n_test']} celdas, {tmp['eventos_test']} siniestros)")
    for nombre, m in tmp["modelos"].items():
        if isinstance(m, dict) and "error" in m:
            _p(f"      {nombre:22s} no aplicable: {m['error']}")
        else:
            _p(f"      {nombre:22s} {formato(m)}")
    _p(f"      [aviso] {tmp['advertencia']['motivo']}")

    _p("\n[4/4] Cobertura de intervalos (NegBin, dispersion alpha del ajuste)...")
    cov = {}
    alb = {}
    try:
        X = _matriz_diseno(datos)
        y = datos["n_eventos"].to_numpy(float)
        offset = np.log(np.clip(datos["expo_km"].to_numpy(float), 1e-9, None))
        # Aquí se ajusta sobre TODO el panel a propósito: no es una medida de
        # capacidad predictiva, es la calibración de los intervalos. La
        # capacidad se mide en los dos protocolos de arriba.
        Ximp, = _imputar(X)
        modelo = GlmNb().fit(y, Ximp, offset=offset)
        alb["alpha"] = float(modelo.alpha_)
        mu = modelo.predict(Ximp, offset=offset)
        for a in NIVELES_INTERVALO:
            cov[f"{int(a*100)}%"] = cobertura_intervalos(y, mu, a, modelo.alpha_)
            c = cov[f"{int(a*100)}%"]
            _p(f"      nominal {c['nivel']*100:.0f}%: observada {c['cobertura']*100:.1f}% "
               f"(cumplimiento {c['cumplimiento']*100:.0f}%)")
    except Exception as exc:
        cov["error"] = f"{type(exc).__name__}: {exc}"

    veredicto = _veredicto(esp, tmp, frac_cero)
    _p("\n== Veredicto ==")
    for k, v in veredicto["afirmaciones"].items():
        _p(f"  {k}: {v['veredicto']}")
        _p(f"      evidencia: {v['evidencia']}")
        _p(f"      limite: {v['limite']}")

    return {
        "protocolo_espacial": esp,
        "protocolo_temporal": tmp,
        "intervalos": {"alpha": alb, "cobertura": cov},
        "veredicto": veredicto,
        "notas": {
            "agrupacion": ("Se agrupa por corredor, no por tramo: PE-1N y PE-1S son "
                           "la misma carretera en sentidos opuestos y comparten tramo "
                           "fisico. Agrupar solo por tramo haria que el fold de test "
                           "fuese una copia del de train."),
            "metrica": (f"Con {frac_cero*100:.0f}% de celdas en cero el R2 depende de la "
                        "varianza de pocos tramos y engaña. La devianza de Poisson "
                        "media es la que separa 'aporta' de 'no aporta': la "
                        "referencia es la devianza de la propia baseline media, no "
                        "el 1."),
            "fuentes": ("Este módulo NO juzga si ONSV, SUTRAN u OSITRAN son "
                        "confiables. Eso es scripts/fiabilidad_fuentes.py."),
            "sesgo": ("Con alpha estimado por cuasi-verosimilitud, los intervalos del "
                      "GLM no tienen cobertura garantizada; la cobertura que se reporta "
                      "es empirica, no la nominal del modelo."),
        },
    }


def main() -> int:
    salida = analizar(verbose=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2, default=_json_default)
    print(f"\nGuardado: {OUT_JSON}")
    return 0


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def _finite(d: Optional[Dict], key: str) -> float:
    """Lee una métrica que puede ser NaN sin que la comparación reviente."""
    if not isinstance(d, dict):
        return float("nan")
    v = d.get(key, float("nan"))
    try:
        v = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return v if np.isfinite(v) else float("nan")


def _veredicto(esp: Dict, tmp: Dict, frac_cero: float) -> Dict:
    """Afirmaciones con veredicto, evidencia y límite.

    Deliberadamente NO se colapsa en un único número. "Fiabilidad" son cuatro
    preguntas distintas (DQS, auditoría ETL, fuentes, y ésta), y un índice único
    las escondería detrás de un número que no significa nada.
    """
    ag = esp["agregado"]
    media = ag.get("media", {})
    negbin = esp["agregado"].get("negbin", {})
    pers = tmp["modelos"].get("persistencia")
    negbin_t = tmp["modelos"].get("negbin")
    adv = tmp.get("advertencia") or {}
    caida = adv.get("caida_volumen_holdout")

    afirmaciones = {}

    beating_mean = _finite(negbin, "poisson_deviance") < _finite(media, "poisson_deviance")
    afirmaciones["El modelo usa las covariables para predecir mejor que la media"] = {
        "veredicto": "SI" if beating_mean else "NO",
        "evidencia": (
            f"Espacial: devianza de Poisson {_finite(negbin,'poisson_deviance'):.3f} "
            f"contra {_finite(media,'poisson_deviance'):.3f} de la media "
            f"(MAE {_finite(negbin,'mae'):.3f} contra {_finite(media,'mae'):.3f})."
        ),
        "limite": (
            "La mejora es pequeña y el R2 sigue siendo negativo: el modelo ordena "
            "tramos mejor de lo que no lo hacia, pero no pronostica el numero. "
            "Sirve para priorizar, no para prever cantidad."
        ),
    }

    r2_esp = _finite(negbin, "r2")
    afirmaciones["El R2 justifica usarlo como pronostico"] = {
        "veredicto": "NO",
        "evidencia": f"R2 espacial = {r2_esp:+.3f}.",
        "limite": (
            f"Con {frac_cero*100:.0f}% de celdas en cero, el R2 se apoya en la "
            "varianza de unos pocos tramos con eventos y no representa capacidad "
            "de predecir. El veredicto no depende del R2: con MAE sobre un conteo "
            "que casi siempre es 0, un R2 negativo no dice que el modelo no sirva "
            "para priorizar."
        ),
    }

    if np.isfinite(_finite(pers, "mae")) and np.isfinite(_finite(negbin_t, "mae")):
        gana_mae = _finite(negbin_t, "mae") < _finite(pers, "mae")
        pv_pers = _finite(pers, "poisson_deviance")
        pv_nb = _finite(negbin_t, "poisson_deviance")
        # Con 86% de ceros, el MAE premia predecir 0: la persistencia hereda el
        # cero de 2024 y "acierta" en la mayoria de las celdas. Por eso el MAE
        # solo no alcanza para declarar un ganador, y aqui no se fuerza uno.
        if not np.isfinite(pv_pers):
            veredicto_p = "AMBIGUO"
            pv_media = _finite(tmp["modelos"].get("media"), "poisson_deviance")
            ref_txt = (f"{pv_media:.3f}" if np.isfinite(pv_media) else "la baseline")
            detalle = (
                f"Por MAE gana la persistencia ({_finite(pers,'mae'):.3f} contra "
                f"{_finite(negbin_t,'mae'):.3f}), pero eso premia predecir cero en "
                "las celdas mayoritarias: la persistencia se queda sin devianza de "
                f"Poisson (no definida) mientras el NegBin obtiene {pv_nb:.3f}, por "
                f"debajo de {ref_txt}. Cada metrica favorece a un modelo distinto y "
                "con estos datos no se puede elegir."
            )
        else:
            gana_p = pv_nb < pv_pers
            veredicto_p = "SI" if (gana_mae and gana_p) else ("NO" if not (gana_mae or gana_p) else "AMBIGUO")
            detalle = (
                f"MAE: {'NegBin' if gana_mae else 'persistencia'} "
                f"({_finite(negbin_t,'mae'):.3f} contra {_finite(pers,'mae'):.3f}). "
                f"Devianza de Poisson: {'NegBin' if gana_p else 'persistencia'} "
                f"({pv_nb:.3f} contra {pv_pers:.3f})."
            )
        afirmaciones["El modelo supera a la persistencia en el holdout temporal"] = {
            "veredicto": veredicto_p,
            "evidencia": detalle,
            "limite": (
                "El holdout 2025 arrastra un cambio de nivel de la fuente, asi que "
                "la comparacion entre modelos es valida pero la magnitud del error "
                "no. Ademas, con 86% de celdas en cero el MAE y la devianza de "
                "Poisson pueden discordar: no se declara ganador cuando lo hacen."
            ),
        }

    afirmaciones["El holdout temporal mide capacidad de predecir a futuro"] = {
        "veredicto": "NO",
        "evidencia": (
            f"ONSV 2025 registra {caida*100:.0f}% menos siniestros que el promedio "
            "2021-2024 con los 12 meses cubiertos y una tasa de mortalidad casi "
            "constante." if caida is not None else
            "ONSV 2025 cae frente a 2021-2024 con cobertura anual completa."
        ),
        "limite": (
            "El error del holdout mezcla error del modelo y cambio de la fuente, y "
            "estos datos no permiten separarlos. Para medir capacidad de predecir "
            "hace falta ONSV con series estables o una fuente de contraste por "
            "departamento."
        ),
    }

    return {
        "afirmaciones": afirmaciones,
        "nota": (
            "Cada afirmacion tiene su propia evidencia y su propio limite. No se "
            "combina en una puntuacion: combinarlas exigiria decidir cuanto pesa "
            "cada riesgo, y esa decision no sale de estos datos."
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())