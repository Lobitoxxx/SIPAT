# -*- coding: utf-8 -*-
"""Orquestación del pipeline ETL (sección 18 y 26).

Pipeline de 15 etapas por dataset, invocable en modo Prefect o secuencial puro.
Trazabilidad: artifacts/runs/<run_id>/manifest.json + registros en DuckDB (lineage).
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from src.cleaning.clean import clean
from src.cleaning.transform_log import TransformationLog
from src.extract.factory import get_extractor
from src.extract.register_raw import register_bronze
from src.lineage.registry import Lineage
from src.load import aggregations
from src.load import gold as gold_loader
from src.load import silver as silver_loader
from src.profiling.profile import profile
from src.quality import dimensions, model_ready as model_ready_mod
from src.quality import quarantine as qz
from src.quality.domain_rules import detect_violations
from src.quality.gates import evaluate_gate
from src.transform.features import derive_features
from src.utils import hashing, paths, versioning
from src.utils.configloader import (
    expand_path,
    load_aggregations,
    load_catalogs,
    load_contract,
    load_quality_rules,
    load_settings,
    load_sources,
)
from src.utils.logging_util import get_logger
from src.validation.contract import validate_contract
from src.sql_engine.engine import duckdb_engine

logger = get_logger("etl.flow")


def run_dataset(
    dataset: str,
    settings: Dict[str, Any],
    sources: Dict[str, Any],
    contracts: Dict[str, Any],
    quality_cfg: Dict[str, Any],
    run_id: str,
    duck,
) -> Dict[str, Any]:
    ds_cfg = settings["datasets"][dataset]
    spec = sources[dataset].copy()
    spec["path"] = expand_path(spec["path"])
    contract = contracts[dataset]
    catalogs = load_catalogs(dataset)
    run_dir = paths.artifacts_dir("runs", run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    lineage = Lineage(duck)
    stages: Dict[str, Any] = {}
    started = datetime.now(timezone.utc).isoformat()
    clean_frame: Optional[pd.DataFrame] = None
    frame_cache: Dict[str, pd.DataFrame] = {}
    gate_result: Dict[str, Any] = {}

    def get_clean() -> pd.DataFrame:
        if clean_frame is None:
            raise RuntimeError("clean no ejecutado")
        return clean_frame

    def get_transform() -> pd.DataFrame:
        if "transform" in frame_cache:
            return frame_cache["transform"]
        return get_clean()

    def _safe(o):
        if isinstance(o, dict):
            return {k: _safe(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_safe(v) for v in o]
        if hasattr(o, "to_parquet") or hasattr(o, "frame") or hasattr(o, "raw_path"):
            shape = getattr(o, "frame", None)
            return {"obj": o.__class__.__name__,
                    "rows": len(shape) if shape is not None else 0}
        if isinstance(o, (str, int, float, bool)) or o is None:
            return o
        return str(o)

    def stage(name: str, fn: Callable[[], Any]) -> Any:
        logger.info("etapa=%s dataset=%s", name, dataset,
                    extra={"run_id": run_id, "dataset": dataset, "operation": name})
        try:
            payload = fn()
            stages[name] = {"status": "OK", "payload": _safe(payload)}
            return payload
        except Exception as exc:
            stages[name] = {"status": "ERROR", "error": str(exc), "trace": traceback.format_exc()}
            logger.error("etapa=%s falló: %s", name, exc,
                         extra={"run_id": run_id, "dataset": dataset, "operation": name})
            raise

    # 1 start
    stage("start", lambda: {"run_id": run_id, "started_at": started, "dataset": dataset})

    # 2 extract
    res = stage("extract", lambda: get_extractor(spec, logger=logger).extract())

    # 3 register_raw (Bronze inmutable, idempotente)
    bronze = stage("register_raw", lambda: register_bronze(res, run_id, ds_cfg["version"]))
    lineage.register_dataset_line(
        dataset, "bronze", run_id, str(bronze.get("path", "")), int(bronze.get("rows", 0)),
        int(bronze.get("cols", 0)), str(bronze.get("md5", "")),
    )

    # 4 profiling_before (sobre el crudo extraído)
    profile_before_ctx = stage("profiling_before", lambda: profile(res.frame, dataset, "before", run_id))

    # 5 clean (renombrado canónico + normalización) — el contrato se valida sobre el
    #    dataset canónico, no sobre el fichero crudo con nombres de origen.
    def _clean():
        nonlocal clean_frame
        tlog = TransformationLog(run_id, dataset, run_dir)
        df = clean(res.frame, ds_cfg, tlog, contract)
        clean_frame = df
        frame_cache["clean"] = df
        tlog.save()
        return {"rows_in": len(res.frame), "rows_out": len(df), "n_ops": len(tlog.entries),
                "transform_log": str(run_dir / f"transform_log_{dataset}.json")}

    stage("clean", _clean)

    # 6 schema_validation (contrato sobre el frame canónico)
    contract_valid = stage("schema_validation", lambda: validate_contract(get_clean(), contract))

    # 7 transform (features de dominio)
    def _transform():
        df = derive_features(get_clean(), dataset)
        frame_cache["transform"] = df
        return {"rows": len(df), "cols": df.shape[1], "features": [c for c in df.columns if c not in res.frame.columns]}

    stage("transform", _transform)

    # 8 data_quality (DQS ponderado + violaciones de reglas de dominio)
    def _quality():
        df = get_transform()
        dqs = dimensions.compute_dqs(df, settings, contract, catalogs, dataset=dataset)
        violations = detect_violations(
            df,
            quality_cfg["domain_rules"].get(dataset, {}).get("rules", []),
            catalogs,
        )
        return {"dqs": dqs, "violations": violations, "rows": len(df), "frame_ref": "transform"}

    quality = stage("data_quality", _quality)

    # 9 quarantine (reglas criticales del frame post-transform)
    def _quarantine():
        df = get_transform()
        out = qz.push_quarantine(df, quality["violations"], dataset, run_id, spec.get("path", ""))
        return {"path": str(out), "records": len(json.loads(Path(out).read_text(encoding="utf-8")))}

    quarantine = stage("quarantine", _quarantine)

    # 10 quality_gate
    def _gate():
        g = evaluate_gate(
            quality["dqs"], quality["violations"], quality_cfg, dataset, run_id,
            source=spec.get("path"), df=None,  # la cuarentena ya se resolvió en la etapa 9
        )
        gate_result.update(g)
        return g

    gate_result = stage("quality_gate", _gate)
    lineage.record_quality_score(run_id, dataset, quality["dqs"], gate_result.get("status", "FAILED"))

    # 11 load_silver
    def _silver():
        df = get_transform()
        out = silver_loader.write_silver(df, dataset, run_id, ds_cfg["version"])
        lineage.upsert_dataset_version(dataset, "silver", run_id, out["path"], out["rows"], df.shape[1],
                                       hashing.file_md5(out["path"]))
        return out

    silver = stage("load_silver", _silver)

    # 12 build_gold (Golden: analytics, model_ready si cumple, agregaciones DuckDB)
    def _gold():
        df = get_transform()
        mready = model_ready_mod.is_model_ready(
            dataset=dataset,
            contract_status="VALID" if contract_valid["valid"] else "INVALID",
            gates_status=gate_result.get("status", "FAILED"),
            lineage_available=True,
            critical_errors=gate_result.get("n_critical_errors", 0),
            dqs=gate_result.get("dqs", 0.0),
            versioned=True,
        )
        gold: Dict[str, Any] = {}
        if mready["model_ready"]:
            analytics = gold_loader.write_gold_analytics(df, dataset, run_id, ds_cfg["version"])
            gold["analytics"] = analytics
            gold["model_ready_ds"] = gold_loader.write_model_ready(df, dataset, run_id, ds_cfg["version"])
            for layer, art in (("gold_analytics", analytics), ("gold_model_ready", gold["model_ready_ds"])):
                lineage.register_dataset_line(
                    dataset, layer, run_id, str(art["path"]), int(art["rows"]), int(art.get("cols", 0)),
                    hashing.file_md5(art["path"]),
                )
            # Tabla SQL consultable sobre el Silver del run.
            table = f"{dataset}_silver"
            duck.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{silver['path']}')")
            aggs = aggregations.build_aggregations(duck, table, load_aggregations(dataset))
            gold["aggregations"] = aggregations.persist_aggregations(duck, dataset, aggs, run_id)
            gold["aggregations_preview"] = {k: len(v) for k, v in aggs.items()}
        else:
            gold["blocked"] = mready
        return {"model_ready": mready["model_ready"], "criterion": mready["criterion"], "artifacts": gold}

    gold = stage("build_gold", _gold)

    # 13 profiling_after (sobre el dataset transformado)
    profile_after_ctx = stage("profiling_after", lambda: profile(get_transform(), dataset, "after", run_id))

    # 14 generate_report (reports/quality/<dataset>_<run_id>.html)
    def _report():
        from src.reports.report import generate_quality_report

        tlog = json.loads(Path(run_dir / f"transform_log_{dataset}.json").read_text(encoding="utf-8"))
        out = generate_quality_report(
            dataset, run_id, gate_result,
            profile_before=profile_before_ctx,
            profile_after=profile_after_ctx,
            transform_log=tlog,
            # El reporte incrusta las figuras de DQS por dimensión y de nulos
            # antes/después. Sin `dqs` el HTML sale igual, solo sin figuras.
            dqs=quality["dqs"],
        )
        return {"report": str(out)}

    stage("generate_report", _report)

    # 15 finish
    finish = {
        "status": "OK",
        "gate": gate_result,
        "silver": silver,
        "gold": gold,
        "quarantine": quarantine,
        "rows_in": len(res.frame),
        "rows_out": int(frame_cache.get("transform", frame_cache["clean"]).shape[0]),
    }
    stages["finish"] = {"status": "OK", "payload": finish}
    versioning.save_run_manifest(
        run_id,
        {"project": settings["project"]["name"], "started_at": started, "status": "OK", "stages": stages,
         "datasets": {dataset: {"dqs": gate_result.get("dqs"),
                                "gate": gate_result.get("status"),
                                "rows_out": finish["rows_out"]}}},
    )
    return {"stages": stages, "gate": gate_result, "quarantine": quarantine}


def run_pipeline(datasets: Optional[List[str]] = None, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Ejecuta el pipeline ETL para los datasets indicados (por defecto todos).

    Cierra la conexión DuckDB con CHECKPOINT para que las tablas silver y el
    catálogo de lineage queden duraderos y consultables desde otra conexión.
    """
    settings = load_settings()
    sources = load_sources()
    contracts = {ds: load_contract(ds, settings) for ds in settings["datasets"]}
    quality_cfg = load_quality_rules()
    run_id = versioning.new_run_id()
    duck = duckdb_engine(db_path)
    lineage = Lineage(duck)
    lineage.open_run(run_id, settings["project"]["name"], versioning.read_version())
    for ds in datasets or list(settings["datasets"]):
        lineage.register_source(ds, sources.get(ds, {}))
    results: Dict[str, Any] = {}
    ok = True
    started = hashing.now_iso()
    for ds in datasets or list(settings["datasets"]):
        try:
            r = run_dataset(ds, settings, sources, contracts, quality_cfg, run_id, duck)
            results[ds] = r
            if r["gate"].get("status") == "FAILED":
                ok = False
        except SystemExit:
            ok = False
            results[ds] = {"gate": {"status": "ERROR"}}
        except Exception as exc:
            logger.error("run_dataset %s: %s", ds, exc, extra={"run_id": run_id, "operation": str(exc)})
            ok = False
            results[ds] = {"gate": {"status": "ERROR"}, "error": str(exc)}
    status = "OK" if ok else "FAILED"
    lineage.close_run(run_id, status)
    total = {
        "project": settings["project"]["name"],
        "started_at": started,
        "status": status,
        "stages": {ds: r.get("stages", {}) for ds, r in results.items()},
        "datasets": {
            ds: {"dqs": r["gate"].get("dqs"), "gate": r["gate"].get("status")}
            for ds, r in results.items()
        },
    }
    manifest = versioning.save_run_manifest(run_id, total)
    # CHECKPOINT + close: deja el .duckdb en disco legible por otra conexión.
    try:
        duck.execute("CHECKPOINT")
    except Exception as exc:  # pragma: no cover - no debe abortar la corrida
        logger.warning("checkpoint DuckDB falló: %s", exc)
    finally:
        duck.close()
    return {"run_id": run_id, "manifest": str(manifest), "results": results, "status": status}

