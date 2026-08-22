# Módulo "Ruta segura" — Manual

Planificador de viajes que compara rutas alternativas entre dos puntos del Perú
según **riesgo histórico** (accidentes geocodificados con descripción y popups),
**riesgo predictivo** (modelo NegBin de Fase 1 aplicado a la ruta), **clima y
avisos** (SENAMHI + INDECI/COEN + Open-Meteo), **incidentes en vivo** (SUTRAN) y
**tiempo/distancia**, recomendando la ruta más segura, la más rápida y la más
corta. Su objetivo es la **prevención antes de viajar**: el conductor revisa,
antes de partir, qué puede encontrar en el camino.

## 1. Arquitectura

| Componente | Script / Servicio | Rol |
|---|---|---|
| Red vial + ruteo | **OSRM self-hosted** (Docker, perfil `car`, MLD) sobre OSM de Perú | Calcula hasta 3 alternativas entre cualquier par de puntos del país |
| Geocodificación | Photon (`photon.komoot.io`) con fallback Nominatim | Convierte texto o `lat,lon` en coordenadas |
| Riesgo histórico | `scripts/riesgo_red.py` (scipy cKDTree) | Índice espacial de 18,807 puntos: ONSV 5,014 + SUTRAN 7,656 + OSITRAN 6,137 (sintéticos sobre corredores concesionados); cada punto lleva descripción (fecha, tipo, causa, clima…) |
| Riesgo predictivo | `scripts/prediccion.py` (statsmodels NegBin) | Re-entrena el NegBin de Fase 1 (3,750 tramos) y empalma la ruta OSRM a los tramos modelados (cKDTree) → siniestros/km esperados y cobertura de red |
| Clima y avisos | `scripts/clima.py` | Avisos SENAMHI 24h (WFS), pronóstico Open-Meteo, emergencias INDECI/COEN (portal, 7 días) — caché con TTL |
| Alertas históricas | `scripts/alertas_sutran.py` (archivo acumulativo) | Zonas de incidentes recurrentes archivadas en `sutran_alertas_historico.json` |
| Alertas en vivo | `scripts/alertas_sutran.py` (caché TTL 15 min) | Estado actual de la red (normal/restringido/interrumpido) con motivo, KM y ubigeo |
| Motor | `scripts/ruta_segura.py` | Orquesta geocoding → rutas → scoring → predicción → ranking → mapa folium (con popups) |
| Reporte | `scripts/reporte_ruta.py` | Reporte HTML autocontenido (mapa + perfil + tipos + predicción + clima + alertas) |
| API | `api/app.py` | FastAPI en :8000 (rutas, viaje completo, alertas, avisos) |
| Datos OSITRAN | `scripts/ositran_data.py` | Accidentes (16 concesiones) y tráfico vehicular por peaje (PNDA) |
| Capa OSM | `scripts/download_osm.py` + `scripts/osrm_build.py` | Descarga `peru-latest.osm.pbf` (~243 MB) y construye el grafo de ruteo |

### 1.1 Fórmula de riesgo
```
score_km = (n + 0.5 * gravedad_ponderada) / km  +  alertas_hist_km  +  trafico_km
```
- `n`: puntos de accidente dentro de ±1 km del trayecto (ONSV + SUTRAN + OSITRAN).
- `gravedad_ponderada = Σ (fallecidos×3 + lesionados×1 + 1)`.
- `alertas_hist_km`: alertas SUTRAN archivadas en el buffer, ponderadas por estado
  (interrumpido ×2, restringido ×1, normal ×0.3).
- `trafico_km`: exposición vehicular (AADT, veh/día, último año OSITRAN por peaje):
  `Σ min(AADT/100 000, 0.5)` para peajes a ≤15 km del trayecto (señal de corredores
  de alto tránsito, sin dominar el score).
- Penalización en vivo (se suma al score): interrumpido **+5**, restringido **+1**
  por alerta dentro de ±2 km.

### 1.2 Motor v2 — factor temporal y perfil por segmento
- `riesgo_red.factor_temporal(dt)`: pondera el score según la hora/día de salida.
  Sábado ×1.25, domingo ×1.1, noche (19–5h) ×1.3, madrugada (5–8h) ×1.05.
  Se aplica sobre `score_km` antes de sumar penalizaciones:
  `score_km_penalizado = score_km × factor + Σ penalizaciones`.
- `riesgo_red.perfil_segmentos(geometry, segment_km=5.0)`: divide la geometría en
  tramos de 5 km y devuelve el `score_km` de cada uno → **perfil de riesgo** a lo
  largo del trayecto (visualizado en dashboard y reporte).
- `ruta_segura.analizar(origin, dest, salida="YYYY-MM-DD HH:MM")` incorpora ambos:
  la salida se traduce a `factor_temporal` y cada ruta devuelve su `perfil`.
- `ruta_segura.resumen_analisis()`: serializa el resultado para consumidores JSON
  (API/reporte), con hasta 500 accidentes históricos por ruta.

### 1.3 Capa predictiva — modelo NegBin aplicado a la ruta (`prediccion.py`)
- `RiesgoPredictivo` re-entrena el NegBin de Fase 1 sobre `dataset_modelo.csv`
  (3,750 tramos; misma especificación que `modelo_glm.py`) y guarda la **tasa
  esperada por km** (`pred / longitud`) por tramo.
- `predecir_ruta(geometry)`: muestrea la ruta OSRM cada 500 m, empalma cada punto
  al tramo modelado más cercano (cKDTree, umbral 2 km) y devuelve:
  `pred_siniestros_km` (media), `cobertura_pct` (fracción de la ruta cubierta por
  la red modelada) y la tasa por segmentos de 5 km (alineado al perfil).
- Es el **riesgo predictivo**, independiente del score histórico (se muestra como
  segundo indicador Bajo/Medio/Alto en el dashboard y la API).
- `tipos_incidente(accidentes)`: composición de los accidentes históricos en el
  buffer → **"¿qué puede pasar?"** (top tipos, causas y climas + fallecidos/heridos).

### 1.4 Clima y emergencias (`clima.py`)
- `avisos_senamhi()`: avisos meteorológicos de 24 h del **WFS público de SENAMHI**
  (`idesep.senamhi.gob.pe/geoserver/g_prono_pp_24h/ows`), geometrías MultiPolygon
  con nivel (1/2/3). Caché 1 h.
- `avisos_en_ruta(avisos, geometry, buffer_km=5)`: intersección con shapely.
- `pronostico_openmeteo(geometry)`: pronóstico **Open-Meteo** (sin API key) en
  1–4 puntos del trayecto → temp. min/máx, probabilidad de lluvia, viento. Caché
  1 h por ruta.
- `emergencias_coen()`: reportes de emergencia de los últimos 7 días del **portal
  INDECI/COEN** (títulos parseados: tipo + distrito + departamento, geocodificados
  con Photon/Nominatim). Caché 6 h. `emergencias_en_ruta()` filtra por proximidad.

### 1.5 Accidentes con descripción y popups
Los tres cargadores de `riesgo_red.py` (`_load_onsv/_load_sutran/_load_ositran`)
ahora incluyen campos descriptivos:
- **ONSV**: fecha y hora del siniestro, clase, ruta (PE-1N…), km de red,
  departamento/provincia/distrito, condición climática, causa principal y
  específica, superficie de calzada, tipo de vía, red vial.
- **SUTRAN**: fecha (`yyyymmdd`→`dd/mm/yyyy`), modalidad (despiste/choque/atropello…),
  departamento, código de vía, kilómetro.
- **OSITRAN**: moda del tramo (tipo/causa/clima) más total de accidentes, distribuida
  en los puntos sintéticos.

`ruta_segura._popup_accidente()` construye el HTML del popup (fuente, fecha, tipo,
ubicación, gravedad, causa, entorno) y `mapa()` lo asocia a cada punto: en el mapa
del dashboard y del reporte **el usuario hace clic en un accidente y lee su
descripción**.

## 2. Instalación

Requisitos: Python 3.10+, Docker (para OSRM), paquetes `pandas`, `numpy`,
`scipy`, `folium`, `streamlit`, `fastapi` (opcional, API), `uvicorn`.

```
pip install pandas numpy scipy folium streamlit fastapi uvicorn
```

### 2.1 Grafo de ruteo (una vez por versión de OSM)
```
python scripts/download_osm.py          # descarga peru-latest.osm.pbf (~243 MB)
python scripts/osrm_build.py --all      # extract + partition + customize
python scripts/osrm_build.py --serve    # inicia osrm-routed en localhost:5000
```

### 2.2 Datos OSITRAN (una vez, o con `--raw` para re-descargar)
```
python scripts/ositran_data.py
```
Produce `data/processed/ositran_accidentes.csv`, `ositran_trafico.csv`,
`ositran_tramos_geocod.csv` (71 tramos con coordenadas; 16,943 accidentes) y
`ositran_peajes_geo.json` (55 peajes con tráfico 2019–2025).

## 3. Uso

### CLI
```
python scripts/ruta_segura.py "Lima" "Huancayo"                 # ranking + mapa HTML
python scripts/ruta_segura.py "Lima" "Huancayo" --json          # solo JSON
python scripts/ruta_segura.py "Lima" "Huancayo" --salida "2026-08-15 19:30"  # con factor temporal
python scripts/ruta_segura.py "-12.046,-77.028" "-12.065,-75.204"  # coords directas
python scripts/ruta_segura.py "Jauja" "Pichanaqui" --out out/ruta.html
```

### API (FastAPI)
```
uvicorn api.app:app --port 8000        # http://127.0.0.1:8000
curl -X POST http://127.0.0.1:8000/ruta_segura \
  -H "Content-Type: application/json" \
  -d '{"origin":"Trujillo","dest":"Chiclayo","salida":"2026-08-15 19:30"}'
```
Respuesta: origen/destino geocodificados, `factor_temporal`, `salida`, `ranking`
(segura/rápida/corta), y por ruta: km, minutos, `score_km_penalizado`, perfil por
segmentos, **predicción NegBin** (`prediccion`) y **tipos de incidente**
(`tipos_incidente`), accidentes históricos con descripción y alertas en vivo.

Endpoints adicionales:
- `POST /ruta_segura_completa` — todo lo anterior más `resumen_riesgo`
  (niveles **histórico** y **predictivo** Bajo/Medio/Alto) y `clima`
  (`pronostico`, `avisos_senamhi` en ruta, `emergencias_coen` cerca).
- `GET /alertas` — últimas alertas SUTRAN (cache 15 min).
- `GET /avisos` — avisos SENAMHI activos + emergencias COEN (7 días).
- `GET /health` — puntos de riesgo y alertas archivadas.

### Reporte HTML estático (autónomo)
```
python scripts/reporte_ruta.py "Lima" "Huancayo" --salida "2026-08-15 19:30"
python scripts/reporte_ruta.py "Trujillo" "Chiclayo" --out out/reporte.html
```
Genera un único `.html` autocontenido (mapa folium + perfil de riesgo embebido en
base64) con: resumen, mapa con **popups de accidentes**, "¿qué puede pasar?"
(tipos/causas históricas), **riesgo predictivo NegBin**, comparativa de rutas,
perfil por segmento, **clima y emergencias** (pronóstico, avisos SENAMHI en ruta,
emergencias COEN cerca) y alertas en vivo. El dashboard reutiliza la misma
función (`reporte_desde_resumen`) para el botón **Generar reporte (HTML)**.

### Dashboard (Streamlit)
```
streamlit run dashboard/app.py   # http://localhost:8501 → pestaña "🛡️ Ruta segura"
```
La pestaña "**Prevención antes de viajar**" permite origen/destino, fecha y hora
de salida (factor temporal) y botón **Calcular**. Tras el cálculo muestra:
- **Dos indicadores de riesgo**: histórico (score /km) y predictivo (NegBin), cada
  uno con nivel Bajo/Medio/Alto.
- **Mapa de ancho completo** con accidentes clicables (popups descriptivos) y
  ranking (segura/rápida/corta).
- Tabla comparativa, **perfil de riesgo por segmento** (línea continua = histórico,
  punteada = predicción, doble eje).
- **"¿Qué puede pasar?"** (tipos/causas en el buffer).
- **Clima y avisos**: pronóstico del trayecto, avisos SENAMHI en ruta y
  emergencias COEN cerca (botón "Actualizar clima ahora" fuerza la recarga).
- Botón **Generar reporte (HTML)** + descarga.
- Alertas SUTRAN en vivo filtrables por estado.

### Alertas SUTRAN
```
python scripts/alertas_sutran.py        # fuerza descarga y lista alertas actuales
```

## 4. Casos de uso verificados

| Origen → Destino | km | min | Score | Nota |
|---|---|---|---|---|
| Lima → Huancayo | 301.4 | 374 | 8.57 | Carretera Central (Chosica–Ticlio–La Oroya–Jauja); 961 accidentes en buffer; 3 peajes (AADT máx 1,784) |
| Lima → Huancayo (sáb 18h) | 301.4 | 374 | 10.71 | Mismo trayecto con factor temporal ×1.25 |
| Jauja → Pichanaqui | 200.3 / 242.8 | 256 / 273 | 1.23 / 2.03 | 2 alternativas; la corta también es la más segura |
| Trujillo → Chiclayo | 199.4 | 201 | 5.20 | Panamericana Norte; señal OSITRAN (16) presente; 5 peajes (AADT máx 3,495) |
| Arequipa → Cusco | 718.6 | 870 | 1.49 | Interoceánica Sur; señal OSITRAN fuerte (73) |
| Coordenadas directas | — | — | — | Acepta `lat,lon` |

Riesgo predictivo verificado (Lima → Huancayo): `pred_siniestros_km = 0.67`
(≈1 accidente esperado por 1.5 km) sobre 41 tramos modelados, cobertura 42%.
Sobre la misma ruta, el 13/08/2026 la capa COEN detectó el **sismo de Chongos
Bajo (JUNÍN) a ~9 km del trayecto** y 3 avisos SENAMHI intersectando la ruta:
ejemplo real de "prevención antes de viajar".

## 5. Limitaciones

- **OSRM**: requiere Docker corriendo; `localhost:5000`. Si la máquina reinicia,
  arrancar Docker Desktop y `python scripts/osrm_build.py --serve`.
- **HISTORICO_MAPA de SUTRAN** devuelve vacío (del lado del servidor): el histórico
  se acumula localmente con cada descarga de alertas (`sutran_alertas_historico.json`).
- **Geocodificación**: Photon es el proveedor principal; Nominatim devuelve 403 en
  algunas redes. Nombres muy cortos/ambiguos pueden geocodificar a otro lugar.
- **OSITRAN** no publica coordenadas: solo el 40% de sus accidentes está localizado
  (tramos cuyos extremos se geocodificaron correctamente). El tráfico vehicular por
  peaje (55/60 con ubicación) alimenta el score como señal de exposición (`trafico_km`).
- **Score normalizado por km**: rutas largas tienden a puntajes menores; el ranking
  "segura" compara puntajes normalizados, no riesgo absoluto.
- **Cobertura predictiva parcial**: el dataset de modelado cubre la red nacional
  principal; rutas en vías secundarias pueden tener `cobertura_pct` baja (el
  dashboard lo advierte). El empalme ruta↔tramos es aproximado (umbral 2 km).
- **Clima/COEN**: dependen de servicios externos (SENAMHI WFS, Open-Meteo, portal
  INDECI). Si alguno cae, la capa se omite sin romper el análisis (degradación
  controlada) y se sirve la última caché válida.
- Las alternativas de OSRM pueden ser 1 sola (p.ej. Lima→Huancayo) cuando no hay
  corredores alternos razonables.

## 6. Artefactos

| Artefacto | Ruta |
|---|---|
| Motor | `scripts/ruta_segura.py`, `scripts/osrm_router.py`, `scripts/riesgo_red.py`, `scripts/alertas_sutran.py`, `scripts/ositran_data.py` |
| Predictivo | `scripts/prediccion.py` |
| Clima / COEN | `scripts/clima.py` |
| API | `api/app.py` (uvicorn en 127.0.0.1:8000) |
| Reporte HTML | `scripts/reporte_ruta.py` |
| Infraestructura | `scripts/download_osm.py`, `scripts/osrm_build.py` |
| Grafo OSM | `data/raw/osm/peru-latest.osm.pbf` (+ `.osrm*`) |
| Datos procesados | `data/processed/ositran_*.csv`, `ositran_peajes_geo.json`, `dashboard/sutran_alertas*.json`, `dashboard/geocode_cache.json`, `dashboard/avisos_senamhi.json`, `dashboard/coen_emergencias.json`, `dashboard/coen_geocode.json`, `dashboard/openmeteo_*.json` |
| Modelo | `data/processed/dataset_modelo.csv` (3,750 tramos) |
| Mapas | `data/processed/dashboard/ruta_segura.html`, `dashboard/_map_ruta.html`, `dashboard/reporte_ruta.html` |
