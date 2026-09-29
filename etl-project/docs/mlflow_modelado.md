# Fase de modelado y MLflow

## Estado actual: la puerta está preparada, el modelo no está entrenado

SIPAT-ETL publica `data/gold/<dataset>_model_ready_1.0.parquet` **solo si** se cumplen las seis
condiciones de MODEL_READY (contrato válido, gate `PASSED`, lineage disponible, 0 críticos,
DQS ≥ umbral, versión registrada). Los datasets actuales cumplen las seis.

`src/ml/placeholder.py` define el esqueleto: `split_no_leakage()` y la estructura de metadatos
de MLflow. No hay entrenamiento, porque no es objetivo de la capa ETL.

## Targets disponibles

| Dataset | Columna target | Tipo | Nota |
|---|---|---|---|
| `onsv` | `fallecidos` | conteo | desbalanceado: muchos ceros |
| `cinemometros` | `velocidad_detectada` | continua | además `exceso_kmh` y `excede_limite` ya derivados |

## Reglas de no fuga (obligatorias)

1. El dataset de entrada es **siempre** `gold/model_ready_*.parquet`, nunca Silver ni Bronze.
2. `split_no_leakage(df, target, test_ratio, seed)` parte de forma determinista.
3. **Todo `fit` ocurre dentro de `train`**: imputación de nulos, escalado, PCA, selección de
   variables y codificación de categóricas. El objeto ajustado se aplica después a `test`.
4. El preprocesado se persiste con el modelo y se reutiliza en inferencia.
5. El `run_id` del pipeline se propaga a la corrida de MLflow para poder auditar
   "este modelo se entrenó con los datos de esta corrida".

Esqueleto de entrenamiento sin fugas:

```python
from src.ml.placeholder import split_no_leakage, mlflow_placeholder
import pandas as pd

df = pd.read_parquet("data/gold/onsv_model_ready_1.0.parquet")
target = "fallecidos"

# 1) Partición determinista
parts = split_no_leakage(df, target, test_ratio=0.2, seed=42)
train, test = parts["train"], parts["test"]

# 2) Todo ajuste, SOLO con train
mediana = train[target].median()
train_f = train.fillna({"vehiculos_danados": mediana})   # fit
test_f = test.fillna({"vehiculos_danados": mediana})    # apply (no fit)

X_train, y_train = train_f.drop(columns=[target]), train_f[target]
X_test, y_test = test_f.drop(columns=[target]), test_f[target]

# 3) Modelo (aún no añadido: ver nota de dependencias)
# model = HistGradientBoostingRegressor().fit(X_train, y_train)

# 4) Metadatos de trazabilidad
meta = mlflow_placeholder("onsv", run_id="run-20260929-134816-7969fdc2")
meta["features"] = list(X_train.columns)
meta["algorithm"] = "HistGradientBoostingRegressor"
meta["dataset_version"] = "1.0"
```

## MLflow

```bash
pip install mlflow
mlflow ui --backend-store-uri sqlite:///artifacts/mlflow.db
```

Registrar la corrida con lo que exige la reproducibilidad:

```python
import mlflow

with mlflow.start_run(run_name=f"onsv-{run_id}") as run:
    mlflow.log_param("dataset", "onsv")
    mlflow.log_param("dataset_version", "1.0")
    mlflow.log_param("pipeline_run_id", run_id)   # enlace con el manifest ETL
    mlflow.log_param("seed", 42)
    mlflow.log_param("test_ratio", 0.2)
    mlflow.log_params({"target": target, "n_train": len(X_train), "n_test": len(X_test)})
    mlflow.log_metrics({"mae": ..., "rmse": ..., "r2": ...})
    mlflow.log_artifact("data/gold/onsv_model_ready_1.0.parquet")
```

## Nota sobre dependencias

`placeholder.py` usa solo pandas y numpy (split determinista con `numpy.default_rng`).
`scikit-learn` **no** está en `requirements.txt` a propósito: la capa ETL no entrena modelos,
y fijar una librería de ML aquí acoplaría el pipeline a un stack de modelado que aún no se ha
decidido. Cuando se añada el entrenamiento, `scikit-learn` entra en un
`requirements-ml.txt` separado.

## Validación del modelo (CRISP-DM, fase Evaluation)

- **onsv**: el target `fallecidos` es un conteo muy desbalanceado. Métricas: MAE y RMSE
  (no R²), y una línea base `DummyRegressor` para demostrar mejora real.
- **cinemometros**: regresión sobre `velocidad_detectada`; reportar MAE/RMSE y el error
  absoluto en `exceso_kmh`, que es la magnitud accionable.
- En ambos: reportar siempre el **intervalo** de las métricas, porque con un solo split la
  varianza puede ser alta. Para datos de conteo, `PoissonRegressor` o `TweedieRegressor`
  suelen funcionar mejor que un regresor lineal.
