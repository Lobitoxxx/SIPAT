## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Estado del proyecto (SIPAT)

Objetivo: analítica de siniestralidad vial en la Red Vial Nacional de Perú + módulo de "ruta segura".

Completado:
- Fase 0 (inventario de datos) y Fase 1 (geocodificación lineal por km, dataset espacial, modelo NegBin con IRRs, 12 puntos negros, 6 figuras).
- Datasets procesados en `data/processed/` (`tramos_red.csv`, `onsv_nacional_geocod.csv` 5,014, `sutran_accidentes_geocod.csv` 7,656, `dataset_modelo.csv` 3,750x40, `puntos_negros.csv`, `features_distancia.csv`).
- Dashboard Streamlit en `dashboard/app.py` (6 pestañas rediseñadas; datos ligeros en `data/processed/dashboard/`).
- Informes: `docs/informe_sipat.md`, `docs/matriz_tecnica.md`; figuras en `docs/figuras/`.

En curso (mejoras del módulo "ruta segura"):
- Motor v1 terminado y validado: `download_osm.py`, `osrm_build.py`, `osrm_router.py`, `riesgo_red.py`, `alertas_sutran.py`, `ruta_segura.py`, pestaña "Ruta segura" en el dashboard.
- Integrado: alertas históricas SUTRAN (archivo acumulativo `sutran_alertas_historico.json` como señal de zonas de incidentes recurrentes) y datos OSITRAN (`ositran_data.py`: 71 tramos geocodificados/16,943 accidentes + 55 peajes con tráfico) como capa espacial del índice de riesgo.
- Manual del módulo: `docs/modulo_ruta_segura.md`.
- Mejoras completadas (13/08/2026): **motor v2** (`riesgo_red.factor_temporal(dt)` + `perfil_segmentos()`; `analizar(..., salida=)` y `resumen_analisis()` en `ruta_segura.py`), **API FastAPI** (`api/app.py`, uvicorn :8000, POST `/ruta_segura` + `/health` + `/alertas`), **reporte HTML estático** (`scripts/reporte_ruta.py`, autocontenido), **rediseño integral del dashboard** (`dashboard/app.py`: 6 pestañas coherentes, panel Ruta segura con salida, perfil de riesgo Plotly y alertas filtrables), **tráfico OSITRAN en el score** (`trafico_km = Σ min(AADT/100 000, 0.5)` por peaje a ≤15 km).
- Mejoras completadas (13/08/2026, tarde): **producto "Prevención antes de viajar"** — (1) accidentes con descripción + popups clicables en el mapa (`riesgo_red._load_onsv/_load_sutran/_load_ositran` enriquecidos; `ruta_segura._popup_accidente()`); (2) **capa predictiva** `scripts/prediccion.py` (NegBin de Fase 1 re-entrenado con statsmodels, `predecir_ruta` empalma ruta→tramos con cKDTree, `tipos_incidente` = "¿qué puede pasar?"); (3) **clima y emergencias** `scripts/clima.py` (avisos SENAMHI WFS `idesep.senamhi.gob.pe/geoserver/g_prono_pp_24h/ows` + pronóstico Open-Meteo + emergencias COEN del portal `portal.indeci.gob.pe/emergencias/`, geocodificadas; caches con TTL); (4) pestaña "Antes de salir" con dos indicadores (histórico y predictivo Bajo/Medio/Alto), mapa full-width, sección clima/avisos/COEN con botón "Actualizar clima ahora" y **botón Generar reporte HTML**; (5) API ampliada (`POST /ruta_segura_completa` con `resumen_riesgo`+`clima`, `GET /avisos`); (6) reporte con secciones nuevas (`_tipos_html/_prediccion_html/_clima_html`, `reporte_desde_resumen()`).
- Verificado: API `/ruta_segura_completa` Lima→Huancayo → histórico 8.51 (Alto), predictivo 0.67 sini/km (Medio, cov 42%), pronóstico -6.7–23.4 °C, 3 avisos SENAMHI en ruta, sismo COEN a 9 km; AppTest clic "Calcular" → 0 excepciones.
- Mejoras completadas (22/08/2026): **rediseño moderno del dashboard + reportes ciudadanos**.
  - Dashboard modularizado: `dashboard/app.py` (orquestador) + `theme.py` (CSS moderno Inter/gradiente indigo, cards, pills de riesgo, banners, hero) + `viaja_seguro.py` (pestaña principal) + `reporta.py` (ciudadana) + `analitica.py` (mapa/puntos/tendencias) + `modelo_tab.py` (rutas críticas/modelo). 7 pestañas: 🧭 Viaja seguro · 📣 Reporta · 🗺️ Mapa nacional · ⚠️ Puntos negros · 📈 Tendencias · 🏆 Rutas críticas · 📊 Modelo.
  - "Viaja seguro" como producto principal: pills de rutas populares (Lima→Huancayo etc.), cards KPI (distancia/riesgo histórico/riesgo IA/ruta más segura/accidentes en ruta), banner de riesgo semáforo, mapa full-width con popups, perfil km a km, clima/SENAMHI/COEN, reportes ciudadanos cercanos a la ruta y reporte HTML descargable.
  - **Reportes ciudadanos**: `scripts/reportes_ciudadanos.py` (`agregar_reporte` con validación Perú+dedupe 10 min, `listar_reportes`, `reportes_en_ruta`, `punto_en_km`, `estadisticas`); storage append-only `data/processed/dashboard/reportes_ciudadanos.json` + fotos en `reportes_fotos/`; pestaña Reporta permite foto (PNG/JPG), tipo/severidad/descripción, ubicación por km-slider de la ruta calculada o referencia geocodificada; mapa de reportes con fotos embebidas base64 en popups; API `GET/POST /reportes`.
  - Verificación: AppTest 7 tabs + "Analizar mi ruta" → 0 excepciones; batería completa 30/30 PASS.
- Mejoras completadas (22/08/2026, tarde): **contraste de fuentes + README**.
  - `dashboard/theme.py`: sidebar ya no fuerza texto claro en widgets (inputs/selects/chips con texto oscuro explícito); secundarios oscurecidos (`.sub`/.mini-note #64748b, `.lbl` #475569); banners con color de texto temático; métricas y tabs inactivas con contraste explícito; captions #475569.
  - `README.md` nuevo en raíz: qué es SIPAT, 7 pestañas + tabla de endpoints API, fuentes de datos con volúmenes reales, pipeline completo (geocodificación lineal → dataset 3750×40 → multi-fuente/puntos negros/NegBin), fórmula del score_km con umbrales y factor temporal, estructura de carpetas, puesta en marcha, verificación 30 checks, decisiones metodológicas y limitaciones. Red vial = ~28,900 km.
- Mejoras completadas (22/08/2026, noche): **tema claro fijado + README con Mermaid**.
  - `.streamlit/config.toml`: base="light", primaryColor #4f46e5, textColor #0f172a — ningún widget puede invertirse a oscuro.
  - `dashboard/theme.py` ronda 2: ticks del slider del sidebar en claro (#cbd5e1), placeholders #475569, headings/enlaces/dataframe/expander con contraste explícito, estilo_plotly con title_font y tickfont coloreados.
  - README: diagrama ASCII del pipeline reemplazado por mermaid flowchart (fuentes→ingesta→procesos→servicios) + sequenceDiagram del flujo "Viaja seguro" + flowchart del reporte ciudadano.
  - Repo publicado en GitHub: https://github.com/Lobitoxxx/SIPAT (rama main; .gitignore excluye data/raw/ OSM 2.5GB, caches, reportes ciudadanos por privacidad).
- Pendiente: nada urgente; próximas ideas = tráfico OSITRAN en el score (hecho), rediseño del grafo, exportaciones.

## Documentación reciente (22/09/2026)

- **Diagrams-visuals**: 4 diagramas Archify interactivos en `docs/archify/` (`sipat-architecture.html`, `sipat-dataflow.html`, `sipat-sequence.html`, `sipat-workflow.html`), enlazados desde el README (sección 4) con preview vía htmlpreview.github.io. Generados con la CLI global de Archify; los candidatos JSON se editan en `Temp\opencode\archify-candidates\` y se entregan con `archify.mjs deliver <type> <json> <out.html> --quality showcase`.
- **README** (sección 4 y 5): nueva narrativa de arquitectura (topología en estrella con la API FastAPI como hub y sus justificaciones) y metodología SCRUM + CRISP-DM (6 fases mapeadas + gantt de 3 sprints). Secciones reordenadas (1-10).
- Detalles de validación Archify (para próximos diagramas): labels 7px+ (no dejar que subetiquetas bajen de 7px si `viewBox` > ~1080); los retornos largos con etiqueta automática inflan el ancho → usar `labelAt`/`fromSide:top` para mantener `viewBox` ≤ ~1080; los edges que cruzan lane-bandas de phases/groups no pasan `readable-v2` (routes cross-lane requieren columnas con hueco ≥ 56px o misma columna sin group).

Convenciones del entorno:
- Windows/PowerShell. La consola muestra ~1 linea de stdout por llamada: redirigir a archivo UTF-8 (`*> file.log`) y leerlo.
- Procesos largos: `Start-Process -FilePath python ... -WindowStyle Hidden` (sobreviven entre comandos).
- Cliente OSRM local: `localhost:5000` (Docker). Alertas SUTRAN: `gis.sutran.gob.pe/alerta_sutran/script_cgm/carga_xlsx.php?tipo=MAPA`.
- Rutas clave del grafo de conocimiento: god nodes `_load()`, `locate()`, `route_geometry()`, `haversine_km()`, `audit()` (ver `graphify-out/GRAPH_REPORT.md`).
