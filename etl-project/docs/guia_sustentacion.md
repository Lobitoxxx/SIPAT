# Guía de sustentación — SIPAT-ETL

Material de apoyo para la defensa del proyecto. Cada sección responde a lo que
preguntaría un jurado técnico, con la evidencia concreta del repositorio.

---

## 1. Preguntas frecuentes sobre el alcance

### ¿Qué hace el sistema?

Transforma dos fuentes reales de datos de siniestralidad vial del Perú (ONSV y SUTRAN)
en tres capas consultables (Bronze/Silver/Gold), midiendo la calidad en cada paso y
**deteniéndose** si los datos no cumplen el contrato.

### ¿Por qué esos dos datasets?

Porque son las fuentes que el workspace SIPAT ya tenía, y son heterogéneos a propósito:
un XLSX con preámbulo y nombres sucios frente a un CSV de 160 mil filas. Un sistema ETL
que solo funciona con datos limpios no es un sistema ETL.

### ¿Cuál es la diferencia con el proyecto SIPAT original?

SIPAT es analítica (modelos de riesgo, rutas seguras, dashboard). SIPAT-ETL es la **capa de
ingesta y calidad** que debería preceder a ese análisis. SIPAT-ETL no calcula riesgo ni
recomienda rutas: garantiza que cuando SIPAT analice, analice datos que pasaron un contrato.

### ¿Por qué 9.106 y no más registros de ONSV?

Porque ese es el contenido completo del XLSX disponible en el workspace. El pipeline no
filtra: Bronze conserva las 9.106 filas y Silver también; la transformación no descarta
registros, los **marca** (cuarentena) cuando violan reglas críticas.

---

## 2. Preguntas sobre arquitectura

### ¿Por qué Medallion y no un modelo de dos capas?

Porque la separación permite **reproducir** cualquier estado derivado sin volver a la
fuente. Si un bug aparece en Silver, se regenera desde Bronze (inmutable) sin volver a
descargar el XLSX. El coste es almacenamiento duplicado; el beneficio es que ningún error
de transformación es irreversible.

### ¿Por qué Bronze es inmutable?

Porque es la única forma de auditar. Si Bronze se pudiera sobrescribir, un pipeline con un
bug podría "reescribir la historia". Aquí, además, si el fichero fuente cambia, el Bronze
previo **se archiva** con sufijo `_superseded_<timestamp>` en lugar de borrarse.

### ¿Por qué Parquet y no CSV?

Parquet es columnar: la Silver de cinemómetros (160.018 × 13) ocupa 2 MB frente a ~25 MB en
CSV, y las agregaciones solo leen las columnas necesarias. Además conserva los tipos (fechas
como fechas, no como texto), que es la mitad de los problemas de este proyecto.

### ¿Por qué DuckDB y no PostgreSQL?

Porque el requisito es un motor SQL analítico **local** sin servidor que mantener. DuckDB
lee Parquet directamente, así que las agregaciones Gold se ejecutan sobre los mismos ficheros
sin copia intermedia. Migrar a PostgreSQL o Snowflake es cambiar la conexión, no la lógica:
las agregaciones son SQL declarativo en YAML.

### ¿Por qué 15 etapas y no un script lineal?

Porque cada etapa es un punto de inspección. El `manifest.json` guarda el resultado de las 15,
así que se responde "¿en qué paso se rompió?" sin depurar un proceso de tres horas. El coste
es ceremonialidad; el beneficio es que un fallo de datos se localiza en un paso.

### ¿Por qué el contrato se valida después de limpiar?

Porque el fichero crudo usa nombres como `'COORDENADAS  LONGITUD'` y
`'¿EXISTE SEÑAL VERTICAL?'`. Validar el contrato contra el crudo daría más de veinte errores
de "columna inexistente" que son ruido, no hallazgos. El contrato describe la capa **Silver**,
donde están los nombres canónicos. Por eso las columnas extra se toleran (`allow_extra: true`).

---

## 3. Preguntas sobre calidad de datos

### ¿Qué es el DQS exactamente?

Un número 0-100 ponderado a partir de seis dimensiones (completitud, validez, unicidad,
consistencia, integridad, frescura) con pesos configurables. **No es una probabilidad de que
los datos sean verdaderos**, y el docstring de `src/quality/dimensions.py` lo dice
explícitamente para que nadie lo malinterprete.

### ¿Por qué el DQS de ONSV bajó de 94.97 a 92.07?

Porque **el indicador estaba mal calculado**. La dimensión de validez aplicaba un umbral
`>= 0` a toda columna numérica; las coordenadas del Perú son negativas (−18° a 0°, −81° a
−68°), así que latitud y longitud puntuaban 0 %. Al corregir la validación para usar el rango
declarado en el contrato, la validez pasó a 100 y la frescura empezó a calcularse de verdad
(12.06 en vez del 100 artificial), bajando la media ponderada.

La lección: un indicador de calidad que nunca falla es un indicador mal construido. Que el
DQS bajara al corregir el código es evidencia de que el sistema mide algo real.

### ¿Por qué la frescura es 12 y no es un problema?

Porque los datos son históricos (siniestros 2021-2025). Un registro de 2021 no es "fresco" en
2026, y el sistema debe decirlo. Por eso la frescura pesa 0.08: es un atributo de la fuente,
no un defecto del proceso. Si la fuente se actualiza, el DQS sube solo.

### ¿Qué pasa si una regla crítica falla?

Tres cosas: (1) el gate pasa a `FAILED`, (2) cada registro se escribe en
`data/quarantine/` con regla, valor original y valor esperado, (3) `model_ready` no se publica
aunque Silver sí. El dato sospechoso se conserva y se marca, no se descarta en silencio.

### ¿La cuarentena está vacía? ¿No hace nada entonces?

El fichero se escribe **siempre**, aunque esté vacío, precisamente para poder auditar que la
comprobación se ejecutó. Un sistema que solo escribe cuando hay problemas no permite
distinguir "no hubo problemas" de "no se comprobó". Ahora hay 0 registros porque el pipeline
limpia lo que puede y marca lo que no puede, y al no quedar críticos no hay nada que aislar.

### ¿Por qué imputan `vehiculos_danados` con la mediana?

Porque es la estrategia menos sesgada para un conteo con 30.9 % de nulos, y queda **registrada**
en el `TransformationLog` (estrategia y nº de registros afectados). La alternativa —dejar NaN o
imputar 0— sesgaría los modelos hacia "daños = 0". Es una decisión discutible y está anotada
como limitación: para modelos predictivos conviene añadir un indicador
`vehiculos_danados_was_imputed`.

### ¿Por qué no eliminan los outliers?

Porque eliminarlos es una decisión analítica, no de limpieza, y puede destruir información
real (un atropello con 15 fallecidos es un outlier legítimo). La política
`outlier_policy: report` los **detecta y reporta** con el método IQR, sin borrar nada.
Modificarla a `flag` añade una marca; nunca se hace `drop` automático.

### ¿Cómo trataron los acentos?

La limpieza aplica `fold_accents`, así que `CAÍDA DE PASAJERO` se convierte en
`CAIDA DE PASAJERO`. Los catálogos se escribieron **en la forma plegada** y la comparación
usa una función `_norm()` común, de modo que catálogo y dato comparan exactamente. Antes de
esa corrección, el sistema registraba 532 warnings legítimos.

---

## 4. Preguntas sobre implementación

### ¿Cómo se garantiza que nada esté hardcodeado?

Toda la lógica de negocio vive en YAML: `settings.yaml` (pesos, planes de limpieza, renombres,
formatos de fecha), `contracts/*.yaml` (tipos, rangos, catálogos permitidos),
`quality_rules.yaml` (reglas y severidad), `catalogs/*.yaml` (dominio y agregaciones). Cambiar
el umbral de calidad o añadir una regla nueva no requiere tocar Python. El único dato en código
es la lista de tipos soportados por el validador de contratos.

### ¿Qué pasa si el formato de la fuente cambia?

El perfilado (`profiling_before`) y la validación de contrato lo detectan: columnas que
desaparecen rompen el contrato, columnas nuevas aparecen como extra (toleradas pero
documentadas en `details_by_column.__extra_columns`), y los tipos que no encajan disparan la
regla `type`. El fallo es visible en la etapa 6, no tres etapas después.

### ¿Cómo se ejecuta dos veces sin duplicar datos?

Por la idempotencia de Bronze: se compara el `source_md5` registrado en el `.meta.json` con el
del fichero actual. Si coinciden, no se reescribe. Si difieren, se archiva el anterior y se
registra el nuevo. El lineage usa índices únicos en `(dataset, layer, run_id)`, así que los
registros de lineage tampoco se duplican. Verificado: dos corridas seguidas dan el mismo DQS.

### ¿Qué es MODEL_READY?

Una condición que debe cumplirse **todas** a la vez: contrato `VALID`, gate `PASSED`, lineage
disponible, 0 errores críticos, DQS ≥ umbral y versión registrada. Si algo falla, el dataset
`model_ready` no se escribe y el motivo queda en el manifest (`gold.blocked.criterion`). Es la
puerta que evita que un modelo se entrene sobre datos que no pasaron el control de calidad.

### ¿Cómo se evita el data leakage?

`split_no_leakage` parte el dataset de forma determinista (semilla fija), y el contrato es
explícito: imputación, escalado y PCA se ajustan **solo sobre train** y luego se aplican ya
ajustados a test. El split por sí solo no evita fugas; el orden de las operaciones sí, y está
documentado en el docstring de la función.

---

## 5. Preguntas sobre operation y escalabilidad

### ¿Cómo se ejecuta?

```bash
python scripts/run_pipeline.py                    # auto (Prefect si está)
python scripts/run_pipeline.py --engine sequential
python scripts/verify_etl.py                      # 4/4 checks
python -m pytest tests -q                         # 87 tests
streamlit run etl-ui/app.py
```

### ¿Qué pasa si Prefect no está instalado?

El pipeline **no se detiene**: `run_pipeline_auto` cae a ejecución secuencial y lo deja
registrado en el log. Es una decisión deliberada: una herramienta de orquestación no debe ser
un punto único de fallo para el proceso de datos.

### ¿Cómo escala a 10 millones de filas?

En su estado actual, en memoria. El camino ya está preparado: el backend es configurable
(`etl.backend`, hoy `pandas`, con nota de migración a `polars`), Parquet permite el
particionado por fecha, y DuckDB hace el pushdown de filtros sobre ficheros, así que la
Silver grande no necesita cargarse entera para agregar. Lo que falta es el particionado y la
ejecución por lotes.

### ¿Cómo se audita una corrida antigua?

`artifacts/runs/<run_id>/manifest.json` tiene las 15 etapas, el DQS y el estado. Y en DuckDB:

```sql
SELECT r.run_id, r.status, q.dataset, q.score, q.gate
FROM runs r JOIN quality_scores q USING (run_id)
ORDER BY r.started_at DESC;
```

### ¿Qué no está hecho?

Están declarados como limitación, no escondidos: no hay claves foráneas reales (integridad
está fijada a 100 porque los datasets son independientes), no hay validación cruzada entre
datasets, Prefect usa backend local efímero, y los datos no están versionados con DVC. Cada
uno tiene su documento de ruta en `docs/`.
