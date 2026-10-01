# -*- coding: utf-8 -*-
"""Añade celdas de visualización (matplotlib) a los 3 notebooks.

Antes de este cambio los notebooks eran 100 % prints/describe: cero figuras.
Estas celdas embebidas hacen visible lo que los números dicen.

    python scripts/add_viz_cells.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

# estilo común que se antepone a las celdas de gráficos
#
# IMPORTANTE: en un notebook NO se debe hacer matplotlib.use('Agg'). El backend
# Agg suprime el render inline y `plt.show()` se convierte en un no-op: las
# celdas se ejecutan "sin error" pero no muestran ninguna figura. Agg solo es
# necesario en scripts (scripts/graficos_etl.py, donde ya lo pone figures.py).
STYLE = [
    "import matplotlib.pyplot as plt",
    "import seaborn as sns",
    "",
    "sns.set_theme(style='whitegrid', context='notebook')",
    "plt.rcParams.update({'figure.dpi': 110, 'savefig.dpi': 110, 'savefig.bbox': 'tight'})",
    "PALETTE = ['#4f46e5', '#059669', '#d97706', '#dc2626', '#0891b2']",
    "",
    "# Mostrar en línea y capturar cualquier figura como imagen embebida.",
    "from IPython.display import Image as _IPImage, display",
    "import base64 as _b64",
    "from pathlib import Path as _Path",
    "",
    "def _show(png_path):",
    "    \"\"\"Muestra un PNG en línea dentro del notebook.\"\"\"",
    "    p = _Path(png_path)",
    "    if not p.exists():",
    "        print('Falta', p, '- ejecuta python scripts/graficos_etl.py')",
    "        return",
    "    display(_IPImage(data=_b64.b64decode(_b64.b64encode(p.read_bytes()))))",
]


def md(*lines: str) -> dict:
    return {"cell_type": "markdown", "id": f"viz-{next(_ids):03d}", "metadata": {},
            "source": [l + "\n" for l in lines][:-1] + [lines[-1]]}


def code(*lines: str) -> dict:
    return {"cell_type": "code", "id": f"viz-{next(_ids):03d}", "execution_count": None,
            "metadata": {}, "outputs": [],
            "source": [l + "\n" for l in lines][:-1] + [lines[-1]]}


from itertools import count
_ids = count(1)


def validate(cells: list, name: str) -> None:
    for i, c in enumerate(cells):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        try:
            compile(src, f"{name}::cell{i}", "exec")
        except SyntaxError as exc:
            raise SystemExit(f"{name}: celda {i} con error de sintaxis: {exc.msg} "
                             f"(linea {exc.lineno})\n  {exc.text!r}")


# ---------------------------------------------------------------- ONSV ----
onsv_viz = [
    md("## 1.14 · Visualización: distribución de las variables",
       "",
       "Los números de las secciones anteriores en imagen. Aquí se ve la **firma de la",
       "censurea de ONSV**: un pico en la última edad de `fallecidos`",
       "(hasta 33 muertos en un mismo siniestro), que es donde se concentra el riesgo.",
       "El DQS **no** detectaría ese valor: es un dato formalmente válido (positivo,",
       "en rango según el contrato) ymuy extremo. Por eso los outliers se **reportan** y no",
       "se borran: son información real sobre la cola de la distribución."),
    code(*STYLE,
         "# En este notebook el dataframe disponible es el CRUDO (`raw`), y varias",
         "# columnas llegan como `object` (tipos mezclados en el XLSX).",
         "num = [c for c in ['CANTIDAD DE FALLECIDOS', 'CANTIDAD DE LESIONADOS',",
         "                   'CANTIDAD DE VEHICULOS DAÑADOS', 'COORDENADAS LATITUD',",
         "                   'COORDENADAS  LONGITUD'] if c in raw.columns]",
         "num_df = raw[num].apply(pd.to_numeric, errors='coerce')",
         "print('Variables numéricas del crudo:', list(num_df.columns))",
         "print('Dtypes tras coerción:', num_df.dtypes.to_dict())",
         "axes = num_df.hist(bins=30, figsize=(14, 7), color=PALETTE[0], edgecolor='white')",
         "plt.tight_layout()",
         "plt.show()"),
    code("skew = num_df.skew().round(2).sort_values(ascending=False)",
         "print('Asimetría (skewness) por variable:')",
         "print(skew.to_string())",
         "print('\\nInterpretación: |skew| > 1.5 = cola larga; > 3 = la media es poco representativa.')",
         "plt.figure(figsize=(8, 4))",
         "ax_sk = plt.gca()",
         "ax_sk.barh(range(len(skew)), skew.values, color=PALETTE[0])",
         "ax_sk.set_yticks(range(len(skew)))",
         "ax_sk.set_yticklabels(skew.index, fontsize=9)",
         "ax_sk.invert_yaxis()",
         "plt.axvline(0, color='black', lw=1)",
         "plt.axvline(1.5, color='#dc2626', ls='--', lw=1, label='umbral 1.5')",
         "plt.axvline(-1.5, color='#dc2626', ls='--', lw=1)",
         "plt.title('Asimetría de las variables numéricas')",
         "plt.xlabel('skewness')",
         "plt.legend()",
         "plt.tight_layout()",
         "plt.show()"),
    code("f = pd.to_numeric(raw['CANTIDAD DE FALLECIDOS'], errors='coerce').dropna()",
         "q1, q3 = f.quantile([0.25, 0.75])",
         "iqr = q3 - q1",
         "print(f'Descriptor:\\n{f.describe().round(2).to_string()}')",
         "print(f'\\nIQR = {iqr:.1f} | umbral superior = {q3 + 1.5*iqr:.1f} fatalities')",
         "n_out = int((f > q3 + 1.5*iqr).sum())",
         "print(f'Outliers por IQR: {n_out} ({n_out/len(f)*100:.2f}%)')",
         "fig, ax = plt.subplots(1, 2, figsize=(13, 4))",
         "ax[0].hist(f, bins=25, color=PALETTE[0], edgecolor='white')",
         "ax[0].axvline(q3 + 1.5*iqr, color='#dc2626', ls='--', label='umbral IQR')",
         "ax[0].set_title('Distribución de fallecidos por siniestro')",
         "ax[0].set_xlabel('fallecidos')",
         "ax[0].legend()",
         "sns.boxplot(x=f, ax=ax[1], color=PALETTE[0])",
         "ax[1].set_title('Boxplot: la cola derecha concentra el riesgo')",
         "plt.tight_layout()",
         "plt.show()"),
    md("## 1.15 · Correlación variables-objetivo",
       "",
       "Qué variables se mueven con `fallecidos`. Solo numéricas: las categóricas",
       "requieren codificación y se tratan aparte con boxplots."),
    code("vars_num = [c for c in ['CANTIDAD DE FALLECIDOS', 'CANTIDAD DE LESIONADOS',",
         "                          'CANTIDAD DE VEHICULOS DAÑADOS', 'COORDENADAS LATITUD',",
         "                          'COORDENADAS  LONGITUD'] if c in raw.columns]",
         "_num = raw[vars_num].apply(pd.to_numeric, errors='coerce')",
         "corr = (_num.corr(numeric_only=True)['CANTIDAD DE FALLECIDOS']",
         "        .drop('CANTIDAD DE FALLECIDOS').sort_values(key=abs, ascending=False))",
         "print('Correlación de Pearson con fatalities:')",
         "print(corr.round(3).to_string())",
         "print('\\nInterpretación: |r| < 0.2 = relación débil. Buscar alta correlación aquí sería una '",
         "      'trampa: fatalities depende sobre todo del TIPO de siniestro, no de la geografía.')",
         "plt.figure(figsize=(8, 4.5))",
         "sns.barplot(x=corr.values, y=corr.index, palette='coolwarm')",
         "plt.axvline(0, color='black', lw=1)",
         "plt.title('Correlación con fatalities (Pearson)')",
         "plt.tight_layout()",
         "plt.show()"),
    code("print('Fallecidos medios por clase de siniestro:')",
         "_f = pd.to_numeric(raw['CANTIDAD DE FALLECIDOS'], errors='coerce').fillna(0)",
         "g = (raw.assign(_f=_f)",
         "     .groupby('CLASE SINIESTRO', dropna=False)['_f']",
         "     .agg(['count', 'mean', 'sum'])",
         "     .sort_values('mean', ascending=False))",
         "g['media_fallecidos'] = g['mean'].round(2)",
         "print(g[['count', 'media_fallecidos', 'sum']].head(12).to_string())",
         "top = g.head(12)",
         "plt.figure(figsize=(9, 4.5))",
         "ax_cls = plt.gca()",
         "ax_cls.barh(range(len(top)), top['media_fallecidos'].values, color=PALETTE[2])",
         "ax_cls.set_yticks(range(len(top)))",
         "ax_cls.set_yticklabels(top.index, fontsize=9)",
         "ax_cls.invert_yaxis()",
         "plt.axvline(_f.mean(), color='#dc2626', ls='--',",
         "            label=f'media global = {_f.mean():.2f}')",
         "plt.xlabel('fallecidos medios por siniestro')",
         "plt.title('Fallecidos medios por clase: aquí SÍ está la señal')",
         "plt.legend()",
         "plt.tight_layout()",
         "plt.show()"),
]

# ------------------------------------------------------- CINEMOMETROS ----
cine_viz = [
    md("## 2.10 · Visualización: exceso de velocidad",
       "",
       "La magnitud accionable del dataset. El histograma muestra una masa junto al",
       "límite y una cola larga: la cola es donde está el riesgo vial.",
       "De nuevo: los outliers **no se borran**; se reportan y se estudian como señal."),
    code(*STYLE,
         "exceso = (v - lim).clip(lower=0)",
         "print('Exceso sobre el límite (km/h):')",
         "print(exceso.describe().round(2).to_string())",
         "fig, ax = plt.subplots(1, 2, figsize=(14, 4.5))",
         "ax[0].hist(exceso, bins=40, color=PALETTE[0], edgecolor='white')",
         "ax[0].axvline(lim.median(), color='#dc2626', ls='--', label='límite mediano')",
         "ax[0].set_title('Distribución del exceso de velocidad')",
         "ax[0].set_xlabel('km/h por encima del límite')",
         "ax[0].legend()",
         "sns.boxplot(x=exceso, ax=ax[1], color=PALETTE[0])",
         "ax[1].set_title('Boxplot: cola derecha = exceso grave')",
         "plt.tight_layout()",
         "plt.show()"),
    code("q1, q3 = exceso.quantile([0.25, 0.75])",
         "iqr = q3 - q1",
         "umbral = q3 + 1.5 * iqr",
         "print(f'IQR = {iqr:.1f} | umbral superior = {umbral:.1f} km/h')",
         "print(f'Outliers: {int((exceso > umbral).sum()):,} ({(exceso > umbral).mean()*100:.2f}%)')",
         "plt.figure(figsize=(9, 4.5))",
         "sns.histplot(exceso, bins=40, kde=True, color=PALETTE[0], stat='density')",
         "plt.axvline(umbral, color='#dc2626', ls='--', label=f'umbral IQR = {umbral:.1f}')",
         "plt.title('Exceso de velocidad con umbral IQR')",
         "plt.legend()",
         "plt.tight_layout()",
         "plt.show()"),
    md("## 2.11 · Velocidad por carretera y por región",
       "",
       "No todos los puntos de control son iguales: si una carretera concentra exceso,",
       "ahí hay más riesgo de accidente. Esta es la lectura que justifica el módulo de",
       "\"ruta segura\" del SIPAT."),
    code("por_carretera = (cine.assign(_e=exceso.reset_index(drop=True))",
         "                   .groupby('CARRETERA', dropna=False)['_e']",
         "                   .agg(['count', 'mean']).sort_values('mean', ascending=False))",
         "por_carretera['exceso_medio'] = por_carretera['mean'].round(2)",
         "top = por_carretera.head(10)",
         "print('Exceso medio por carretera (top 10):')",
         "print(top[['count', 'exceso_medio']].to_string())",
         "plt.figure(figsize=(9, 4.5))",
         "sns.barplot(data=top.reset_index(), x='CARRETERA', y='exceso_medio', color=PALETTE[2])",
         "plt.xticks(rotation=35, ha='right')",
         "plt.axhline(exceso.mean(), color='#dc2626', ls='--', label=f'media global = {exceso.mean():.2f}')",
         "plt.ylabel('exceso medio (km/h)')",
         "plt.title('Exceso medio por carretera')",
         "plt.legend()",
         "plt.tight_layout()",
         "plt.show()"),
    code("por_region = (cine.assign(_e=exceso.reset_index(drop=True))",
         "                  .groupby('REGION', dropna=False)['_e']",
         "                  .agg(['count', 'mean']).sort_values('mean', ascending=False))",
         "por_region['exceso_medio'] = por_region['mean'].round(2)",
         "top = por_region.head(12)",
         "plt.figure(figsize=(9, 4.5))",
         "sns.barplot(data=top.reset_index(), x='REGION', y='exceso_medio', color=PALETTE[0])",
         "plt.xticks(rotation=35, ha='right')",
         "plt.axhline(exceso.mean(), color='#dc2626', ls='--', label='media global')",
         "plt.ylabel('exceso medio (km/h)')",
         "plt.title('Exceso medio por región (los nombres ya vienen normalizados por el ETL)')",
         "plt.legend()",
         "plt.tight_layout()",
         "plt.show()"),
]

# ------------------------------------------------- SILVER / DQS / GATE ----
silver_viz = [
    md("## 3.10 · Visualización: el DQS y sus dimensiones",
       "",
       "Las seis dimensiones del DQS con su peso. Un radar deja ver de un vistazo que",
       "**frescura** es la única dimensión baja, y eso NO es un defecto: los datos son",
       "históricos (siniestros 2021-2025).",
       "El contraste con la dimensión **validez** es el que importa: si miraras solo el",
       "número agregado (92.07) no sabrías que la validez es 100 y la frescura 12."),
    code(*STYLE,
         "WEIGHTS = SETTINGS['quality']['weights']",
         "dims = [k for k in dqs if k in WEIGHTS]",
         "vals = [dqs[k] for k in dims]",
         "pesos = [WEIGHTS[k] for k in dims]",
         "import math",
         "ang = [n / len(dims) * 2 * math.pi for n in range(len(dims))]",
         "ang += ang[:1]",
         "fig = plt.figure(figsize=(7.5, 6.5))",
         "ax = plt.subplot(111, polar=True)",
         "ax.plot(ang, vals + vals[:1], color=PALETTE[0], lw=2, label='valor')",
         "ax.fill(ang, vals + vals[:1], color=PALETTE[0], alpha=0.18)",
         "ax.plot(ang, [v * 100 for v in pesos] + [pesos[0] * 100], color=PALETTE[2],",
         "        lw=1.6, ls='--', label='peso x100 (referencia)')",
         "ax.set_xticks(ang[:-1])",
         "ax.set_xticklabels([d[:11] for d in dims], fontsize=9)",
         "ax.set_ylim(0, 100)",
         "ax.set_title(f'DQS {dqs[\"dqs\"]:.2f} por dimensión', pad=20)",
         "ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.12), fontsize=8)",
         "plt.tight_layout()",
         "plt.show()"),
    code("print('Desglose ponderado:')",
         "for k in WEIGHTS:",
         "    print(f'  {k:14} {dqs[k]:7.2f}  peso {WEIGHTS[k]:.2f}  aporta {dqs[k]*WEIGHTS[k]:6.2f}')",
         "print(f'  {\"DQS\":14} {dqs[\"dqs\"]:7.2f}')",
         "plt.figure(figsize=(8, 4))",
         "# OJO: dqs tiene más claves que pesos (dqs, n_rows, weights...). Hay que",
         "# alinear por las claves de WEIGHTS, no pasar dqs.values() tal cual.",
         "ks = list(WEIGHTS)",
         "vals_ = [dqs[k] for k in ks]",
         "bars = plt.bar(ks, vals_, color=PALETTE[0])",
         "for b, k, a in zip(bars, ks, [dqs[k] * WEIGHTS[k] for k in ks]):",
         "    b.set_color(PALETTE[2] if dqs[k] < 50 else PALETTE[0])",
         "    plt.text(b.get_x() + b.get_width()/2, dqs[k] + 2, f\"+{a:.1f}\",",
         "             ha='center', fontsize=9)",
         "plt.axhline(dqs['dqs'], color='#dc2626', ls='--', label=f\"DQS = {dqs['dqs']:.2f}\")",
         "plt.ylabel('puntaje 0-100')",
         "plt.xticks(rotation=25, ha='right')",
         "plt.title('Dimensiones del DQS (naranja = por debajo de 50)')",
         "plt.legend()",
         "plt.tight_layout()",
         "plt.show()"),
    md("## 3.11 · Las figuras de confiabilidad",
       "",
       "Estas son las mismas figuras que genera `scripts/graficos_etl.py` y que se",
       "publican en `docs/figuras/etl/`. Se generan aquí para que el notebook sea",
       "autosuficiente."),
    code("from src.quality import figures as GF",
         "figs = GF.figures_dir()",
         "print('Figuras disponibles en', figs)",
         "for p in sorted(figs.glob('onsv_*.png')):",
         "    print('  ', p.name, f'({p.stat().st_size//1024} KB)')"),
    code("_show(figs / 'onsv_sensibilidad_pesos.png')"),
    code("import json as _json",
         "# Cargar la evaluación de confiabilidad guardada (no se recalcula aquí).",
         "_files = sorted((ROOT / 'reports' / 'auditoria').glob('onsv_auditoria_*.json'), reverse=True)",
         "if _files:",
         "    _rel = _json.loads(_files[0].read_text(encoding='utf-8'))",
         "    boot = _rel['detalle']['bootstrap']",
         "else:",
         "    boot = {}",
         "    print('Ejecuta: python scripts/graficos_etl.py')",
         "",
         "recompute = {k: v for k, v in boot.items() if isinstance(v, dict) and 'punto' in v}",
         "print('Intervalos de confianza del DQS (bootstrap):')",
         "for k, v in recompute.items():",
         "    print(f\"  {k:14} {v['punto']:7.2f}  IC [{v['ic_inf']:.2f}, {v['ic_sup']:.2f}]\"",
         "          f\"  amplitud {v['amplitud']:.2f}\")",
         "print('\\nUn IC estrecho significa que el DQS es un estimador muy estable:',",
         "      ' el mismo input daría el mismo número con otra muestra.')",
         "if recompute:",
         "    fig, ax = plt.subplots(figsize=(7.5, 4))",
         "    ks = list(recompute)",
         "    for i, k in enumerate(ks):",
         "        v = recompute[k]",
         "        ax.plot([v['ic_inf'], v['ic_sup']], [i, i], lw=4, color=PALETTE[0], solid_capstyle='round')",
         "        ax.plot(v['punto'], i, 'o', ms=7, color='#dc2626', zorder=3)",
         "    ax.set_yticks(range(len(ks)))",
         "    ax.set_yticklabels(ks, fontsize=9)",
         "    ax.set_xlim(0, 100)",
         "    ax.invert_yaxis()",
         "    ax.set_xlabel('Puntaje 0-100')",
         "    ax.set_title('DQS por dimensión con intervalo de confianza')",
         "    plt.tight_layout()",
         "    plt.show()"),
    md("## 3.12 · Nulos antes y después: la prueba visual de la limpieza",
       "",
       "Lo que la limpieza resolvió y lo que **no** pudo resolver. Las columnas que",
       "siguen casi vacías no las arregla ningún `fillna`: sencillamente la fuente de",
       "datos no las trae."),
    code("import json",
         "pb = json.loads((ROOT / 'reports' / 'profiling' / 'onsv_before_profile.json').read_text(encoding='utf-8'))",
         "pa = json.loads((ROOT / 'reports' / 'profiling' / 'onsv_after_profile.json').read_text(encoding='utf-8'))",
         "fig = GF.plot_nulls_before_after(pb, pa, 'onsv', GF.figures_dir())",
         "if fig:",
         "    _show(fig)",
         "else:",
         "    print('Sin perfiles: ejecuta el pipeline.')"),
    md("## 3.13 · Sensibilidad a los pesos: ¿de quién es el 92.07?",
       "",
       "La pregunta más incómoda que se puede hacer a un indicador ponderado: *el peso",
       "0.22 de completitud lo elegiste tú, así que el 92.07 también es tuyo*.",
       "Este gráfico es la respuesta: se recalcula el DQS con 300 combinaciones de pesos",
       "y con cuatro escenarios declarados en la configuración."),
    code("_ws_sens = None",
         "import json as _json2",
         "_files2 = sorted((ROOT / 'reports' / 'auditoria').glob('onsv_auditoria_*.json'), reverse=True)",
         "if _files2:",
         "    _rel2 = _json2.loads(_files2[0].read_text(encoding='utf-8'))",
         "    _ws_sens = dict(_rel2['detalle']['weight_sensitivity'])",
         "    _ws_sens['distribucion_valores'] = _rel2['detalle'].get('weight_sensitivity_distribucion', [])",
         "    p = GF.plot_weight_sensitivity(_ws_sens, GF.figures_dir(), 'onsv')",
         "    if p:",
         "        _show(p)",
         "    print('\\nEscenarios de pesos alternativos:')",
         "    for e in _ws_sens.get('scenarios', []):",
         "        print(f\"  {e['name']:22} {e['dqs']:6.2f}   (delta {e['delta_vs_config']:+.2f})  {e['note']}\")",
         "else:",
         "    print('Ejecuta: python scripts/graficos_etl.py')"),
]

JOBS = {
    "01_exploracion_onsv.ipynb": onsv_viz,
    "02_exploracion_cinemometros.ipynb": cine_viz,
    "03_silver_dqs_gate.ipynb": silver_viz,
}

for nombre, celdas in JOBS.items():
    path = NB / nombre
    nb = json.loads(path.read_text(encoding="utf-8"))
    # Inserta antes de la celda de conclusiones si existe, si no al final.
    idx = len(nb["cells"])
    for i, c in enumerate(nb["cells"]):
        src = "".join(c.get("source", []))
        if c.get("cell_type") == "markdown" and src.startswith("## ") and (
            "Conclusiones" in src or "conclusiones" in src
        ):
            idx = i
            break
    validate(celdas, nombre)
    nb["cells"][idx:idx] = celdas
    path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{nombre}: +{len(celdas)} celdas de visualización (insertadas en {idx})")
