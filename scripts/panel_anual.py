"""Panel tramo × año: los conteos que el modelo necesita para hablar del tiempo.

POR QUÉ ESTE MÓDULO EXISTE
---------------------------
`dataset_modelo.csv` es un agregado **por tramo**: 3.750 filas, un solo conteo
`y_onsv` y **ningún año**. Con ese archivo no se puede responder a dos preguntas
que el proyecto afirma responder:

  - ¿la exposición son km o son km·año? El campo `expo_km` lo trata como km, y el
    comentario del código decía "objetivo estandarizada por año" sin que hubiera
    ningún año en ninguna parte.
  - ¿el modelo predice el año que viene? Sin un eje temporal no hay forma de
    hacer un holdout temporal; cualquier validación es espacial.

Este módulo reconstruye el panel desde los eventos geocodificados, asignando cada
siniestro a su tramo y su año, y devuelve la **rejilla completa** (todos los tramos
× todos los años, con ceros donde no hubo siniestros). Los ceros importan: son la
información de que ese tramo-no-ese-año tuvo cero, que es justo lo que un modelo
de conteos necesita y lo que un `y > 0` filtrado borra.

El `features_engine.py` usa el panel para exponer km·año, y `validez_predictiva.py`
lo usa para el holdout temporal. Una sola definición de "evento en un tramo en un
año" para los dos, que es lo que evita que el diagnóstico y el producto midan
cosas distintas.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

__all__ = [
    "asignar_tramos",
    "asignar_por_km_red",
    "construir_panel",
    "panel_a_agregado_tramo",
    "resumen_panel",
]

# Radio de asignación a tramo en grados (~1.1 km). Es el que ya usaba
# `modelo_multi.py` al casar SUTRAN contra los centroides de tramo; mantenerlo
# evita que el panel y el modelo asignen distinto.
RADIO_ASIGNACION_GRADOS = 0.02


def asignar_tramos(
    eventos: pd.DataFrame,
    tramo_xy: np.ndarray,
    fecha_col: str = "fecha_dt",
    lat_col: str = "lat",
    lon_col: str = "lon",
    radio: float = RADIO_ASIGNACION_GRADOS,
) -> pd.DataFrame:
    """Añade `idx_tramo` y `anio` a `eventos` según el tramo centroide más cercano.

    Los eventos fuera del radio quedan con `idx_tramo = -1`: se conservan en la
    tabla (para poder auditarlos) pero no entran en el panel, porque forzarles un
    tramo inventaría exposición.
    """
    ev = eventos.copy()
    lat = pd.to_numeric(ev[lat_col], errors="coerce").to_numpy(dtype=float)
    lon = pd.to_numeric(ev[lon_col], errors="coerce").to_numpy(dtype=float)
    fechas = pd.to_datetime(ev[fecha_col], errors="coerce")

    ev["anio"] = fechas.dt.year.astype("Int64")
    ev["mes"] = fechas.dt.month.astype("Int64")

    if len(tramo_xy) == 0 or len(ev) == 0:
        ev["idx_tramo"] = -1
        return ev

    tree = cKDTree(np.asarray(tramo_xy, dtype=float))
    dist, idx = tree.query(np.column_stack([lon, lat]), k=1, distance_upper_bound=radio)
    # cKDTree devuelve len(ev) como índice cuando no hay vecino dentro del radio.
    idx = np.where(np.isfinite(dist), idx, -1)
    ev["idx_tramo"] = idx
    ev["dist_tramo"] = np.where(idx >= 0, dist, np.nan)
    return ev


def asignar_por_km_red(
    eventos: pd.DataFrame,
    tramos: pd.DataFrame,
    col_ruta: str = "ruta",
    col_km: str = "km_red",
    fecha_col: str = "fecha_dt",
) -> pd.DataFrame:
    """Asigna por **(ruta, km en la red)**, que es el método canónico del proyecto.

    Es la misma regla que `features_tramos.tramo_id()` usa para producir
    `onsv_n` / `sutran_n`: se busca el tramo de esa ruta que contiene ese
    kilometraje. Se replica aquí en vez de llamar a aquel script porque ese
    archivo ejecuta todo el pipeline al importarse.

    Importa que sea *la misma* asignación y no "una buena": con el método de
    centroides, 1.183 de los 3.750 tramos cambiaban de conteo, así que el panel y
    `dataset_modelo.csv`_dirían dos cosas distintas sobre el mismo tramo. Dos
    recuentos del mismo objeto tienen que salir del mismo emparejamiento.
    """
    ev = eventos.copy()
    ev["anio"] = pd.to_datetime(ev[fecha_col], errors="coerce").dt.year.astype("Int64")

    t = tramos[["ruta", "km0", "km1"]].copy()
    t["ruta"] = t["ruta"].astype(str)
    km0 = pd.to_numeric(t["km0"], errors="coerce")
    km1 = pd.to_numeric(t["km1"], errors="coerce")

    rutas = set(t["ruta"])
    km_ev = pd.to_numeric(ev.get(col_km), errors="coerce")
    ruta_ev = ev[col_ruta].astype(str)

    asignados: List[Optional[int]] = []
    for ruta, km in zip(ruta_ev, km_ev):
        if ruta not in rutas or pd.isna(km):
            asignados.append(None)
            continue
        m = (t["ruta"] == ruta) & (km0 <= km) & (km1 >= km)
        if not m.any():
            asignados.append(None)
            continue
        pos = int(np.flatnonzero(m.to_numpy())[0])
        asignados.append(pos)

    ev["idx_tramo"] = pd.array(asignados, dtype="Int64")
    return ev


def construir_panel(
    eventos: pd.DataFrame,
    tramo_ids: Sequence,
    long_km: Optional[Sequence[float]] = None,
    anios: Optional[Sequence[int]] = None,
    col_fallecidos: str = "fallecidos",
    col_tramo: str = "idx_tramo",
) -> pd.DataFrame:
    """Rejilla completa tramo × año con conteos, fallecidos y exposición.

    Devuelve columnas: `idx_tramo`, `anio`, `n_eventos`, `n_fallecidos`,
    `expo_km`, `expo_km_anio`, `densidad_anual`.

    `expo_km` es la longitud del tramo (una vez por tramo); `expo_km_anio` es esa
    longitud multiplicada por el número de años de la rejilla, que es la unidad
    que hace comparables tramos de 2 km con tramos de 30 km.
    """
    ev = eventos.copy()
    ev = ev[ev[col_tramo].astype("Int64") >= 0]

    if anios is None:
        vals = pd.to_numeric(ev["anio"], errors="coerce").dropna().astype(int).unique()
        anios = sorted(vals.tolist())
    anios = [int(a) for a in anios]

    idx_ids = pd.Index(pd.to_numeric(pd.Series(tramo_ids)).astype(int), name="idx_tramo")
    if long_km is None:
        long_km = np.ones(len(idx_ids))
    long_km = np.asarray(long_km, dtype=float)

    rejilla = pd.MultiIndex.from_product(
        [idx_ids, pd.Index(anios, name="anio")], names=["idx_tramo", "anio"]
    ).to_frame(index=False)

    conteos = (
        ev.groupby([col_tramo, "anio"], dropna=True)
        .agg(n_eventos=("anio", "size"), n_fallecidos=(col_fallecidos, "sum"))
        .reset_index()
        .rename(columns={col_tramo: "idx_tramo"})
    )
    conteos["idx_tramo"] = conteos["idx_tramo"].astype(int)

    panel = rejilla.merge(conteos, on=["idx_tramo", "anio"], how="left")
    panel["n_eventos"] = panel["n_eventos"].fillna(0).astype(int)
    panel["n_fallecidos"] = pd.to_numeric(panel["n_fallecidos"], errors="coerce").fillna(0)

    long_map = pd.Series(long_km, index=idx_ids.to_numpy())
    panel["expo_km"] = panel["idx_tramo"].map(long_map).fillna(0.0)
    panel["expo_km_anio"] = panel["expo_km"] * len(anios)
    panel["densidad_anual"] = np.where(
        panel["expo_km"] > 0, panel["n_eventos"] / panel["expo_km"], np.nan
    )
    return panel


def panel_a_agregado_tramo(
    panel: pd.DataFrame,
    col_n: str = "n_eventos",
    col_fal: str = "n_fallecidos",
    prefijo: str = "y_",
) -> pd.DataFrame:
    """Colapsa el panel por tramo: total, media anual y años con eventos."""
    g = panel.groupby("idx_tramo")
    out = pd.DataFrame(
        {
            f"{prefijo}total": g[col_n].sum(),
            f"{prefijo}anual_medio": g[col_n].mean(),
            f"{prefijo}fallecidos": g[col_fal].sum(),
            f"{prefijo}anios_con_evento": g[col_n].apply(lambda s: int((s > 0).sum())),
        }
    )
    return out


def resumen_panel(panel: pd.DataFrame, expo_km_total: float = 0.0) -> Dict[str, object]:
    """Cifras de control del panel: celdas, ceros, media por año y celdas vacías."""
    n = len(panel)
    con_evento = int((panel["n_eventos"] > 0).sum())
    por_anio = (
        panel.groupby("anio")["n_eventos"].sum().astype(int).to_dict() if n else {}
    )
    return {
        "n_tramos": int(panel["idx_tramo"].nunique()) if n else 0,
        "anios": sorted({int(a) for a in panel["anio"]}) if n else [],
        "n_celdas": n,
        "celdas_con_evento": con_evento,
        "celdas_en_cero": n - con_evento,
        "proporcion_celdas_en_cero": (n - con_evento) / n if n else None,
        "n_eventos_total": int(panel["n_eventos"].sum()) if n else 0,
        "eventos_por_anio": por_anio,
        "densidad_global_por_km_anio": (
            panel["n_eventos"].sum() / (expo_km_total * len(panel["anio"].unique()))
            if n and expo_km_total > 0
            else None
        ),
    }