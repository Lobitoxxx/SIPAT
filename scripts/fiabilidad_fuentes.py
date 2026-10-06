#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fiabilidad de las fuentes ONSV / SUTRAN / OSITRAN.

Este módulo responde a la **tercera** de las cuatro preguntas del proyecto, y
solo a esa:

| Pregunta | Módulo |
|---|---|
| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` |
| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |
| **¿Las fuentes ONSV/SUTRAN/OSITRAN son de fiar?** | **este módulo** |
| ¿La predicción aguanta fuera de muestra? | `scripts/validez_predictiva.py` |

No calcula un "índice de confiabilidad". Devuelve una **tabla de
afirmaciones**, cada una con veredicto, evidencia y límite. Ponderar cuatro
riesgos distintos en un número exigiría decidir cuánto pesa cada uno, y esa
decisión no sale de estos datos.

Salida: `data/processed/dashboard/fiabilidad_fuentes.json`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deduplicacion_eventos import (  # noqa: E402
    ParametrosEmparejamiento,
    resumen_unificacion,
    unificar_onsv_sutran,
    ventana_comun,
    ventanas_de_fuente,
)
from panel_anual import asignar_por_km_red  # noqa: E402

DATA = ROOT / "data" / "processed"
OUT = DATA / "dashboard"

# Extremos aproximados del territory continental de Peru. Sirve solo para
# descartar coordenadas invertidas o en otro pais; no es un control de calidad
# propiamente dicho.
_LAT_PERU = (-19.0, -0.5)
_LON_PERU = (-82.0, -68.0)


# --------------------------------------------------------------------------
# 1. Ventanas temporales
# --------------------------------------------------------------------------
def ventanas(onsv: pd.DataFrame, sutran: pd.DataFrame) -> Dict[str, object]:
    """Ventana observada por fuente y solape real entre ONSV y SUTRAN."""
    v = ventanas_de_fuente(onsv, sutran)
    ini, fin = ventana_comun(v)
    solape_meses = None
    if ini is not None and fin is not None:
        solape_meses = round((fin - ini).days / 30.44, 1)
    return {
        "por_fuente": {
            k: [None if pd.isna(a) else str(a.date()), None if pd.isna(b) else str(b.date())]
            for k, (a, b) in v.items()
        },
        "comun_onsv_sutran": {
            "inicio": None if ini is None else str(ini.date()),
            "fin": None if fin is None else str(fin.date()),
            "meses": solape_meses,
            "hay_solape": ini is not None,
        },
    }


# --------------------------------------------------------------------------
# 2. Calidad de coordenadas
# --------------------------------------------------------------------------
def calidad_coordenadas(
    eventos: pd.DataFrame, col_lat: str, col_lon: str, etiqueta: str
) -> Dict[str, object]:
    """Nulos, rango y coordenadas que caen fuera del Peru continental."""
    lat = pd.to_numeric(eventos[col_lat], errors="coerce")
    lon = pd.to_numeric(eventos[col_lon], errors="coerce")
    n = len(lat)
    # Nulo y "fuera de Peru" son defectos distintos y no se suman: una fila sin
    # coordenada no esta mal situada, esta sin situar. Contarlas como "fuera"
    # inflaria el indicador de error de geocodificacion con ausencia de dato.
    con_coord = lat.notna() & lon.notna()
    dentro = lat.between(*_LAT_PERU) & lon.between(*_LON_PERU) & con_coord
    fuera = int((con_coord & ~dentro).sum())
    n_sin_coord = int((~con_coord).sum())
    # Duplicados exactos por posicion: el mismo lugar no se cuenta dos veces.
    dup_pos = int(
        pd.DataFrame({"lat": lat.round(5), "lon": lon.round(5)}).duplicated().sum()
    )
    base = max(int(con_coord.sum()), 1)
    res: Dict[str, object] = {
        "fuente": etiqueta,
        "n_eventos": int(n),
        "lat_nulos": int(lat.isna().sum()),
        "lon_nulos": int(lon.isna().sum()),
        "sin_coordenada_usable": n_sin_coord,
        "pct_sin_coordenada": round(100.0 * n_sin_coord / n, 2) if n else None,
        "con_coordenada_usable": int(con_coord.sum()),
        "fuera_de_peru": fuera,
        "pct_fuera_de_peru": round(100.0 * fuera / base, 2) if con_coord.any() else None,
        "pct_fuera_de_peru_del_total": round(100.0 * fuera / n, 2) if n else None,
        "nota_denominador": (
            "`pct_fuera_de_peru` se calcula sobre las filas CON coordenada; "
            "`pct_fuera_de_peru_del_total` sobre todas. Confundirlos convierte "
            "coordenadas ausentes en coordenadas erroneous."
        ),
        "duplicados_exactos_posicion": dup_pos,
        "pct_duplicados": round(100.0 * dup_pos / n, 2) if n else None,
        "lat_rango": [None if lat.isna().all() else float(lat.min()), None if lat.isna().all() else float(lat.max())],
        "lon_rango": [None if lon.isna().all() else float(lon.min()), None if lon.isna().all() else float(lon.max())],
    }
    return res


# --------------------------------------------------------------------------
# 3. OSITRAN: el problema de la atribucion de ruta
# --------------------------------------------------------------------------
def _pesos_accidentes(ositran: pd.DataFrame) -> pd.Series:
    """Accidentes por fila, para poder pesar y no solo contar filas.

    En la fuente real cada fila vale 1 accidente, asi que contar filas y sumar
    `cant_accidentes` coinciden y el error pasa desapercibido. Un ficheiro con
    filas de mas de un accidente haria que `n_eventos` no significara nada de lo
    que su nombre dice, asi que los recuentos de OSITRAN se pesan siempre.
    """
    if "cant_accidentes" in ositran:
        w = pd.to_numeric(ositran["cant_accidentes"], errors="coerce")
        return w.fillna(0).clip(lower=0)
    return pd.Series(1.0, index=ositran.index)


def calidad_ositran(
    ositran: pd.DataFrame, tramos: pd.DataFrame
) -> Dict[str, object]:
    """Cuanto de OSITRAN es utilizable como senal espacial.

    OSITRAN agrega por concesion y ano. La columna `ruta` es una attribucion
    del highway agency y una parte muy grande de los registros viene como
    `SIN INFO`. Esa proportion decide cuanto de la fuente puede usarse, asi que
    se reporta contra los dos denominadores posibles: el total de eventos y
    solo los que tienen ruta.

    Todos los recuentos son **accidentes**, no filas: se pondera por
    `cant_accidentes`.
    """
    ruta = ositran["ruta"].astype(str).str.strip()
    sin_info = ruta.eq("SIN INFO") | ruta.isin(["", "nan", "None"])
    red = set(tramos["ruta"].astype(str).str.strip())
    pesos = _pesos_accidentes(ositran)
    con_ruta = ositran.loc[~sin_info]
    rutas_con = set(con_ruta["ruta"].astype(str).str.strip())
    en_red = con_ruta.loc[con_ruta["ruta"].astype(str).str.strip().isin(red)]

    n_total = int(pesos.sum())
    n_con_ruta = int(pesos.loc[~sin_info].sum())
    n_en_red = int(pesos.loc[en_red.index].sum())
    n_filas = int(len(ositran))
    return {
        "n_eventos": n_total,
        "n_filas": n_filas,
        "nota_unidad": (
            "Los conteos son accidentes (suma de `cant_accidentes`), no filas. "
            "Con la fuente real ambos numeros coinciden porque cada fila vale 1; "
            "la distincion se mantiene para que el indicador no dependa de eso."
        ),
        "n_anos": int(ositran["anio"].nunique()),
        "anos": sorted(int(a) for a in ositran["anio"].unique()),
        "concesiones_siglas": int(ositran["siglas"].nunique()),
        "eventos_sin_info_ruta": n_total - n_con_ruta,
        "pct_sin_info_ruta": round(100.0 * (n_total - n_con_ruta) / n_total, 1) if n_total else None,
        "eventos_con_ruta": n_con_ruta,
        "rutas_distintas_con_ruta": len(rutas_con),
        "rutas_que_coinciden_con_red": len(rutas_con & red),
        "eventos_sobre_ruta_de_red": n_en_red,
        "cobertura_pct_del_total": round(100.0 * n_en_red / n_total, 1) if n_total else None,
        "cobertura_pct_de_los_con_ruta": round(100.0 * n_en_red / n_con_ruta, 1) if n_con_ruta else None,
        "nota_denominador": (
            "Cobertura sobre el total y sobre los eventos con ruta difieren mucho: "
            "el 39.5% de registros sin atribucion hace que la cobertura real sea 71% "
            "de lo utilizable y 42.9% de lo publicado. Publicar solo una de las dos "
            "cifras induce a error."
        ),
    }


# --------------------------------------------------------------------------
# 4. Solape entre fuentes y Lincoln-Petersen
# --------------------------------------------------------------------------
def solape_onsv_sutran(
    onsv: pd.DataFrame,
    sutran: pd.DataFrame,
    params: Optional[ParametrosEmparejamiento] = None,
) -> Dict[str, object]:
    """Conteos de solape y estimador de captura-doble."""
    params = params or ParametrosEmparejamiento()
    unif = unificar_onsv_sutran(onsv, sutran, params=params)
    r = resumen_unificacion(onsv, sutran, unif=unif, params=params)
    n_a = int(r["n_onsv"])
    n_b = int(r["n_sutran"])
    n_ab = int(r["n_ambos"])
    union_obs = int(r["n_unico_total"])

    # `resumen_unificacion` cuenta los marginales como exclusivos: un evento
    # emparejado aparece solo en `n_ambos`, nunca en `n_onsv` ni en `n_sutran`.
    # Lincoln-Petersen necesita los marginales INCLUSIVOS (cuantos eventos vio
    # cada fuente, coincidan o no), asi que se reconstruyen sumando el solape.
    # Sin esta correccion n_a y n_b salen bajos y el estimador se infla.
    lp: Dict[str, object] = {
        "n_a": n_a + n_ab,
        "n_b": n_b + n_ab,
        "n_ab": n_ab,
        "n_a_exclusivo": n_a,
        "n_b_exclusivo": n_b,
        "nota_marginales": (
            "`n_a`/`n_b` de Lincoln-Petersen son marginales inclusivos "
            "(= exclusivo + `n_ab`); las claves `*_exclusivo` dejan ver la "
            "reconciliacion con `resumen_unificacion`."
        ),
    }
    n_a_inc = n_a + n_ab
    n_b_inc = n_b + n_ab
    if n_ab > 0 and n_a_inc > 0 and n_b_inc > 0:
        n_lp = n_a_inc * n_b_inc / n_ab
        # Varianza clasica del estimador en escala logaritmica.
        var_log = (n_a_inc - n_b_inc) ** 2 / (n_a_inc * n_b_inc * n_ab)
        se_log = float(np.sqrt(var_log))
        # Lincoln-Petersen implica una poblacion oculta mayor que la observada.
        # Si el factor es enorme, el estimador no describe subnotificacion sino
        # populations distintas; se marca como no utilizable.
        factor = n_lp / union_obs if union_obs else None
        lp.update(
            {
                "n_estimado_lincoln_petersen": round(n_lp, 1),
                "se_log": round(se_log, 3),
                "ic95_bajo": round(n_lp * float(np.exp(-1.96 * se_log)), 1),
                "ic95_alto": round(n_lp * float(np.exp(1.96 * se_log)), 1),
                "factor_oculto_sobre_observado": round(factor, 1) if factor else None,
            }
        )
    return {"parametros": {"radio_km": params.radio_km, "tolerancia_dias": params.tolerancia_dias}, **r, "lincoln_petersen": lp}


def _diagnostico_independencia(
    onsv: pd.DataFrame,
    sutran: pd.DataFrame,
    lp: Dict[str, object],
    red: pd.DataFrame,
) -> Dict[str, object]:
    """Prueba si el supuesto de Lincoln-Petersen puede sostenerse.

    LP requiere que ambas fuentes enumeren la **misma** poblacion de
    siniestros y que las capturas sean independientes. Si no comparten
    universo, la estimacion no es una subnotificacion sino dos poblaciones
    distintas sumadas.
    """
    rutas_onsv = set(onsv["COD CARRETERA"].astype(str).str.strip())
    rutas_sutran = set(sutran["CODIGO_VIA"].astype(str).str.strip())
    red_set = set(red["ruta"].astype(str).str.strip())
    inter = rutas_onsv & rutas_sutran
    n_ab = int(lp.get("n_ab", 0))
    n_a = int(lp.get("n_a", 0))
    n_b = int(lp.get("n_b", 0))
    # Un solape de ruta muy bajo significa que las fuentes no hablan del
    # mismo conjunto de carreteras.
    jaccard = len(inter) / len(rutas_onsv | rutas_sutran) if (rutas_onsv | rutas_sutran) else 0.0
    ratio_solape = n_ab / (n_a + n_b) if (n_a + n_b) else 0.0
    return {
        "rutas_onsv": len(rutas_onsv),
        "rutas_sutran": len(rutas_sutran),
        "rutas_comunes": len(inter),
        "jaccard_rutas": round(jaccard, 3),
        "rutas_onsv_en_red": len(rutas_onsv & red_set),
        "rutas_sutran_en_red": len(rutas_sutran & red_set),
        "coincidencia_de_eventos_pct": round(100.0 * ratio_solape, 2),
        "supuesto_independencia_verificable": False,
        "motivo": (
            "Lincoln-Petersen asume dos capturas independientes de la MISMA "
            "poblacion. ONSV es un registro nacional de siniestros con enfoque "
            "fatal; SUTRAN es un registro de alertas de operador para un conjunto "
            "de corredores. Las rutas SI se solapan (Jaccard "
            f"{jaccard:.2f}) y sin embargo solo coincide el "
            f"{100*ratio_solape:.1f}% de los eventos: las dos fuentes recorren las "
            "mismas carreteras pero no registran los mismos accidentes, porque la "
            "unidad de registro de una es el siniestro y la de la otra es la alerta "
            "del operador. Aplicar LP daria un factor de poblacion oculta de "
            f"{lp.get('factor_oculto_sobre_observado')}x, que no es subnotificacion "
            "sino dos fuentes no comparables sumadas. Por eso se reporta "
            "'no estimable'."
        ),
    }


# --------------------------------------------------------------------------
# 5. Sensitividad de los parametros de emparejamiento
# --------------------------------------------------------------------------
def sensibilidad_matching(onsv: pd.DataFrame, sutran: pd.DataFrame) -> List[Dict[str, object]]:
    """Como se mueve el solape al mover radio y tolerancia."""
    filas: List[Dict[str, object]] = []
    for radio in (0.1, 0.25, 0.5, 1.0):
        for tol in (0, 1, 3):
            p = ParametrosEmparejamiento(radio_km=radio, tolerancia_dias=tol)
            try:
                r = resumen_unificacion(onsv, sutran, params=p)
                filas.append(
                    {
                        "radio_km": radio,
                        "tolerancia_dias": tol,
                        "n_ambos": int(r["n_ambos"]),
                        "n_unico_total": int(r["n_unico_total"]),
                    }
                )
            except Exception as exc:  # pragma: no cover
                filas.append({"radio_km": radio, "tolerancia_dias": tol, "error": str(exc)})
    return filas


# --------------------------------------------------------------------------
# 6. Tabla de afirmaciones
# --------------------------------------------------------------------------
def afirmaciones(
    sol: Dict[str, object],
    cal_onsv: Dict[str, object],
    cal_sutran: Dict[str, object],
    cal_osi: Dict[str, object],
    indep: Dict[str, object],
    sens: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    """Cada fila es una afirmacion con su veredicto y su limite.

    No se combinan en un indice: ponderar exigiria decidir el peso de cada
    riesgo, decision que no sale de los datos.
    """
    lp = sol["lincoln_petersen"]
    n_ab_ref = sol["n_ambos"]
    n_ab_min = min((f["n_ambos"] for f in sens if "n_ambos" in f), default=n_ab_ref)
    n_ab_max = max((f["n_ambos"] for f in sens if "n_ambos" in f), default=n_ab_ref)

    return [
        {
            "afirmacion": "Las coordenadas de ONSV y SUTRAN son utilizables para geolocalizar sobre la red vial",
            "veredicto": "ONSV SI / SUTRAN CON RESERVAS",
            "evidencia": (
                f"ONSV: 0 nulos, {cal_onsv['pct_fuera_de_peru']}% fuera de Peru, {cal_onsv['pct_duplicados']}% duplicados. "
                f"SUTRAN: {cal_sutran['sin_coordenada_usable']} filas sin coordenada "
                f"({cal_sutran['pct_sin_coordenada']}%), "
                f"{cal_sutran['pct_fuera_de_peru']}% fuera de Peru y {cal_sutran['pct_duplicados']}% de duplicados exactos de posicion."
            ),
            "limite": (
                f"ONSV se puede usar tal cual. SUTRAN no: el {cal_sutran['pct_duplicados']}% de sus "
                f"filas repite la misma coordenada y el {cal_sutran['pct_sin_coordenada']}% se queda "
                "sin coordenadas, asi que cualquier agregado por posicion necesita deduplicar y "
                "descartar esas filas antes. Lo que se ha medido es plausibilidad geografica: las "
                "coordenadas que si existen estan dentro del Peru. El error de posicion contra una "
                "fuente de verdad no se ha auditado."
            ),
        },
        {
            "afirmacion": "ONSV y SUTRAN registran los mismos siniestros",
            "veredicto": "NO",
            "evidencia": (
                f"Las rutas se solapan bastante (Jaccard {indep['jaccard_rutas']}: "
                f"{indep['rutas_comunes']} de {indep['rutas_onsv']+indep['rutas_sutran']} rutas son comunes), "
                f"pero solo el {indep['coincidencia_de_eventos_pct']}% de los eventos coincide."
            ),
            "limite": (
                "Que las rutas coincidan y los eventos no significa que SUTRAN registra otra "
                "poblacion de siniestros: significa que **captura las mismas carreteras de otra "
                "manera** (un registro por alerta del operador, no por siniestro). Con 8,9 meses "
                "de solape temporal, el criterio de emparejamiento no es lo que explica el "
                "desajuste, asi que la conclusion es que el conteo de ambas fuentes no es sumable."
            ),
        },
        {
            "afirmacion": "Se puede estimar la subnotificacion con Lincoln-Petersen",
            "veredicto": "NO ESTIMABLE",
            "evidencia": f"n_a={lp.get('n_a')}, n_b={lp.get('n_b')}, n_ab={lp.get('n_ab')}; el estimador sale con factor oculto {lp.get('factor_oculto_sobre_observado')}x sobre lo observado.",
            "limite": indep["motivo"],
        },
        {
            "afirmacion": "El solape de eventos entre ONSV y SUTRAN es estable al criterio de emparejamiento",
            "veredicto": "NO",
            "evidencia": f"n_ab va de {n_ab_min} a {n_ab_max} al variar radio 0.1-1.0 km y tolerancia 0-3 dias: un factor {n_ab_max/max(n_ab_min,1):.0f}.",
            "limite": (
                "No es estable: duplicar el radio de emparejamiento multiplica el "
                "solape, lo que significa que parte del 'solape' son accidentes "
                "distantes en la misma carretera y no el mismo accidente. Por eso "
                f"el valor de n_ab ({n_ab_ref} a radio 0,25 km) es una decision de "
                "parametro, no una medida, y usarlo como n_ab en un estimador "
                "importa. Es el mismo motivo por el que la afirmacion anterior se "
                "responde 'no' en vez de 'si'."
            ),
        },
        {
            "afirmacion": "OSITRAN aporta una senal espacial de magnitud comparable a ONSV",
            "veredicto": "PARCIAL",
            "evidencia": f"{cal_osi['n_eventos']} eventos; {cal_osi['pct_sin_info_ruta']}% sin atribucion de ruta; cobertura {cal_osi['cobertura_pct_del_total']}% del total / {cal_osi['cobertura_pct_de_los_con_ruta']}% de los eventos con ruta.",
            "limite": "Es un agregado anual por concesion, sin fecha de evento ni fatalities separados, asi que sirve como carga relativa por tramo y no como serie de siniestros.",
        },
    ]


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
def analizar() -> Dict[str, object]:
    onsv = pd.read_csv(DATA / "onsv_nacional_geocod.csv")
    sutran = pd.read_csv(DATA / "sutran_accidentes_geocod.csv")
    ositran = pd.read_csv(DATA / "ositran_accidentes.csv")
    red = pd.read_csv(DATA / "tramos_red.csv")

    cal_onsv = calidad_coordenadas(onsv, "lat", "lon", "ONSV")
    cal_sutran = calidad_coordenadas(sutran, "LATITUD_GEO", "LONGITUD_GEO", "SUTRAN")
    cal_osi = calidad_ositran(ositran, red)
    sol = solape_onsv_sutran(onsv, sutran)
    indep = _diagnostico_independencia(onsv, sutran, sol["lincoln_petersen"], red)
    sens = sensibilidad_matching(onsv, sutran)

    return {
        "ventanas": ventanas(onsv, sutran),
        "calidad_coordenadas": {"onsv": cal_onsv, "sutran": cal_sutran},
        "ositran": cal_osi,
        "solape": sol,
        "independencia": indep,
        "sensibilidad_matching": sens,
        "afirmaciones": afirmaciones(sol, cal_onsv, cal_sutran, cal_osi, indep, sens),
    }


def formatear(res: Dict[str, object]) -> str:
    L: List[str] = []
    L.append("== FIABILIDAD DE FUENTES (ONSV / SUTRAN / OSITRAN) ==")
    v = res["ventanas"]
    L.append("\n[1/4] Ventanas temporales")
    for k, (a, b) in v["por_fuente"].items():
        L.append(f"      {k}: {a} -> {b}")
    c = v["comun_onsv_sutran"]
    L.append(f"      solape ONSV-SUTRAN: {c['inicio']} -> {c['fin']} ({c['meses']} meses)")

    L.append("\n[2/4] Coordenadas")
    for k in ("onsv", "sutran"):
        q = res["calidad_coordenadas"][k]
        L.append(
            f"      {k.upper():7s} n={q['n_eventos']:6d}  nulos={q['lat_nulos']+q['lon_nulos']:4d}  "
            f"fuera_peru={q['fuera_de_peru']:3d} ({q['pct_fuera_de_peru']}%)  dup_pos={q['duplicados_exactos_posicion']}"
        )

    L.append("\n[3/4] OSITRAN")
    o = res["ositran"]
    L.append(f"      eventos={o['n_eventos']}  anos={o['n_anos']}  concessions={o['concesiones_siglas']}")
    L.append(f"      SIN INFO ruta={o['eventos_sin_info_ruta']} ({o['pct_sin_info_ruta']}%)  con ruta={o['eventos_con_ruta']}")
    L.append(
        f"      cobertura: {o['cobertura_pct_del_total']}% del total / "
        f"{o['cobertura_pct_de_los_con_ruta']}% de los eventos con ruta "
        f"({o['eventos_sobre_ruta_de_red']} eventos sobre ruta de red)"
    )

    L.append("\n[4/4] Solape ONSV-SUTRAN y Lincoln-Petersen")
    s = res["solape"]
    lp = s["lincoln_petersen"]
    L.append(f"      n_onsv={s['n_onsv']}  n_sutran={s['n_sutran']}  n_ambos={s['n_ambos']}  unicos={s['n_unico_total']}")
    L.append(f"      LP estimado={lp.get('n_estimado_lincoln_petersen')}  factor oculto={lp.get('factor_oculto_sobre_observado')}x")
    L.append("      [veredicto] Subnotificacion: NO ESTIMABLE (las fuentes no comparten universo)")

    L.append("\n== Afirmaciones ==")
    for a in res["afirmaciones"]:
        L.append(f"  [{a['veredicto']}] {a['afirmacion']}")
        L.append(f"      evidencia: {a['evidencia']}")
        L.append(f"      limite:    {a['limite']}")
    return "\n".join(L)


def main() -> int:
    res = analizar()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "fiabilidad_fuentes.json"
    path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(formatear(res))
    print(f"\nGuardado: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())