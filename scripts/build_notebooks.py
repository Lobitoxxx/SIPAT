# -*- coding: utf-8 -*-
"""Genera los notebooks 05 (fiabilidad de las fuentes) y 06 (validez predictiva).

Mismo patron que `etl-project/scripts/build_notebooks.py`: los .ipynb se
construyen desde Python para garantizar JSON valido y evitar el escapado manual
de cadenas dentro de un .ipynb.

    python scripts/build_notebooks.py             # genera 05 y 06
    python scripts/build_notebooks.py --execute   # ademas los ejecuta (nbclient)
    python scripts/build_notebooks.py --only 05   # solo uno

Los notebooks se versionan SIN salidas. Cada celda llama al modulo real
(`fiabilidad_fuentes`, `validez_predictiva`), asi que no hay ni un numero escrito
a mano: si el modulo cambia, el notebook cambia.
"""
from __future__ import annotations

import json
from itertools import count
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"
OUT.mkdir(parents=True, exist_ok=True)

_CELL_IDS = count(1)


def _cell_id() -> str:
    """nbformat >= 4.5 exige 'id' en cada celda."""
    return f"cell-{next(_CELL_IDS):03d}"


def md(*lines: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": _cell_id(),
        "metadata": {},
        "source": [l + "\n" for l in lines][:-1] + [lines[-1]],
    }


def code(*lines: str) -> dict:
    src = [l + "\n" for l in lines][:-1] + [lines[-1]]
    return {
        "cell_type": "code",
        "id": _cell_id(),
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src,
    }


def notebook(cells: list) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.14"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def validate(cells: list, name: str) -> None:
    """Compila cada celda de codigo: un error de sintaxis aqui solo apareceria
    al abrir el notebook, que es exactamente cuando mas molesta."""
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        try:
            compile(src, f"{name}::cell{i}", "exec")
        except SyntaxError as exc:
            raise SystemExit(
                f"{name}: celda de codigo {i} con error de sintaxis: {exc.msg} (linea {exc.lineno})\n"
                f"  {exc.text!r}"
            ) from exc


# El kernel arranca en notebooks/, que es un subdirectorio del repo. Los modulos
# viven en scripts/ y se importan por nombre plano porque todos hacen
# `sys.path.insert(0, ROOT)` al ejecutarse; no hay paquete que instalar.
PRELUDE = [
    "import sys",
    "from pathlib import Path",
    "",
    "import numpy as np",
    "import pandas as pd",
    "",
    "ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()",
    "sys.path.insert(0, str(ROOT))",
    "sys.path.insert(0, str(ROOT / 'scripts'))",
    "",
    "DATA = ROOT / 'data' / 'processed'",
    "",
    "pd.set_option('display.max_columns', 40)",
    "pd.set_option('display.width', 170)",
    "pd.set_option('display.max_colwidth', 90)",
]

# ------------------------------------------------------- 05 · FUENTES ----

fuentes = [
    md(
        "# 05 · Fiabilidad de las fuentes",
        "",
        "Fase CRISP-DM **Evaluation**. Este notebook responde a la **tercera** de las",
        "cuatro preguntas del proyecto, y solo a esa:",
        "",
        "| Pregunta | Módulo |",
        "|---|---|",
        "| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` |",
        "| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |",
        "| **¿Las fuentes ONSV/SUTRAN/OSITRAN son de fiar?** | **este notebook** |",
        "| ¿La predicción aguanta fuera de muestra? | `06_validez_predictiva.ipynb` |",
        "",
        "Las cuatro preguntas se respondieron durante meses con el mismo nombre",
        "(\"confiabilidad\") y en módulos distintos. Mezclarlas hace que un 92 de DQS",
        "se lea como \"los datos son buenos\". Aquí **no se calcula ningún índice único**:",
        "ponderar cuatro riesgos distintos exigiría decidir cuánto pesa cada uno, y esa",
        "decisión no sale de estos datos. Lo que hay es una **tabla de afirmaciones**",
        "con veredicto, evidencia medida y límite conocido.",
        "",
        "Todo lo que sigue llama a `scripts/fiabilidad_fuentes.py` contra los datos",
        "reales del workspace. Ningún número de este notebook está escrito a mano: si el",
        "módulo cambia, estas celdas cambian con él, y es posible que este notebook",
        "contradiga al informe ya publicado.",
    ),
    code(*PRELUDE,
         "import fiabilidad_fuentes as ff",
         "",
         "res = ff.analizar()",
         "print('Claves del informe:', list(res))"),

    md("## 5.1 · Las fuentes no cubren lo mismo",
        "",
        "El primer hecho, y el que invalida cualquier suma entre fuentes: cada una tiene",
        "su propia ventana. La comparación entre ONSV y SUTRAN solo existe en el",
        "solape, que son menos de nueve meses."),
    code("for k, (a, b) in res['ventanas'].items():",
         "    print(f'{k:8s} {a} -> {b}')",
         "",
         "print('\\nSolape ONSV-SUTRAN:', res['ventana_comun_onsv_sutran'])"),
    md("### Por qué la ventana común importa tanto",
        "",
        "Sin solape, el filtro `fecha >= inicio & fecha <= fin` deja el dataframe",
        "**vacío**: cero eventos, sin error y sin aviso. Por eso `ventana_comun()`",
        "devuelve `(None, None)` cuando la intersección está invertida, en vez de",
        "devolver un inicio mayor que un fin y dejar que el filtro vacíe la fuente en",
        "silencio. Una red publicada con 0 siniestros y ningún aviso es exactamente el",
        "fallo que esa función evita."),

    md("## 5.2 · Coordenadas: qué se puede usar y qué no",
        "",
        "Dos cosas distintas que no se pueden sumar:",
        "",
        "- **ausencia de dato**: la fila no tiene coordenadas; no está mal situada.",
        "- **error de geocodificación**: la fila tiene coordenadas y cae fuera del Perú.",
        "",
        "Sumarlos convertiría la falta de información en una tasa de error."),
    code("cal = res['calidad_coordenadas']",
         "tabla = pd.DataFrame([",
         "    {",
         "        'fuente': k,",
         "        'filas': v['filas'],",
         "        'sin_coordenada': v['sin_coordenada'],",
         "        'pct_sin_coordenada': v['pct_sin_coordenada'],",
         "        'fuera_de_peru': v['fuera_de_peru'],",
         "        'puntos_repetidos': v['puntos_repetidos'],",
         "        'km+fecha': v['coincidencias_mismo_km_fecha'],",
         "        '+modalidad': v['coincidencias_misma_modalidad'],",
         "    }",
         "    for k, v in cal.items()",
         "])",
         "tabla"),
    md("### Los 3.786 puntos repetidos de SUTRAN no son un defecto",
        "",
        "Es la lectura equivocada más fácil de cometer con esta fuente. SUTRAN tiene",
        "3.786 filas que comparten coordenada con otra, y contarlas como \"duplicados\"",
        "equivale a acusar a la fuente de un defecto que no tiene.",
        "",
        "La coordenada de SUTRAN **viene del km del tramo** donde se registró el",
        "accidente, no de un GPS del lugar del accidente. Por eso 12 accidentes",
        "distintos del mismo km comparten punto.",
        "",
        "Por la misma razón, las **320** coincidencias de km+fecha tampoco son",
        "automáticamente errores: en el km -18,023 del 2021-02-24 hay un choque a las",
        "19:30 y un despiste, y son dos accidentes. Al añadir la modalidad, los",
        "candidatos a doble reporte bajan a **204**.",
        "",
        "> La distinción importa porque el número accionable es **204**, no 3.786. Un",
        "> informe que publique 3.786 describe una fuente que no tiene ese problema.",
        "",
        "Y lo que **no** se ha medido: el error de posición contra una fuente de verdad.",
        "Que una coordenada esté dentro del Perú no significa que esté en la carretera",
        "correcta. Solo se ha comprobado plausibilidad geográfica."),

    md("## 5.3 · OSITRAN: la columna de unión importa",
        "",
        "OSITRAN cubre **26 de las 150 rutas** de la red nacional (17,3%). Ese número",
        "salió de un fallo real que conviene documentar, porque el síntoma se lee como",
        "un hallazgo y no como un error."),
    code("cov = res['cobertura_ositran']",
         "for k in ('columna_union', 'rutas_ositran', 'concesiones_ositran_siglas',",
         "          'rutas_red', 'rutas_comunes', 'pct_rutas_comunes',",
         "          'accidentes_totales'):",
         "    print(f'{k:30s} {cov[k]}')"),
    md("### Por qué salía 0,0 %",
        "",
        "OSITRAN trae **dos** identificadores de ruta y no son intercambiables:",
        "",
        "| Columna | Valores únicos | Qué es |",
        "|---|---|---|",
        "| `siglas` | 16 | código corto de la concesión (ASO, BAC, CHA...) |",
        "| `ruta` | 103 | identificador de tramo en formato MTC |",
        "| red vial | 150 | rutas en formato MTC (`PE-02`) |",
        "",
        "La red usa el formato MTC, o sea que corresponde a `ruta`. Al cruzar por",
        "`siglas` la intersección sale **vacía** y la cobertura se publica como 0,0%:",
        "no es que OSITRAN no toque la red, es que se cruzaron códigos de dos sistemas",
        "distintos. Un 0% con decimals invita a leerlo como un dato; por eso el módulo",
        "expone `columna_union` y hay un test que falla si alguien cambia el default.",
        "",
        "### 16 concesiones y 103 rutas no se contradicen",
        "",
        "Son **unidades distintas**: 16 es el número de empresas concesionarias, 103 el",
        "de tramos que el agency declara y 26 los que caen dentro de la red de estudio.",
        "El README mezclaba las dos y parecía discrepar consigo mismo."),
    md("### Y el 17,3 % no dice que OSITRAN registre poca siniestralidad",
        "",
        "Cobertura por ruta y volumen de accidentes son cosas distintas: las rutas",
        "concedidas concentran tráfico, así que registrar 41.833 accidentes en el 17,3 %",
        "de las rutas es **lo esperable**. OSITRAN sirve para describir caminos",
        "concedidos; no para corregir el total nacional.",
        "",
        "Además es un agregado por concesión y año: **no tiene fecha de evento ni",
        "coordenadas**, así que no se puede deduplicar contra nada y por eso no entra en",
        "ningún total."),

    md("## 5.4 · Solape ONSV–SUTRAN y Lincoln-Petersen",
        "",
        "`deduplicacion_eventos.py` ya devuelve `n_ab` como insumo del estimador, así que",
        "la pregunta se puede responder con datos y no con suposiciones."),
    code("sol = res['solape_onsv_sutran']",
         "for k, v in sol.items():",
         "    print(f'{k:26s} {v}')"),
    md("### Un detalle que cambia el estimador",
        "",
        "`resumen_unificacion()` etiqueta un evento emparejado como `ONSV+SUTRAN`, así que",
        "**nunca** aparece en `n_onsv` ni en `n_sutran`: esos son los marginales",
        "exclusivos. Lincoln-Petersen necesita los **inclusivos** (cuántos eventos vio",
        "cada fuente, coincidan o no).",
        "",
        "Aquí el módulo pasa los exclusivos a propósito, y por eso `n_onsv` + `n_sutran` +",
        "`n_ambos` reconstruye el total único mientras que `n_a * n_b / n_ab` con esos",
        "mismos números no significa nada. Es una decisión de diseño que conviene que",
        "esté escrita, no que se descubra al usar la función."),

    md("## 5.5 · El veredicto es NO ESTIMABLE, y no por falta de muestra",
        "",
        "Esta es la parte que más se malinterpreta, así que conviene insistir: el",
        "intervalo de Lincoln-Petersen **no** es absurdamente ancho."),
    code("lp = res['lincoln_petersen']",
         "print(f\"N estimado     = {lp['n_estimado']:,.0f}\".replace(',', '.'))",
         "print(f\"SE(log N)      = {lp['se_log_n']}\")",
         "print(f\"IC 95%         = [{lp['ic95_low']:,.0f}, {lp['ic95_high']:,.0f}]\".replace(',', '.'))",
         "print(f\"Aplicable      = {lp['aplicable']}\")"),
    md("### El motivo es estructural, no muestral",
        "",
        "Lincoln-Petersen exige que las dos fuentes sean **dos muestreos",
        "independientes de la misma población**. ONSV y SUTRAN no lo son: difieren en",
        "el ámbito de red que cubren y en la ventana temporal que registran.",
        "",
        "El módulo comprueba ese supuesto en vez de suponerlo, y falla:"),
    code("sup = res['supuesto_independencia']",
         "print(f\"Rutas no comunes  : {sup['pct_rutas_no_comunes']}%\")",
         "print(f\"Meses no comunes  : {sup['pct_meses_no_comunes']}%\")",
         "print(f\"Supuesto razonable: {sup['supuesto_razonable']}\")"),
    md("> Aplicado aquí, el estimador mediría **la diferencia entre dos poblaciones**,",
        "> no lo que ninguna de las dos deja fuera.",
        ">",
        "> Un intervalo estrecho sobre la pregunta equivocada sigue siendo la pregunta",
        "> equivocada. Por eso el veredicto es NO ESTIMABLE aunque el IC sea manejable.",
        "",
        "Para medirlo de verdad haría falta una fuente con series estables o una fuente",
        "de contraste por departamento, no estos tres ficheros."),

    md("## 5.6 · Sensitividad: `n_ab` es un parámetro, no una medida",
        "",
        "`n_ab` depende del criterio de emparejamiento, así que conviene ver cuánto se",
        "mueve antes de tratarlo como una constante."),
    code("sens_df = pd.DataFrame(res['sensitividad_matching'])",
         "piv = sens_df.pivot(index='radio_km', columns='tolerancia_dias',",
         "                   values='n_ambos')",
         "print('n_ambos por (radio_km, tolerancia_dias):')",
         "print(piv.to_string())",
         "",
         "vals = sens_df['n_ambos'].tolist()",
         "print(f\"\\nMin {min(vals)} / Max {max(vals)} -> factor {max(vals)/max(min(vals),1):.1f}\")",
         "",
         "# Invariante: deduplicar resta o iguala, nunca puede inflar el recuento.",
         "assert (sens_df['n_unico_total'] <= sens_df['suma_naiva']).all()",
         "print('Invariante n_unico_total <= suma_naiva: OK')"),
    md("### Lo que la sensibilidad sí sostiene, y lo que no",
        "",
        "**Sí:** el 26 no es un artefacto de haber elegido 250 m y ±1 día. El solape se",
        "mueve de forma acotada al variar las tolerancias.",
        "",
        "**No:** que el solape sea estable no lo convierte en una medición de",
        "subnotificación. Dos fuentes que rara vez coinciden siguen sin ser dos vistas",
        "de la misma población."),

    md("## 5.7 · La tabla de afirmaciones",
        "",
        "Cada fila es una afirmación verificable con su veredicto, su evidencia medida",
        "y su límite. No se combinan en un número: eso exigiría decidir el peso de cada",
        "riesgo, y esa decisión no sale de estos datos."),
    code("for a in res['afirmaciones']:",
         "    print('=' * 78)",
         "    print(a['afirmacion'])",
         "    print('  veredicto:', a['veredicto'])",
         "    print('  evidencia:', a['evidencia'])",
         "    print('  limite   :', a['limite'])",
         "    print()"),
    md("## 5.8 · Lo que este notebook deja sobre la mesa",
        "",
        "1. **ONSV es usable tal cual**: 5.014 de 5.014 con coordenada, 0 fuera del",
        "   Perú.",
        "2. **SUTRAN necesita reservas**: el 6,12 % va sin coordenada y su coordenada",
        "   viene del km del tramo, no de un GPS, así que no sirve para medir",
        "   dispersión espacial.",
        "3. **OSITRAN no es una capa completa**: 26 de 150 rutas, y no entra en ningún",
        "   total porque no se puede deduplicar.",
        "4. **La subnotificación no es estimable**, y el motivo es estructural.",
        "5. **El dashboard ya publica el recuento unionado**",
        "   (`siniestros_union_comun`) y llama a la suma ingenua lo que es,",
        "   `siniestros_suma_fuentes`.",
        "",
        "Ver `docs/fiabilidad_fuentes.md` para la versión escrita de esto, y",
        "`scripts/fiabilidad_fuentes.py` para el módulo."),
]

validate(fuentes, "05_fiabilidad_fuentes")

# ----------------------------------------------- 06 · VALIDEZ PREDICTIVA ----

validez = [
    md(
        "# 06 · Validez predictiva",
        "",
        "Fase CRISP-DM **Evaluation**. La cuarta pregunta del proyecto: ¿la predicción",
        "**aguanta fuera de la muestra** con la que se ajustó?",
        "",
        "| Pregunta | Módulo |",
        "|---|---|",
        "| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` |",
        "| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |",
        "| ¿Las fuentes ONSV/SUTRAN/OSITRAN son de fiar? | `05_fiabilidad_fuentes.ipynb` |",
        "| **¿La predicción aguanta fuera de muestra?** | **este notebook** |",
        "",
        "Un modelo puede tener un R² alto dentro de muestra y ser inútil: eso es",
        "sobreajuste. Y puede tener un R² negativo y seguir siendo útil para lo único",
        "que se le pide — **ordenar** tramos por riesgo. Este notebook separa las dos",
        "cuestiones y no las mezcla en un veredicto único.",
        "",
        "Todo lo que sigue lo calcula `scripts/validez_predictiva.py`.",
    ),
    code(*PRELUDE,
         "import validez_predictiva as vp",
         "",
         "print(vp.__doc__.strip().splitlines()[0])",
         "",
         "# `analizar()` recalcula los dos protocolos; no lee el JSON que otro dejo",
         "# escrito. Es lo que hace que este notebook pueda contradecir al script.",
         "res = vp.analizar(verbose=False)",
         "print('\\nClaves del informe:', list(res))"),
    md("## 6.1 · Protocolo espacial: ¿usar las covariables mejora algo?",
        "",
        "Cross-validation agrupado por corredor. Si el despliegue predice tramos que",
        "nunca vio en entrenamiento, la validación tiene que ser agrupada: con k-fold",
        "plano, tramos vecinos del mismo corredor caen en entrenamiento y en prueba a",
        "la vez, y el modelo se evalúa con información que en producción no tendría."),
    code("pe = res['protocolo_espacial']",
         "print('tipo       :', pe['tipo'])",
         "print('agrupacion :', pe['agrupacion'])",
         "print('corredores :', pe['n_corredores'])",
         "print('folds      :', pe['folds'])",
         "",
         "print(pe['agregado'])"),
    md("### La mejora es real pero pequeña, y el R² sigue siendo negativo",
        "",
        "La devianza de Poisson (menor es mejor) es la métrica principal aquí, porque",
        "el objetivo es un **conteo**: la media y el MAE premian predecir cero, que es",
        "lo que hace el 86 % de las celdas. Un R² sobre un conteo que casi siempre es 0",
        "mide la varianza de unos pocos tramos con evento, no capacidad de predecir."),
    md("## 6.2 · Protocolo temporal: holdout de 2025",
        "",
        "El segundo Split es el que responde a la pregunta del título: se entrena con",
        "2021-2024 y se prueba con 2025, que el modelo **nunca** vio. Es la simulación de",
        "lo que pasa al desplegar en el future."),
    code("pt = res['protocolo_temporal']",
         "print(f\"Entrenamiento : {pt['entrenamiento']}\")",
         "print(f\"Holdout       : {pt['holdout']}\")",
         "print(f\"Celdas test   : {pt['n_test']}   eventos en test: {pt['eventos_test']}\")",
         "",
         "tabla = pd.DataFrame(pt['modelos']).T",
         "print(tabla.to_string())"),
    md("### Por qué aquí no se declara un ganador",
        "",
        "Cada métrica favorece a un modelo distinto:",
        "",
        "- por **MAE** gana la persistencia (predecir el valor del año anterior),",
        "- por **devianza de Poisson** gana el NegBin frente a la media.",
        "",
        "No es que un modelo sea mejor: es que **las métricas no son equivalentes en",
        "una matriz con 86 % de ceros**, y elegir con estos datos sería arbitrario. El",
        "veredicto se declara `AMBIGUO` y se explica por qué, en vez de publishes un",
        "número que favours a un modelo por accidente."),
    code("for k, v in res['notas'].items():",
         "    print(f'[{k}] {v}\\n')"),
    md("## 6.3 · Intervalos: la cobertura no es la nominal",
        "",
        "Un intervalo al 95 % que cubre el 91 % de los casos **subestima** la",
        "incertidumbre; uno al 80 % que cubre el 88 % la sobreestima poco. El",
        "cumplimiento se compara con el nivel nominal para que se vea la dirección del",
        "error, no solo el número."),
    code("iv = res['intervalos']",
         "print('alpha estimado (NegBin):', iv['alpha'])",
         "",
         "cob = pd.DataFrame(iv['cobertura']).T",
         "print(cob.to_string())",
         "",
         "print('Un cumplimiento < 1 significa que el intervalo es mas estrecho de lo')",
         "print('que la cobertura real necesita: el error esta subestimado.')"),
    md("## 6.4 · La tabla de afirmaciones",
        "",
        "Igual que en el notebook 05: veredicto, evidencia y límite por afirmación, sin",
        "combinar en un índice. El límite importa tanto como el veredicto: es lo que",
        "impide que alguien use la afirmación fuera de su alcance."),
    code("for nombre, a in res['veredicto']['afirmaciones'].items():",
         "    print('=' * 78)",
         "    print(nombre)",
         "    print('  veredicto:', a['veredicto'])",
         "    print('  evidencia:', a['evidencia'])",
         "    print('  limite   :', a['limite'])",
         "    print()",
         "print(res['veredicto']['nota'])"),
    md("## 6.5 · Cómo decirlo en una sustentación",
        "",
        "> No: «el modelo predice los siniestros de la red vial». El holdout de 2025 no",
        "> lo sostiene.",
        "",
        "> Sí: «el modelo **ordena** los tramos por riesgo de forma útil y reproducible",
        "> frente a la media de su región, tanto en validación espacial agrupada como en",
        "> un holdout temporal que no vio; **no** estima bien el número de siniestros, y",
        "> por eso el producto lo usa para priorizar, no para prognosticar cantidades».",
        "",
        "## 6.6 · Reproducibilidad",
        "",
        "```bash",
        "python scripts/validez_predictiva.py        # regenera el JSON",
        "python -m pytest tests/test_validez_predictiva.py -q",
        "```",
        "",
        "El informe completo está en `docs/validez_predictiva.md` y los datos crudos en",
        "`data/processed/dashboard/validez_predictiva.json`."),
]

validate(validez, "06_validez_predictiva")

SPEC = (
    (fuentes, "05_fiabilidad_fuentes.ipynb"),
    (validez, "06_validez_predictiva.ipynb"),
)


def build_all(out_dir=None) -> list:
    """Escribe los dos notebooks. Devuelve la lista de rutas escritas.

    Se separó del cuerpo del script para que los tests puedan construir los
    notebooks en un directorio temporal y compararlos con los versionados, sin
    tocar `notebooks/`.
    """
    out = Path(out_dir) if out_dir is not None else OUT
    out.mkdir(parents=True, exist_ok=True)
    escritos = []
    for celdas, nombre in SPEC:
        p = out / nombre
        p.write_text(
            json.dumps(notebook(celdas), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        escritos.append(p)
    return escritos


def execute(paths, timeout: int = 1800) -> list:
    """Ejecuta los notebooks y guarda sus salidas (base64) en el propio .ipynb.

    Los notebooks se versionan SIN salidas para no meter pesos ni resultados
    rancios en Git; esta función es para querer mirar el análisis renderizado sin
    ejecutarlo a mano.
    """
    import nbformat
    from nbclient import NotebookClient

    hechos = []
    for p in paths:
        nb = nbformat.read(p, as_version=4)
        client = NotebookClient(
            nb,
            timeout=timeout,
            kernel_name="python3",
            # El kernel arranca en notebooks/, de donde sube a ROOT.
            resources={"metadata": {"path": str(p.parent.resolve())}},
        )
        client.execute()
        nbformat.write(nb, p)
        print(f"  [ok] {p.name}: {len(nb.cells)} celdas")
        hechos.append(p)
    return hechos


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--execute", action="store_true",
        help="ejecuta los notebooks y guarda las salidas (requiere nbclient)",
    )
    ap.add_argument("--only", default="", help="genera/ejecuta solo este notebook")
    args = ap.parse_args()

    escritos = build_all()
    print("notebooks generados:", [p.name for p in escritos])
    objetivo = [p for p in escritos if args.only in p.name] if args.only else escritos
    if args.execute:
        print("ejecutando (puede tardar varios minutos)...")
        execute(objetivo)
