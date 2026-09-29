# -*- coding: utf-8 -*-
"""Flow de Prefect 3 para el pipeline ETL (sección 18/26).

El pipeline tiene DOS modos de ejecución con el MISMO resultado:

  * ``prefect``  — cada dataset se ejecuta como un task de Prefect, con
                   reintentos, caché y traza de cada etapa en la UI.
  * ``sequential`` — fallback en Python puro, sin servidor de Prefect.

Se elige el modo automáticamente: si Prefect no está instalado o el backend no
arranca (p. ej. sin Docker/DBus), se degrada a secuencial y se deja constancia
en el log. Esto evita que el pipeline deje de funcionar por un problema de
infraestructura del orquestador.

Uso:
    python scripts/run_pipeline.py --engine prefect
    python scripts/run_pipeline.py --engine sequential
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from src.orchestration.flow import run_pipeline
from src.utils.logging_util import get_logger

logger = get_logger("etl.prefect")


def prefect_available() -> bool:
    try:
        import prefect  # noqa: F401
    except Exception:
        return False
    return True


def run_pipeline_sequential(
    datasets: Optional[List[str]] = None, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    return run_pipeline(datasets=datasets, db_path=db_path)


def run_pipeline_prefect(
    datasets: Optional[List[str]] = None, db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Ejecuta el pipeline como un flow de Prefect.

    Cada dataset es un task independiente. Prefect se usa como capa de
    orquestación: no se replica la lógica del pipeline, solo se envuelve.
    """
    from prefect import flow, task

    settings = __import__("src.utils.configloader", fromlist=["load_settings"]).load_settings()
    targets = datasets or list(settings["datasets"])

    @task(name="etl-dataset", retries=1, retry_delay_seconds=5)
    def _run_one(dataset: str) -> Dict[str, Any]:
        # El pipeline real se ejecuta con un DuckDB dedicado por task para que
        # Prefect pueda reintentar sin colisionar con otra ejecución.
        tmp_db = (db_path.parent / f"prefect_{dataset}.duckdb") if db_path else None
        res = run_pipeline(datasets=[dataset], db_path=tmp_db)
        return res["results"][dataset]

    @flow(name="sipat-etl-pipeline", log_prints=False)
    def _flow() -> Dict[str, Any]:
        return {ds: _run_one(ds) for ds in targets}

    _flow()
    # Tras el flow, generamos el manifest agregado en secuencial para mantener
    # un único punto de verdad para la UI y los tests.
    return run_pipeline(datasets=targets, db_path=db_path)


def run_pipeline_auto(
    datasets: Optional[List[str]] = None,
    db_path: Optional[Path] = None,
    engine: str = "auto",
) -> Dict[str, Any]:
    """Despacha al motor indicado. `auto` usa Prefect si está disponible."""
    if engine == "sequential":
        return run_pipeline_sequential(datasets, db_path)
    if engine == "prefect":
        if not prefect_available():
            logger.warning("Prefect no disponible; uso fallback secuencial.")
            return run_pipeline_sequential(datasets, db_path)
        try:
            return run_pipeline_prefect(datasets, db_path)
        except Exception as exc:
            logger.warning("Flow Prefect falló (%s); uso fallback secuencial.", exc)
            return run_pipeline_sequential(datasets, db_path)
    # auto
    if prefect_available():
        try:
            return run_pipeline_prefect(datasets, db_path)
        except Exception as exc:
            logger.warning("Flow Prefect falló (%s); uso fallback secuencial.", exc)
    else:
        logger.info("Prefect no instalado; ejecuto en modo secuencial.")
    return run_pipeline_sequential(datasets, db_path)
