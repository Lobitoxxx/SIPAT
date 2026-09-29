# -*- coding: utf-8 -*-
"""Criterio MODEL_READY (sección 31): ¿puede este dataset pasar a preparación de ML?

Requisitos: contrato válido, gates aprobados, lineage disponible, 0 errores críticos,
calidad >= umbral y versión registrada. Si no, se bloquea/advierte (sección 34).
"""
from __future__ import annotations

from typing import Any, Dict


def is_model_ready(
    dataset: str,
    contract_status: str,
    gates_status: str,
    lineage_available: bool,
    critical_errors: int,
    dqs: float,
    min_dqs: float = 90.0,
    versioned: bool = True,
) -> Dict[str, Any]:
    conditions = {
        "contrato_valido": contract_status == "VALID",
        "gates_aprobados": gates_status == "PASSED",
        "lineage_disponible": bool(lineage_available),
        "errores_criticos_0": critical_errors == 0,
        "dqs_suficiente": dqs >= min_dqs,
        "version_registrada": bool(versioned),
    }
    ready = all(conditions.values())
    return {
        "dataset": dataset,
        "model_ready": ready,
        "criterion": conditions,
        "decision": "MODEL_READY" if ready else "NO_MODEL_READY",
        "note": "Dataset apto para preparación ML sin fugas (fit solo en train, ver src/ml)."
        if ready
        else "No cumple todos los criterios; se bloquea su uso downstream.",
    }