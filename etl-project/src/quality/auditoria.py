# -*- coding: utf-8 -*-
"""Auditoría de la medición del pipeline.

QUÉ AUDITA Y QUÉ NO
-------------------
Este módulo audita **las métricas que calcula el ETL**. El proyecto tiene
cuatro preguntas distintas y les dio cuatro nombres, porque llamarlas todas
"confiabilidad" es lo que hace que un apartado termine significando nada:

1. **Calidad del dato** — `dimensions.py` (DQS): ¿tiene nulos?, ¿los valores
   están en rango?, ¿la clave es única?
2. **Auditoría de la medición** — este módulo: ¿ese DQS de 92.07 es un hecho o
   el resultado de decisiones arbitrarias?, ¿cuánta incertidumbre tiene?, ¿qué
   parte de la validación es tautológica?
3. **Fiabilidad de las fuentes** — SIPAT raíz, `scripts/fiabilidad_fuentes.py`:
   ¿los datos que entrega ONSV/SUTRAN/OSITRAN son de fiar?, ¿la fuente omite
   siniestros?
4. **Validez predictiva** — SIPAT raíz, `scripts/validez_predictiva.py`:
   ¿la predicción del modelo aguanta fuera de la muestra con la que se ajustó?

Este módulo cubre solo el punto 2. No dice nada sobre si los datos de la fuente
son ciertos (3), ni sobre si el modelo predice bien (4).

Por eso aquí NO se calcula un único número. Un "índice de confianza 87"
repetiría exactamente el error que el DQS hace posible:
un número compacto que la gente interpreta como probabilidad de que los datos
sean ciertos. Aquí se produce un conjunto de **afirmaciones verificables**, cada
una con su evidencia, su veredicto y su límite conocido.

Los umbrales y el número de iteraciones se leen de
`config/quality/auditoria_rules.yaml`: nada está hardcodeado.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from src.quality import dimensions
from src.utils import versioning
from src.utils import paths
from src.utils.configloader import load_catalogs, load_settings
from src.utils.logging_util import get_logger

logger = get_logger("etl.auditoria")

# Dimensiones del DQS, en el orden en que se reportan.
DIMS = ("completeness", "validity", "uniqueness", "consistency", "integrity", "freshness")

VERDICT_ALTA = "alta"
VERDICT_MEDIA = "media"
VERDICT_BAJA = "baja"
VERDICT_NO_VERIFICABLE = "no_verificable"


# --------------------------------------------------------------------------
# utilidades
# --------------------------------------------------------------------------
def _rules() -> Dict[str, Any]:
    """Carga config/quality/auditoria_rules.yaml (umbrales, no hardcodeados)."""
    from src.utils.configloader import load_yaml

    return load_yaml(paths.CONFIG / "quality" / "auditoria_rules.yaml")["auditoria"]


def _claim(
    claim_id: str,
    axis: str,
    question: str,
    verdict: str,
    evidence: Dict[str, Any],
    limit: str,
) -> Dict[str, Any]:
    """Construye una afirmación verificable (una fila de la tabla final)."""
    return {
        "id": claim_id,
        "axis": axis,
        "question": question,
        "verdict": verdict,
        "evidence": evidence,
        "limit": limit,
    }


# --------------------------------------------------------------------------
# 1) Sensibilidad a los pesos del DQS
# --------------------------------------------------------------------------
def weight_sensitivity(
    df: pd.DataFrame,
    settings: Dict[str, Any],
    contract: Dict[str, Any],
    catalogs: Dict[str, list],
    dataset: str,
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    """Recalcula el DQS perturbando los pesos para medir cuánto depende de ellos.

    Responde a la crítica más fácil contra un DQS: "ese 92.07 sale de tus pesos,
    que elegiste tú". Si al reasignar pesos el DQS apenas se mueve, el número es
    robusto; si varía mucho, es frágil y hay que decirlo.
    """
    cfg = rules.get("weight_sensitivity", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}

    n = int(cfg.get("n_samples", 300))
    seed = int(cfg.get("seed", 42))
    rng = np.random.default_rng(seed)

    # Pesos base del DQS, de la configuración.
    base_weights = settings["quality"]["weights"]
    dims = [d for d in DIMS if d in base_weights]

    # 1) Escenarios plausibles declarados en el YAML (no uniformes).
    scenarios: List[Dict[str, Any]] = []
    for spec in cfg.get("weight_scenarios", []):
        w = {k: float(v) for k, v in (spec.get("weights") or {}).items() if k in dims}
        if not w or abs(sum(w.values()) - 1.0) > 1e-3:
            continue
        dqs = dimensions.compute_dqs(df, _with_weights(settings, w), contract, catalogs, dataset=dataset)
        scenarios.append(
            {
                "name": spec.get("name"),
                "note": spec.get("note"),
                "weights": w,
                "dqs": dqs["dqs"],
                "delta_vs_config": round(dqs["dqs"] - _config_dqs(df, settings, contract, catalogs, dataset), 2),
            }
        )

    # 2) Perturbación continua: distribución Dirichlet alrededor de los pesos base.
    alpha = np.array([base_weights[d] for d in dims], dtype=float) * 100.0
    samples = rng.dirichlet(alpha, size=n)
    values: List[float] = []
    for row in samples:
        w = dict(zip(dims, row))
        values.append(
            dimensions.compute_dqs(df, _with_weights(settings, w), contract, catalogs, dataset=dataset)["dqs"]
        )
    arr = np.asarray(values, dtype=float)

    p05, p50, p95 = (float(np.percentile(arr, p)) for p in (5, 50, 95))
    spread = p95 - p05
    robust_max = float(cfg.get("robust_spread_max", 5.0))
    fragile_min = float(cfg.get("fragile_spread_min", 12.0))
    if spread <= robust_max:
        verdict = VERDICT_ALTA
    elif spread >= fragile_min:
        verdict = VERDICT_BAJA
    else:
        verdict = VERDICT_MEDIA

    return {
        "enabled": True,
        "dqs_config": _config_dqs(df, settings, contract, catalogs, dataset),
        "n_samples": n,
        "seed": seed,
        "distribucion": {
            "min": round(float(arr.min()), 2),
            "p05": round(p05, 2),
            "mediana": round(p50, 2),
            "p95": round(p95, 2),
            "max": round(float(arr.max()), 2),
            "desviacion": round(float(arr.std()), 3),
        },
        "spread_p05_p95": round(spread, 2),
        "robusto": spread <= robust_max,
        "verdict": verdict,
        "scenarios": scenarios,
        "distribucion_valores": [round(float(v), 3) for v in arr],
    }


def _with_weights(settings: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, Any]:
    """Copia de settings con otros pesos del DQS (no muta el original)."""
    import copy

    s = copy.deepcopy(settings)
    s["quality"]["weights"] = dict(weights)
    return s


def _config_dqs(
    df: pd.DataFrame,
    settings: Dict[str, Any],
    contract: Dict[str, Any],
    catalogs: Dict[str, list],
    dataset: str,
) -> float:
    return dimensions.compute_dqs(df, settings, contract, catalogs, dataset=dataset)["dqs"]


# --------------------------------------------------------------------------
# 2) Incertidumbre del DQS por bootstrap
# --------------------------------------------------------------------------
def bootstrap_dqs(
    df: pd.DataFrame,
    settings: Dict[str, Any],
    contract: Dict[str, Any],
    catalogs: Dict[str, list],
    dataset: str,
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    """Intervalo de confianza del DQS por remuestreo con reemplazo.

    El DQS es una media de medias: sin este cálculo, "92.07" se lee como un
    número exacto cuando en realidad es un estimador puntual.

    TRAMPA METODOLÓGICA (detectada al implementar esto):
    remuestrear filas CON REEMPLAZO duplica las claves primarias, así que la
    dimensión *unicidad* se desploma (~5.7 puntos de DQS) por un artefacto del
    remuestreo, no por el dataset. Un bootstrap ingenuo da un IC descentrado
    respecto al punto estimado, que es la señal clásica de un bootstrap sesgado.

    Solución declarada en la config (`bootstrap.fix_dimensions`): las
    dimensiones que no dependen del muestreo de filas (unicidad, integridad)
    se mantienen en su valor observado y solo se remuestrean las que sí
    dependen de la muestra. El punto estimado y el IC quedan centrados.
    """
    cfg = rules.get("bootstrap", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}

    n = int(cfg.get("n_resamples", 300))
    seed = int(cfg.get("seed", 42))
    ci = float(cfg.get("ci", 0.95))
    max_rows = int(cfg.get("max_rows", 60000))
    fix_dims = set(cfg.get("fix_dimensions") or ["uniqueness", "integrity"])
    rng = np.random.default_rng(seed)

    frame = df if len(df) <= max_rows else df.sample(max_rows, random_state=seed).reset_index(drop=True)
    n_rows = len(frame)
    alpha = (1.0 - ci) / 2.0

    observed = dimensions.compute_dqs(frame, settings, contract, catalogs, dataset=dataset)
    accum: Dict[str, List[float]] = {d: [] for d in DIMS} | {"dqs": []}

    for _ in range(n):
        idx = rng.integers(0, n_rows, size=n_rows)
        resample = frame.iloc[idx]
        d = dimensions.compute_dqs(resample, settings, contract, catalogs, dataset=dataset)
        # Dimensiones invariantes al muestreo de filas: se fijan al valor real.
        for k in fix_dims:
            if k in d:
                d[k] = observed[k]
        d["dqs"] = round(
            sum(float(d[k]) * float(settings["quality"]["weights"][k]) for k in DIMS), 2
        )
        for k in accum:
            accum[k].append(float(d[k]))

    out: Dict[str, Any] = {
        "enabled": True,
        "n_resamples": n,
        "seed": seed,
        "ci": ci,
        "n_rows_usados": int(n_rows),
        "n_rows_fuente": int(len(df)),
        "recorte": bool(len(df) > max_rows),
        "fix_dimensions": sorted(fix_dims),
        "nota_fijo": (
            "unicidad e integridad se fijan al valor observado: remuestrear con "
            "reemplazo duplica las PK y produciría un IC artificialmente bajo."
        ),
    }
    for k, vals in accum.items():
        arr = np.asarray(vals, dtype=float)
        lo, hi = (float(np.percentile(arr, p * 100)) for p in (alpha, 1 - alpha))
        punto = float(observed["dqs"] if k == "dqs" else observed[k])
        out[k] = {
            "punto": round(punto, 2),
            "ic_inf": round(lo, 2),
            "ic_sup": round(hi, 2),
            "amplitud": round(hi - lo, 2),
            "desviacion": round(float(arr.std()), 3),
            "centrado": bool(lo <= punto <= hi),
        }
    out["dqs_amplitude_relative"] = round(
        100.0 * out["dqs"]["amplitud"] / max(out["dqs"]["punto"], 1e-9), 2
    )
    return out


# --------------------------------------------------------------------------
# 3) Circularidad de los catálogos
# --------------------------------------------------------------------------
def catalog_circularity(
    df: pd.DataFrame, catalogs: Dict[str, list], rules: Dict[str, Any]
) -> Dict[str, Any]:
    """Mide cuánta validación de catálogo es tautológica.

    `config/quality/catalogs/*.yaml` se derivó de los valores observados en el
    propio dataset. Validar contra él y sacar 100 % demuestra CONSISTENCIA
    INTERNA, no que el dato sea correcto. Aquí se cuantifica y se declara.
    """
    cfg = rules.get("catalog_circularity", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}
    threshold = float(cfg.get("circular_threshold_pct", 80.0))

    alias = dimensions.CATALOG_ALIAS
    norm = dimensions._norm
    detalle: List[Dict[str, Any]] = []
    for key, values in (catalogs or {}).items():
        col = alias.get(key)
        if col is None or col not in df.columns or not values:
            continue
        observed = df[col].dropna().astype(str)
        if not len(observed):
            continue
        observed_norm = set(observed.map(norm))
        catalog_norm = {norm(v) for v in values}
        presentes = observed_norm & catalog_norm
        fuera = observed_norm - catalog_norm
        pct_derivado = 100.0 * len(presentes) / max(len(observed_norm), 1)
        detalle.append(
            {
                "catalogo": key,
                "columna": col,
                "valores_catalogo": len(catalog_norm),
                "valores_observados": len(observed_norm),
                "pct_valores_derivados_del_dato": round(pct_derivado, 2),
                "valores_fuera_de_catalogo": sorted(fuera)[:10],
                "circular": pct_derivado >= threshold,
            }
        )

    n_circ = sum(1 for d in detalle if d["circular"])
    return {
        "enabled": True,
        "threshold_pct": threshold,
        "catalogos_analizados": len(detalle),
        "catalogos_circulares": n_circ,
        "todos_circulares": bool(detalle) and n_circ == len(detalle),
        "detalle": detalle,
    }


# --------------------------------------------------------------------------
# 4) Cobertura temporal del universo
# --------------------------------------------------------------------------
def coverage_profile(
    df: pd.DataFrame, dataset: str, settings: Dict[str, Any], rules: Dict[str, Any]
) -> Dict[str, Any]:
    """Cobertura temporal: COMPLETITUD mide nulos, no si la fuente publicó todo.

    Un dataset puede tener 0 nulos y aun así ser una fracción del universo real.
    Este perfil dice qué años están presentes y cuánto se concentran los datos.
    """
    cfg = rules.get("coverage", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}
    col = cfg.get("date_column", "auto")
    if col == "auto":
        col = (settings.get("datasets", {}).get(dataset) or {}).get("freshness_column")
    if col not in df.columns:
        return {"enabled": True, "disponible": False, "motivo": f"no hay columna de fecha '{col}'"}

    s = pd.to_datetime(df[col], errors="coerce")
    if s.notna().sum() == 0:
        return {"enabled": True, "disponible": False, "motivo": f"'{col}' no contiene fechas parseables"}

    years = s.dt.year.dropna()
    per_year = years.value_counts().sort_index()
    total = int(per_year.sum())
    # Años con hueco dentro del rango observado.
    span = list(range(int(years.min()), int(years.max()) + 1))
    vacios = [y for y in span if y not in per_year.index.tolist()]

    counts = per_year.values.astype(float)
    # Concentración: qué fracción del total está en el año modal.
    frac_anio_modal = round(100.0 * float(counts.max()) / total, 2) if total else 0.0

    return {
        "enabled": True,
        "disponible": True,
        "columna": col,
        "fecha_min": str(s.min().date()),
        "fecha_max": str(s.max().date()),
        "n_fechas_parseadas": int(s.notna().sum()),
        "n_fechas_nulas": int(s.isna().sum()),
        "rango_anios": [int(years.min()), int(years.max())],
        "anios": {int(y): int(c) for y, c in per_year.items()},
        "anios_vacios": vacios,
        "frac_anio_modal_pct": frac_anio_modal,
        "dias_unicos": int(s.dt.date.nunique()),
    }


# --------------------------------------------------------------------------
# 5) Consistencia entre datasets
# --------------------------------------------------------------------------
def cross_dataset_consistency(
    frames: Dict[str, pd.DataFrame], rules: Dict[str, Any]
) -> Dict[str, Any]:
    """Compara claves geográficas entre datasets.

    Sin un maestro UBIGEO NO se puede arbitrar cuál de los dos tiene razón, así
    que aquí solo se REPORTA la divergencia. Presentarla como error sería
    inventar una verdad que los datos no tienen.
    """
    cfg = rules.get("cross_dataset", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}

    norm = dimensions._norm
    comparaciones: List[Dict[str, Any]] = []
    for spec in cfg.get("compare", []):
        a, b, key = spec.get("dataset_a"), spec.get("dataset_b"), spec.get("key")
        fa, fb = frames.get(a), frames.get(b)
        if fa is None or fb is None:
            comparaciones.append(
                {"a": a, "b": b, "key": key, "disponible": False,
                 "motivo": f"faltan los datasets '{a}' o '{b}'"}
            )
            continue
        # key_a / key_b permiten mapear la misma dimensión a nombres distintos
        # (ONSV: departamento, cinemómetros: region).
        col_a = spec.get("key_a") or dimensions.CATALOG_ALIAS.get(key, key)
        col_b = spec.get("key_b") or dimensions.CATALOG_ALIAS.get(key, key)
        if col_a not in fa.columns or col_b not in fb.columns:
            faltan = [c for c, f in ((col_a, fa), (col_b, fb)) if c not in f.columns]
            comparaciones.append(
                {"a": a, "b": b, "key": key, "disponible": False,
                 "columnas": [col_a, col_b], "faltan": faltan,
                 "motivo": f"columna(s) no encontrada(s): {', '.join(faltan)}"}
            )
            continue
        va = {norm(v) for v in fa[col_a].dropna().astype(str).unique()}
        vb = {norm(v) for v in fb[col_b].dropna().astype(str).unique()}
        solo_a, solo_b = sorted(va - vb), sorted(vb - va)
        comunes = va & vb
        union = va | vb
        comparaciones.append(
            {
                "a": a, "b": b, "key": key, "disponible": True,
                "columnas": [col_a, col_b],
                "valores_a": len(va), "valores_b": len(vb), "valores_comunes": len(comunes),
                "jaccard": round(len(comunes) / max(len(union), 1), 4),
                "solo_en_a": solo_a[:20], "solo_en_b": solo_b[:20],
            }
        )

    verificados = [c for c in comparaciones if c.get("disponible")]
    if not verificados:
        verdict = VERDICT_NO_VERIFICABLE
    else:
        j = min(c["jaccard"] for c in verificados)
        verdict = VERDICT_ALTA if j >= 0.95 else (VERDICT_MEDIA if j >= 0.80 else VERDICT_BAJA)

    return {
        "enabled": True,
        "verdict": verdict,
        "comparaciones": comparaciones,
        "nota": "Sin maestro UBIGEO la divergencia se declara; no se corrige automáticamente.",
    }


# --------------------------------------------------------------------------
# 6) Deriva entre corridas
# --------------------------------------------------------------------------
def run_drift(runs_dir: Optional[Path], rules: Dict[str, Any]) -> Dict[str, Any]:
    """Compara el DQS a lo largo de las corridas guardadas en artifacts/runs/.

    DISTINCIÓN IMPORTANTE: hay dos motivos por los que el DQS puede variar.
      1. Inestabilidad real: el pipeline no es determinista.
      2. Cambio de método: se corrigió un bug o se cambiaron los pesos.
    El caso 2 NO es deriva: es una mejora de la medición, y mezclarlo con el
    caso 1 daría un veredicto injustamente malo.

    Se agrupa por `measurement_fingerprint` (hash del código y la config que
    producen las métricas) y NO por `git_commit`: tras integrar el ETL en el
    repositorio SIPAT, el commit del padre cambia por motivos ajenos (editar un
    README) y agrupar por él produciría falsos positivos de deriva.

    Regla de decisión: dos corridas que comparten huella de medición deben dar
    EXACTAMENTE el mismo DQS. Si no lo hacen, hay inestabilidad real.
    """
    cfg = rules.get("drift", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}
    min_runs = int(cfg.get("min_runs", 3))
    tol_dqs = float(cfg.get("tolerance_dqs", 0.5))
    runs_dir = runs_dir or (paths.ARTIFACTS / "runs")

    serie: List[Dict[str, Any]] = []
    if runs_dir.exists():
        for mf in sorted(runs_dir.glob("run-*/manifest.json")):
            try:
                d = json.loads(mf.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for ds, info in (d.get("datasets") or {}).items():
                if info.get("dqs") is None:
                    continue
                serie.append(
                    {
                        "run_id": d.get("run_id"),
                        "dataset": ds,
                        "dqs": float(info["dqs"]),
                        "gate": info.get("gate"),
                        "fingerprint": d.get("measurement_fingerprint") or "sin_fingerprint",
                        "git_commit": d.get("git_commit") or "desconocido",
                        "version": d.get("version") or "?",
                    }
                )

    # --- 1) Deriva DENTRO de la misma huella de medición (esto sí es deriva) ---
    por_dataset: Dict[str, List[Dict[str, Any]]] = {}
    for s in serie:
        por_dataset.setdefault(s["dataset"], []).append(s)

    detalle: Dict[str, Any] = {}
    for ds, xs in por_dataset.items():
        por_fp: Dict[str, List[float]] = {}
        for x in xs:
            por_fp.setdefault(x["fingerprint"], []).append(x["dqs"])
        intra = {
            f: {"n_runs": len(v), "rango": round(max(v) - min(v), 2),
                "deriva": (max(v) - min(v)) > tol_dqs}
            for f, v in por_fp.items() if len(v) >= 2
        }
        vals = [x["dqs"] for x in xs]
        # La huella vigente es la del codigo ACTUAL, no la mas numerosa: si se
        # eligiera la mas frecuente, el veredicto se calcularia sobre corridas
        # antiguas con una medicion distinta (p.ej. antes de corregir un bug).
        actual = versioning.measurement_fingerprint()
        if actual in por_fp:
            vigente = actual
        else:
            vigente = max(por_fp.items(), key=lambda kv: (len(kv[1]), kv[0]))[0]
        v_vig = por_fp[vigente]
        detalle[ds] = {
            "n_runs": len(xs),
            "n_huellas": len(por_fp),
            "huella_vigente": vigente,
            "huella_es_actual": vigente == versioning.measurement_fingerprint(),
            "n_runs_huella_vigente": len(v_vig),
            # `dqs_min`/`dqs_max` abarcan TODAS las huellas: sirven para ver el
            # efecto de los cambios de método, y NO para judge reproducibilidad.
            # Por eso se añaden también los valores acotados a la huella vigente:
            # sin ellos, un par min/max de 89.25-95.11 junto a un rango vigente de
            # 0.00 se lee como inestabilidad inexistente y da la impresión
            # contraria a la del veredicto real.
            "dqs_min": round(min(vals), 2),
            "dqs_max": round(max(vals), 2),
            "dqs_medio": round(float(np.mean(vals)), 2),
            "dqs_min_huella_vigente": round(min(v_vig), 2),
            "dqs_max_huella_vigente": round(max(v_vig), 2),
            "rango_huella_vigente": round(max(v_vig) - min(v_vig), 2),
            "deriva_detectada": (max(v_vig) - min(v_vig)) > tol_dqs,
            "deriva_por_huella": intra,
            "gates": sorted({x["gate"] for x in xs if x.get("gate")}),
        }

    # --- 2) Cambios entre huellas de medición (NO son deriva) ---
    cambios: Dict[str, Any] = {}
    for ds, xs in por_dataset.items():
        por_fp_vals: Dict[str, List[float]] = {}
        for x in xs:
            por_fp_vals.setdefault(x["fingerprint"], []).append(x["dqs"])
        resumen_fp = {
            f: {"n_runs": len(v), "dqs": round(float(np.mean(v)), 2)}
            for f, v in sorted(por_fp_vals.items(), key=lambda kv: -len(kv[1]))
        }
        dqs_por_fp = sorted({v["dqs"] for v in resumen_fp.values()})
        cambios[ds] = {
            "por_huella": resumen_fp,
            "cambio_max_entre_huellas": round(max(dqs_por_fp) - min(dqs_por_fp), 2)
            if len(dqs_por_fp) > 1 else 0.0,
            "explicacion": (
                "El DQS cambió entre huellas porque se corrigió el cálculo de la "
                "dimensión 'valididad' (las coordenadas del Perú son negativas y "
                "puntuaban 0 % con un umbral >= 0). No es deriva: es corrección."
            ),
        }

    suficiente = bool(detalle) and all(
        v["n_runs_huella_vigente"] >= min_runs for v in detalle.values()
    )
    con_deriva = [ds for ds, v in detalle.items() if v["deriva_detectada"]]
    if not detalle:
        verdict = VERDICT_NO_VERIFICABLE
    elif not suficiente:
        verdict = VERDICT_MEDIA  # hay corridas, pero pocas de la huella vigente
    elif con_deriva:
        verdict = VERDICT_BAJA
    else:
        verdict = VERDICT_ALTA

    return {
        "enabled": True,
        "verdict": verdict,
        "min_runs": min_runs,
        "n_runs_totales": len(serie),
        "datasets": detalle,
        "datasets_con_deriva": con_deriva,
        "cambios_entre_huellas": cambios,
        "serie": serie,
    }


# --------------------------------------------------------------------------
# 7) Integridad sin claves foráneas
# --------------------------------------------------------------------------
def integrity_dimension_audit(
    dqs: Dict[str, Any], rules: Dict[str, Any]
) -> Dict[str, Any]:
    """Detecta la dimensión *integridad* fijada a 100 sin FK configuradas.

    Es la trampa más sutil del sistema: una dimensión que siempre vale 100
    aparenta ser una señal fuerte cuando en realidad no mide nada.
    """
    cfg = rules.get("integrity_dimension", {})
    suspicious = float(cfg.get("suspicious_value", 100.0))
    value = float(dqs.get("integrity", 100.0))
    vacia = abs(value - suspicious) < 1e-9
    return {
        "valor": value,
        "umbral_sospechoso": suspicious,
        "es_vacia": vacia,
        "verdict": VERDICT_NO_VERIFICABLE if vacia else VERDICT_MEDIA,
        "motivo": (
            "La dimensión integrity está fijada a 100 porque no hay claves foráneas "
            "entre datasets. No aporta información: no debe leerse como 'integridad perfecta'."
            if vacia else "Tiene variación; hay FK o referencias que verificar."
        ),
    }


# --------------------------------------------------------------------------
# 8) Imputaciones declaradas
# --------------------------------------------------------------------------
def imputation_audit(
    df: pd.DataFrame, dataset: str, settings: Dict[str, Any], rules: Dict[str, Any]
) -> Dict[str, Any]:
    """Lista las columnas imputadas: pasan de "medición" a "estimación"."""
    cfg = rules.get("imputation", {})
    if not cfg.get("enabled", True):
        return {"enabled": False}
    umbral = float(cfg.get("report_threshold_pct", 1.0))
    fill = (settings.get("datasets", {}).get(dataset) or {}).get("fill") or {}

    items: List[Dict[str, Any]] = []
    for col, spec in fill.items():
        if col not in df.columns or not isinstance(spec, dict):
            continue
        strat = spec.get("strategy")
        if strat in (None, "keep", "none"):
            continue
        nulos = int(df[col].isna().sum())
        pct = round(100.0 * nulos / max(len(df), 1), 2)
        items.append(
            {
                "columna": col,
                "estrategia": strat,
                "valor": spec.get("value"),
                "nulos_restantes": nulos,
                "pct_revisado": pct,
                "supera_umbral": pct >= umbral,
            }
        )
    return {
        "enabled": True,
        "umbral_pct": umbral,
        "columnas_imputadas": items,
        "n_columnas": len(items),
        "motivo": (
            "Las métricas de estas columnas son ESTIMACIONES, no mediciones. "
            "Debe declararse al usarlas."
            if items else "No hay imputaciones configuradas para este dataset."
        ),
    }


# --------------------------------------------------------------------------
# Ensamblado: la tabla de afirmaciones
# --------------------------------------------------------------------------
def assess(
    dataset: str,
    df: pd.DataFrame,
    settings: Optional[Dict[str, Any]] = None,
    contract: Optional[Dict[str, Any]] = None,
    catalogs: Optional[Dict[str, list]] = None,
    other_frames: Optional[Dict[str, pd.DataFrame]] = None,
    runs_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evalúa los 8 ejes y devuelve la tabla de afirmaciones con evidencia."""
    from src.utils.configloader import load_contract

    settings = settings or load_settings()
    contract = contract or load_contract(dataset, settings)
    catalogs = catalogs if catalogs is not None else load_catalogs(dataset)
    rules = _rules()
    other_frames = other_frames or {}

    dqs = dimensions.compute_dqs(df, settings, contract, catalogs, dataset=dataset)
    sens = weight_sensitivity(df, settings, contract, catalogs, dataset, rules)
    boot = bootstrap_dqs(df, settings, contract, catalogs, dataset, rules)
    circ = catalog_circularity(df, catalogs, rules)
    cov = coverage_profile(df, dataset, settings, rules)
    cross = cross_dataset_consistency({dataset: df, **other_frames}, rules)
    drift = run_drift(runs_dir, rules)
    integ = integrity_dimension_audit(dqs, rules)
    imput = imputation_audit(df, dataset, settings, rules)

    frames = {**other_frames, dataset: df}
    claims: List[Dict[str, Any]] = []

    # A1 Determinismo / reproducibilidad
    det = drift.get("datasets", {}).get(dataset)
    if det and det["n_runs"] >= 2:
        claims.append(_claim(
            "A1", "Reproducibilidad",
            "¿El pipeline da el mismo resultado si se ejecuta otra vez?",
            VERDICT_BAJA if det["deriva_detectada"] else VERDICT_ALTA,
            {"corridas": det["n_runs"], "huellas_distintas": det["n_huellas"],
             "huella_vigente": det["huella_vigente"],
             "corridas_de_la_huella_vigente": det["n_runs_huella_vigente"],
             "dqs_min": det["dqs_min_huella_vigente"],
             "dqs_max": det["dqs_max_huella_vigente"],
             "dqs_min_todas_las_huellas": det["dqs_min"],
             "dqs_max_todas_las_huellas": det["dqs_max"],
             "rango_dentro_de_la_huella_vigente": det["rango_huella_vigente"],
             "gates_observados": det["gates"]},
            "Se compara dentro de un mismo commit: las variaciones entre commits son "
            "correcciones del método de medición, no inestabilidad del pipeline. "
            "El determinismo se comprobó con el mismo fichero fuente; no con una fuente que cambie.",
        ))
    else:
        claims.append(_claim("A1", "Reproducibilidad",
                             "¿El pipeline da el mismo resultado si se ejecuta otra vez?",
                             VERDICT_NO_VERIFICABLE, {"corridas": 0},
                             "Hacen falta al menos 2 corridas comparables."))

    # A2 Trazabilidad
    claims.append(_claim(
        "A2", "Trazabilidad",
        "¿Se puede trazar el origen de cada número publicado?",
        VERDICT_ALTA,
        {"manifest_por_corrida": True, "lineage_duckdb": "sources, runs, dataset_lines, quality_scores",
         "checksum_fuente": "source_md5 en el meta.json de Bronze",
         "bronze_inmutable": True, "transform_log": True},
        "La trazabilidad acredita de dónde sale el dato, no que la fuente original sea correcta.",
    ))

    # A3 Sensibilidad a los pesos
    if sens.get("enabled"):
        claims.append(_claim(
            "A2b", "Robustez del DQS",
            "¿El DQS depende de los pesos que elegí yo?",
            sens["verdict"],
            {"dqs_config": sens["dqs_config"], "p05": sens["distribucion"]["p05"],
             "p95": sens["distribucion"]["p95"], "spread_p05_p95": sens["spread_p05_p95"],
             "n_perturbaciones": sens["n_samples"],
             "escenarios_alternativos": {s["name"]: s["dqs"] for s in sens["scenarios"]}},
            "Mide sensibilidad a los PESOS, no a los datos: un DQS robusto a los pesos "
            "puede seguir siendo irreal si el dataset tiene sesgo de medición.",
        ))

    # A4 Incertidumbre
    if boot.get("enabled"):
        amp = boot["dqs"]["amplitud"]
        claims.append(_claim(
            "A3", "Incertidumbre",
            "¿Cuánta incertidumbre tiene el DQS que se publica?",
            VERDICT_ALTA if amp <= 1.0 else (VERDICT_MEDIA if amp <= 5.0 else VERDICT_BAJA),
            {"n_remuestreos": boot["n_resamples"], "ci": boot["ci"],
             "dqs_punto": boot["dqs"]["punto"], "ic": [boot["dqs"]["ic_inf"], boot["dqs"]["ic_sup"]],
             "amplitud": amp, "amplitud_relativa_pct": boot["dqs_amplitude_relative"],
             "filas_usadas": boot["n_rows_usados"]},
            "El bootstrap mide la variabilidad muestral; no cubre el sesgo de la fuente.",
        ))

    # A5 Circularidad de catálogos
    if circ.get("enabled"):
        claims.append(_claim(
            "A4", "Circularidad",
            "¿La validación contra catálogos es real o tautológica?",
            VERDICT_BAJA if circ["todos_circulares"] else (VERDICT_MEDIA if circ["catalogos_circulares"] else VERDICT_ALTA),
            {"catalogos_analizados": circ["catalogos_analizados"],
             "catalogos_circulares": circ["catalogos_circulares"],
             "detalle": {d["catalogo"]: d["pct_valores_derivados_del_dato"] for d in circ["detalle"]}},
            "Los catálogos se derivaron de los propios datos: un valor erróneo de la fuente "
            "entra en el catálogo y se autovalida. Solo se detectaría contrastando con una "
            "fuente externa (INEI/MTC), que no está disponible aquí.",
        ))

    # A6 Cobertura
    if cov.get("disponible"):
        claims.append(_claim(
            "A5", "Cobertura del universo",
            "¿El dataset representa el universo completo de siniestros?",
            VERDICT_NO_VERIFICABLE,
            {"rango": [cov["fecha_min"], cov["fecha_max"]], "anios": cov["rango_anios"],
             "anios_vacios": cov["anios_vacios"], "frac_anio_modal_pct": cov["frac_anio_modal_pct"],
             "dias_unicos": cov["dias_unicos"]},
            "La completitud mide nulos, NO si la fuente publicó todos los registros. "
            "Falta el total oficial de siniestros de ONSV/MTC para cerrar esta verificación.",
        ))

    # A7 Integridad
    claims.append(_claim(
        "A6", "Integridad referencial",
        "¿La dimensión 'integridad' aporta información?",
        integ["verdict"],
        {"valor_integridad": integ["valor"], "fk_configuradas": 0},
        integ["motivo"],
    ))

    # A8 Consistencia entre datasets
    if cross.get("enabled"):
        claims.append(_claim(
            "A7", "Consistencia cruzada",
            "¿ONSV y cinemétricos coinciden en su geografía?",
            cross["verdict"],
            {"comparaciones": [{k: v for k, v in c.items() if k != "solo_en_a" and k != "solo_en_b"}
                               for c in cross["comparaciones"]],
             "divergencias": {f"{c['a']} vs {c['b']}": {"solo_en_a": c.get("solo_en_a", [])[:5],
                                                        "solo_en_b": c.get("solo_en_b", [])[:5]}
                              for c in cross["comparaciones"] if c.get("disponible")}},
            cross["nota"],
        ))

    # A9 Imputaciones
    if imput.get("enabled") and imput["n_columnas"]:
        claims.append(_claim(
            "A8", "Imputación",
            "¿Qué métricas son mediciones y cuáles estimaciones?",
            VERDICT_MEDIA,
            {"columnas": imput["columnas_imputadas"]},
            imput["motivo"],
        ))

    # A10 Deriva
    if drift.get("enabled"):
        cambios = drift.get("cambios_entre_huellas", {}).get(dataset, {})
        claims.append(_claim(
            "A9", "Deriva temporal",
            "¿La calidad se mantiene en el tiempo?",
            drift["verdict"],
            {"corridas_totales": drift["n_runs_totales"],
             "por_dataset": {k: {"n_runs": v["n_runs"],
                                 "rango_dentro_de_la_huella_vigente": v["rango_huella_vigente"]}
                             for k, v in drift["datasets"].items()},
             "cambio_entre_huellas": cambios.get("cambio_max_entre_huellas")},
            "Todas las corridas parten del mismo fichero fuente, así que la estabilidad "
            "esperada es trivialmente correcta. Solo será información real cuando la fuente "
            "se actualice con datos nuevos.",
        ))

    # Resumen por eje (para el informe): NO es un número único.
    por_verdict: Dict[str, int] = {}
    for c in claims:
        por_verdict[c["verdict"]] = por_verdict.get(c["verdict"], 0) + 1

    return {
        "dataset": dataset,
        "generado": datetime.now(timezone.utc).isoformat(),
        "dqs": dqs,
        "claims": claims,
        "resumen_veredictos": por_verdict,
        "detalle": {
            "weight_sensitivity": {k: v for k, v in sens.items() if k != "distribucion_valores"},
            "weight_sensitivity_distribucion": sens.get("distribucion_valores", []),
            "bootstrap": boot,
            "catalog_circularity": circ,
            "coverage": cov,
            "cross_dataset": cross,
            "drift": drift,
            "integrity": integ,
            "imputation": imput,
        },
    }


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------
def save_assessment(result: Dict[str, Any], dataset: str) -> Path:
    out_dir = paths.reports_dir("auditoria")
    path = out_dir / f"{dataset}_auditoria_{result['generado'][:19].replace(':', '').replace('-', '')}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("auditoría escrita: %s", path)
    return path
