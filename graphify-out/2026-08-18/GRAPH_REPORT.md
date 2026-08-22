# Graph Report - SIPAT  (2026-08-14)

## Corpus Check
- 70 files · ~9,757,290 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 391 nodes · 563 edges · 40 communities (24 shown, 16 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- geocode.py
- reporte_ruta.py
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
- verificar_proyecto.py
- ruta_segura.py
- osrm_build.py
- graphify_obsidian.py
- AGENTS.md
- graphify.js
- download_osm.py
- ositran_data.py
- alertas_sutran.py
- boot_services.py
- OSRMClient
- arrancar_servicios.ps1
- opencode.json

## God Nodes (most connected - your core abstractions)
1. `analizar()` - 19 edges
2. `RiesgoIndex` - 16 edges
3. `ruta_segura_completa()` - 11 edges
4. `main()` - 11 edges
5. `reporte_desde_resumen()` - 11 edges
6. `Matriz Técnica SIPAT — Inventario de Datos (Fase 0)` - 11 edges
7. `3. Fichas detalladas` - 11 edges
8. `emergencias_coen()` - 10 edges
9. `_load()` - 10 edges
10. `_xy()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `alertas()` --calls--> `get_alertas()`  [INFERRED]
  api/app.py → scripts/alertas_sutran.py
- `ruta_segura_completa()` --calls--> `avisos_en_ruta()`  [INFERRED]
  api/app.py → scripts/clima.py
- `ruta_segura_completa()` --calls--> `avisos_senamhi()`  [INFERRED]
  api/app.py → scripts/clima.py
- `ruta_segura_completa()` --calls--> `emergencias_coen()`  [INFERRED]
  api/app.py → scripts/clima.py
- `ruta_segura_completa()` --calls--> `emergencias_en_ruta()`  [INFERRED]
  api/app.py → scripts/clima.py

## Import Cycles
- None detected.

## Communities (40 total, 16 thin omitted)

### Community 0 - "geocode.py"
Cohesion: 0.07
Nodes (26): LineString, Construye el dataset espacial de analisis: 1. data/processed/tramos_red.csv :…, Valida interpolacion km->punto contra CGM (coords + progresiva), y genera…, project_to_km(), Diagnostico: km real del punto proyectado sobre la ruta vs PROGRESIVA., Devuelve el km aproximado del punto proyectado sobre la ruta., Feature engineering: sinuosidad por tramo y dataset listo para modelar., haversine_km() (+18 more)

### Community 1 - "reporte_ruta.py"
Cohesion: 0.15
Nodes (27): avisos(), _anillos(), _avisos_cerca_puntos(), avisos_en_ruta(), avisos_senamhi(), _cached(), _clasificar_tipo(), _descargar() (+19 more)

### Community 2 - "audit_extra.py"
Cohesion: 0.33
Nodes (4): DataFrame, load_csv(), Path, Auditoria corregida: sep automatico + ONSV por hojas + red vial.

### Community 3 - "dashboard/app.py"
Cohesion: 0.25
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
Cohesion: 0.10
Nodes (19): 1.1 Fórmula de riesgo, 1.2 Motor v2 — factor temporal y perfil por segmento, 1.3 Capa predictiva — modelo NegBin aplicado a la ruta (`prediccion.py`), 1.4 Clima y emergencias (`clima.py`), 1.5 Accidentes con descripción y popups, 1. Arquitectura, 2.1 Grafo de ruteo (una vez por versión de OSM), 2.2 Datos OSITRAN (una vez, o con `--raw` para re-descargar) (+11 more)

### Community 9 - "download_ingemmet.py"
Cohesion: 0.67
Nodes (3): download_layer(), layer_info(), Descarga las capas de INGEMMET por rangos de OBJECTID y las guarda como GeoJSON.

### Community 11 - "RiesgoIndex"
Cohesion: 0.09
Nodes (23): _features(), _fit(), get_predictor(), Capa predictiva: modelo NegBin de Fase 1 aplicado a rutas OSRM. -…, Tasa predictiva (siniestros/km) para cada punto muestreado de la ruta., Riesgo predictivo del modelo NegBin a lo largo de una ruta. Devuelve tasa media…, Replica la especificacion de features de Fase 1 (modelo_glm.py)., Entrena NegBin (Fase 1) y devuelve (modelo, pred por tramo). (+15 more)

### Community 23 - "3. Fichas detalladas"
Cohesion: 0.06
Nodes (34): 10.1 Fuentes nuevas investigadas (validado el 13/08/2026), 10.2 Arquitectura del módulo, 10.3 Scripts nuevos, 10.4 Base de conocimiento (Graphify + Obsidian), 10.4a Señal histórica de alertas, 10.5 Manual del módulo, 10.6 Validación motor v2 y entregas (13/08/2026), 10. Fase 2 — Módulo "Ruta segura" (nuevas fuentes y arquitectura) (+26 more)

### Community 25 - "SIPAT — Informe Final de Análisis de Siniestralidad Vial en Perú"
Cohesion: 0.10
Nodes (20): 1. Resumen ejecutivo, 2. Datos y metodología, 3.1 Magnitud y tendencia, 3.2 Tipología, 3.3 Geografía, 3. Hallazgos descriptivos, 4. Modelo de riesgo por tramo (NegBin), 5. Limitaciones (+12 more)

### Community 26 - "verificar_proyecto.py"
Cohesion: 0.21
Nodes (15): check_api_endpoints(), check_dashboard_apptest(), check_data_assets(), check_docs(), check_exports(), check_graph(), check_port(), check_reports() (+7 more)

### Community 27 - "ruta_segura.py"
Cohesion: 0.09
Nodes (38): alertas(), health(), _nivel(), API FastAPI del modulo 'Ruta segura'. Endpoints: POST /ruta_segura {origin,…, ruta_segura(), ruta_segura_completa(), RutaRequest, BaseModel (+30 more)

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

### Community 35 - "boot_services.py"
Cohesion: 0.57
Nodes (7): main(), read_log_tail(), start_api(), start_osrm(), start_streamlit(), test_port(), wait_port()

### Community 36 - "OSRMClient"
Cohesion: 0.32
Nodes (3): OSRMClient, Cliente HTTP para el router OSRM local (localhost:5000, perfil car). Uso desde…, coords: [(lon,lat), ...]; devuelve lista de dicts de rutas.

### Community 37 - "arrancar_servicios.ps1"
Cohesion: 0.70
Nodes (4): Start-API(), Start-OSRM(), Start-Streamlit(), Test-Port()

### Community 38 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

## Knowledge Gaps
- **63 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `graphify`, `Estado del proyecto (SIPAT)`, `1. Resumen ejecutivo` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `avisos_en_ruta()` connect `reporte_ruta.py` to `geocode.py`, `ruta_segura.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `analizar()` connect `ruta_segura.py` to `reporte_ruta.py`, `alertas_sutran.py`, `dashboard/app.py`, `OSRMClient`, `RiesgoIndex`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `analizar()` (e.g. with `ruta_segura()` and `ruta_segura_completa()`) actually correct?**
  _`analizar()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `ruta_segura_completa()` (e.g. with `avisos_en_ruta()` and `avisos_senamhi()`) actually correct?**
  _`ruta_segura_completa()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `graphify` to the rest of the system?**
  _63 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `geocode.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07152496626180836 - nodes in this community are weakly interconnected._
- **Should `reporte_ruta.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1477832512315271 - nodes in this community are weakly interconnected._