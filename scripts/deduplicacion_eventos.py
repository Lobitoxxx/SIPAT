"""Unificación de eventos de distintas fuentes: ¿son el mismo siniestro?

POR QUÉ ESTE MÓDULO EXISTE
---------------------------
`modelo_multi.py` calculaba la respuesta combinada como

    y_total = y_onsv + y_sutran + y_ositran

Eso suma **tres universos que no se pueden sumar**:

1. **Ventanas temporales distintas.** Medidas sobre los datos reales del workspace:
   ONSV va de 2021-01-01 a 2025-12-28, SUTRAN de 2020-01-01 a 2021-09-30 y
   OSITRAN de 2019 a 2026. Sumarlos es sumar periodos distintos, así que el
   "total" no describe ninguna ventana concreta.
2. **Solapamiento.** El mismo accidente lo reportan ONSV (notificación a la
   policía) y SUTRAN (concesionario). Sumarlos cuenta el evento dos veces.
3. **Imposibilidad de emparejar OSITRAN.** `ositran_accidentes.csv` es un
   agregado por ruta/año/mes/causa: **no tiene fecha de evento ni coordenadas**.
   No se puede deduplicar contra nada, así que no debe entrar en un total.

La salida de este módulo es un dataframe con **una fila por siniestro único**, con
la etiqueta de qué fuentes lo vieron. Eso permite construir un `y_total` honesta
(unión deduplicada dentro de la ventana común) y estimar el subregistro con
Lincoln-Petersen usando n_a, n_b y n_ab medidos, en vez de suponer que las fuentes
son independientes.

LA REGLA DE EMPAREJAMIENTO
--------------------------
Una fila de B es duplicado de una de A si cae **dentro del radio y dentro de la
ventana temporal**, y el emparejamiento es **uno a uno**: cada fila de A se consume
como mucho una vez, para que un mismo evento de A no absorba diez de B. Los
parámetros (radio, días) viven en `ParametrosEmparejamiento` y sus valores por
defecto están justificados con datos, no puestos porque sí.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

__all__ = [
    "ParametrosEmparejamiento",
    "VENTANAS_REFERENCIA",
    "ventanas_de_fuente",
    "ventana_comun",
    "emparejar_uno_a_uno",
    "unificar_onsv_sutran",
    "resumen_unificacion",
]

# Ventanas medidas sobre los ficheros del workspace. Se recalculan en
# `ventanas_de_fuente`; esta copia documenta lo que se observó y permite detectar
# que la fuente cambió de cobertura.
VENTANAS_REFERENCIA = {
    "ONSV": ("2021-01-01", "2025-12-28"),
    "SUTRAN": ("2020-01-01", "2021-09-30"),
    "OSITRAN": ("2019-01-01", "2026-12-31"),  # agregado anual, sin fecha de evento
}

_KM_POR_GRADO = 111.0


@dataclass(frozen=True)
class ParametrosEmparejamiento:
    """Tolerancias del emparejamiento, con su justificación.

    `radio_km=0.25`: el error de geocodificación lineal de ONSV sobre la red vial
    es de metros, así que a 250 m lo que se empareja es el mismo punto de la
    calzada. Un radio mayor emparejaría dos accidentes distintos de un tramo
    corto; uno menor partiría el mismo evento en dos.

    `tolerancia_dias=1`: las notificaciones llegan con retraso, y ±1 día separa
    "el mismo evento" de "el evento de al lado".
    """

    radio_km: float = 0.25
    tolerancia_dias: int = 1


def ventanas_de_fuente(
    onsv: pd.DataFrame, sutran: pd.DataFrame
) -> Dict[str, Tuple[pd.Timestamp, pd.Timestamp]]:
    """Ventana temporal observada de cada fuente, leída de los datos."""
    o = pd.to_datetime(onsv["fecha"], errors="coerce")
    s = pd.to_datetime(sutran["FECHA_DT"], errors="coerce")
    return {
        "ONSV": (o.min(), o.max()),
        "SUTRAN": (s.min(), s.max()),
    }


def ventana_comun(
    ventanas: Dict[str, Tuple[pd.Timestamp, pd.Timestamp]],
    fuentes: Tuple[str, ...] = ("ONSV", "SUTRAN"),
) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """Intersección de las ventanas. Sin intersección devuelve `(None, None)`.

    Importa distinguir "no hay solape" de "hay cero eventos en el solape". Si
    `max(inicios) > min(fines)` la intersección está **invertida** y, si se
    devuelve tal cual, el filtro `fecha >= ini & fecha <= fin` deja el dataframe
    vacío: cero eventos, sin error y sin aviso. Con datos reales Eso aparece
    cuando una fuente cubre meses que la otra no cubre, y el efecto es publicar
    una red con 0 siniestros. Aquí se devuelve `(None, None)` y quien llama decide
    cómo señalarlo.
    """
    lows = [ventanas[f][0] for f in fuentes if f in ventanas]
    highs = [ventanas[f][1] for f in fuentes if f in fuentes]
    if not lows or not highs:
        return (None, None)
    ini, fin = max(lows), min(highs)
    if pd.isna(ini) or pd.isna(fin) or ini > fin:
        return (None, None)
    return (ini, fin)


def emparejar_uno_a_uno(
    a: pd.DataFrame,
    b: pd.DataFrame,
    fecha_a: str = "fecha_dt",
    fecha_b: str = "fecha_dt",
    lat_a: str = "lat",
    lon_a: str = "lon",
    lat_b: str = "lat",
    lon_b: str = "lon",
    params: ParametrosEmparejamiento = ParametrosEmparejamiento(),
) -> pd.DataFrame:
    """Empareja las filas de `b` contra las de `a`, consuming cada `a` una vez.

    Devuelve un dataframe alineado con el índice de `b` y columnas:
      - `pos_a`: posición (entera) de la fila de `a` emparejada, o -1.
      - `dist_km`: distancia en km entre las coordenadas emparejadas.
      - `delta_dias`: diferencia absoluta de fecha en días.
    """
    vacio = pd.DataFrame(
        {"pos_a": -1, "dist_km": np.nan, "delta_dias": np.nan}, index=b.index, dtype=float
    )
    if len(a) == 0 or len(b) == 0:
        vacio["pos_a"] = vacio["pos_a"].astype(int)
        return vacio

    lat_a = pd.to_numeric(a[lat_a], errors="coerce").to_numpy(dtype=float)
    lon_a = pd.to_numeric(a[lon_a], errors="coerce").to_numpy(dtype=float)
    fecha_a = pd.to_datetime(a[fecha_a], errors="coerce").to_numpy()
    fecha_a_dias = fecha_a.astype("datetime64[D]").astype(float)

    lat_b = pd.to_numeric(b[lat_b], errors="coerce").to_numpy(dtype=float)
    lon_b = pd.to_numeric(b[lon_b], errors="coerce").to_numpy(dtype=float)
    fecha_b = pd.to_datetime(b[fecha_b], errors="coerce").to_numpy()
    fecha_b_dias = fecha_b.astype("datetime64[D]").astype(float)

    # Rows of `a` with no usable coordinate or date are excluded from the tree
    # *before* building it. `cKDTree` raises `ValueError: data must be finite` on
    # NaN, and the real CSVs do have accidents without coordinates, so the whole
    # pipeline died on data that should simply be unmatchable. Note also that
    # `NaT.astype("datetime64[D]").astype(float)` is `-9.2e18`, not NaN: it passes
    # `np.isfinite`, so the date guard below checks the values, not just the dtype.
    coord_a_ok = np.isfinite(lon_a) & np.isfinite(lat_a) & np.isfinite(fecha_a_dias)
    filas_a = np.flatnonzero(coord_a_ok)
    if len(filas_a) == 0:
        vacio["pos_a"] = vacio["pos_a"].astype(int)
        return vacio

    # Original position of `a`, so `pos_a` keeps pointing into `a`'s own indexing.
    tree = cKDTree(np.column_stack([lon_a[filas_a], lat_a[filas_a]]))
    rad_grados = params.radio_km / _KM_POR_GRADO
    consumido = np.zeros(len(a), dtype=bool)

    pos_a = np.full(len(b), -1, dtype=int)
    dist_km = np.full(len(b), np.nan)
    delta_dias = np.full(len(b), np.nan)

    for j in range(len(b)):
        if not (np.isfinite(lon_b[j]) and np.isfinite(lat_b[j]) and np.isfinite(fecha_b_dias[j])):
            continue
        vecinos_pos = tree.query_ball_point([lon_b[j], lat_b[j]], r=rad_grados)
        if not vecinos_pos:
            continue
        vecinos = filas_a[np.asarray(vecinos_pos, dtype=int)]
        mejor = -1
        mejor_dist = np.inf
        for ia in vecinos:
            if consumido[ia] or not np.isfinite(fecha_a_dias[ia]):
                continue
            if abs(fecha_b_dias[j] - fecha_a_dias[ia]) > params.tolerancia_dias:
                continue
            # lon se corrige por cos(lat): sin eso, la distancia se infla hacia los polos.
            dist = (
                np.hypot(
                    (lon_b[j] - lon_a[ia]) * np.cos(np.radians(lat_b[j])),
                    lat_b[j] - lat_a[ia],
                )
                * _KM_POR_GRADO
            )
            if dist < mejor_dist:
                mejor, mejor_dist = ia, dist
        if mejor >= 0:
            consumido[mejor] = True
            pos_a[j] = mejor
            dist_km[j] = mejor_dist
            delta_dias[j] = abs(fecha_b_dias[j] - fecha_a_dias[mejor])

    return pd.DataFrame({"pos_a": pos_a, "dist_km": dist_km, "delta_dias": delta_dias}, index=b.index)


def unificar_onsv_sutran(
    onsv: pd.DataFrame,
    sutran: pd.DataFrame,
    params: ParametrosEmparejamiento = ParametrosEmparejamiento(),
    col_ruta_onsv: str = "COD CARRETERA",
    col_km_onsv: str = "km_red",
    col_ruta_sutran: str = "CODIGO_VIA",
    col_km_sutran: str = "KM",
) -> pd.DataFrame:
    """Una fila por siniestro único de ONSV ∪ SUTRAN, dentro de la ventana común.

    Columnas de salida:
      - `fuentes`: "ONSV", "SUTRAN" u "ONSV+SUTRAN".
      - `fecha`: la de ONSV si el evento fue visto por las dos; si no, la que haya.
      - `fallecidos`: **máximo** de las dos fuentes, no la suma: es el mismo
        evento, y sumar también doblaría las víctimas.
      - `ruta`, `km_red`: suficiente para asignar el evento único a su tramo.

    `ruta`/`km_red` se arrastran porque sin ellos la unión sirve para contar pero
    no para repartir: un total de red correcto con un reparto por tramo que sigue
    sumando las dos fuentes deja el error hidden en la columna que se publica.
    En un par emparejado manda ONSV (posición geocodificada más fina).
    """
    o = onsv.copy()
    o["fecha_dt"] = pd.to_datetime(o["fecha"], errors="coerce")
    o["lat"] = pd.to_numeric(o["lat"], errors="coerce")
    o["lon"] = pd.to_numeric(o["lon"], errors="coerce")
    o["fallecidos"] = pd.to_numeric(o["fallecidos"], errors="coerce")
    o["ruta"] = o[col_ruta_onsv].astype(str).str.strip() if col_ruta_onsv in o else ""
    o["km_red"] = pd.to_numeric(
        o[col_km_onsv], errors="coerce") if col_km_onsv in o else np.nan
    o = o.reset_index(drop=True)

    s = sutran.copy()
    s["fecha_dt"] = pd.to_datetime(s["FECHA_DT"], errors="coerce")
    s["lat"] = pd.to_numeric(s["LATITUD_GEO"], errors="coerce")
    s["lon"] = pd.to_numeric(s["LONGITUD_GEO"], errors="coerce")
    s["fallecidos"] = pd.to_numeric(s["FALLECIDOS"], errors="coerce")
    s["ruta"] = s[col_ruta_sutran].astype(str).str.strip() if col_ruta_sutran in s else ""
    s["km_red"] = pd.to_numeric(
        s[col_km_sutran], errors="coerce") if col_km_sutran in s else np.nan
    s = s.reset_index(drop=True)

    ini, fin = ventana_comun(ventanas_de_fuente(o, s))
    if ini is None:
        return pd.DataFrame(
            {"fecha_dt": pd.Series(dtype="datetime64[ns]"), "lat": np.nan, "lon": np.nan,
             "fallecidos": np.nan, "ruta": "", "km_red": np.nan,
             "fuentes": pd.Series(dtype=object)}
        )

    o = o[(o["fecha_dt"] >= ini) & (o["fecha_dt"] <= fin)].reset_index(drop=True)
    s = s[(s["fecha_dt"] >= ini) & (s["fecha_dt"] <= fin)].reset_index(drop=True)

    match = emparejar_uno_a_uno(
        o, s, fecha_a="fecha_dt", fecha_b="fecha_dt",
        lat_a="lat", lon_a="lon", lat_b="lat", lon_b="lon", params=params,
    )

    pos_a = match["pos_a"].to_numpy()
    es_duplicado = pos_a >= 0

    cols = ["fecha_dt", "lat", "lon", "fallecidos", "ruta", "km_red"]
    filas = pd.concat(
        [
            o[cols].assign(fuentes="ONSV"),
            s.loc[~es_duplicado, cols].assign(fuentes="SUTRAN"),
        ],
        ignore_index=True,
    )

    # Cada fila de ONSV va seguida, en este orden, por las de SUTRAN.
    col_fal = filas.columns.get_loc("fallecidos")
    col_fue = filas.columns.get_loc("fuentes")
    fal_sutran = s["fallecidos"].to_numpy(dtype=float)
    for j in np.flatnonzero(es_duplicado):
        ia = int(pos_a[j])
        # Busca el máximo de ambas fuentes: si SUTRAN registra más víctimas, es el
        # mismo evento con más detalle, no dos eventos.
        filas.iat[ia, col_fal] = np.nanmax([filas.iat[ia, col_fal], fal_sutran[j]])
        filas.iat[ia, col_fue] = "ONSV+SUTRAN"

    return filas.sort_values("fecha_dt").reset_index(drop=True)


def resumen_unificacion(
    onsv: pd.DataFrame,
    sutran: pd.DataFrame,
    unif: Optional[pd.DataFrame] = None,
    params: ParametrosEmparejamiento = ParametrosEmparejamiento(),
) -> Dict[str, object]:
    """Conteos auditables: n_a, n_b, n_ab, únicos y solape.

    `n_ab` es el insumo de Lincoln-Petersen; `doble_conteo_evitado` es lo que la
    suma ingenua `y_onsv + y_sutran` habría inflado.
    """
    if unif is None:
        unif = unificar_onsv_sutran(onsv, sutran, params=params)
    etiquetas = unif["fuentes"].value_counts().to_dict() if len(unif) else {}
    n_ab = int(etiquetas.get("ONSV+SUTRAN", 0))
    return {
        "n_onsv": int(etiquetas.get("ONSV", 0)),
        "n_sutran": int(etiquetas.get("SUTRAN", 0)),
        "n_ambos": n_ab,
        "n_unico_total": int(len(unif)),
        "suma_naiva": n_ab * 2 + int(etiquetas.get("ONSV", 0)) + int(etiquetas.get("SUTRAN", 0)),
        "doble_conteo_evitado": n_ab,
    }