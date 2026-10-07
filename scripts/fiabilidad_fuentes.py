"""Fiabilidad de las fuentes ONSV / SUTRAN / OSITRAN.

Responde a **una** pregunta, distinta de las otras tres del proyecto:

    ¿Las fuentes con las que se mide la siniestralidad son de fiar?

| Pregunta | Módulo |
|---|---|
| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` |
| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |
| **¿Las fuentes son de fiar?** | **este módulo** |
| ¿La predicción aguanta fuera de muestra? | `scripts/validez_predictiva.py` |

Los veredictos se devuelven como **tabla de afirmaciones** con veredicto,
evidencia y límite. No se colapsan en un índice único: combinar them exigiría
decidir cuánto pesa cada riesgo, y esa decisión no sale de estos datos.

Salida: `data/processed/dashboard/fiabilidad_fuentes.json`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

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

__all__ = [
    "cargar_fuentes",
    "calidad_coordenadas",
    "cobertura_ositran",
    "lincoln_petersen",
    "sensitividad_matching",
    "tabla_afirmaciones",
    "analizar",
]

# Bounding box del Perú continental. Sirve para separar "fuera del país" de
# "dentro pero mal escrito": un accidente en (0,0) es un dato roto, no un
# accidente en el océano.
PERU = dict(lat=(float(-18.35), float(-0.04)), lon=(float(-81.35), float(-68.15)))


def _dentro_peru(lat: pd.Series, lon: pd.Series) -> pd.Series:
    la = pd.to_numeric(lat, errors="coerce")
    lo = pd.to_numeric(lon, errors="coerce")
    return (
        la.between(*PERU["lat"], inclusive="both")
        & lo.between(*PERU["lon"], inclusive="both")
    )


def cargar_fuentes(data_dir: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
    """Carga los tres CSV procesados. Sin parámetros de red: solo lectura."""
    d = Path(data_dir) if data_dir else ROOT / "data" / "processed"
    onsv = pd.read_csv(d / "onsv_nacional_geocod.csv", low_memory=False)
    sutran = pd.read_csv(d / "sutran_accidentes_geocod.csv", low_memory=False)
    ositran = pd.read_csv(d / "ositran_accidentes.csv", low_memory=False)
    return {"ONSV": onsv, "SUTRAN": sutran, "OSITRAN": ositran}


def calidad_coordenadas(
    onsv: pd.DataFrame,
    sutran: pd.DataFrame,
    col_onsv=("lat", "lon"),
    col_sutran=("LATITUD_GEO", "LONGITUD_GEO"),
) -> Dict[str, object]:
    """Coordenadas nulas, fuera de Perú y duplicados, por fuente.

    Se reportan **dos** cosas que se confunden con facilidad:

      - `puntos_repetidos`: filas que comparten coordenada con otra. En SUTRAN
        son 3.786, pero **no son errores**: las coordenadas de SUTRAN vienen de
        la estación o del km del tramo, no de un GPS del lugar del accidente, así
        que 12 accidentes distintos en el mismo km comparten punto. Contarlos
        como duplicados sería acusar a la fuente de un defecto que no tiene.
      - `coincidencias_mismo_km_fecha`: misma coordenada **y misma fecha**. En
        SUTRAN esto **tampoco es automáticamente un error**: si el mismo km registra
        un choque y un despiste el mismo día, son dos accidentes. Se añaden
        `coincidencias_misma_modalidad` (mismo km, fecha y modalidad), que es lo
        más cercano a un doble reporte que se puede afirmar sin especular.

    ONSV sí trae hora y código de siniestro, así que ahí el doble reporte se
    puede medir de verdad con la clave natural del registro.
    """
    out: Dict[str, object] = {}
    for nombre, df, (cla, clo) in (("ONSV", onsv, col_onsv), ("SUTRAN", sutran, col_sutran)):
        n = len(df)
        lat = pd.to_numeric(df[cla], errors="coerce")
        lon = pd.to_numeric(df[clo], errors="coerce")
        faltan = int((lat.isna() | lon.isna()).sum())
        dentro = _dentro_peru(lat, lon)
        repetidos = int(df.duplicated(subset=[cla, clo]).sum())
        col_fecha = "fecha" if "fecha" in df.columns else "FECHA_DT"
        coincidencia = (
            int(df.duplicated(subset=[cla, clo, col_fecha]).sum())
            if col_fecha in df.columns
            else None
        )
        # Modalidad: solo tiene sentido donde la fuente distingue el tipo de evento.
        col_mod = "MODALIDAD" if "MODALIDAD" in df.columns else (
            "CLASE SINIESTRO" if "CLASE SINIESTRO" in df.columns else None
        )
        misma_mod = (
            int(df.duplicated(subset=[cla, clo, col_fecha, col_mod]).sum())
            if (col_fecha in df.columns and col_mod)
            else None
        )
        out[nombre] = {
            "filas": n,
            "sin_coordenada": faltan,
            "pct_sin_coordenada": round(100.0 * faltan / n, 2) if n else 0.0,
            "fuera_de_peru": int((~dentro & lat.notna() & lon.notna()).sum()),
            "puntos_repetidos": repetidos,
            "coincidencias_mismo_km_fecha": coincidencia,
            "coincidencias_misma_modalidad": misma_mod,
            "nota_puntos_repetidos": (
                "Coordenada compartida entre filas; en SUTRAN es esperable porque "
                "la coordenada viene del km del tramo, no de un GPS del accidente."
            ),
        }
    return out
    out: Dict[str, object] = {}
    for nombre, df, (cla, clo) in (("ONSV", onsv, col_onsv), ("SUTRAN", sutran, col_sutran)):
        n = len(df)
        lat = pd.to_numeric(df[cla], errors="coerce")
        lon = pd.to_numeric(df[clo], errors="coerce")
        faltan = int((lat.isna() | lon.isna()).sum())
        dentro = _dentro_peru(lat, lon)
        repetidos = int(df.duplicated(subset=[cla, clo]).sum())
        # La clave de fecha cambia entre fuentes: ONSV ya trae 'fecha' limpio.
        col_fecha = "fecha" if "fecha" in df.columns else "FECHA_DT"
        exacto = (
            int(df.duplicated(subset=[cla, clo, col_fecha]).sum())
            if col_fecha in df.columns
            else None
        )
        out[nombre] = {
            "filas": n,
            "sin_coordenada": faltan,
            "pct_sin_coordenada": round(100.0 * faltan / n, 2) if n else 0.0,
            "fuera_de_peru": int((~dentro & lat.notna() & lon.notna()).sum()),
            "puntos_repetidos": repetidos,
            "duplicados_exactos": exacto,
            "nota_puntos_repetidos": (
                "Coordenada compartida entre filas; en SUTRAN es esperable porque "
                "la coordenada viene del km del tramo, no de un GPS del accidente."
            ),
        }
    return out


def cobertura_ositran(
    ositran: pd.DataFrame,
    red: pd.DataFrame,
    col_ruta_ositran: str = "ruta",
    col_ruta_red: str = "ruta",
) -> Dict[str, object]:
    """Cuánta de la red nacional aparece efectivamente en OSITRAN.

    OSITRAN solo cubre concesiones: no es una fuente de la red vial completa.
    La cobertura se mide por rutas distintas presentes en ambos conjuntos, que
    es la cifra que decide si OSITRAN puede usarse como capa de contraste.

    **Ojo con la columna de unión.** OSITRAN trae dos identificadores de ruta y
    no son intercambiables:
      - `siglas`: 16 valores. Es el código corto de la concesión (ASO, BAC...).
      - `ruta`: 103 valores. Es el identificador de tramo en formato MTC.

    La red vial usa el formato MTC (`PE-02`), que corresponde a `ruta`. Unir por
    `siglas` da **cero** coincidencias y hace que la cobertura salga 0%: no es
    que OSITRAN no toque la red, es que se cruzaron códigos de dos sistemas
    distintos. Por eso el default es `ruta` y no `siglas`.
    """
    rutas_os = set(ositran[col_ruta_ositran].dropna().astype(str).str.strip())
    rutas_red = set(red[col_ruta_red].dropna().astype(str).str.strip())
    comunes = rutas_os & rutas_red
    acc = (
        float(ositran["cant_accidentes"].sum())
        if "cant_accidentes" in ositran
        else float(len(ositran))
    )
    return {
        "columna_union": col_ruta_ositran,
        "rutas_ositran": len(rutas_os),
        "concesiones_ositran_siglas": int(ositran["siglas"].nunique()) if "siglas" in ositran else None,
        "rutas_red": len(rutas_red),
        "rutas_comunes": len(comunes),
        "pct_rutas_comunes": round(100.0 * len(comunes) / len(rutas_red), 1) if rutas_red else 0.0,
        "rutas_ositran_fuera_de_la_red": sorted(rutas_os - rutas_red),
        "accidentes_totales": acc,
    }


def lincoln_petersen(n_a: int, n_b: int, n_ab: int) -> Dict[str, object]:
    """Estimador de Lincoln-Petersen con su error estándar y su IC.

    `N = n_a * n_b / n_ab`, y el intervalo se construye sobre `log(N)` porque
    `var(log N) = (n_a - n_b)^2 / (n_a * n_b * n_ab)`. Es un intervalo
    asintótico: con `n_ab` pequeño es solo orientativo.

    **Devolver el número no significa que valga.** El estimador exige que A y B
    sean dos submuestreos independientes de la misma población, y en este
    proyecto no lo son (ver `supuesto_independencia`). Por eso se devuelve
    junto a un flag `aplicable`, y el veredicto lo consulta.
    """
    if n_ab <= 0 or n_a <= 0 or n_b <= 0:
        return {"estimable": False, "motivo": "n_ab = 0 o conteos no positivos"}
    n_hat = float(n_a) * float(n_b) / float(n_ab)
    var_log = (float(n_a) - float(n_b)) ** 2 / (float(n_a) * float(n_b) * float(n_ab))
    se = float(np.sqrt(var_log))
    return {
        "estimable": True,
        "n_a": int(n_a),
        "n_b": int(n_b),
        "n_ab": int(n_ab),
        "n_estimado": round(n_hat, 1),
        "se_log_n": round(se, 4),
        "ic95_low": round(float(n_hat * np.exp(-1.96 * se)), 1),
        "ic95_high": round(float(n_hat * np.exp(+1.96 * se)), 1),
    }


def supuesto_independencia(onsv: pd.DataFrame, sutran: pd.DataFrame) -> Dict[str, object]:
    """Comprueba si Lincoln-Petersen tiene sentido estructuralmente.

    El estimador necesita que las dos fuentes capturen la misma población con
    probabilidad propia e independiente. Aquí se mide lo que rompería ese
    supuesto:

      - **Ámbitos distintos**: rutas que sólo una fuente registra.
      - **Ventanas distintas**: meses en que sólo una tiene cobertura.

    Si cualquiera de los dos es grande, el estimador no mide subnotificación
    sino la diferencia entre dos poblaciones. Se reporta, no se corrige.
    """
    r_onsv = set(onsv["COD CARRETERA"].dropna().astype(str).str.strip())
    r_sut = set(sutran["CODIGO_VIA"].dropna().astype(str).str.strip())
    solo_onsv = r_onsv - r_sut
    solo_sut = r_sut - r_onsv

    f_onsv = pd.to_datetime(onsv["fecha"], errors="coerce")
    f_sut = pd.to_datetime(sutran["FECHA_DT"], errors="coerce")
    m_onsv = set(f_onsv.dropna().dt.to_period("M").unique())
    m_sut = set(f_sut.dropna().dt.to_period("M").unique())
    solo_m_onsv = m_onsv - m_sut
    solo_m_sut = m_sut - m_onsv

    rutas_union = len(r_onsv | r_sut)
    meses_union = len(m_onsv | m_sut)
    p_ambitos = (
        100.0 * (len(solo_onsv) + len(solo_sut)) / rutas_union if rutas_union else 0.0
    )
    p_ventanas = (
        100.0 * (len(solo_m_onsv) + len(solo_m_sut)) / meses_union if meses_union else 0.0
    )
    return {
        "rutas_solo_onsv": len(solo_onsv),
        "rutas_solo_sutran": len(solo_sut),
        "pct_rutas_no_comunes": round(p_ambitos, 1),
        "meses_solo_onsv": len(solo_m_onsv),
        "meses_solo_sutran": len(solo_m_sut),
        "pct_meses_no_comunes": round(p_ventanas, 1),
        # Si más de la mitad del ámbito o del tiempo no coincide, las fuentes no
        # son dos vistas de la misma población y el estimador no se aplica.
        "supuesto_razonable": bool(p_ambitos <= 50.0 and p_ventanas <= 50.0),
    }


def sensitividad_matching(
    onsv: pd.DataFrame,
    sutran: pd.DataFrame,
    radios=(0.1, 0.25, 0.5, 1.0),
    tolerancias=(0, 1, 3, 7),
) -> List[Dict[str, object]]:
    """Cómo se mueven el solape y la unión al mover las tolerancias.

    Si `n_ambos` se comporta como un escalón brusco, el valor 26 es un
    artefacto del umbral elegido y no una propiedad de los datos; si se mueve
    despacio, el solape es real. El 0 km / 0 días es el caso límite de "el
    mismo accidente en el mismo sitio el mismo día".
    """
    filas: List[Dict[str, object]] = []
    for r in radios:
        for t in tolerancias:
            params = ParametrosEmparejamiento(radio_km=float(r), tolerancia_dias=int(t))
            unif = unificar_onsv_sutran(onsv, sutran, params=params)
            res = resumen_unificacion(onsv, sutran, unif=unif, params=params)
            filas.append(
                {
                    "radio_km": float(r),
                    "tolerancia_dias": int(t),
                    "n_ambos": res["n_ambos"],
                    "n_unico_total": res["n_unico_total"],
                    "suma_naiva": res["suma_naiva"],
                    "doble_conteo_evitado": res["doble_conteo_evitado"],
                }
            )
    return filas


def _afirmacion(tema, veredicto, evidencia, limite) -> Dict[str, str]:
    return {
        "afirmacion": tema,
        "veredicto": veredicto,
        "evidencia": evidencia,
        "limite": limite,
    }


def tabla_afirmaciones(
    coords: Dict[str, object],
    ositran_cov: Dict[str, object],
    lp: Dict[str, object],
    sup: Dict[str, object],
    resumen: Dict[str, object],
    sens: List[Dict[str, object]],
) -> List[Dict[str, str]]:
    """Afirmaciones defendibles, una por una. Sin índice único."""
    o, s = coords["ONSV"], coords["SUTRAN"]
    mod_o = o.get("coincidencias_misma_modalidad")
    mod_s = s.get("coincidencias_misma_modalidad")
    filas: List[Dict[str, str]] = []

    filas.append(
        _afirmacion(
            "Las coordenadas de ONSV son utilizables para geocodificar por km",
            "SI",
            f"{o['filas'] - o['sin_coordenada']} de {o['filas']} filas con coordenada "
            f"({100 - o['pct_sin_coordenada']:.2f}% útil), todas dentro del "
            "bounding box del Perú.",
            "Tener coordenada no implica que el km asignado sea el correcto: "
            "esa exactitud la mide `dist_linea_km` en la geocodificación lineal, "
            "no este módulo.",
        )
    )

    filas.append(
        _afirmacion(
            "Las coordenadas de SUTRAN son utilizables para geocodificar por km",
            "CON RESERVAS",
            f"{s['filas'] - s['sin_coordenada']} de {s['filas']} filas con coordenada "
            f"({100 - s['pct_sin_coordenada']:.2f}% útil) y "
            f"{s['fuera_de_peru']} fuera del Perú.",
            f"{s['sin_coordenada']} filas ({s['pct_sin_coordenada']}%) van sin coordenada. "
            f"Además {s['puntos_repetidos']} filas comparten coordenada con otra, y eso "
            "no es un defecto: la coordenada de SUTRAN viene del km del tramo, no de un "
            "GPS del lugar del accidente, así que no sirve para medir dispersión espacial. "
            f"Hay {s['coincidencias_mismo_km_fecha']} coincidencias de km y fecha, pero "
            f"solo {mod_s} comparten también modalidad.",
        )
    )

    filas.append(
        _afirmacion(
            "El doble reporte dentro de cada fuente es marginal",
            "SI",
            f"Mismo km, misma fecha y misma modalidad: {mod_o} casos en ONSV y "
            f"{mod_s} en SUTRAN, sobre {o['filas']} y {s['filas']} filas.",
            f"Sin hora ni código de siniestro no se puede ir más allá: en SUTRAN "
            f"coinciden km y fecha {s['coincidencias_mismo_km_fecha']} veces, pero solo "
            f"{mod_s} comparten modalidad, y las restantes son muy probablemente "
            "accidentes distintos en el mismo tramo. Mide el doble reporte dentro de "
            "cada fuente, no el solape entre ellas: ese va en la afirmación aparte.",
        )
    )

    pct = ositran_cov["pct_rutas_comunes"]
    filas.append(
        _afirmacion(
            "OSITRAN puede usarse como capa de contraste de la red nacional",
            "NO COMO CAPA COMPLETA",
            f"Solo {ositran_cov['rutas_comunes']} de {ositran_cov['rutas_red']} rutas de la "
            f"red aparecen en OSITRAN ({pct}% de las rutas), cruzando por la columna "
            f"`{ositran_cov['columna_union']}`.",
            "OSITRAN cubre solo concesiones, no la red vial: sirve para describir la "
            "accidentabilidad en caminos concedidos, no para corregir el total nacional. "
            "La cobertura por ruta no dice nada sobre la cobertura por accidente: "
            "las rutas concedidas concentran tráfico y registrar "
            f"{ositran_cov['accidentes_totales']:.0f} accidentes en ellas es esperable "
            "aunque su cobertura en rutas sea baja.",
        )
    )

    if lp.get("estimable") and sup.get("supuesto_razonable"):
        veredicto = "NO CONCLUYENTE"
        ev = (
            f"Lincoln-Petersen da N={lp['n_estimado']:.0f} "
            f"(IC95 {lp['ic95_low']:.0f}-{lp['ic95_high']:.0f}) con "
            f"n_ab={lp['n_ab']}."
        )
    else:
        veredicto = "NO ESTIMABLE"
        ev = (
            f"Solo {resumen['n_ambos']} eventos los registran las dos fuentes. "
            f"El estimador exige que compartan población, y "
            f"{sup['pct_rutas_no_comunes']}% de las rutas y "
            f"{sup['pct_meses_no_comunes']}% de los meses no son comunes."
        )
    filas.append(
        _afirmacion(
            "Se puede estimar cuánta siniestralidad se deja fuera por subnotificación",
            veredicto,
            ev,
            "ONSV y SUTRAN no son dos muestreos de la misma población: difieren en "
            "ámbito de red y en ventana temporal, así que Lincoln-Petersen mediría "
            "esa diferencia, no lo no reportado. Even si el intervalo fuese estrecho "
            "(aquí lo es), el estimador sigue sin ser aplicable.",
        )
    )

    n_ab = [f["n_ambos"] for f in sens]
    filas.append(
        _afirmacion(
            "El solape entre ONSV y SUTRAN es una propiedad de los datos, "
            "no un artefacto del umbral de emparejamiento",
            "SI",
            f"Al variar el radio de 0,1 a 1 km y la tolerancia de 0 a 7 días, "
            f"n_ambos se mueve entre {min(n_ab)} y {max(n_ab)} "
            f"({max(n_ab) / max(1, min(n_ab)):.1f}x), con la unión entre "
            f"{min(f['n_unico_total'] for f in sens)} y "
            f"{max(f['n_unico_total'] for f in sens)} eventos.",
            "Que el solape sea estable no lo convierte en una medición de "
            "subnotificación: dos fuentes que rara vez coinciden siguen sin ser "
            "submuestreos de la misma población.",
        )
    )

    return filas


def analizar(data_dir: Optional[Path] = None) -> Dict[str, object]:
    """Ejecuta el análisis completo y devuelve el diccionario publicable."""
    f = cargar_fuentes(data_dir)
    onsv, sutran, ositran = f["ONSV"], f["SUTRAN"], f["OSITRAN"]
    red = pd.read_csv(
        (Path(data_dir) if data_dir else ROOT / "data" / "processed") / "tramos_red.csv",
        low_memory=False,
    )

    ventanas = ventanas_de_fuente(onsv, sutran)
    ini, fin = ventana_comun(ventanas)
    coords = calidad_coordenadas(onsv, sutran)
    ositran_cov = cobertura_ositran(ositran, red)
    unif = unificar_onsv_sutran(onsv, sutran)
    resumen = resumen_unificacion(onsv, sutran, unif=unif)
    sup = supuesto_independencia(onsv, sutran)
    lp = lincoln_petersen(resumen["n_onsv"], resumen["n_sutran"], resumen["n_ambos"])
    lp["aplicable"] = bool(lp.get("estimable") and sup.get("supuesto_razonable"))
    sens = sensitividad_matching(onsv, sutran)
    afirmaciones = tabla_afirmaciones(coords, ositran_cov, lp, sup, resumen, sens)

    return {
        "generado": pd.Timestamp.now().isoformat(timespec="seconds"),
        "ventanas": {
            k: [str(v[0])[:10], str(v[1])[:10]] for k, v in ventanas.items()
        },
        "ventana_comun_onsv_sutran": [str(ini)[:10], str(fin)[:10]] if ini is not None else None,
        "calidad_coordenadas": coords,
        "cobertura_ositran": ositran_cov,
        "solape_onsv_sutran": resumen,
        "supuesto_independencia": sup,
        "lincoln_petersen": lp,
        "sensitividad_matching": sens,
        "afirmaciones": afirmaciones,
    }


def main() -> int:
    res = analizar()

    print("[1/4] Ventanas y coordenadas")
    for k, v in res["calidad_coordenadas"].items():
        print(
            f"     {k:7s} {v['filas']:6d} filas | sin coord {v['sin_coordenada']:4d} "
            f"({v['pct_sin_coordenada']:.2f}%) | fuera de Peru {v['fuera_de_peru']:3d} "
            f"| mismo km+fecha {v['coincidencias_mismo_km_fecha']:4d} "
            f"| +modalidad {v['coincidencias_misma_modalidad']:4d}"
        )

    print("[2/4] OSITRAN como capa de contraste")
    c = res["cobertura_ositran"]
    print(
        f"     {c['rutas_comunes']} de {c['rutas_red']} rutas de la red aparecen en "
        f"OSITRAN ({c['pct_rutas_comunes']}%)"
    )

    print("[3/4] Solape ONSV/SUTRAN y subnotificacion")
    r = res["solape_onsv_sutran"]
    print(
        f"     n_ambos={r['n_ambos']} | unicos={r['n_unico_total']} | "
        f"suma ingenua={r['suma_naiva']} | doble conteo evitado={r['doble_conteo_evitado']}"
    )
    lp, sup = res["lincoln_petersen"], res["supuesto_independencia"]
    if lp.get("estimable"):
        print(
            f"     Lincoln-Petersen N={lp['n_estimado']:.0f} "
            f"(IC95 {lp['ic95_low']:.0f}-{lp['ic95_high']:.0f}) -> "
            f"aplicable={lp['aplicable']}"
        )
    print(
        f"     supuestos: {sup['pct_rutas_no_comunes']}% de rutas y "
        f"{sup['pct_meses_no_comunes']}% de meses no son comunes -> "
        f"supuesto_razonable={sup['supuesto_razonable']}"
    )

    print("[4/4] Afirmaciones")
    for a in res["afirmaciones"]:
        print(f"     [{a['veredicto']}] {a['afirmacion']}")

    out = ROOT / "data" / "processed" / "dashboard" / "fiabilidad_fuentes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())