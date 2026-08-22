# Graph Report - SIPAT  (2026-08-13)

## Corpus Check
- 53 files · ~9,346,403 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 304 nodes · 384 edges · 35 communities (19 shown, 16 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- geocode.py
- ruta_segura.py
- audit_extra.py
- dashboard/app.py
- audit.py
- audit_all_raw.py
- ckan_api.py
- check_codes.py
- Módulo "Ruta segura" — Manual
- download_ingemmet.py
- audit_onsv_deep.py
- RiesgoIndex
- dataset_files.py
- download.py
- ingemmet_stats.py
- modelo_glm.py
- resource_files.py
- analisis_rutas.py
- analisis_temporal.py
- debug_ingemmet.py
- eda_tramos.py
- explore_shapefile.py
- graficos.py
- 3. Fichas detalladas
- SIPAT — Informe Final de Análisis de Siniestralidad Vial en Perú
- 10. Fase 2 — Módulo "Ruta segura" (nuevas fuentes y arquitectura)
- OSRMClient
- osrm_build.py
- graphify_obsidian.py
- AGENTS.md
- graphify.js
- download_osm.py
- ositran_data.py
- alertas_sutran.py

## God Nodes (most connected - your core abstractions)
1. `RiesgoIndex` - 16 edges
2. `analizar()` - 14 edges
3. `main()` - 11 edges
4. `Matriz Técnica SIPAT — Inventario de Datos (Fase 0)` - 11 edges
5. `3. Fichas detalladas` - 11 edges
6. `_load()` - 10 edges
7. `SIPAT — Informe Final de Análisis de Siniestralidad Vial en Perú` - 9 edges
8. `get_alertas()` - 8 edges
9. `reporte()` - 8 edges
10. `10. Fase 2 — Módulo "Ruta segura" (nuevas fuentes y arquitectura)` - 8 edges

## Surprising Connections (you probably didn't know these)
- `alertas()` --calls--> `get_alertas()`  [INFERRED]
  api/app.py → scripts/alertas_sutran.py
- `analizar_ruta()` --calls--> `analizar()`  [INFERRED]
  dashboard/app.py → scripts/ruta_segura.py
- `health()` --calls--> `get_index()`  [INFERRED]
  api/app.py → scripts/riesgo_red.py
- `ruta_segura()` --calls--> `analizar()`  [INFERRED]
  api/app.py → scripts/ruta_segura.py
- `ruta_segura()` --calls--> `resumen_analisis()`  [INFERRED]
  api/app.py → scripts/ruta_segura.py

## Import Cycles
- None detected.

## Communities (35 total, 16 thin omitted)

### Community 0 - "geocode.py"
Cohesion: 0.07
Nodes (26): LineString, Construye el dataset espacial de analisis: 1. data/processed/tramos_red.csv :…, Valida interpolacion km->punto contra CGM (coords + progresiva), y genera…, project_to_km(), Diagnostico: km real del punto proyectado sobre la ruta vs PROGRESIVA., Devuelve el km aproximado del punto proyectado sobre la ruta., Feature engineering: sinuosidad por tramo y dataset listo para modelar., haversine_km() (+18 more)

### Community 1 - "ruta_segura.py"
Cohesion: 0.09
Nodes (34): alertas(), health(), API FastAPI del modulo 'Ruta segura'. Endpoints: POST /ruta_segura {origin,…, ruta_segura(), RutaRequest, BaseModel, get, post (+26 more)

### Community 2 - "audit_extra.py"
Cohesion: 0.33
Nodes (4): DataFrame, load_csv(), Path, Auditoria corregida: sep automatico + ONSV por hojas + red vial.

### Community 3 - "dashboard/app.py"
Cohesion: 0.29
Nodes (4): cache_data, analizar_ruta(), load(), Dashboard SIPAT — Siniestralidad Vial en la Red Vial Nacional de Perú + Ruta…

### Community 4 - "audit.py"
Cohesion: 0.60
Nodes (4): audit(), detect_encoding(), detect_sep(), Auditoría técnica de un archivo de datos: estructura, calidad y cobertura.

### Community 5 - "audit_all_raw.py"
Cohesion: 0.40
Nodes (3): load(), Path, Reaudita todos los archivos crudos y escribe reporte UTF-8 en docs/auditorias.

### Community 6 - "ckan_api.py"
Cohesion: 0.40
Nodes (3): Lista los recursos de un dataset del portal Datos Abiertos vía API CKAN., La URL directa puede dar 404; se extrae del HTML de la página del recurso., resource_download_url()

### Community 8 - "Módulo "Ruta segura" — Manual"
Cohesion: 0.12
Nodes (16): 1.1 Fórmula de riesgo, 1.2 Motor v2 — factor temporal y perfil por segmento, 1. Arquitectura, 2.1 Grafo de ruteo (una vez por versión de OSM), 2.2 Datos OSITRAN (una vez, o con `--raw` para re-descargar), 2. Instalación, 3. Uso, 4. Casos de uso verificados (+8 more)

### Community 9 - "download_ingemmet.py"
Cohesion: 0.67
Nodes (3): download_layer(), layer_info(), Descarga las capas de INGEMMET por rangos de OBJECTID y las guarda como GeoJSON.

### Community 11 - "RiesgoIndex"
Cohesion: 0.14
Nodes (13): aadt_peajes(), _haversine(), Puntos sinteticos sobre corredores concesionados (accidentes OSITRAN).…, Indices de accidentes dentro del buffer de la ruta., Lista de accidentes (dicts) dentro del buffer, para mapas., Indices de alertas historicas dentro del buffer de la ruta., Score local por tramos de ~segment_km a lo largo de la ruta. Devuelve lista de…, Peajes con trafico vehicular (OSITRAN) como senal de exposicion. Guarda lat/lon… (+5 more)

### Community 23 - "3. Fichas detalladas"
Cohesion: 0.07
Nodes (26): 1. Resumen ejecutivo, 2. Tabla consolidada, 3.10 INGEMMET — Peligros Geológicos (ArcGIS REST), 3.1 SUTRAN — Accidentes en Carreteras 2020–2021 (TARGET 1), 3.2 SUTRAN — Reportes preliminares CGM 2020–2021 (TARGET 2), 3.3 ONSV — Siniestros de Tránsito Fatales 2021–2025 (TARGET PRINCIPAL), 3.4 ONSV — Histórico 2008–2025, 3.5 MTC — Red Vial SINAC 2022–2024 (+18 more)

### Community 25 - "SIPAT — Informe Final de Análisis de Siniestralidad Vial en Perú"
Cohesion: 0.10
Nodes (20): 1. Resumen ejecutivo, 2. Datos y metodología, 3.1 Magnitud y tendencia, 3.2 Tipología, 3.3 Geografía, 3. Hallazgos descriptivos, 4. Modelo de riesgo por tramo (NegBin), 5. Limitaciones (+12 more)

### Community 26 - "10. Fase 2 — Módulo "Ruta segura" (nuevas fuentes y arquitectura)"
Cohesion: 0.25
Nodes (8): 10.1 Fuentes nuevas investigadas (validado el 13/08/2026), 10.2 Arquitectura del módulo, 10.3 Scripts nuevos, 10.4 Base de conocimiento (Graphify + Obsidian), 10.4a Señal histórica de alertas, 10.5 Manual del módulo, 10.6 Validación motor v2 y entregas (13/08/2026), 10. Fase 2 — Módulo "Ruta segura" (nuevas fuentes y arquitectura)

### Community 27 - "OSRMClient"
Cohesion: 0.32
Nodes (3): OSRMClient, Cliente HTTP para el router OSRM local (localhost:5000, perfil car). Uso desde…, coords: [(lon,lat), ...]; devuelve lista de dicts de rutas.

### Community 28 - "osrm_build.py"
Cohesion: 0.60
Nodes (5): build(), _docker(), main(), Construye y levanta el router OSRM (perfil car) para Peru en Docker. Uso:…, serve()

### Community 29 - "graphify_obsidian.py"
Cohesion: 0.67
Nodes (3): main(), Genera un vault Obsidian desde graphify-out/graph.json para visualizar el…, slug()

### Community 33 - "ositran_data.py"
Cohesion: 0.23
Nodes (15): _cargar_cache(), _coords_por_token(), _dentro_peru(), _extremos(), _guardar_cache(), _int(), _len_km(), _load_peajes() (+7 more)

### Community 34 - "alertas_sutran.py"
Cohesion: 0.19
Nodes (14): alertas_en_ruta(), _archivar(), _dist_km(), _fetch(), get_alertas(), get_historico(), _motivo(), normalizar() (+6 more)

## Knowledge Gaps
- **58 isolated node(s):** `graphify`, `Estado del proyecto (SIPAT)`, `1. Resumen ejecutivo`, `Pipeline de geocodificación (SUTRAN)`, `3.1 Magnitud y tendencia` (+53 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RiesgoIndex` connect `RiesgoIndex` to `ruta_segura.py`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `get_index()` connect `ruta_segura.py` to `RiesgoIndex`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `analizar()` connect `ruta_segura.py` to `OSRMClient`, `alertas_sutran.py`, `dashboard/app.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `analizar()` (e.g. with `ruta_segura()` and `analizar_ruta()`) actually correct?**
  _`analizar()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify`, `Estado del proyecto (SIPAT)`, `1. Resumen ejecutivo` to the rest of the system?**
  _58 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `geocode.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07152496626180836 - nodes in this community are weakly interconnected._
- **Should `ruta_segura.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09246088193456614 - nodes in this community are weakly interconnected._