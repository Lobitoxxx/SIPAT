# Matriz Técnica SIPAT — Inventario de Datos (Fase 0)

> Auditoría realizada sobre archivos reales descargados el 11/08/2026.
> Fuentes: Plataforma Nacional de Datos Abiertos, ONSV, INGEMMET (ArcGIS REST).
> Reportes de auditoría crudos: `docs/auditorias/`.

---

## 1. Resumen ejecutivo

- **El proyecto es viable.** Existen 3 fuentes de siniestros/accidentes con datos puntuales, dos de ellas con coordenadas exactas y una unible por código de ruta + kilómetro.
- **ONSV Siniestros Fatales 2021–2025 es el dataset estrella**: 9,106 registros, 27 atributos, georreferenciado, con causa, señalización, clima y características de vía.
- **La clave de unión espacial** `CODIGO_VIA + KILOMETRO` es común a SUTRAN, ONSV e INGEMMET, y coincide con los códigos del shapefile de red vial (formato `PE-XX`).
- **INGEMMET**: 29,252 eventos de peligros geológicos descargados vía API (4 capas), listos para análisis de proximidad.
- **Brechas detectadas**:
  - El dataset de **flujo vehicular mensual (2014–2025)** fue **retirado del portal** (404). Alternativa disponible: GeoJSON de 233 estaciones de peaje (2024–2025).
  - **INDECI Emergencias**: no disponible en el portal nacional (SINPAD con acceso restringido).
  - **Infracciones de tránsito**: fragmentado por entidad (municipalidades, SAT Lima) → diferir a 2ª etapa.

---

## 2. Tabla consolidada

| # | Fuente / Dataset | Archivo local | Formato | Registros | Cobertura | Coordenadas | Rol SIPAT | Estado |
|---|---|---|---|---|---|---|---|---|
| 1 | SUTRAN Accidentes en Carreteras 2020–2021 | `data/raw/sutran_accidentes/accidentes_carreteras_2020-2021_sutran.csv` | CSV | 8,155 × 9 | 2020-01→2021-12 | No (km) | Target 1 (accidentes red nacional) | Listo |
| 2 | SUTRAN Reportes preliminares CGM | `data/raw/sutran_reportes_cgm/reportes_preliminares_cgm_2020-2021.csv` | CSV | 3,832 × 14 | 2020-01→2021-11 | **Sí** | Target 2 + validación geocodificación | Listo |
| 3 | ONSV Siniestros de Tránsito Fatales | `data/raw/onsv/siniestros_fatales_2021-2025.xlsx` | XLSX (1 hoja) | 9,106 × 27 | 2021-01→2025-12 | **Sí** | **Target principal** (fatalidades) | Listo* |
| 4 | ONSV Histórico 2008–2025 | `data/raw/onsv/historico_2008-2025.xlsx` | XLSX (tabla ancha) | 35 × 141 | 2008–2025 | — | Contexto / tendencias | Uso opcional |
| 5 | MTC Red Vial SINAC 2022–2024 | `data/raw/mtc_red_vial/red_vial_nacional_2022-2024.csv` | CSV | 20,255 × 20 | cortes 2022/23/24 | No (km) | Infraestructura (features de vía) | Listo |
| 6 | MTC Red Vial espacial (dic16) | `data/raw/mtc_datos_espaciales/rvn_dic16/red_vial_nacional_dic16.shp` | Shapefile | 3,750 polilíneas | 2016 | **Sí** | **Geometría** para unión por km | Listo |
| 7 | MTC Unidades de Peaje 2024–2025 | `data/raw/mtc_flujo_peajes/unidades_peaje_2024-2025.geojson` | GeoJSON | 233 puntos | corte 2024 | **Sí** | Exposición (peajes) | Listo |
| 8 | SUTRAN Cinemómetros 2019–2021 | `data/raw/sutran_cinemometros/cinemometros_2019-2021.csv` | CSV | 160,018 × 9 | 2019-10→2021 | **Sí** | Fiscalización de velocidad (feature) | Listo |
| 9 | SUTRAN Cinemómetros 2022 | `data/raw/sutran_cinemometros/cinemometros_2022.xlsx` | XLSX | 103,092 × 7 | 2022 | **No** | Idem, esquema distinto | Listo (parcial) |
| 10 | INGEMMET Peligros Geológicos | `data/raw/ingemmet/layer*_*.geojson` (4 archivos) | GeoJSON | 29,252 pts | 2002–2009 (capa 0) | **Sí** | Riesgo geohidrológico | Listo |
| — | INDECI Emergencias | — | — | — | — | — | Descartado (no disponible) | Descartado |
| — | Infracciones de tránsito | — | — | — | — | — | Segunda etapa | Diferido |

\* Requiere leer la hoja con `header=4` (filas de título/nota en la parte superior).

---

## 3. Fichas detalladas

### 3.1 SUTRAN — Accidentes en Carreteras 2020–2021 (TARGET 1)
- **Columnas:** `FECHA_CORTE, FECHA (yyyymmdd), HORA, DEPARTAMENTO, CODIGO_VÍA, KILOMETRO, MODALIDAD, FALLECIDOS, HERIDOS`
- **Calidad:** sin nulos aparentes; 29 departamentos; 175 códigos de vía; 6 modalidades (DESPISTE, CHOQUE, ATROPELLO, VOLCADURA, ESPECIAL, N.I.).
- **Limitación:** `FALLECIDOS`/`HERIDOS`/`KILOMETRO` en texto (pueden contener `N.I.`); sin coordenadas → geocodificar por unión a red vial.

### 3.2 SUTRAN — Reportes preliminares CGM 2020–2021 (TARGET 2)
- **Columnas:** `NRO_REPORTE, FECHA_ACC, HORA_ACC, MODALIDAD_ACC, CANT_FALLECIDOS, CANT_HERIDOS, LATITUD, LONGITUD, PROGRESIVA, CODIGO_VIA, DEPARTAMENTO, PROVINCIA, DISTRITO`
- **Calidad:** LAT/LON float **sin nulos**; `PROGRESIVA` 80 nulos (2%); `CODIGO_VIA` 31 nulos (<1%).
- **Uso:** target con coordenadas exactas + validación cruzada de la geocodificación de 3.1.

### 3.3 ONSV — Siniestros de Tránsito Fatales 2021–2025 (TARGET PRINCIPAL)
- **Estructura:** xlsx, hoja `SINIESTROS`, cabecera real en fila 4 (`header=4`).
- **Columnas (27):** CÓDIGO SINIESTRO, FECHA, HORA, CLASE SINIESTRO, CANTIDAD DE FALLECIDOS/LESIONADOS/VH DAÑADOS, DEPARTAMENTO/PROVINCIA/DISTRITO, ZONA, TIPO DE VÍA, RED VIAL, COD CARRETERA, **COORDENADAS LATITUD/LONGITUD**, CONDICIÓN CLIMÁTICA, ZONIFICACIÓN, CARACTERÍSTICAS DE VÍA, PERFIL LONGITUDINAL, SUPERFICIE DE CALZADA, ¿SEÑAL VERTICAL? (+2 clasificaciones), ¿SEÑAL HORIZONTAL?, CAUSA FACTOR PRINCIPAL, CAUSA ESPECÍFICA.
- **Cobertura:** 2021-01-01 → 2025-12-30. Por año: 2021: 2,392 | 2022: 2,480 | 2023: 2,001 | 2024: 1,555 | 2025: 678 (preliminar).
- **Calidad coordenadas:** LAT 0 nulos, LON 1 nulo; todas en rango válido del Perú.
- **RED VIAL:** NACIONAL 5,014 | URBANO 2,045 | PROVINCIAL 949 | DEPARTAMENTAL 770 | SIN CLASIFICAR 328.
- **CLASE:** CHOQUE 2,875 | DESPISTE 2,571 | ATROPELLO 1,871 | ATROPELLO FUGA 885 | VOLCADURA 313 | otras.
- **CAUSA FACTOR PRINCIPAL:** EN PROCESO DE INVESTIGACIÓN 4,609 | IMPRUDENCIA DEL CONDUCTOR 3,497 | IMPRUDENCIA DEL PEATÓN 593 | otras.
- **Totales:** 10,859 fallecidos y 7,837 lesionados en el período.
- **Uso:** al ser multi-atributo (vía, clima, señalización, causa), es la base del modelo espacial de fatalidad.

### 3.4 ONSV — Histórico 2008–2025
- Tabla estadística ancha (35 × 141, cabeceras múltiples) de siniestralidad por departamento/clase/mes.
- **Uso:** contexto y benchmark nacional; no es data de modelado.

### 3.5 MTC — Red Vial SINAC 2022–2024
- **Columnas (20):** `ID_RVN, ID_DEPARTAMENTO, DEPARTAMENTO, CODIGO_RUTA, TRAYECTORIA, INICIO, FINAL, CLASIFICACION_EJE, JERARQUIA, LONGITUD, NRO_CARRILES, SUPERFICIE, SUPERFICIE_L, ESTADO, ESTADO_L, CODIGO_CONCESION, NOMBRE_CONCESION, CODIGO_LOGISTICO, CORREDOR_LOGISTICO, FECHA_CORTE`
- 161 rutas; `FECHA_CORTE` en 3 cortes (2022-12-31, 2023-12-31, 2024-07-31) — quedarse con el corte más reciente.
- **JERARQUIA:** 100% RN. **SUPERFICIE_L:** Pavimentado 11,594 | Asfaltado económico 5,991 | Afirmado 1,772 | Trocha 488 | Sin afirmar 274 | Proyectado 136. **ESTADO_L:** Bueno 10,558 | Regular 8,180 | Malo 1,381 | Sin info 136.
- **Uso:** atributos de infraestructura por tramo (km inicial/final) para features de vía.

### 3.6 MTC — Red Vial espacial (dic16) — GEOMETRÍA
- Shapefile: 3,750 polilíneas, **WGS84 (EPSG:4326)**; DBF en **ISO-8859-1** (leer con `encoding='iso-8859-1'`).
- **Campos clave:** `cCodRuta` / `cCodRutaDi` (formato `PE-XX`), `dkmInicio`, `dkmFinal`, `dLongitud`, `dNroCarril`, `dAncCalzad`, `cTopografi` (MONTAÑOSO/…), `dVelProTra` (velocidad de proyecto), `cSuperfici`, `cEstadoDic`, `cRegion` (COSTA/SIERRA/SELVA), `cDepartame`, `cNomRuta`.
- **Uso:** base para **geocodificar por kilómetro** (locate a lo largo de la polilínea con el km del accidente) y para calcular pendientes/curvatura.
- **Nota:** corresponde a dic. 2016; si se requiere red más actual en geometría, contrastar con el CSV SINAC (3.5) por `CODIGO_RUTA`.

### 3.7 MTC — Unidades de Peaje 2024–2025 (EXPOSICIÓN)
- GeoJSON: 233 puntos, WGS84.
- **Campos:** `IDPEAJE, NOMBRE, CODPEAJE, CODRUTA (PE-1S), INICIO (km), CODCLOG, DEPARTAMENTO/PROVINCIA/DISTRITO, ES_CONCES, TITULAR, UBICACION (km+xxx), ESTADO, ADMINIST, FECCORTE`.
- **Uso:** posición exacta de peajes → unión por `CODRUTA + INICIO` con la red vial; base para proxy de exposición (densidad de control).
- ⚠️ **Gap:** el flujo vehicular mensual por peaje (2014–2025) fue retirado del portal (404). No hay series temporales de tránsito disponibles públicamente.

### 3.8 SUTRAN — Cinemómetros 2019–2021
- 160,018 registros; columnas: `NRO_DETECCION, FECHA_PAPELETA, REGION, CARRETERA, LATITUD, LONGITUD, LIMITE_VELOCIDAD, VELOCIDAD_DETECTADA, FECHA_CORTE`.
- Georreferenciado; 11 regiones; 7 carreteras; velocidad detectada vs límite → **exceso de velocidad como feature de riesgo** (densidad/severidad de infracciones por tramo).

### 3.9 SUTRAN — Cinemómetros 2022
- 103,092 registros; **esquema distinto y sin coordenadas**: `ITEM, DEPARTAMENTO, FECHA_PAPELETA, VELOCIDAD_FISCALIZADA, VELOCIDAD_DETECTADA, CARRETERA, TIPO DE VEHÍCULO`.
- **Decisión:** usar solo para agregados por `DEPARTAMENTO + CARRETERA` si el período 2022 es necesario.

### 3.10 INGEMMET — Peligros Geológicos (ArcGIS REST)
- Descargados vía `geocatmin.ingemmet.gob.pe/arcgis/rest/services/SERV_PELIGROS_GEOLOGICOS/MapServer` (paginación por rango de OBJECTID; el servicio no soporta offset):
  - `layer0_Peligros_Geológicos.geojson` — **18,133 pts** (FECHA 2002–2009; TIP_PELIGRO codificado `1000|1100`…; UBIGEO; COO_NORTE/ESTE en UTM; NM_DPTO/PROV/DIST).
  - `layer1_Otros_Peligros_Geológicos.geojson` — **8,908 pts**.
  - `layer2_Zonas_Críticas.geojson` — **2,186 pts** (ZONA, REGION, PARAJE, PROVINCIA/DISTRITO).
  - `layer3_Peligros_por_Región.geojson` — 25 polígonos regionales.
- **Uso:** distancia mínima de cada tramo/accidente al evento geológico más cercano (riesgo por proximidad) y densidades por tramo.

---

## 4. Claves de relación y estrategia de unión espacial

| Dataset | Código de ruta | Posición lineal | Coordenadas |
|---|---|---|---|
| SUTRAN Accidentes (3.1) | `CODIGO_VÍA` | `KILOMETRO` | — |
| SUTRAN CGM (3.2) | `CODIGO_VIA` | `PROGRESIVA` | `LATITUD/LONGITUD` |
| ONSV Fatales (3.3) | `COD CARRETERA` | — | `COORDENADAS LATITUD/LONGITUD` |
| MTC Red SINAC (3.5) | `CODIGO_RUTA` | `INICIO/FINAL` | — |
| MTC Red espacial (3.6) | `cCodRutaDi` | `dkmInicio/dkmFinal` | Geometría (polilínea) |
| MTC Peajes (3.7) | `CODRUTA` | `INICIO` | Punto |
| INGEMMET (3.10) | — | — | Punto (WGS84/UTM) + UBIGEO |

**Pipeline propuesto (Fase 1):**
1. Normalizar códigos de ruta a formato `PE-XX` (y variantes departamentales/provinciales para ONSV).
2. Para registros sin coordenadas: **snap lineal** — proyectar el km sobre la polilínea de `cCodRutaDi` del shapefile (interpolación de coordenadas).
3. Validar el snapping contra los puntos reales de ONSV (9,106) y CGM (3,832).
4. Asignar atributos de infraestructura del tramo (superficie, estado, carriles, concesión) por `CODIGO_RUTA + km`.
5. Calcular features espaciales: distancia a INGEMMET, densidad de cinemómetros, distancia a peaje.

---

## 5. Ventana temporal viable y cobertura

- **ONSV fatales:** 2021–2025 (2025 preliminar) → es la ventana principal.
- **SUTRAN accidentes/CGM:** 2020–2021 → para ampliar hacia atrás o comparar.
- **Cinemómetros:** 2019–2022 (esquema homogéneo solo 2019–2021).
- **Red vial SINAC:** cortes 2022, 2023, 2024 → alinear el corte más cercano a la fecha del siniestro.
- **Red espacial:** dic-2016 → desactualizada; usar atributos del SINAC (2022–24) y solo la geometría para snapping.

**Recomendación de scope:** modelo sobre **red vial nacional (JERARQUIA=RN)** con ONSV filtrado `RED VIAL = NACIONAL` (5,014 siniestros), o sin filtrar si se incorpora la red departamental/provincial del shapefile.

---

## 6. Datos no disponibles / descartados

| Fuente | Motivo |
|---|---|
| INDECI — Emergencias históricas | No publicado en la Plataforma Nacional de Datos Abiertos; SINPAD/Geoportal INDECI con acceso restringido. Cubierto parcialmente por INGEMMET (riesgo geológico). |
| Infracciones de tránsito | Fragmentado por entidad (municipalidades, SAT Lima); sin cobertura nacional consistente. Diferir a 2ª etapa. |
| Flujo vehicular mensual por peaje | Dataset retirado del portal (404 en URLs históricas). Solo quedan las estaciones de peaje (3.7). |

---

## 7. Riesgos de datos

1. **Esquemas cambiantes entre años** (cinemómetros 2019–21 vs 2022) → normalizar por año.
2. **Formato de fechas inconsistente**: enteros `yyyymmdd` (SUTRAN) vs datetime (ONSV) → estandarizar.
3. **Codificación de vías**: `CODIGO_VÍA` (con tilde) vs `CODIGO_VIA` vs `COD CARRETERA` vs `CODRUTA` → mapeo necesario.
4. **Red espacial desactualizada (2016)** → errores de snapping en tramos nuevos; validar contra ONSV/CGM.
5. **INGEMMET capa 0 con FECHA 2002–2009** → la proximidad al evento geológico es estática.
6. **2025 preliminar** en ONSV → tratar como corte incompleto.
7. **Duplicación potencial de eventos entre capas INGEMMET** → deduplicar por proximidad/CÓD_INV antes de usar.

---

## 8. Próximos pasos (Fase 1)

1. Script de **normalización** (códigos de vía, fechas, tipos).
2. **Geocodificación por km** sobre el shapefile (con validación ONSV/CGM).
3. **Construcción del dataset espacial de análisis** (tramos × atributos × exposiciones).
4. Análisis exploratorio (EDA) y primeros mapas (notebooks).

---

## 9. Estado Fase 1 (11/08/2026)

### 9.1 Validación de la geometría de red (dic16)
- **Precisión geométrica alta:** 5,004 siniestros ONSV `RED VIAL=NACIONAL` proyectados al shapefile → **98.1% a <100 m** de la polilínea (mediana 4 m, p99 1.2 km). La geometría dic16 es fiable en el espacio.

### 9.2 Validación de la interpolación km → punto
- **Método correcto** (peajes MTC con km exacto): errores de hasta **14 m** (Ilo, Pampa Galeras, San Antonio, San Nicolás).
- **Salvedad importante:** la **referencia de kilometraje MTC cambió** para algunas rutas entre dic16 y los datos 2024–25. Errores medios por ruta: PE-1N 2.9 km, PE-1S 6.3 km, PE-3S 5.0 km, PE-30C 3.1 km, y **PE-5N (463 km) y PE-3N (78 km)** con referencias incompatibles. Idem en `PROGRESIVA` de CGM (PE-5N, PE-3N).
- **Consecuencia:** geocodificar con la referencia de la propia fuente (SUTRAN `KILOMETRO` es contemporáneo a dic16 y coherente); evitar mezclar km de fuentes 2024–25 sobre dic16 sin ajuste.
- **CGM `PROGRESIVA` tiene mala calidad** (mediana ~1 km, colas enormes) → solo usar sus coordenadas, no su progresiva.

### 9.3 Datasets procesados (`data/processed/`)
| Archivo | Contenido |
|---|---|
| `tramos_red.csv` | 3,750 tramos, 150 rutas + SINAC (`region`, `clasifica`, `topografia`, `carriles`, `vel_proy`, `superficie`) |
| `onsv_nacional_geocod.csv` | 5,014 siniestros ONSV nacionales + `km_red`, `dist_linea_km`, tramo asignado |
| `sutran_accidentes_geocod.csv` | 8,155 accidentes; **93.9% geocodificados** (7,656 con lat/lon) |
| `cinemometros_clean.csv` | 160,018 detecciones con coordenadas |
| `features_distancia.csv` | por tramo: dist. a INGEMMET/peaje/cinemómetro + conteos por radio |
| `dataset_tramos.csv` | **dataset maestro**: 3,750 × 31 (SINAC + siniestros ONSV/SUTRAN + exposiciones + `siniestros_km`, `fallecidos_km`) |

### 9.4 Hallazgos EDA (`docs/auditorias/eda_tramos.txt`)
- 5,004 siniestros ONSV en red (6,228 fallecidos) y 7,605 accidentes SUTRAN 2020–21 (1,255 fallecidos). 66% de tramos sin siniestro; 515 tramos con ≥3.
- Rutas de mayor tasa (siniestros/100 km): **PE-20 (208), PE-1N (78), PE-22 (65), PE-34A (64)**, PE-1NO, PE-1SE.
- Correlación con `siniestros_km` (tramo): `vel_proy` **+0.23**, dist. a cinemómetro **−0.17**, INGEMMET a <5 km **+0.16**, dist. a peaje −0.10. Tramos con cinemómetro ≤2 km: **0.75 vs 0.26 siniestros/km** (sin cinemómetro).
- Correlaciones débiles a nivel de tramo (muchos ceros) → para modelar, agregar por unidad más gruesa y usar regresión con exposición (km) y efecto por ruta.

### 9.5 Scripts de Fase 1 (`scripts/`)
- `geocode.py` — geocodificación lineal por km (interpolación geodésica; `locate`, `snap_distance`).
- `build_geocoded.py` — geocodificación SUTRAN + validación CGM.
- `validate_geo.py`, `validate_peajes.py`, `diagnose_km.py` — validaciones.
- `build_dataset.py` — tramos + ONSV + cinemómetros limpios.
- `features_tramos.py` — features espaciales por tramo (STRtree).
- `eda_tramos.py` — EDA del dataset maestro.

### 9.6 Análisis y modelo (ver `docs/informe_sipat.md`)
- **Tendencia:** siniestros fatales bajan (2,392→1,555) pero **fallecidos/siniestro suben** (1.18→1.22). Pico sábados y 18 h.
- **Regiones:** COSTA 46 vs SIERRA 13 vs SELVA 7 siniestros/100 km.
- **Modelo NegBin** (exposición km, cluster por ruta): terreno plano IRR 2.0, carriles 1.54/carril, vel_proy 1.20 por +10 km/h, sinuosidad 0.67, cerca de INGEMMET/cinemómetros asociado a más siniestros.
- **12 puntos negros** priorizados (`data/processed/puntos_negros.csv`): PE-5N km 1081–1099 (28), PE-1N km 21.7–22.4 y km 0–0.5 (Lima), PE-34J, PE-20.
- **Figuras:** `docs/figuras/` (6 PNG: mapas de siniestralidad/puntos negros/contexto, tendencia temporal, ranking rutas, forest plot IRRs).
- **Fecha ONSV:** formato `DD/MM/YYYY` → leer con `format="%d/%m/%Y"` (bug detectado y corregido en `build_dataset.py`).

---

## 10. Fase 2 — Módulo "Ruta segura" (nuevas fuentes y arquitectura)

### 10.1 Fuentes nuevas investigadas (validado el 13/08/2026)
| Fuente | Qué aporta | Acceso | Estado |
|---|---|---|---|
| ONSV **Datos abiertos** (`onsv.gob.pe/datosabiertos`) | Nuevos datasets: PERSONAS INVOLUCRADAS y VEHÍCULOS INVOLUCRADOS en siniestros fatales 2021–2025 (preliminar); HISTORICO 2008–2025; visor de alerta de siniestros en tiempo real | Descarga directa | Identificado |
| **SUTRAN Mapa Interactivo de Alertas** (`gis.sutran.gob.pe/alerta_sutran/`) | Incidentes en vivo: puntos con lat/lon, motivo (ACCIDENTES/HUMANO/CLIMATOLOGICO/INFRAESTRUCTURA), estado (normal/restringido/interrumpido), KM, ubigeo. Endpoint JSON público: `script_cgm/carga_xlsx.php?tipo=MAPA` (también `HISTORICO_MAPA`). Stream Socket.IO `190.81.47.145:3001` | **Endpoints scrapeables** | **Integrado** |
| **OSITRAN Data** (`serviciosdigitales.ositran.gob.pe:8443/PortalDatosOsitran/` + PNDA) | 16 concesiones: accidentes de tránsito, llamadas de emergencia, auxilios mecánicos, asistencias médicas, **tráfico vehicular** (exposición) y recaudación | Portal + PNDA (mensual) | **Integrado (parcial)**: accidentes sin coords → 71 tramos geocodificados (16,943 acc.) como capa espacial; tráfico por peaje (55/60) como exposición |
| **SINADEF (MINSA)** | Fallecidos con diagnóstico (extraer accidentes de tránsito vía ICD-10 V00–V99) | Temporalmente deshabilitado (cierre SINADEF); alternativas en datosabiertos.gob.pe | Identificado |
| **Geofabrik** (`download.geofabrik.de/south-america/peru.html`) | Red OSM completa de Perú: `peru-latest.osm.pbf` ~243 MB (actualización diaria) | Descarga libre | **Descargado** |
| **Waze for Cities (CCP)** | Alertas de usuarios en vivo (GeoRSS/JSON; `atf=ROAD_CLOSED,ACCIDENT`) | Requiere partner agreement | Identificado |
| **Photon / Nominatim** | Geocodificación gratuita (sin key; Photon sin limitación de comas) | API pública | **Integrado** |
| **Google Maps Directions** | Tráfico en vivo y rutas | **De pago**: Essentials $5–10/1,000 req (cap 10,000/mes) | Descartado (pago) |

### 10.2 Arquitectura del módulo
- **Ruteo**: OSRM self-hosted en Docker (`localhost:5000`, perfil `car`, algoritmo MLD) sobre `peru-latest.osm.pbf`. Cobertura: todo Perú.
- **Riesgo histórico**: `scripts/riesgo_red.py` — índice cKDTree (proyección equirectangular local, lat0=−10°) con **18,807 puntos** (ONSV 5,014 + SUTRAN 7,656 + OSITRAN 6,137 sintéticos). `score_route()` = muestreo cada 500 m, conteo en buffer ±1 km, gravedad (fallecidos×3 + lesionados×1 + 1) normalizado por km + alertas históricas SUTRAN (interrumpido ×2, restringido ×1, normal ×0.3) + **tráfico OSITRAN** (`trafico_km` = Σ min(AADT/100 000, 0.5) para peajes a ≤15 km, señal de exposición).
- **Motor v2 (temporal)**: `factor_temporal(dt)` — sáb ×1.25, dom ×1.1, noche 19–5h ×1.3, madrugada 5–8h ×1.05; `score_km_penalizado = score_km × factor + penalizaciones`. `perfil_segmentos(geometry, 5 km)` → perfil de riesgo por segmento en cada ruta.
- **Incidentes en vivo**: `scripts/alertas_sutran.py` — scrape de `carga_xlsx.php?tipo=MAPA` con caché TTL 15 min; motivo derivado por regex; penalización: interrumpido +5, restringido +1 (radio ±2 km).
- **Motor**: `scripts/ruta_segura.py` — geocoding Photon → hasta 3 alternativas OSRM → ranking `segura/rapida/corta` → mapa folium coloreado por riesgo con accidentes históricos y alertas en vivo.
- **Entrega**: CLI (`--salida`, `--json`), **API FastAPI** `api/app.py` (POST `/ruta_segura` con `salida`, GET `/health`, GET `/alertas`), **reporte HTML estático** `scripts/reporte_ruta.py` (autocontenido: mapa + perfil en base64), **dashboard** rediseñado (pestaña Ruta segura con selector de salida, perfil Plotly, alertas filtrables).

### 10.3 Scripts nuevos
| Script | Función |
|---|---|
| `download_osm.py` | Descarga `peru-latest.osm.pbf` de Geofabrik a `data/raw/osm/` |
| `osrm_build.py` | `docker run osrm/osrm-backend` (extract/partition/customize + routed MLD en :5000) |
| `osrm_router.py` | Cliente HTTP de OSRM (route con alternativas, nearest) |
| `riesgo_red.py` | Índice espacial + `score_route` + `factor_temporal` + `perfil_segmentos` |
| `alertas_sutran.py` | Alertas SUTRAN en vivo con caché + archivo histórico acumulativo |
| `ruta_segura.py` | Motor de decisión + mapa folium + CLI + `resumen_analisis()` |
| `reporte_ruta.py` | Reporte HTML estático autónomo |
| `ositran_data.py` | Accidentes y tráfico vehicular OSITRAN (PNDA) → tramos geocodificados + peajes |
| `api/app.py` | API FastAPI (uvicorn, puerto 8000) |
| `graphify_obsidian.py` | Genera vault Obsidian desde `graphify-out/graph.json` |

### 10.4a Señal histórica de alertas
- `HISTORICO_MAPA` de SUTRAN devuelve vacío (lado servidor) → el sistema **acumula**
  localmente cada descarga de alertas en `data/processed/dashboard/sutran_alertas_historico.json`
  (dedupe por `item|fecha_actualizacion`). El `RiesgoIndex` lo carga como capa de
  "zonas de incidentes recurrentes" (peso por estado: interrumpido ×2, restringido ×1, normal ×0.3).
- Capa OSITRAN: `RiesgoIndex` distribuye puntos sintéticos cada ~1 km sobre los tramos
  geocodificados (peso reparte los accidentes del tramo). Contribuye al `score_km`.

### 10.5 Manual del módulo
- `docs/modulo_ruta_segura.md` — arquitectura, instalación, uso (CLI/API/reporte/dashboard),
  casos verificados (Lima→Huancayo, Jauja→Pichanaqui, Trujillo→Chiclayo, Arequipa→Cusco)
  y limitaciones (OSRM necesita Docker, HISTORICO_MAPA vacío, OSITRAN sin coords, geocoding ambiguo).

### 10.6 Validación motor v2 y entregas (13/08/2026)
- `factor_temporal`: sáb 18h → 1.25; mié 12h → 1.0; dom 23h → 1.43 (×1.1 ×1.3). Lima→Huancayo sáb 18h: score 10.71 (vs 8.57 neutro), 59 segmentos de perfil.
- **Tráfico OSITRAN en el score**: Trujillo→Chiclayo 5 peajes en buffer (AADT máx 3,495, `trafico_km` 0.068, score 5.20); Lima→Huancayo 3 peajes (AADT máx 1,784, `trafico_km` 0.040, score 8.57). Se propaga a API, dashboard y reporte (`riesgo.trafico_km/peajes_buffer/aadt_max`).
- API: `/health` OK (18,807 puntos, 22 alertas históricas); POST `/ruta_segura` Trujillo→Chiclayo `salida=2026-08-15 19:30` → factor 1.625, `score_km_penalizado` 8.46, perfil por ruta.
- Reporte HTML: `data/processed/dashboard/reporte_ruta.html` (492 KB, autocontenido).
- Dashboard rediseñado: AppTest con clic en "Calcular" → 0 excepciones; mapa 1.2 MB y tabla de rutas generados.

### 10.4 Base de conocimiento (Graphify + Obsidian)
- Grafo del proyecto en `graphify-out/` (`graph.json` + `GRAPH_REPORT.md` + `graph.html`), indexado **solo código** (tree-sitter, offline, sin API key): 304 nodos, 384 enlaces, 35 comunidades; god nodes: `_load()`, `locate()`, `route_geometry()`, `haversine_km()`, `audit()`.
- Vault Obsidian en `graphify-out/obsidian/` (304 notas + índice), generado por `scripts/graphify_obsidian.py`. Abrir como vault en Obsidian para navegar el grafo.
- `AGENTS.md` con regla *query-first* (`graphify query/path/explain`) para consultas del codebase y estado del proyecto.
