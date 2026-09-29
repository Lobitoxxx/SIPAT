# Migración a Airflow (DAG equivalente)

El pipeline actual usa **Prefect 3** con fallback secuencial. Si el proyecto pasa a exigir
programación por calendario, dependencias entre datasets y operators consolidada en UI, la
migración es directa porque `run_dataset()` y `run_pipeline()` no dependen de Prefect.

## Principio de la migración

`src/orchestration/flow.py` no importa Prefect. Solo `src/orchestration/prefect_flow.py` lo
hace, y únicamente como envoltorio. Por tanto, la lógica de negocio es portable tal cual.

## DAG equivalente

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.utils.task_group import TaskGroup

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
}

with DAG(
    dag_id="sipat_etl_daily",
    start_date=datetime(2026, 1, 1),
    schedule_interval="0 6 * * *",          # diario 06:00
    catchup=False,
    default_args=default_args,
    tags=["etl", "sipat", "peru"],
) as dag:

    # 1) Esperar a que la ONSV publique el fichero del día.
    wait_onsv = FileSensor(
        task_id="wait_onsv_file",
        filepath="/opt/data/incoming/siniestros_{ds}.xlsx",
        poke_interval=600,                   # 10 min
        timeout=8 * 3600,                    # esperar hasta 8 h
        mode="reschedule",                   # no ocupa un worker
    )

    # 2) Verificar la integridad del proyecto antes de tocar datos.
    verify = BashOperator(
        task_id="verify_project",
        bash_command="cd /opt/sipat/etl-project && python scripts/verify_etl.py",
    )

    # 3) Un TaskGroup por dataset: Bronze → Silver → Gold, en paralelo entre sí.
    with TaskGroup(group_id="datasets") as datasets:
        onsv = BashOperator(
            task_id="onsv",
            bash_command="cd /opt/sipat/etl-project && "
                         "python scripts/run_pipeline.py --dataset onsv --engine sequential",
        )
        cin = BashOperator(
            task_id="cinemometros",
            bash_command="cd /opt/sipat/etl-project && "
                         "python scripts/run_pipeline.py --dataset cinemometros --engine sequential",
        )

    # 4) Solo si AMBOS pasan el gate, se publica.
    publish = PythonOperator(
        task_id="publish_gold",
        python_callable=_publish_if_all_passed,
        op_kwargs={"db": "/opt/sipat/etl-project/artifacts/lineage/sipat_lineage.duckdb"},
    )

    # 5) Notificar el resultado (DQS por dataset).
    notify = BashOperator(
        task_id="notify",
        bash_command="cd /opt/sipat/etl-project && python scripts/notify_quality.py || true",
        trigger_rule="all_done",   # notificar también si falló
    )

    wait_onsv >> verify >> datasets >> publish >> notify
```

## Tabla de correspondencia

| SIPAT-ETL (15 etapas) | Tarea Airflow | Nota |
|---|---|---|
| `start` + `extract` + `register_raw` + `clean` ... | un `BashOperator` por dataset | el pipeline ya es atómico y registra su propio manifest |
| `run_id` | `{{ run_id }}` / `{{ ds }}` | mapear el `run_id` de Airflow al manifest para trazar |
| `quality_gate` | `ShortCircuitOperator` | si el gate es `FAILED`, no publicar Gold |
| `quarantine` | ninguna | ya dentro del pipeline; se notifica si hay registros |
| reintentos Prefect | `default_args["retries"]` | misma semántica |
| caché Prefect | no equivalente directo | usar `ExternalTaskSensor` si un dataset depende de otro |

## Lo que NO hay que migrar

- Las 15 etapas y su `manifest.json`: son el contrato de trazabilidad, independiente del orquestador.
- `TransformationLog`, quarantine, DQS, contratos: son código puro de pandas.
- Las agregaciones Gold: son SQL declarativo en YAML, ejecutable con `duckdb` o con `PostgresHook`.

## Migración mínima si se quiere mantener Prefect

Si el problema no es Airflow sino **persistencia de estado**, no hace falta migrar: basta
configurar un backend de Prefect con almacenamiento:

```bash
prefect config set backend=db
prefect config set PREFECT_API_DATABASE_CONNECTION_URL=postgresql+psycopg2://user:pass@host/db
```

Con backend persistente, el historial de flows queda en PostgreSQL y se puede consultar desde la
UI de Prefect sin cambiar una línea de código.
