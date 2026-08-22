# SIPAT — Informe Final de Análisis de Siniestralidad Vial en Perú

> Fecha: 11/08/2026 · Período analizado: 2021–2025 (ONSV) · Red de estudio: Red Vial Nacional
> Entregables complementarios: `docs/matriz_tecnica.md` (inventario Fase 0), `docs/auditorias/` (reportes crudos), `docs/figuras/` (visualizaciones).

---

## 1. Resumen ejecutivo

- Se construyó el **dataset espacial** de la siniestralidad fatal en la Red Vial Nacional: **3,750 tramos de la red** (dic16, 150 rutas, 28,502 km) enriquecidos con **5,014 siniestros fatales ONSV 2021–2025**, **7,605 accidentes SUTRAN 2020–2021** geocodificados, y exposiciones espaciales (peajes, cinemómetros, peligros geológicos INGEMMET).
- **La geocodificación por kilómetro fue validada**: 98.1% de los siniestros ONSV están a <100 m de la geometría de red (mediana 4 m); el método de interpolación logra errores de **14 m** contra peajes MTC con km exacto.
- **Modelo de regresión NegBin** (con exposición por km y errores cluster por ruta) identificó los factores asociados a mayor siniestralidad fatal.
- Se priorizaron **12 puntos negros** (tramos con exceso de siniestros sobre lo esperado; top 8 en sección 4).

---

## 2. Datos y metodología

| Componente | Detalle |
|---|---|
| Fuentes | ONSV siniestros fatales (2021–2025, 9,106 reg. georref.), SUTRAN accidentes (2020–2021, 8,155 reg., sin coords → geocodificados), SUTRAN CGM (validación), MTC red vial dic16 (geometría + SINAC), INGEMMET (29,252 peligros geológicos), peajes MTC (233), cinemómetros (160,018). |
| Unidad de análisis | **Tramo de red** (polilínea dic16). Cada siniestro se asignó a un tramo por `ruta + km`. |
| Variable objetivo | `siniestros_km` = conteo ONSV 2021–2025 / longitud del tramo (km). |
| Modelo | Regresión **Negative Binomial** (sobre-dispersión confirmada, α≈1; Poisson rechazado por AIC 11,984→8,663) con **offset = log(km)** y **errores cluster por ruta**. |

### Pipeline de geocodificación (SUTRAN)
1. Normalización de códigos de vía a `PE-XX`.
2. Proyección del `KILOMETRO` sobre la polilínea del shapefile (interpolación geodésica de distancias acumuladas).
3. Resultado: **7,656 de 8,155 accidentes geocodificados (93.9%)**.
4. Validación cruzada con CGM/peajes: método correcto; **la referencia de kilometraje MTC cambió** en dic16 vs 2024–25 (PE-1S ≈6 km, PE-5N/PE-3N incompatibles) → solo usar la referencia de la propia fuente.

---

## 3. Hallazgos descriptivos

### 3.1 Magnitud y tendencia
- **9,106 siniestros fatales · 10,859 fallecidos · 7,837 lesionados** (2021–2025; 2025 preliminar: 678).
- Los siniestros **descienden** (2,392 → 1,555 entre 2021 y 2024), pero la **gravedad aumenta**: fallecidos por siniestro pasan de **1.18 a 1.22**.
- **Fines de semana**: sábado 1,854 y domingo 1,517 siniestros (máximos); viernes 1,174.
- **Hora**: pico a las **18:00** (1,767) y franja 15–21 h concentra ~1/3 del total.
- Mes con mayor siniestralidad relativa: junio (1,192/4 años).

### 3.2 Tipología
- **CLASE**: CHOQUE 2,875 · DESPISTE 2,571 · ATROPELLO 1,871 · ATROPELLO FUGA 885 · VOLCADURA 313.
- **CAUSA**: 4,609 "EN PROCESO DE INVESTIGACIÓN" (51% — limitación de datos); del resto, **IMPRUDENCIA DEL CONDUCTOR 3,497** domina claramente; infraestructura vial como causa: solo 75.
- **CONDICIÓN CLIMÁTICA**: despejado 7,768 (85%) → el clima NO es el factor predominante.
- **SUPERFICIE**: asfaltada 7,108 (78%); **afirmado 655 + trocha 619** (~14%) concentran siniestros fatales en vías no pavimentadas.
- **SEÑALIZACIÓN**: solo ~2,000 registros responden; donde se reporta, hay señal vertical en 1,306 y horizontal en 1,308.

### 3.3 Geografía
- **Departamentos** (fallecidos): LIMA 2,069 · LA LIBERTAD 1,063 · CUSCO 998 · AREQUIPA 886 · PUNO 854 · CAJAMARCA 660.
- **Regiones geográficas (tasa por 100 km)**: **COSTA 46.1** · SIERRA 13.3 · SELVA 7.1. La costa es la más riesgosa por km (densidad de tránsito + altas velocidades).
- **Rutas** (siniestros en red nacional): PE-1N 1,031 · PE-1S 639 · PE-3S 614 · PE-3N 305 · PE-5N 277 · PE-34A 192.
- **Tramos críticos** (km): Panamericana Norte km 0–27 (Lima), Panamericana Sur km 4–13, PE-34B km 217, PE-3N km 1276.

---

## 4. Modelo de riesgo por tramo (NegBin)

| Variable | IRR | IC 95% | p |
|---|---|---|---|
| Terreno **plano** (vs montañoso) | **2.02** | 1.46–2.77 | <0.001 |
| **Carriles** (por carril adicional) | **1.54** | 1.30–1.82 | <0.001 |
| **Velocidad de proyecto** (por +10 km/h) | **1.20** | 1.13–1.26 | <0.001 |
| **Sinuosidad** (tramos con curvas) | **0.67** | 0.57–0.79 | <0.001 |
| Distancia a peligro geológico (log; más cerca=+) | 0.72 | 0.60–0.87 | 0.001 |
| Distancia a cinemómetro (log; más cerca=+) | 0.87 | 0.77–1.00 | 0.041 |
| **Superficie buena** | **1.48** | 1.11–1.98 | 0.009 |
| Región Selva (vs costa) | 0.67 | 0.41–1.09 | 0.107 |

**Interpretación (con cautela):** los tramos **planos, multicarril, de alta velocidad y con buen estado de vía** concentran más siniestros fatales por km. La sinuosidad reduce la velocidad efectiva y, con ello, la siniestralidad fatal. La cercanía a peligros geológicos y a cinemómetros se asocia a mayor siniestralidad (los cinemómetros se instalan donde ya hay riesgo). **Advertencia**: varias variables son proxy de volumen de tránsito (el flujo vehicular público fue retirado del portal), por lo que no deben leerse como causalidad pura.

### Puntos negros priorizados (residual > 1.5, ≥5 siniestros; 12 en total)
Top 8 por exceso:
| Ruta | Tramo (km) | Siniestros | Exceso (residual) |
|---|---|---|---|
| **PE-5N** | 1081.1–1099.0 | 28 | 3.33 |
| **PE-1N** | 21.7–22.4 | 8 | 3.08 |
| **PE-34J** | 94.2–105.2 | 7 | 2.64 |
| PE-20 | 14.3–16.4 | 9 | 2.45 |
| PE-1N | 0.0–0.5 | 7 | 2.31 |
| PE-20 | 11.0–14.3 | 17 | 2.21 |
| PE-34A | 119.1–124.1 | 8 | 2.16 |
| PE-3N | 1560.6–1578.9 | 7 | 2.06 |

---

## 5. Limitaciones

1. **Flujo vehicular no disponible** (retirado del portal) → no se puede calcular tasas ajustadas por tránsito; se usan proxy (carriles, velocidad de proyecto, estado de vía).
2. **Red vial dic16** como geometría base; los km de fuentes 2024–25 (peajes, CGM) no siempre coinciden con su referencia (PE-5N, PE-3N).
3. **Causas ONSV**: 51% en investigación; subregistro de causas relacionadas a infraestructura.
4. **Cinemómetros y peajes** cubren solo corredores principales (106/3,750 tramos con cinemómetro ≤2 km).
5. **2025 preliminar** (hasta ~junio) → no comparar tasas anuales 2025.
6. **INGEMMET** capa 0 con eventos 2002–2009 → proximidad estática.
7. SUTRAN es la misma fuente informante en muchos casos; la comparación SUTRAN/ONSV (ratio PE-22 ≈ 4.8 vs PE-3S ≈ 1.1) sugiere diferencias de cobertura por ruta.

---

## 6. Recomendaciones

1. **Intervenciones en puntos negros**: auditar los 12 tramos priorizados (especialmente PE-5N km 1081–1099 y Panamericana Norte/Sur en Lima); evaluar reductores de velocidad y señalización en los tramos urbanos-adyacentes (km 0–27 PE-1N, km 4–13 PE-1S).
2. **Gestión de velocidad**: la velocidad de proyecto y el terreno plano son los mayores multiplicadores → políticas de límites diferenciados por tramo (velocidades dinámicas), control en fines de semana y franja 15–21 h.
3. **Vías no pavimentadas** (afirmado/trocha = 14% de siniestros fatales): priorizar mejora de superficie y señalización en corredores PE-5N/PE-34J.
4. **Monitorización anual**: repetir el modelo con el corte completo 2025; incorporar flujo vehicular cuando se publique.
5. **Sistema de seguimiento por tramo**: exportar `dataset_tramos.csv` como línea base de indicadores (siniestros/km, fallecidos/km).

---

## 7. Archivos y reproducción

### Dashboard interactivo (Streamlit)
```
python scripts/prep_dashboard.py        # prepara datos ligeros (una vez)
streamlit run dashboard/app.py          # abre el navegador en http://localhost:8501
```
- **Pestañas**: mapa de siniestralidad por tramo (folium + puntos negros) · puntos negros · tendencia (año/mes/día/hora/gravedad) · rutas y departamentos · modelo (forest plot IRR) y explorador de tramos.
- **Filtros laterales**: región, rutas, umbral de siniestros/km, departamentos y años.

| Artefacto | Ruta |
|---|---|
| Dashboard | `dashboard/app.py` |
| Datos del dashboard | `data/processed/dashboard/` |
| Dataset maestro (3,750×40) | `data/processed/dataset_modelo.csv` |
| SUTRAN geocodificado | `data/processed/sutran_accidentes_geocod.csv` |
| ONSV nacional + km | `data/processed/onsv_nacional_geocod.csv` |
| Puntos negros | `data/processed/puntos_negros.csv` |
| Módulo de geocodificación | `scripts/geocode.py` |
| Feature engineering | `scripts/features_engine.py` |
| Modelo | `scripts/modelo_glm.py` |
| Gráficos | `docs/figuras/*.png` (6 figuras) |
| Auditorías | `docs/auditorias/*.txt` |

**Reproducción** (en orden):
```
python scripts/build_dataset.py        # tramos + ONSV + cinemómetros limpios
python scripts/features_tramos.py      # features de distancia
python scripts/features_engine.py      # sinuosidad + dataset_modelo
python scripts/modelo_glm.py           # modelo NegBin + puntos negros
python scripts/graficos.py             # figuras
python scripts/prep_dashboard.py       # datos para el dashboard
streamlit run dashboard/app.py         # dashboard interactivo
```

---

## 8. Módulo "Ruta segura" (fase 2)

### 8.1 Objetivo
Al planificar un viaje de ciudad A a ciudad B, comparar rutas alternativas según: (1) **riesgo histórico** (accidentes ONSV+SUTRAN geocodificados en el trayecto), (2) **incidentes en vivo** (Mapa Interactivo de Alertas de SUTRAN) y (3) tiempo/distancia, recomendando la **ruta más segura**, la más rápida y la más corta.

### 8.2 Arquitectura (todo open source, sin costo)
- **Red y ruteo — OSRM self-hosted** (Docker, perfil `car`): extracto OSM de Perú (`download.geofabrik.de`, `peru-latest.osm.pbf` ~243 MB) procesado con `osrm-extract/partition/customize` + `osrm-routed --algorithm mld` en `localhost:5000`. Soporta cualquier punto del país (todo Perú).
- **Geocodificación — Photon** (`photon.komoot.io`, sin key) con fallback a Nominatim; acepta texto o `lat,lon`.
- **Riesgo histórico — `scripts/riesgo_red.py`**: índice espacial (scipy cKDTree sobre proyección equirectangular local) con **18,807 puntos**: ONSV 5,014 + SUTRAN 7,656 + OSITRAN 6,137 (sintéticos cada ~1 km sobre corredores concesionados, peso = accidentes/tramo). `score_route()` muestrea la polilínea cada 500 m, cuenta accidentes en buffer ±1 km y pondera gravedad (fallecidos ×3 + lesionados ×1 + 1), normalizado por km, sumando las **alertas históricas SUTRAN** archivadas (interrumpido ×2, restringido ×1, normal ×0.3) y la **exposición de tráfico OSITRAN** (Σ AADT/100 000, peajes a ≤15 km).
- **Incidentes en vivo — `scripts/alertas_sutran.py`**: scrapea el endpoint público `gis.sutran.gob.pe/alerta_sutran/script_cgm/carga_xlsx.php?tipo=MAPA` (JSON: `normal/restringido/interrumpido` con lat/lon, motivo, KM, ubigeo). Clasifica motivo por regex (ACCIDENTE/FENOMENO/INFRAESTRUCTURA/HUMANO) y cachea 15 min en disco. Penalización en el riesgo: interrumpido +5, restringido +1 por alerta en ±2 km.
- **Motor — `scripts/ruta_segura.py`**: geocodifica → pide hasta 3 alternativas a OSRM → puntúa cada ruta (riesgo/km penalizado) → ranking `segura/rapida/corta` → mapa folium con rutas coloreadas por riesgo, accidentes históricos (morado ONSV / naranja SUTRAN / teal OSITRAN) y alertas en vivo.
- **Motor v2**: `riesgo_red.factor_temporal(dt)` (sáb ×1.25, dom ×1.1, noche 19–5h ×1.3, madrugada 5–8h ×1.05) y `perfil_segmentos(geometry, 5 km)` → perfil de riesgo por segmento en cada ruta.
- **Entrega**: CLI, **API FastAPI** (`api/app.py`, POST `/ruta_segura` + `/health` + `/alertas`), **reporte HTML estático autónomo** (`scripts/reporte_ruta.py`) y pestaña rediseñada en el dashboard.

### 8.3 Uso
```
python scripts/download_osm.py                         # pbf Perú (una vez)
python scripts/osrm_build.py --all                     # build grafo + servidor :5000
python scripts/ruta_segura.py "Lima" "Huancayo" --salida "2026-08-15 19:30"
uvicorn api.app:app --port 8000                        # API
python scripts/reporte_ruta.py "Lima" "Huancayo" --out out/reporte.html
streamlit run dashboard/app.py                         # pestaña "🛡️ Ruta segura"
```

### 8.4 Validación
- Ruta Lima→Huancayo: 301.4 km / 374 min por Carretera Central (Chosica–Matucana–Ticlio–La Oroya–Jauja), consistente con la distancia real (~300 km).
- Par Jauja→Pichanaqui: 2 alternativas (200.3 y 242.8 km) rankeadas por riesgo.
- Alertas SUTRAN en vivo: 22 alertas actuales parseadas correctamente (estado, motivo, KM, ubigeo).
- Motor v2: sáb 18h → factor 1.25, dom 23h → 1.43; Lima→Huancayo sáb 18h score 10.71 (vs 8.57 sin factor); perfil de 59 segmentos.
- Tráfico OSITRAN: Trujillo→Chiclayo 5 peajes en buffer (AADT máx 3,495 veh/día, trafico_km 0.068); Lima→Huancayo 3 peajes (AADT máx 1,784, trafico_km 0.040).
- API: POST Trujillo→Chiclayo con `salida` → factor 1.625 (sáb 19:30), perfil completo; `/health` reporta 18,807 puntos y 22 alertas históricas.
- AppTest del dashboard rediseñado: 0 excepciones al calcular; mapa y tabla de rutas generados.

### 8.5 Artefactos nuevos
| Artefacto | Ruta |
|---|---|
| Descarga OSM | `scripts/download_osm.py` |
| Build OSRM | `scripts/osrm_build.py` |
| Cliente OSRM | `scripts/osrm_router.py` |
| Riesgo histórico | `scripts/riesgo_red.py` |
| Alertas en vivo | `scripts/alertas_sutran.py` |
| Datos OSITRAN | `scripts/ositran_data.py` (`data/processed/ositran_*.csv`) |
| Motor ruta segura | `scripts/ruta_segura.py` |
| API FastAPI | `api/app.py` |
| Reporte HTML | `scripts/reporte_ruta.py` |
| Dashboard | `dashboard/app.py` (6 pestañas, panel Ruta segura rediseñado) |
| Grafo de conocimiento | `graphify-out/` (graph.json + vault Obsidian + wiki) |
| Vault Obsidian | `graphify-out/obsidian/` (abrir como vault en Obsidian) |
