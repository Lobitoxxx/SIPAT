# -*- coding: utf-8 -*-
"""Preparación ML sin fugas (secciones 29-30): TODO Bootstrap para la fase de modelado.

Reglas (sección 34 - principios):
- Imputación, escalado y cualquier fit SE HACEN SOLO sobre el split train.
- El dataset gold/model_ready_*.parquet es la entrada; nunca se re-entrena sobre silver.
- MLflow preparado: experiment_id, run_id, dataset_version, features, algorithm,
  hyperparameters, metrics, artifacts, model, code_version.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

TARGETS = {"onsv": "fallecidos", "cinemometros": "velocidad_detectada"}


def split_no_leakage(
    df: pd.DataFrame, target: str, test_ratio: float = 0.2, seed: int = 42
) -> Dict[str, pd.DataFrame]:
    """Split determinista train/test, implementada sin dependencias externas.

    Se usa una permutación con semilla fija (numpy `default_rng(seed)`), de modo
    que la partición es reproducible entre ejecuciones y entre máquinas.

    IMPORTANTE (sección 29-30): el split por sí solo no evita fugas. Todo el
    `fit` posterior (imputación, escalado, PCA, selección de variables) debe
    aplicarse SOBRE `train` y luego aplicarse ya fitted a `test`. Por eso el
    llamador recibe los dos frames y nunca el dataset completo.
    """
    if target not in df.columns:
        raise KeyError(f"columna target no encontrada: {target!r}")
    n = len(df)
    n_test = int(round(n * float(test_ratio)))
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    test_idx = order[:n_test]
    train_idx = order[n_test:]
    return {"train": df.iloc[train_idx].reset_index(drop=True), "test": df.iloc[test_idx].reset_index(drop=True)}


EXPERIMENT_DEFAULTS: Dict[str, Any] = {
    "mlflow_tracking_uri": "sqlite:///artifacts/mlflow.db",
    "experiment_name": "sipat-etl",
}


def mlflow_placeholder(dataset: str, run_id: str, model_path: Optional[Path] = None) -> Dict[str, Any]:
    """Estructura de metadatos MLflow que se completará en la fase ML (sección 30)."""
    return {
        "dataset": dataset,
        "pipeline_run_id": run_id,
        "experiment_id": EXPERIMENT_DEFAULTS["experiment_name"],
        "run_id_mlflow": None,
        "dataset_version": None,
        "features": None,
        "algorithm": None,
        "hyperparameters": None,
        "metrics": None,
        "artifacts": str(model_path) if model_path else None,
        "model": None,
        "code_version": None,
        "status": "PENDING",
    }