---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 02 · SIPAT-ETL <span class="sipat-essential">esencial</span></p>
  <h2>Antes de analizar, hay que <i>verificar</i></h2>
  <p class="sipat-section__desc">
    Subproyecto con su propio repositorio Git. Principio rector: <b>los datos crudos nunca se borran ni se sobrescriben</b>.
    Bronze es inmutable, cada transformación queda registrada y cada dataset publicado pasa un <b>quality gate</b> explícito.
  </p>
  <span class="sipat-section__num">02</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>Arquitectura Medallion: RAW → Bronze → Silver → Gold</h1>
  </div>
  <div class="sipat-head__aside">
    Nada se borra<br>
    Bronze inmutable e idempotente
  </div>
</div>

```mermaid
flowchart LR
  subgraph RAW["RAW · fuente original"]
    direction TB
    R1["XLSX ONSV<br/>nombres con acentos, °, espacios dobles"]
    R2["CSV SUTRAN<br/>LIMA vs Lima, lat/lon duplicadas"]
  end
  subgraph B["BRONZE · inmutable"]
    direction TB
    B1["onsv_1.0.parquet<br/>+ md5 · sha256 · run_id · filas"]
  end
  subgraph S["SILVER · limpio y canónico"]
    direction TB
    S1["onsv_silver_1.0.parquet<br/>snake_case · fechas datetime"]
  end
  subgraph G["GOLD · propósito concreto"]
    direction TB
    G1["*_model_ready_*.parquet<br/>(solo si MODEL_READY)"]
    G2["*_agg_*.json · DuckDB"]
  end
  RAW --> B --> S --> G
```

<div class="sipat-cards" style="margin-top:12px">
  <div class="sipat-card">
    <div class="sipat-card__t">🥉 Bronze</div>
    <div class="sipat-card__d">Dato <b>tal cual llega</b> + metadatos. <b>Inmutable</b>: copia, checksum, run_id, fecha de ingesta.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">🥈 Silver</div>
    <div class="sipat-card__d">Contrato YAML. Nombres canónicos, tipos correctos, dedupe, imputación, fechas parseadas. <b>Regenerable</b>.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">🥇 Gold</div>
    <div class="sipat-card__d">Derivado: analítico, <code>model_ready</code> <b>(con gate)</b> y agregaciones SQL en DuckDB.</div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>Pipeline de 15 etapas en 5 fases</h1>
  </div>
  <div class="sipat-head__aside">
    Prefect 3 con fallback secuencial<br>
    Ambas rutas ejecutan la <b>misma</b> función
  </div>
</div>

```mermaid
flowchart LR
  P1["<b>1 · Ingesta</b><br/>start · extract<br/>register_raw → Bronze"] --> P2["<b>2 · Preparación</b><br/>profiling_before<br/>clean · schema_validation<br/>transform"]
  P2 --> P3["<b>3 · Calidad</b><br/>data_quality → DQS<br/>quarantine<br/>quality_gate"]
  P3 --> P4["<b>4 · Publicación</b><br/>load_silver<br/>build_gold + DuckDB"]
  P4 --> P5["<b>5 · Cierre</b><br/>profiling_after<br/>generate_report · finish"]
  P2 -.->|TransformationLog| L1[("artifacts/runs/run_id/<br/>manifest + logs")]
  P3 -.->|DQS + gate result| L1
  P4 -.->|lineage| L2[("DuckDB")]
```

<div class="sipat-split sipat-split--even" style="margin-top:12px">
  <div class="sipat-note">
    <b>Cada etapa</b> registra estado <code>OK/ERROR</code>, payload saneado, traza de excepción y log estructurado
    <code>timestamp | level | module | run_id | dataset | operation</code>.
  </div>
  <div class="sipat-note sipat-note--warn">
    <b>Orquestación:</b> con <code>--engine auto</code> usa Prefect 3 (reintentos, caché, traza en UI).
    Si el orquestador no está, <b>degrada a secuencial y lo registra en el log</b> — el pipeline no se detiene.
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>Data Quality Score: 6 dimensiones ponderadas</h1>
  </div>
  <div class="sipat-head__aside">
    Pesos configurables<br>
    <code>config/settings.yaml</code>
  </div>
</div>

<DqsBar />

<div class="sipat-split sipat-split--even" style="margin-top:12px">
  <div class="sipat-note sipat-note--warn" style="font-size:.78rem">
    <b>El DQS no es una probabilidad</b> de que los datos sean «verdaderos». Es un <b>indicador interno</b>
    de calidad del dataset para la organización. Se documenta como tal para no inducir a error.
  </div>
  <div class="sipat-note" style="font-size:.78rem">
    <b>Nada hardcodeado:</b> pesos, planes de limpieza, renombres, contratos y catálogos viven en
    <code>config/*.yaml</code>. Añadir una regla es editar un YAML, no el código.
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>El quality gate: publica o bloquea</h1>
  </div>
  <div class="sipat-head__aside">
    Reglas críticas exigen <b>100 %</b><br>
    <code>min_quality_score: 90</code>
  </div>
</div>

```mermaid
flowchart LR
  DF[("Dataset Silver")] --> C["Completitud"] & V["Validez"] & U["Unicidad"] & CO["Consistencia"] & I["Integridad"] & F["Frescura"]
  C & V & U & CO & I & F --> W["DQS = Σ (dim × peso)"]
  W --> G{"Quality Gate"}
  V --> Q{"¿reglas críticas<br/>disparadas?"}
  Q -->|Sí| CAR["🗂️ Cuarentena JSON"]
  Q -->|No| MR{"¿DQS ≥ 90?"}
  G --> MR
  MR -->|Sí, sin críticos| P["✅ PASSED"]
  MR -->|DQS bajo| WN["⚠️ WARNING"]
  MR -->|Con críticos| F2["❌ FAILED"]
  P --> MRD{"¿MODEL_READY?"}
  MRD -->|Contrato + lineage + 0 críticos| GOLD["Publica Gold"]
  MRD -->|No| BLOCK["🚫 Bloquea Gold model_ready"]
```

<div class="sipat-note sipat-note--ok" style="margin-top:12px">
  <b>Reglas críticas</b> (<code>config/quality/quality_rules.yaml</code>):
  <code>schema_valid</code>, <code>primary_key_not_null</code>, <code>primary_key_unique</code>,
  <code>target_available</code> al 100 %; <code>referential_integrity</code> al 98 %.
  Cualquier crítico ⇒ <b>FAILED + cuarentena</b>.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>Resultado real sobre datos reales</h1>
  </div>
  <div class="sipat-head__aside">
    Ejecutado, no teórico<br>
    0 críticas · 0 cuarentena
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:13px">
  <KpiCard :value="92.07" :decimals="2" suffix="/100" label="DQS · dataset ONSV" hint="9.106 filas · 33 columnas Silver" tone="green" />
  <KpiCard :value="92.00" :decimals="2" suffix="/100" label="DQS · cinemómetros" hint="160.018 filas · 13 columnas" tone="green" />
  <KpiCard :value="0" label="Violaciones críticas" hint="Ninguna regla crítica disparada" tone="green" />
  <KpiCard :value="0" label="Registros en cuarentena" hint="Ambos datasets pasaron el gate" tone="green" />
</div>

<table class="sipat-table">
  <thead>
    <tr><th>Dataset</th><th>Bronze</th><th>Silver</th><th class="num">DQS</th><th>Gate</th><th class="num">Críticos</th><th class="num">Cuarentena</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>onsv</strong><br><span style="font-size:.72rem;color:#64748b">siniestros fatales 2021-2025</span></td>
      <td>9.106 × 27</td><td>9.106 × 33</td>
      <td class="num">92.07</td><td>✅ PASSED</td><td class="num">0</td><td class="num">0</td>
    </tr>
    <tr>
      <td><strong>cinemometros</strong><br><span style="font-size:.72rem;color:#64748b">velocidades SUTRAN 2019-2021</span></td>
      <td>160.018 × 11</td><td>160.018 × 13</td>
      <td class="num">92.00</td><td>✅ PASSED</td><td class="num">0</td><td class="num">0</td>
    </tr>
  </tbody>
</table>

<div class="sipat-note" style="margin-top:12px">
  <b>Defensible:</b> el DQS no se ajusta para «quedar bien». Las columnas <code>CANTIDAD DE VEHICULOS DAÑADOS</code>
  con 2.813 nulos se imputan por <code>median</code> y <b>la imputación queda registrada</b> en el
  <code>TransformationLog</code>, no escondida.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>12 problemas reales del dato, y su solución configurable</h1>
  </div>
  <div class="sipat-head__aside">
    No son hipotéticos:<br>
    se encontraron <b>ejecutando</b> el pipeline
  </div>
</div>

<table class="sipat-table" style="font-size:.72rem">
  <thead><tr><th style="width:46%">Hallazgo en el dato real</th><th>Solución configurada</th></tr></thead>
  <tbody>
    <tr><td>XLSX de ONSV con <b>4 filas de preámbulo</b> antes de la cabecera</td><td><code>header_row: 4</code> en <code>sources/onsv_xlsx.yaml</code></td></tr>
    <tr><td>Columnas con acentos, <code>¿?</code> y espacios dobles (<code>'COORDENADAS  LONGITUD'</code>)</td><td><code>rename</code> canónico en <code>settings.yaml</code></td></tr>
    <tr><td>Fechas <code>DD/MM/YYYY</code> → pandas las lee como <code>MM/DD</code>: <b>5.463 NaT</b></td><td><code>date_columns</code> con formatos explícitos</td></tr>
    <tr><td>Coordenadas con símbolo grado (<code>-71.3253°</code>)</td><td><code>numeric_strip_chars: ["°","º",","," "]</code></td></tr>
    <tr><td><code>REGION</code> con <code>LIMA</code> y <code>Lima</code> (doble caja)</td><td><code>case_normalize</code> + <code>fold_accents</code></td></tr>
    <tr><td><code>lat</code>/<code>lon</code> duplican exactamente <code>LATITUD</code>/<code>LONGITUD</code></td><td><code>drop_columns</code></td></tr>
    <tr><td><code>CANTIDAD DE VEHICULOS DAÑADOS</code> con <b>2.813 nulos</b></td><td>imputación <code>median</code> registrada</td></tr>
    <tr><td>Columnas <code>object</code> mixtas (datetime + texto) <b>no escribibles en Parquet</b></td><td><code>_parquet_safe()</code> normaliza por contenido</td></tr>
    <tr><td>Acentos que la limpieza elimina (<code>CAÍDA→CAIDA</code>) vs contratos con acento</td><td>catálogos plegados + comparación <code>_norm</code></td></tr>
    <tr><td>Coordenadas del Perú son <b>negativas</b>: un chequeo <code>&gt;= 0</code> las penalizaba a 0 %</td><td><code>validity</code> usa el rango del contrato (lat −18.5..0.2)</td></tr>
    <tr><td><code>freshness_column</code> no estaba en el contrato → frescura fija en 100</td><td>se lee de <code>settings.datasets.&lt;ds&gt;.freshness_column</code></td></tr>
    <tr><td>Idempotencia mal definida (comparar md5 del parquet en vez de la fuente)</td><td>se usa <code>source_md5</code>; el Bronze previo se archiva <code>_superseded_&lt;ts&gt;</code></td></tr>
  </tbody>
</table>

<div class="sipat-note sipat-note--warn" style="margin-top:10px">
  <b>Patrón común:</b> ningún defecto se «parcheó» en el código. Todos viven como <b>regla de configuración</b>
  auditable y reversible.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-essential">esencial</span></span>
    <h1>87 tests, y uno de ellos existe por historia</h1>
  </div>
  <div class="sipat-head__aside">
    <code>pytest tests -q</code><br>
    Sobre datos reales cuando están
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:12px">
  <KpiCard :value="87" label="Tests en verde" hint="unit · integration · data_quality" tone="indigo" />
  <KpiCard :value="28" label="Tests de regresión" hint="test_regressions.py" tone="amber" />
  <KpiCard :value="13" label="Tests sobre datos reales" hint="Fallan si ONSV publica fuera de catálogo" tone="red" />
  <KpiCard :value="3" label="Notebooks verificados" hint="Ejecutan sin errores con nbclient" tone="green" />
</div>

<table class="sipat-table" style="font-size:.76rem">
  <thead><tr><th style="width:34%">Suite</th><th class="num" style="width:8%">Tests</th><th>Qué cubre</th></tr></thead>
  <tbody>
    <tr><td><code>unit/test_core.py</code></td><td class="num">33</td><td>Extractores, contratos, limpieza, TransformationLog, features, DQS, reglas, gates, cuarentena, MODEL_READY, silver, hashing, run_id</td></tr>
    <tr><td><code>unit/test_regressions.py</code></td><td class="num">28</td><td>Regresiones de defectos reales: columnas <code>object</code> mixtas, coordenadas negativas en <code>validity</code>, <code>freshness_column</code>, folding de acentos, tz-naive, split ML</td></tr>
    <tr><td><code>unit/test_smoke.py</code></td><td class="num">4</td><td>Importación de todos los módulos, XLSX con preámbulo, corrida mini end-to-end</td></tr>
    <tr><td><code>integration/</code></td><td class="num">9</td><td>Pipeline completo (15 etapas), manifest, silver/gold/reporte, idempotencia, lineage DuckDB, agregaciones SQL</td></tr>
    <tr><td><code>data_quality/</code></td><td class="num">13</td><td>Contrato y reglas críticas sobre los <b>datos reales</b> del workspace</td></tr>
  </tbody>
</table>

<div class="sipat-note sipat-note--warn" style="margin-top:10px">
  <b>Por qué existe <code>test_regressions.py</code>:</b> los tests con fixtures sintéticas <b>no detectaban</b>
  estos fallos — las coordenadas negativas del Perú puntuaban 0 % en validez porque se asumía <code>&gt;= 0</code>,
  y el XLSX sintético no traía preámbulo. Cada test de ese fichero <b>documenta el fallo original</b>.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">SIPAT-ETL <span class="sipat-optional">detalle</span></span>
    <h1>Trazabilidad: del fichero fuente al Gold</h1>
  </div>
  <div class="sipat-head__aside">
    Lineage en DuckDB<br>
    Registro idempotente
  </div>
</div>

```mermaid
sequenceDiagram
  autonumber
  participant CLI as run_pipeline.py
  participant FL as flow.run_dataset
  participant BR as Bronze
  participant CL as clean
  participant QA as quality
  participant LD as load Silver/Gold
  participant LX as lineage DuckDB
  CLI->>FL: por cada dataset
  FL->>BR: register_raw (inmutable, por source_md5)
  FL->>CL: clean + TransformationLog
  CL->>QA: DQS + reglas de dominio
  QA->>LX: record_quality_score
  QA-->>FL: gate PASSED/WARNING/FAILED
  FL->>LD: write_silver
  LD->>LX: register_dataset_line
  FL->>LD: write_gold (si MODEL_READY)
  FL-->>CLI: manifest + DQS por dataset
```

<div class="sipat-cards" style="margin-top:12px">
  <div class="sipat-card">
    <div class="sipat-card__t">🆔 run_id único</div>
    <div class="sipat-card__d"><code>run-YYYYMMDD-HHMMSS-uuid8</code> por ejecución. Todo el artefacto cuelga de él.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">🗃️ Metadatos Bronze</div>
    <div class="sipat-card__d">Fuente, run_id, versión, <b>MD5 + SHA256</b>, tamaño, filas, columnas, timestamp.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">📊 Lineage DuckDB</div>
    <div class="sipat-card__d">Tablas <code>sources</code>, <code>runs</code>, <code>dataset_lines</code> (bronze·silver·gold) y <code>quality_scores</code>.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#059669">
    <div class="sipat-card__t">🔁 Idempotencia real</div>
    <div class="sipat-card__d">Reejecutar con la misma fuente <b>no duplica filas</b>, no reescribe Bronze y no altera el DQS.</div>
  </div>
</div>
