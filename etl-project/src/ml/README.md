# src/ml — Preparación de datos para modelado (secciones 29-31)

Este paquete está **preparado** para la Fase ML del proyecto (sprints posteriores).
Regla de oro: **sin fugas de datos** — cualquier imputación, escalado, PCA o
selección de features SE AJUSTA SOLO sobre el split de *train*; `test` y
`validation` nunca participan del `fit`.

Preparado ahora:
- `src/ml/placeholder.py` — división `train/test` sin fugas y esqueleto de metadatos
  MLflow (`experiment_id`, `run_id`, `dataset_version`, `features`, `algorithm`,
  `hyperparameters`, `metrics`, `artifacts`, `model`, `code_version`).
- Input canónico: `data/gold/<dataset>_model_ready_<version>.parquet` (solo se genera
  cuando `is_model_ready()` devuelve `MODEL_READY`).

Futuro (documentado en `docs/mlflow_modelado.md`):
- `src/ml/entrenamiento.py`, `src/ml/evaluacion.py`, `src/ml/serve_modelo.py`.
- Registro en MLflow (experiment `sipat-etl`, tracking URI configurable).