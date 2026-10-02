# Validez predictiva: ¿aguanta el modelo fuera de muestra?

Módulo: `scripts/validez_predictiva.py` · Salida: `data/processed/dashboard/validez_predictiva.json`

## Qué pregunta y qué NO pregunta

Este módulo responde a **una** pregunta: *¿la predicción aguanta fuera de muestra?*

No es lo mismo que las otras tres del proyecto, y no las sustituye:

| Pregunta | Dónde se responde |
|---|---|
| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` (DQS) |
| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |
| ¿ONSV/SUTRAN/OSITRAN son de fiar? | `scripts/fiabilidad_fuentes.py` |
| **¿La predicción aguanta fuera de muestra?** | **este módulo** |

Un R² malo aquí no dice que los datos sean malos: dice que el modelo no
pronostica. Son afirmaciones distintas, con consecuencias distintas.

## Cómo se mide

Se reconstruye el panel tramo × año con `panel_anual.construir_panel`, la misma
función que alimenta `dataset_modelo.csv`. Si la validación usara otra
asignación de eventos, mediría un dataset que nadie consume.

**18.750 celdas** (3.750 tramos × 5 años), **86,4% en cero**, **141 corredores**
a partir de 150 rutas.

### Protocolo espacial — "¿sirve en una carretera nueva?"

`GroupKFold` de 5 folds **agrupado por corredor, no por tramo**. `PE-1N` y `PE-1S`
son la misma Panamericana en sentidos opuestos: comparten tramo físico, curvatura
y tráfico. Si quedaran en folds distintos, el test sería una copia del train y
cualquier R² alto mediría memoria, no capacidad de extrapolar.

| Modelo | MAE | RMSE | R² | Dev. Poisson |
|---|---|---|---|---|
| media de entrenamiento | 0,464 | 0,951 | −0,009 | 1,252 |
| mediana de entrenamiento | 0,267 | 0,984 | −0,079 | *n/d* |
| **NegBin con offset** | **0,370** | **0,898** | **+0,102** | **0,824** |

*La mediana predice 0, y la devianza de Poisson no está definida en `mu = 0`.
Recortarla daría un número enorme y sin significado, así que se reporta `n/d`.

**El modelo bate a la media** (0,824 contra 1,252), pero la mejora es pequeña.

### Protocolo temporal — "¿sirve mañana?"

Entrena 2021–2024, predice 2025 (3.750 celdas, 383 siniestros).

| Modelo | MAE | RMSE | R² | Dev. Poisson |
|---|---|---|---|---|
| media | 0,371 | 0,601 | −0,133 | 0,804 |
| mediana | 0,102 | 0,574 | −0,033 | *n/d* |
| NegBin con offset | 0,362 | 0,891 | −1,490 | 0,728 |
| persistencia (año anterior) | 0,212 | 0,776 | −0,888 | *n/d* |

## Cómo se leen las cifras

**La devianza de Poisson no se compara contra 1.** El 1 es una guía suelta y con
λ bajo se aparta bastante: para Poisson(0,3) el valor esperado ronda 0,83. La
referencia exacta es la devianza de la propia baseline `media`, y lo que importa
es si el modelo la baja.

**El R² engaña con 86% de ceros.** Depende de la varianza de unos pocos tramos
con eventos. Sirve para ordenar, no para predecir cantidades.

**MAE y devianza de Poisson pueden discordar.** El MAE premia predecir cero, que
es lo correcto en la mayoría de las celdas. Por eso la persistencia "gana" por
MAE (0,212) pero se queda sin devianza definida, mientras el NegBin gana por
devianza (0,728 contra 0,804 de la media). Cuando las métricas no coinciden el
veredicto sale **AMBIGUO**: no se fuerza un ganador.

## El límite que no se puede sortear

ONSV registra **−67% de siniestros en 2025** frente al promedio 2021–2024, con
los 12 meses cubiertos y una tasa de mortalidad casi constante (1,24 → 1,21
fallecidos por siniestro).

Un descenso del volumen acompañado de una tasa de mortalidad constante no es un
patrón de mejora de la seguridad vial: si bajaran los accidentes graves, la tasa
de mortalidad subiría ligeramente. Lo más consistente es un cambio en la captura
de la fuente.

**Consecuencia:** el error del holdout temporal mezcla error del modelo y cambio
de la fuente, y **estos datos no permiten separarlos**. Por eso el veredicto
"El holdout temporal mide capacidad de predecir a futuro" es **NO**. Medirlo
bien requiere una serie de ONSV estable o una fuente de contraste por
departamento.

## Cobertura de intervalos

Ajustados sobre todo el panel (para calibrar, no para medir capacidad):

| Nominal | Observada | Cumplimiento |
|---|---|---|
| 80% | 88,4% | 111% |
| 95% | 91,0% | 96% |

Los intervalos NB2 con `alpha` de cuasi-verosimilitud no se comportan bien: se
ensanchan de más al 80% y se quedan cortos al 95%. No son publicables como
intervalos de decisión sin recalibrarlos.

## Veredictos

| Afirmación | Veredicto |
|---|---|
| El modelo usa las covariables para predecir mejor que la media | **SÍ** |
| El R² justifica usarlo como pronóstico | **NO** |
| El modelo supera a la persistencia en el holdout | **AMBIGUO** |
| El holdout temporal mide capacidad de predecir a futuro | **NO** |

**Conclusión operativa:** el modelo sirve para **priorizar** tramos (ordena mejor
que la media) y **no** para **prevenir cuántos siniestros** ocurrirán. El
dashboard debe decirlo así en lugar de mostrar un número como si fuera un
pronóstico.

No se colapsa estos veredictos en un índice único: combinarlos exigiría decidir
cuánto pesa cada riesgo, y esa decisión no sale de estos datos.

## Reproducir

```bash
python scripts/validez_predictiva.py
python -m pytest tests/test_validez_predictiva.py -q
```

Requiere `scikit-learn` (ver `requirements.txt` de la raíz).