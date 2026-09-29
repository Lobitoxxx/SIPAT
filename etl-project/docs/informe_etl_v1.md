# Informe técnico — SIPAT-ETL v1.0

**Sistema profesional de ETL, calidad y preparación de datos**
sobre accidentes de la Red Vial Nacional del Perú (ONSV + SUTRAN)

- **Metodología**: CRISP-DM + KDD (modelado de conocimiento) · Kanban (gestión)
- **Fecha**: 29/09/2026
- **Versión**: 1.0.0 (`VERSION`, `pyproject.toml`, `config/settings.yaml`)
- **Estado**: pipeline ejecutado sobre datos reales, 87/87 tests verdes, `verify_etl` 4/4

---

## 1. Resumen ejecutivo

Se construyó un sistema ETL de 15 etapas por dataset sobre **dos fuentes reales**:

| Dataset | Fuente | Formato | Volumen crudo |
|---|---|---|---|
| `onsv` | Siniestros fatales y lesionados, ONSV | XLSX (preámbulo de 4 filas) | 9,106 × 27 |
| `cinemometros` | Papeletas de cinemómetros, SUTRAN | CSV | 160,018 × 11 |

Resultado de la última corrida (`run-20260929-134816-7969fdc2`):

| Dataset | Bronze | Silver | DQS | Gate | Reglas críticas | Cuarentena |
|---|---|---|---|---|---|---|
| `onsv` | 9,106 × 27 | 9,106 × 33 | **92.07** | PASSED | 0 | 0 registros |
| `cinemometros` | 160,018 × 11 | 160,018 × 13 | **92.00** | PASSED | 0 | 0 registros |

Ambos datasets superan el umbral de calidad (`min_quality_score: 90`) y se publican
en las tres capas Medallion (Bronze, Silver, Gold) incluido `model_ready`.

**El hallazgo más relevante del proyecto no fue un dato sucio, sino un defecto del propio
sistema de medición**: la dimensión de *validez* puntuaba las coordenadas de Perú como 0 %
porque aplicaba un umbral `>= 0` a columnas que, por la geografía del país, son negativas.
El DQS de ONSV era 94.97 antes de la corrección y 92.07 después: **el indicador era más alto
porque estaba mal calculado, no porque los datos fueran mejores**. Todos los tests con
fixtures sintéticas pasaban porque usaban coordenadas positivas. Por eso se añadió
`tests/unit/test_regressions.py` (28 tests) que fija cada defecto encontrado sobre datos reales.

---

## 2. Metodología aplicada

### 2.1 CRISP-DM

| Fase CRISP-DM | Mapeo en SIPAT-ETL | Artefactos |
|---|---|---|
| **Business Understanding** | Definir el objetivo: obtener datos aptos para la analítica de siniestralidad | `README.md`, este informe |
| **Data Understanding** | Perfilado antes/después, detección de tipos mixtos, preámbulo, duplicados | `src/profiling/profile.py`, `reports/profiling/*.html` |
| **Data Preparation** | Limpieza configurada, cuarentena, features de dominio | `src/cleaning/clean.py`, `src/transform/features.py` |
| **Modeling** | Preparación sin fugas + esqueleto MLflow | `src/ml/placeholder.py` |
| **Evaluation** | DQS ponderado, quality gates, MODEL_READY | `src/quality/*` |
| **Deployment** | Dashboard de observabilidad + reportes HTML | `etl-ui/app.py`, `reports/quality/*.html` |

Enfoque **KDD**: los catálogos de dominio (`config/quality/catalogs/`) funcionan como base de
conocimiento; las reglas (`quality_rules.yaml`) son el motor de inferencia que las consulta.
Cada nuevo hallazgo real se convierte en una entrada de catálogo o una regla, no en un `if` en el código.

### 2.2 Kanban

El pipeline es un tablero implícito: un dataset solo avanza de columna cuando la columna
anterior está en verde. Las columnas son las 15 etapas; las tarjetas son los datasets.
Un movimiento a "hecho" para Silver/Gold exige gate PASSED.

---

## 3. Arquitectura

### 3.1 Capas Medallion

| Capa | Contrato | Mutabilidad | Contenido |
|---|---|---|---|
| **Bronze** | dato tal cual llega + metadatos | **inmutable** | copia de la fuente + `source_md5`, `run_id`, filas, columnas |
| **Silver** | `config/contracts/*.yaml` | regenerable | nombres canónicos, tipos correctos, dedupe, imputación, features |
| **Gold** | propósito concreto | derivado | `analytics`, `model_ready` (gated), agregaciones JSON |

### 3.2 Las 15 etapas

```
start → extract → register_raw → profiling_before → clean → schema_validation
→ transform → data_quality → quarantine → quality_gate → load_silver
→ build_gold → profiling_after → generate_report → finish
```

El contrato se valida **después** de `clean` (etapa 6), no antes: el fichero crudo usa nombres
con acentos, espacios dobles y `¿?` (`'COORDENADAS  LONGITUD'`, `'¿EXISTE SEÑAL VERTICAL?'`),
así que validar el contrato sobre el crudo produciría 20+ falsos errores.

### 3.3 Orquestación

`scripts/run_pipeline.py --engine {auto|prefect|sequential}`.
En `auto` se usa Prefect 3 (un task por dataset, con reintentos y traza en la UI) y se
degrada a ejecución secuencial si Prefect no está instalado o su backend no arranca.
Ambas rutas llaman a la **misma** `run_pipeline()`: Prefect añade observabilidad, no cambia el resultado.

---

## 4. Data Quality

### 4.1 DQS ponderado

```
DQS = 0.22·completitud + 0.22·validez + 0.15·unicidad
    + 0.15·consistencia + 0.18·integridad + 0.08·frescura
```

**El DQS no es una probabilidad de que los datos sean verdaderos.** Es un indicador interno,
comparable entre corridas del mismo pipeline, útil para decidir si un dataset es publicable.

Desglose real de la última corrida:

| Dimensión | ONSV | Cinemómetros | Qué mide |
|---|---|---|---|
| Completitud | 100.00 | 100.00 | nulos en columnas obligatorias |
| Validez | 100.00 | 100.00 | rangos del contrato + catálogos de dominio |
| Unicidad | 100.00 | 100.00 | duplicados en la clave primaria |
| Consistencia | 100.00 | 100.00 | normalización de caja en categóricas |
| Integridad | 100.00 | 100.00 | claves foráneas (sin FK en v1) |
| Frescura | 12.06 | 12.06 | días desde la fecha más reciente vs. ventana de 365 días |

La frescura es baja **por diseño y es correcto que lo sea**: los datos son históricos
(siniestros 2021-2025, cinemómetros 2019-2021) y no se actualizan. Un dataset deONDSV de
2021 no debeconsidered "fresco" hoy. Por eso pesa 0.08 y no más: no es un defecto del dato,
es un atributo de la fuente.

### 4.2 Quality gates

`config/quality/quality_rules.yaml` define reglas de severidad `critical` y `warning`:

- **Críticas** (PK no nulo/único, fecha parseable, fecha no futura, coordenadas de Perú,
  contadores no negativos, catálogos, formato de hora) → cualquier violación = `FAILED` +
  escritura en `data/quarantine/`.
- **Warnings** → el gate pasa a `WARNING` y el dataset se publica, pero queda registrado.
- El gate es `FAILED` si el DQS < `min_quality_score` (90) o hay críticos.
- `model_ready` exige gate `PASSED` + contrato `VALID` + lineage + 0 críticos + DQS ≥ umbral + versión.

### 4.3 Cuarentena

Cada registro rechazado se escribe en `data/quarantine/<dataset>_quarantine_<run_id>.json` con
`record_id` (determinista: hash de regla + índice + fila), regla incumplida, valor original,
valor esperado y `detected_at`. El fichero se escribe **siempre**, incluso vacío, para poder
auditar que la comprobación se ejecutó.

---

## 5. Hallazgos sobre los datos reales y su solución

| # | Hallazgo | Solución |
|---|---|---|
| 1 | XLSX de ONSV con 4 filas de preámbulo antes de la cabecera real | `header_row: 4` |
| 2 | Nombres con acentos, `¿?` y espacios dobles | mapa `rename` canónico (26 columnas) |
| 3 | Fechas `DD/MM/YYYY` que pandas lee como `MM/DD` → 5,463 `NaT` | `date_columns` con formatos explícitos |
| 4 | Coordenadas con símbolo grado (`-71.325300°`) | `numeric_strip_chars` antes de coerción |
| 5 | `REGION` con `LIMA` y `Lima` a la vez | `case_normalize: upper` |
| 6 | `lat`/`lon` duplican exactamente `LATITUD`/`LONGITUD` (pct igualdad = 1.0) | `drop_columns` |
| 7 | `vehiculos_danados` con 2,813 nulos (30.9 %) | imputación `median` + registro en TransformationLog |
| 8 | `condicion_climatica` con nulos | imputación de dominio `DESCONOCIDO`, declarado en el catálogo |
| 9 | Columnas `object` con tipos mezclados, no escribibles en Parquet | `_parquet_safe()` en Bronze |
| 10 | Acentos en catálogos que la limpieza elimina | catálogos en forma plegada + comparación `_norm()` |

### 5.1 Sobre el hallazgo 9 (el más técnico)

El crudo de ONSV presenta columnas `object` heterogéneas:

- `FECHA SINIESTRO`: `datetime` + `'01/01/2021'` (str)
- `COORDENADAS  LONGITUD`: `float` + `'-71.325300°'` (str)

Parquet exige un tipo único por columna, y PyArrow lanzaba
`Expected bytes, got a 'datetime.datetime' object`, abortando el pipeline en la etapa
`register_raw`. La solución (`_parquet_safe`) normaliza **por contenido, no por nombre** de
columna, con tres intentos: numérico → fecha → literal, y solo acepta la conversión si no
destruye valores. Bronze sigue guardando el dato tal cual llega en términos de información.

---

## 6. Defectos del propio sistema detectados y corregidos

Estos errores son más relevantes para la nota que los datos sucios, porque nacieron del
sistema de medición y de trazabilidad.

| # | Defecto | Impacto | Corrección |
|---|---|---|---|
| D1 | `validity` aplicaba `>= 0` a toda columna numérica | Coordenadas del Perú (negativas) puntuaban **0 %** | Se usa el rango declarado en el contrato |
| D2 | `freshness_column` se leía del contrato, donde no existe | Frescura fijada artificialmente en 100 | Se lee de `settings.datasets.<dataset>.freshness_column` |
| D3 | Alias de catálogo inexistente (`departamentos` vs `departamento`) | La dimensión validez no evaluaba esas columnas | Tabla `CATALOG_ALIAS` en `dimensions.py` |
| D4 | Idempotencia de Bronze comparaba md5 de parquet contra sha256 de la fuente | Condición siempre falsa; un Bronze corrupto se aceptaba para siempre | Se compara `source_md5` del `.meta.json`; si cambia, se archiva como `_superseded_<ts>` |
| D5 | `run_pipeline` no cerraba la conexión DuckDB | Tablas Silver no visibles desde otra conexión | `CHECKPOINT` + `close()` explícitos |
| D6 | `quality_scores` y `sources` existían pero nunca se escribían | Lineage incompleto | Registrados en cada corrida, con índices únicos |
| D7 | `fecha_no_futura` comparaba tz-naive con tz-aware | `TypeError` en ejecución | `datetime.now().date()` (tz-naive) |
| D8 | `_contract_ranges` generaba `(min, None)` | `TypeError` al comparar con `None` | Se excluyen no-numéricos y se usa ±infinito |
| D9 | Test smoke escribía en `data/` y `reports/` reales | Contaminó Bronze con 3 filas de fixture y el pipeline lo aceptó | Fixture aísla `DATA`/`ARTIFACTS`/`REPORTS` con `tmp_path` |
| D10 | `split_no_leakage` importaba `sklearn` | `ModuleNotFoundError` (no estaba en requirements) | Split determinista con `numpy.default_rng` |

El defecto D9 es especialmente illustrative: contaminó `data/bronze/onsv_1.0.parquet` con
3 filas del fixture y la idempotencia (D4) lo aceptó como válido. Solo se detectó al mirar
el tamaño del fichero (8.8 KB en lugar de ~1 MB). Por eso la verificación de integridad
comprueba ahora el número de filas, no solo que el fichero exista.

---

## 6 bis. Confiabilidad de las métricas (apartado transversal)

El DQS mide **propiedades del dato**. La confiabilidad mide **la confianza en las métricas**.
Son preguntas distintas y el proyecto las trata por separado en
[`docs/confiabilidad_etl.md`](confiabilidad_etl.md) y `src/quality/reliability.py`.

Resumen de los 8 ejes evaluados sobre datos reales (4 alta · 2 media · 2 baja · 2 no verificable):

| Eje | Veredicto | Evidencia |
|---|---|---|
| Reproducibilidad | alta | 3 corridas con la misma huella de medición → DQS idéntico |
| Trazabilidad | alta | manifest, lineage DuckDB, `source_md5`, Bronze inmutable |
| Robustez del DQS | media | spread p05–p95 = 8.43 con 300 perturbaciones de pesos |
| Incertidumbre | alta | DQS 92.07, IC 95 % [92.06, 92.09] (amplitud 0.03) |
| **Circularidad de catálogos** | **baja** | 100 % de los catálogos derivan del propio dataset |
| Cobertura del universo | no verificable | 9.106 registros; sin total oficial ONSV/MTC |
| Integridad referencial | no verificable | dimensión fijada a 100 (0 claves foráneas) |
| Consistencia cruzada | baja | Jaccard ONSV↔cinemómetros = 0.40 |
| Imputación | media | `vehiculos_danados` imputado con mediana (30.9 % nulos) |
| Deriva temporal | alta | sin variación en el código vigente |

**Hallazgo principal:** el mismo dataset y el mismo código dan un DQS de **70.26** (frescura
crítica) a **100.00** (solo contrato). El 92.07 refleja una decisión de configuración, no solo
una propiedad del dato. Por eso **no se calcula un "índice de confiabilidad"**: un número único
repetiría el error que hace malinterpretable el DQS.

Tres decisiones metodológicas que hubo que tomar (detalladas en el apartado de confiabilidad):

1. **Huella de medición** (`versioning.measurement_fingerprint()`) en lugar de `git_commit`
   para agrupar corridas: tras integrar el ETL en el repositorio SIPAT, el commit del padre
   cambia por motivos ajenos. `reliability.py` queda **fuera** de la huella a propósito: el
   auditor no produce la medición.
2. **Bootstrap con `fix_dimensions`**: remuestrear con reemplazo duplica las PK y hunde la
   unicidad, dando un IC descentrado (punto 92.07 contra IC [86.45, 86.65]). Las dimensiones
   invariantes al muestreo se fijan.
3. **Cambio de método ≠ deriva**: el DQS bajó de 94.97 a 92.07 al corregir el defecto de las
   coordenadas. `run_drift` separa ambas causas.

---

## 7. Trazabilidad

- **run_id**: `run-YYYYMMDD-HHMMSS-<uuid8>`, único por ejecución.
- **manifest.json** por corrida: estado global, las 15 etapas con su payload, DQS por dataset.
- **TransformationLog** por dataset: cada operación con columna, registros afectados, ejemplos
  antes/después y estrategia. Ejemplo real: `rename_canonical` 27 columnas, `parse_date` 9,106 filas.
- **Lineage DuckDB** (`artifacts/lineage/sipat_lineage.duckdb`): `sources`, `runs`,
  `dataset_lines` (bronze/silver/gold × dataset × run), `quality_scores`. Índices únicos → idempotente.
- **Logging JSON** con `timestamp | level | module | run_id | dataset | operation`.
- **Checksums**: MD5 y SHA256 por fuente y por artefacto publicado.

Consulta de ejemplo:

```sql
SELECT dataset, layer, rows, file_md5, created_at
FROM dataset_lines ORDER BY created_at DESC;
```

---

## 8. Testing

**87 tests, 100 % verdes.**

| Suite | Nº | Alcance |
|---|---|---|
| `tests/unit/test_core.py` | 33 | extractores, contratos, limpieza, TransformationLog, features, DQS, reglas, gates, cuarentena, MODEL_READY, silver, hashing |
| `tests/unit/test_regressions.py` | 28 | un test por cada defecto D1–D10 y por los hallazgos 1–10 |
| `tests/unit/test_smoke.py` | 4 | imports, extracción con preámbulo, corrida mini end-to-end |
| `tests/integration` | 9 | pipeline completo, manifest, silver/gold/reporte, idempotencia, lineage, agregaciones SQL |
| `tests/data_quality` | 13 | contrato y reglas críticas sobre los datos **reales** (skip si no están) |

`tests/data_quality` es la suite más valiosa: valida el sistema contra los ficheros reales del
workspace SIPAT, no contra datos inventados. Si el ONSV publica un valor de `clase` fuera
de catálogo, el test falla.

---

## 9. Limitaciones conocidas

1. **Sin claves foráneas reales.** La dimensión *integridad* esta fijada a 100 porque los datasets
   son independientes; para que aporte valor requiere cruzar ONSV con un maestro de
   carreteras/UBIGEO, que no está en el workspace.
2. **Frescura baja por diseño** (datos históricos). Si la fuente se actualiza, el DQS sube solo.
3. **La regla de fechas futuras** usa la fecha del sistema, que puede estar desviada
   respecto de la fecha real de publicación de la fuente.
4. **Prefect sin servidor persistente**: en `auto` se usa el backend local efímero. Para
   producción hace falta un backend con almacenamiento (ver `docs/airflow_migracion.md`).
5. **Sin validación cruzada entre datasets**: no se comprueba que los Departamentos de ONSV
   coincidan con los de cinemómetros.
6. **`vehiculos_danados` se imputa con la mediana**: es una decisión discutible (media
   poblacional); para modelos predictivos conviene marcarla con un indicador de imputación
   en lugar de perder esa señal.
7. **Sin versionado DVC**: los datos no están versionados en Git (por tamaño); ver `docs/dvc_versionado.md`.

---

## 10. Arquitectura futura

1. **Contratos como código en CI**: validar contratos en cada commit contra los datos reales.
2. **DVC o lakehouse**: versionado de datos con checksum y trazabilidad por versión.
3. **MLflow + modelo de riesgo**: `model_ready` ya está listo; falta entrenar y registrar.
4. **Airflow/Dagster** si se requiere programación por calendario y dependencias entre datasets.
5. **Particionado por fecha** en Bronze para no reescribir el histórico completo cada corrida.
6. **Polars** como backend de DataFrame para textos grandes (ver nota de migración en `src/`).
7. **Maestro UBIGEO** para habilitar la dimensión *integridad* con FK reales.
