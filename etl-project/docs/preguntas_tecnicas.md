# Preguntas técnicas — SIPAT-ETL

Doce preguntas de entrevista técnica con su respuesta. Cada una apunta a código real del
repositorio, para poder citarla durante la sustentación.

---

### 1. ¿Cómo se lee un XLSX con cabecera en la fila 6?

Por configuración, no por código. `config/sources/onsv_xlsx.yaml` declara `header_row: 4`
(base 0), y `src/extract/excel_reader.py` lo pasa a `pd.read_excel`. Si el fichero tuviera la
cabecera en otra fila, se cambia el YAML. Lo mismo aplica a `encoding` en CSV y a los formatos
de fecha en `settings.yaml`.

### 2. ¿Por qué Bronze no se puede sobrescribir?

Porque auditar requiere poder demostrar el estado original. `register_bronze` compara el
`source_md5` guardado en `<dataset>_1.0.meta.json` con el md5 del fichero actual. Si difieren,
el Bronze anterior se renombra a `..._superseded_<timestamp>.parquet` y se escribe el nuevo.
Nada se borra. Un pipeline que puede sobrescribir su historia no puede demostrar nada.

### 3. ¿Cómo se evita que las fechas se parseen como mes/día?

Con formatos explícitos por columna: `settings.yaml` declara
`fecha: ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]` y `clean()` los aplica en orden. Sin eso, pandas
interpreta `05/01/2021` como mayo y genera 5.463 `NaT`. Además, el contrato fija
`min: 2000-01-01` y `max_before_today_days: 0`, y la regla `fecha_parsable` es crítica.

### 4. ¿Qué es DQS y qué no es?

Es un indicador interno ponderado 0-100 (completitud .22, validez .22, unicidad .15,
consistencia .15, integridad .18, frescura .08). **No es una probabilidad de que los datos
sean ciertos.** El docstring de `dimensions.py` lo advierte para evitar el mal uso más común:
interpretar un 92 como "92 % de probabilidad de veracidad".

### 5. ¿Cómo se calcula la validez sin castigar a los datos válidos?

Cada columna numérica se evalúa contra el rango declarado en su contrato. Si el contrato dice
`latitud: min -18.5, max 0.2`, se compara contra ese rango. El valor por defecto `>= 0` solo se
usa cuando no hay rango declarado. Esto importa: el Perú está en hemisferio sur y en
longitud oeste, así que la versión anterior puntuaba 0 % a las coordenadas.

### 6. ¿Por qué los catálogos están sin acentos?

Porque `clean()` aplica `fold_accents` (`CAÍDA DE PASAJERO` → `CAIDA DE PASAJERO`). Si el
catálogo conservara el acento, la comparación fallaría siempre. Además `validity` y
`domain_rules` normalizan con la misma función `_norm()` (NFKD, sin diacríticos, upper,
espacios colapsados), así que el sistema es tolerante si alguien edita el YAML y reintroduce
un acento.

### 7. ¿Qué garantiza que el pipeline sea idempotente?

Tres cosas independientes:

1. **Bronze**: comparación de `source_md5`; si la fuente no cambió, no se reescribe.
2. **Lineage**: índices únicos en `(dataset, layer, run_id)` con `ON CONFLICT DO UPDATE`.
3. **Silver/Gold**: se reescriben siempre con el mismo nombre de versión y son deterministas
   porque la limpieza no depende del reloj (la única parte temporal es `ingestion_timestamp`).

Verificado con `test_pipeline_is_idempotent` y con dos ejecuciones seguidas sobre datos reales.

### 8. ¿Cómo se localiza un error en una corrida?

`artifacts/runs/<run_id>/manifest.json` tiene las 15 etapas con su estado, payload y traza de
excepción. El log JSON incluye `run_id` y `dataset` en cada línea. No hace falta reproducir
el fallo: se lee qué etapa tiene `status: ERROR` y su `trace`.

### 9. ¿Por qué existe `data/quarantine/` si nunca se llenó?

Porque el fichero se escribe siempre, incluso vacío. Si solo se escribiera al haber
incidencias, no se podría distinguir "no hubo ninguna" de "no se comprobó". La existencia del
fichero vacío es la evidencia de que la etapa corrió.

### 10. ¿Cómo se evita el data leakage?

Con orden de operaciones, no con el split. `split_no_leakage` (determinista, `numpy.default_rng`)
genera train/test, y el llamador debe ajustar imputación, escalado y PCA **sobre train** para
después aplicarlos a test. El docstring de la función es explícito: el split por sí solo no
evita fugas. `model_ready` solo se escribe si el dataset pasó el gate, así que el modelo nunca
se entrena sobre datos sin control de calidad.

### 11. ¿Qué pasa si el código tiene un error y Bronze ya está escrito?

El pipeline falla en la etapa 6, 7 o posterior, y Silver/Gold de esa corrida no se producen.
Bronze no se toca. Al corregir el código y reejecutar, Bronze se reutiliza (mismo `source_md5`)
y solo se regenera desde `clean` en adelante. Por eso Bronze es inmutable: permite reintentar
sin volver a la fuente y sin riesgo de empeorar el estado.

### 12. ¿Cómo se cambiaría el sistema si la fuente fuera una API REST?

Se añade `src/extract/api_reader.py` implementando la interfaz de `ExtractResult` y se declara
en `config/sources/` con `type: api`, `endpoint` y `params`. La capa Bronze sigue funcionando
igual (el resultado se persiste igual), y todo lo que viene después es idéntico. Ese es el
motivo de que la extracción esté detrás de una factoría (`src/extract/factory.py`).
