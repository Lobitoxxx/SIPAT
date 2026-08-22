# Graph Report - SIPAT  (2026-08-22)

## Corpus Check
- 82 files · ~7,536,863 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 446 nodes · 664 edges · 42 communities (26 shown, 16 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 32 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- geocode.py
- api/app.py
- audit_extra.py
- render
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
- reportes_ciudadanos.py
- arrancar_servicios.ps1
- opencode.json
- modelo_multi.py

## God Nodes (most connected - your core abstractions)
1. `analizar()` - 19 edges
2. `RiesgoIndex` - 17 edges
3. `render()` - 16 edges
4. `reporte_desde_resumen()` - 12 edges
5. `ruta_segura_completa()` - 11 edges
6. `emergencias_coen()` - 11 edges
7. `main()` - 11 edges
8. `Matriz Técnica SIPAT — Inventario de Datos (Fase 0)` - 11 edges
9. `3. Fichas detalladas` - 11 edges
10. `avisos_senamhi()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `health()` --calls--> `get_index()`  [INFERRED]
  api/app.py → scripts/riesgo_red.py
- `alertas()` --calls--> `get_alertas()`  [INFERRED]
  api/app.py → scripts/alertas_sutran.py
- `ruta_segura()` --calls--> `analizar()`  [INFERRED]
  api/app.py → scripts/ruta_segura.py
- `ruta_segura()` --calls--> `resumen_analisis()`  [INFERRED]
  api/app.py → scripts/ruta_segura.py
- `ruta_segura_completa()` --calls--> `analizar()`  [INFERRED]
  api/app.py → scripts/ruta_segura.py

## Import Cycles
- None detected.

## Communities (42 total, 16 thin omitted)

### Community 0 - "geocode.py"
Cohesion: 0.07
Nodes (26): LineString, Construye el dataset espacial de analisis: 1. data/processed/tramos_red.csv :…, Valida interpolacion km->punto contra CGM (coords + progresiva), y genera…, project_to_km(), Diagnostico: km real del punto proyectado sobre la ruta vs PROGRESIVA., Devuelve el km aproximado del punto proyectado sobre la ruta., Feature engineering: sinuosidad por tramo y dataset listo para modelar., haversine_km() (+18 more)

### Community 1 - "api/app.py"
Cohesion: 0.12
Nodes (32): alertas(), avisos(), health(), _nivel(), API FastAPI del modulo 'Ruta segura'. Endpoints: POST /ruta_segura {origin,…, ReporteRequest, reportes_add(), reportes_list() (+24 more)

### Community 2 - "audit_extra.py"
Cohesion: 0.33
Nodes (4): DataFrame, load_csv(), Path, Auditoria corregida: sep automatico + ONSV por hojas + red vial.

### Community 3 - "render"
Cohesion: 0.13
Nodes (23): _color_ramp(), Pestañas analíticas: Mapa nacional, Puntos negros y Tendencias., tab_mapa(), tab_tendencias(), load(), cache_data, Dashboard SIPAT — Prevención antes de viajar + analítica de siniestralidad vial…, Pestañas Rutas críticas y Modelo NegBin. (+15 more)

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
Cohesion: 0.08
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
Cohesion: 0.08
Nodes (39): export_route(), main(), OSRMClient, Cliente HTTP para el router OSRM local (localhost:5000, perfil car). Uso desde…, coords: [(lon,lat), ...]; devuelve lista de dicts de rutas., Composicion historica de los accidentes en el buffer de la ruta., tipos_incidente(), _alertas_html() (+31 more)

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

### Community 36 - "reportes_ciudadanos.py"
Cohesion: 0.14
Nodes (20): foto_b64(), mapa_reportes(), Pestaña «Reporta un incidente»: reportes ciudadanos con foto y contexto., Devuelve (lat, lon) según la ruta calculada o None., render(), _ubicacion_actual(), agregar_reporte(), estadisticas() (+12 more)

### Community 37 - "arrancar_servicios.ps1"
Cohesion: 0.70
Nodes (4): Start-API(), Start-OSRM(), Start-Streamlit(), Test-Port()

### Community 38 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 40 - "modelo_multi.py"
Cohesion: 0.40
Nodes (5): build_features(), fit_model(), main(), Construye features dummy + transformaciones log (matching Fase 1)., Ajusta NegBin y devuelve resultados.

## Knowledge Gaps
- **63 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `graphify`, `Estado del proyecto (SIPAT)`, `1. Resumen ejecutivo` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `avisos_en_ruta()` connect `api/app.py` to `geocode.py`, `ruta_segura.py`, `render`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `analizar()` connect `ruta_segura.py` to `RiesgoIndex`, `api/app.py`, `alertas_sutran.py`, `render`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `analizar()` (e.g. with `ruta_segura()` and `ruta_segura_completa()`) actually correct?**
  _`analizar()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `render()` (e.g. with `_set_pop()` and `avisos_en_ruta()`) actually correct?**
  _`render()` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `ruta_segura_completa()` (e.g. with `avisos_en_ruta()` and `avisos_senamhi()`) actually correct?**
  _`ruta_segura_completa()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `graphify` to the rest of the system?**
  _63 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `geocode.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07152496626180836 - nodes in this community are weakly interconnected._