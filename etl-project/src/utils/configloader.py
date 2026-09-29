# -*- coding: utf-8 -*-
"""Configuración: carga de YAML y expansión de rutas.

Separación código/configuración (sección 25). Sin credenciales en el repo.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from .paths import CONFIG, ROOT

_DEFAULT_SIPAT_ROOT = ".."


def load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def sipat_root() -> Path:
    """Carpeta del workspace SIPAT (fuentes reales). Sobrescribible con env SIPAT_ROOT."""
    env = os.environ.get("SIPAT_ROOT")
    raw = env if env else _DEFAULT_SIPAT_ROOT
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p).resolve()


def expand_path(template: str) -> str:
    """Expande ${sipat_root} y ${project_root} en rutas de config."""
    if "${sipat_root}" in template:
        return template.replace("${sipat_root}", str(sipat_root()))
    if "${project_root}" in template:
        return template.replace("${project_root}", str(ROOT))
    return template


def load_settings() -> Dict[str, Any]:
    return load_yaml(CONFIG / "settings.yaml")


def load_sources() -> Dict[str, Dict[str, Any]]:
    """Mapea dataset -> spec fuente desde config/sources/*.yaml."""
    sources_dir = CONFIG / "sources"
    out: Dict[str, Dict[str, Any]] = {}
    for f in sorted(sources_dir.glob("*.yaml")):
        data = load_yaml(f)
        src = data.get("source", {})
        ds = src.get("dataset")
        if ds:
            out[ds] = src
    return out


def load_contract(dataset: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    fname = settings["datasets"][dataset]["contract"]
    return load_yaml(CONFIG / "contracts" / fname)


def load_quality_rules() -> Dict[str, Any]:
    return load_yaml(CONFIG / "quality" / "quality_rules.yaml")


def load_catalogs(dataset: str) -> Dict[str, list]:
    """Catálogos de dominio: dataset -> {nombre_catalogo: [valores admitidos]}.

    Filtra las claves que no son catálogos de valores (p. ej. `aggregations`,
    que es una lista de especificaciones SQL), de modo que los consumidores
    puedan iterar sin filtrar.
    """
    data = load_yaml(CONFIG / "quality" / "catalogs" / f"{dataset}.yaml")
    catalogs = data.get("catalogs", {}) or {}
    return {k: v for k, v in catalogs.items() if isinstance(v, list) and k != "aggregations"}


def load_aggregations(dataset: str) -> list:
    """Especificaciones de agregaciones Gold declaradas para el dataset."""
    data = load_yaml(CONFIG / "quality" / "catalogs" / f"{dataset}.yaml")
    return list((data.get("catalogs", {}) or {}).get("aggregations", []) or [])