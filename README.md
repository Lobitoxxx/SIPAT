# 🛡️ SIPAT — Sistema de Prevención de Accidentes de Tránsito

**Analítica de siniestralidad vial y prevención antes de viajar para la Red Vial Nacional del Perú.**

SIPAT cruza más de **51,000 siniestros reales** de tres fuentes oficiales (ONSV, SUTRAN y OSITRAN)
con la red vial nacional georreferenciada, y convierte ese histórico en dos productos:

1. **🧭 Viaja seguro** — el usuario elige origen, destino y hora de salida, y *antes de partir*
   obtiene un mapa de su ruta con cada accidente ocurrido punto por punto, un índice de riesgo
   **histórico** y otro **predictivo (IA)**, el clima y los avisos meteorológicos de la ruta,
   las emergencias activas cercanas, las alertas de tránsito en vivo y un reporte HTML descargable.
2. **📣 Reporta** — cualquier ciudadano puede reportar accidentes, derrumbes, congestión u otros
   peligros con una **foto y contexto**, ubicándolos sobre su propia ruta; esos reportes aparecen
   en los mapas de los demás viajeros.

Complementa lo anterior con analítica nacional: mapa interactivo multi-fuente, puntos negros,
tendencias temporales, ranking de rutas críticas y un modelo estadístico Negative Binomial que
cuantifica qué factores elevan o reducen el riesgo.

---

## 1. Funcionalidades

### Dashboard (Streamlit · `http://localhost:8501`) — 7 pestañas

| Pestaña | Qué ofrece |
|---|---|
| **🧭 Viaja seguro** | Pills de rutas populares, cálculo de hasta 3 rutas alternativas (OSRM), cards KPI (distancia, riesgo histórico, riesgo previsto IA, ruta más segura, accidentes en la ruta), banner semáforo de riesgo, mapa full-width de la ruta con cada accidente clicable (fecha, tipo, causa, gravedad), perfil de riesgo km a km, sección "¿Qué puede pasar?", pronóstico Open-Meteo + avisos SENAMHI + emergencias COEN, alertas SUTRAN en vivo, reportes ciudadanos cercanos y reporte HTML descargable |
| **📣 Reporta un incidente** | Formulario ciudadano: tipo (accidente, congestión, obra, derrumbe, inundación, animal, vía interrumpida…), severidad Leve/Moderado/Grave, descripción, **foto opcional**, autor opcional; ubicación por deslizador de kilómetro sobre tu ruta calculada o por referencia geocodificada ("peaje Pucusana", "km 45 PE-1S"). Mapa nacional de reportes recientes con fotos embebidas en los popups |
| **🗺️ Mapa nacional** | Red vial coloreada por siniestros/km (amarillo→rojo) con capas toggleables: tramos, puntos negros y alertas históricas SUTRAN |
| **⚠️ Puntos negros** | Los 129 tramos con exceso de siniestros estadísticamente significativo, mapa + tabla descargable, fuente dominante por punto |
| **📈 Tendencias** | Series por año/mes/día/hora y gravedad (fallecidos por siniestro), separadas por fuente |
| **🏆 Rutas críticas** | Top 15 rutas y departamentos, tipos y causas más frecuentes |
| **📊 Modelo** | IRRs (Incidence Rate Ratios) del modelo NegBin por fuente con intervalos de confianza, y explorador de los 3,750 tramos |

### API REST (FastAPI · `http://localhost:8000`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio, puntos de riesgo cargados, alertas históricas |
| POST | `/ruta_segura` | Análisis completo de rutas entre origen y destino |
| POST | `/ruta_segura_completa` | Lo anterior + resumen de riesgo (histórico/predictivo) + clima + avisos |
| GET | `/alertas` | Alertas SUTRAN actuales (cache 15 min) |
| GET | `/avisos` | Avisos SENAMHI + emergencias COEN |
| GET | `/reportes` | Reportes ciudadanos de los últimos N días |
| POST | `/reportes` | Registrar un reporte ciudadano (validación Perú + dedupe) |

Ejemplo:

```bash
curl -X POST http://localhost:8000/ruta_segura_completa \
  -H "Content-Type: application/json" \
  -d '{"origin": "Lima", "dest": "Huancayo", "salida": "2026-08-22 08:00"}'
```

### Reporte HTML estático

`scripts/reporte_ruta.py` genera un reporte autocontenido (mapa, perfil de riesgo, clima,
tipos de incidente) desde cualquier resultado de análisis: `reporte_desde_resumen()`.

---

## 2. Fuentes de datos

| Fuente | Contenido | Volumen usado | Archivo procesado |
|---|---|---|---|
| **ONSV** (Observatorio Nacional de Seguridad Vial) | Siniestros fatales/lesionados 2021-2025 con clase, causa, hora, clima | 5,014 geocodificados | `data/processed/onsv_nacional_geocod.csv` |
| **SUTRAN** (Superintendencia de Transporte Terrestre) | Accidentes 2020-2021 + **alertas de tránsito en vivo** (interrumpido/restringido) | 7,656 registros · 4,116 en dashboard · alertas históricas acumuladas | `data/processed/sutran_accidentes_geocod.csv`, `dashboard/sutran_alertas_historico.json` |
| **OSITRAN** (Organismo Supervisor de Inversión en Infraestructura) | Accidentes en 16 concesiones viales 2019-2025 + flujo vehicular (AADT) por peaje | 41,833 accidentes · 55 peajes con tráfico · 71 tramos geocodificados | `data/processed/ositran_*.csv` |
| **MTC** (Ministerio de Transportes) | Red vial nacional segmentada por kilómetro | 3,750 tramos · ~28,918.5 km | `data/processed/tramos_red.csv` |
| **INGEMMET** | Peligros geológicos (para distancia a zonas de riesgo) | capa espacial | `features_distancia.csv` |
| **SENAMHI** (WFS oficial) | Avisos meteorológicos a 24 h (nivel, fecha, recomendación) | cache TTL | cache `clima/` |
| **Open-Meteo** | Pronóstico temperatura/lluvia/viento muestreado sobre la geometría de la ruta | cache TTL | cache `clima/` |
| **COEN-INDECI** | Emergencias activas (incendios, inundaciones, sismos) geocodificadas | últimos 7 días | cache `clima/` |
| **OpenStreetMap / OSRM** | Grafo vial para cálculo de rutas — servidor local en Docker | Perú completo | `data/osm/peru-latest.osm.pbf` |

> Todas las fuentes públicas. Los CSV crudos y procesados se versionan dentro de `data/`.

---

## 2 bis. Capa de ingesta y calidad: `etl-project/`

Antes de que la analítica procese los datos, [`etl-project/`](etl-project/README.md) los
ingiere y **verifica que cumplen un contrato**. Es un subproyecto con su propio repo Git.

| | SIPAT-ETL | SIPAT (este repo) |
|---|---|---|
| **Qué hace** | Extrae, limpia, valida y mide la calidad | Analiza, modela y genera rutas seguras |
| **Salida** | Bronze/Silver/Gold en Parquet + SQL | Mapas, modelos, dashboard |
| **Garantía** | Quality gate: publica o bloquea | Consume datos que pasaron el gate |

```bash
cd etl-project
pip install -r requirements.txt
python scripts/run_pipeline.py     # ONSV 9,106 + cinemómetros 160,018
python scripts/verify_etl.py       # 4/4 checks
python -m pytest tests -q          # 87 tests
```

Estado actual: ambos datasets pasan el gate (DQS 92.07 y 92.00), sin violaciones críticas.
Documentación propia en [`etl-project/docs/`](etl-project/docs/), incluido el
[informe técnico](etl-project/docs/informe_etl_v1.md) con los 10 defectos del propio sistema
que se detectaron y corrigieron sobre datos reales.

---

<a id="auditoria"></a>

## 2 ter. Auditoría: ¿son de fiar los datos y la predicción?

Un DQS de 92 y un buen ajuste en entrenamiento **no garantizan** que las fuentes sean fiables ni
que el modelo prediga. Dos módulos submiten el sistema a prueba y **declaran lo que encuentran**
en vez de producir un único número tranquilizador.

### Las cuatro preguntas, cuatro módulos — no las mezcles

| Pregunta | Dónde se responde | Qué **NO** contesta |
|---|---|---|
| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` (DQS) | Ni si la fuente es de fiar, ni si el modelo predice |
| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` | Audita el **proceso**, no el resultado estadístico |
| **¿Las fuentes ONSV/SUTRAN/OSITRAN son de fiar?** | **`scripts/fiabilidad_fuentes.py`** | Una fuente puede ser fiable y aun así el modelo no predecir |
| **¿La predicción aguanta fuera de muestra?** | **`scripts/validez_predictiva.py`** | Un mal R² aquí no dice que los datos sean malos |

Ambos usan la misma forma de responder: una **tabla de afirmaciones con veredicto + evidencia +
límite**, y **ninguno se colapsa en un índice único**. Combinarlos exigiría decidir cuánto pesa
cada riesgo, y esa decisión no sale de estos datos.

### Fiabilidad de las fuentes

Módulo `scripts/fiabilidad_fuentes.py` · salida `data/processed/dashboard/fiabilidad_fuentes.json`
· detalle en [`docs/fiabilidad_fuentes.md`](docs/fiabilidad_fuentes.md)

| Afirmación | Veredicto | Evidencia / límite |
|---|---|---|
| Las coordenadas de ONSV sirven para geocodificar por km | **SÍ** | 5.014 filas, 0 sin coordenada, 0 fuera del Perú |
| Las coordenadas de SUTRAN sirven para geocodificar por km | **CON RESERVAS** | 499 filas (**6,12 %**) sin coordenada sobre 8.155 |
| El doble reporte dentro de cada fuente es marginal | **SÍ** | 320 coincidencias km+fecha → **204** al añadir modalidad |
| OSITRAN sirve como capa de contraste de la red nacional | **NO COMO CAPA COMPLETA** | Cubre **26 de 150 rutas (17,3 %)** y solo vías concedidas |
| Se puede estimar la subnotificación | **NO ESTIMABLE** | Ver abajo: los dos muestreos no son de la misma población |
| El solape ONSV/SUTRAN no es un artefacto del umbral | **SÍ** | Estable con radio 0,1–1 km y tolerancia 0–7 días |

**Dos errores de lectura que casi llegan a conclusiones falsas:**

- **Los «3.786 duplicados» de SUTRAN no son duplicados.** La coordenada de SUTRAN viene del
  *kilómetro del tramo* donde se registró el accidente, no de un GPS del lugar, así que 12
  accidentes distintos del mismo km comparten punto. El número accionable es **204, no 3.786**.
- **La cobertura de OSITRAN salía 0,0 %** porque se cruzaba con la red por `siglas` (16 valores,
  código corto de concesión) cuando la red vial usa el identificador de tramo en formato MTC
  (`ruta`, 103 valores). Era un cruce de dos sistemas de códigos distintos, no un hallazgo.

**Por qué la subnotificación no es estimable.** Lincoln-Petersen da N ≈ 153.670 (IC95
83.868–281.568) con solo 26 eventos en común y un intervalo **estrecho** (multiplicador ≈ 1,77).
El veredicto sigue siendo NO ESTIMABLE por una razón estructural: el estimador exige dos
muestreos independientes de la misma población, y ONSV/SUTRAN difieren en **56,1 % de rutas no
comunes** y **87,5 % de meses no comunes**. Aplicado aquí mediría la diferencia entre dos
poblaciones. *Una confianza alta sobre la pregunta equivocada sigue siendo la pregunta equivocada.*

### Validez predictiva

Módulo `scripts/validez_predictiva.py` · salida `data/processed/dashboard/validez_predictiva.json`
· detalle en [`docs/validez_predictiva.md`](docs/validez_predictiva.md)

Se reconstruye el panel tramo × año (3.750 × 5 = **18.750 celdas, 86,4 % en cero**) con la misma
función `panel_anual.construir_panel` que alimenta `dataset_modelo.csv`, y se valida con
`GroupKFold` de 5 folds **agrupado por corredor, no por tramo** — `PE-1N` y `PE-1S` son la misma
Panamericana en sentidos opuestos y, separados, el test sería copia del train.

| Modelo | MAE | R² | Dev. Poisson |
|---|---|---|---|
| Media de entrenamiento | 0,464 | −0,009 | 1,252 |
| Mediana de entrenamiento | 0,267 | −0,079 | *n/d* |
| **NegBin con offset** | **0,370** | **+0,102** | **0,824** |

| Afirmación | Veredicto |
|---|---|
| El modelo usa las covariables para predecir mejor que la media | **SÍ** |
| El R² justifica usarlo como pronóstico | **NO** |
| El modelo supera a la persistencia en el holdout temporal | **AMBIGUO** |
| El holdout temporal mide capacidad de predecir a futuro | **NO** |

**El límite que estos datos no pueden sortear.** ONSV registra **−67 % de siniestros en 2025**
frente al promedio 2021-2024, con los 12 meses cubiertos y una tasa de mortalidad casi constante
(1,24 → 1,21 fallecidos por siniestro). Un descenso de volumen con mortalidad constante no es un
patrón de mejora: si bajaran los accidentes graves, la tasa subiría. Lo más consistente es un
**cambio en la captura de la fuente**, y el error del holdout mezcla error del modelo con cambio de
la fuente sin que estos datos permitan separarlos.

**Conclusión operativa:** el modelo sirve para **priorizar** tramos (ordena mejor que la media) y
**no** para **prevenir cuántos siniestros** ocurrirán. El dashboard debe decirlo así en lugar de
mostrar un número como si fuera un pronóstico.

### Reproducir

```bash
python scripts/fiabilidad_fuentes.py      # -> fiabilidad_fuentes.json
python scripts/validez_predictiva.py      # -> validez_predictiva.json  (requiere scikit-learn)
python -m pytest tests/test_fiabilidad_fuentes.py tests/test_validez_predictiva.py -q
```

También hay dos notebooks que explican los hallazgos sobre datos reales:
`notebooks/05_fiabilidad_fuentes.ipynb` y `notebooks/06_validez_predictiva.ipynb`.

---

## 3. Cómo se manejan los datos (pipeline)

```mermaid
flowchart LR
    subgraph FUENTES["Fuentes oficiales"]
        ONSV["ONSV<br/>5,014 siniestros"]
        SUTRAN["SUTRAN<br/>7,656 + alertas"]
        OSITRAN["OSITRAN<br/>41,833 + peajes"]
        MTC["MTC red vial<br/>3,750 tramos · 28,918.5 km"]
        INGEMMET["INGEMMET<br/>peligros geológicos"]
    end

    subgraph INGESTA["Ingesta y geocodificación"]
        GEOC["Geocodificación lineal por km<br/>(abscisado: ruta + km → lat/lon)"]
        MODELO["dataset_modelo.csv<br/>3,750 × 48"]
    end

    subgraph PROCESOS["Procesamiento"]
        BD["build_dashboard_data.py<br/>→ tramos_geo.json multi-fuente"]
        PN["build_puntos_negros.py<br/>EB de Hauer → 133 puntos negros"]
        NB["modelo_multi.py / prediccion.py<br/>NegBin → IRRs + predictor"]
    end

    subgraph SERVICIOS["Servicios"]
        OSRM["OSRM (Docker :5000)"]
        API["FastAPI (:8000)"]
        APP["Streamlit (:8501)"]
    end

    ONSV --> GEOC
    SUTRAN --> GEOC
    OSITRAN --> GEOC
    MTC --> GEOC
    INGEMMET --> MODELO
    GEOC --> MODELO
    MODELO --> BD
    MODELO --> PN
    MODELO --> NB
    BD --> APP
    PN --> APP
    NB --> APP
    OSRM --> APP
    BD --> API
    NB --> API
```

### Pasos clave

1. **Geocodificación lineal**: cada accidente llega con "ruta + kilómetro" (ej. PE-1S km 45).
   Se proyecta al polilíneo correspondiente de la red MTC usando el abscisado por km.
2. **Dataset espacial** (`dataset_modelo.csv`, 3,750 tramos × 48 variables): siniestros por fuente,
   fallecidos, topografía, superficie, velocidad proyectada, carriles, sinuosidad, distancia a
   peligros INGEMMET, peajes, etc.
3. **Unificación multi-fuente** (`build_dashboard_data.py` → `tramos_geo.json`): suma ONSV+SUTRAN+
   OSITRAN por tramo, distribuye accidentes OSITRAN (que vienen por tramo de concesión), añade
   alertas históricas SUTRAN y tráfico de peajes; exporta además los eventos por fuente como CSV
   ligeros para el dashboard.
4. **Puntos negros** (`build_puntos_negros.py`): ventana deslizante de 1 km + tres criterios —
   percentil 95 regional, exceso Empirical Bayes (método de Hauer) > 1.0 y residuos del modelo
   > 2.0 — con campo `fuente_dominante`.
5. **Modelo NegBin** (`modelo_multi.py` / `prediccion.py`): regresión binomial negativa por fuente
   (ONSV, SUTRAN, COMBINADO) con offset de exposición; produce IRRs con IC95% y un predictor que
   empalma cualquier geometría de ruta a los tramos (cKDTree) y devuelve siniestros esperados/km
   con % de cobertura de red.
6. **Índice de riesgo por km** (motor `riesgo_red.py`):

   ```
   score_km = (n_siniestros + 0.5·gravedad)/km
            + alertas_históricas_SUTRAN/km          # zonas recurrentes
            + Σ tráfico_peajes(≤15 km)               # min(AADT/100000, 0.5)
   score_final = score_km · factor_temporal(hora/día) + penalización_alertas_en_vivo
   ```

   Umbrales mostrados al usuario: **histórico** Bajo < 4 ≤ Medio ≤ 8 < Alto (score/km);
   **predictivo** Bajo < 0.5 ≤ Medio ≤ 1.2 < Alto (siniestros/km esperados).
   Factor temporal: sábado ×1.25, domingo ×1.1, noche 19-05h ×1.3, madrugada 05-08h ×1.05;
   alertas SUTRAN "INTERRUMPIDO" suman +5 y "RESTRINGIDO" +1 (±2 km).

### Datos en tiempo real y caches

- Alertas SUTRAN: descarga con TTL de 15 min; cada consulta alimenta el archivo acumulativo
  `sutran_alertas_historico.json` (señal de incidentes recurrentes).
- Clima/avisos/emergencias: cachés JSON con TTL (SENAMHI ~3 h, Open-Meteo ~2 h, COEN ~6 h);
  el botón "Actualizar ahora" fuerza refresco.
- Reportes ciudadanos: almacenamiento **append-only**
  (`data/processed/dashboard/reportes_ciudadanos.json` + fotos en `reportes_fotos/`),
  con validación de coordenadas dentro de Perú y deduplicación de 10 minutos.

### Flujo "Viaja seguro" (antes de salir)

```mermaid
sequenceDiagram
    actor U as Usuario
    participant D as Dashboard<br/>🧭 Viaja seguro
    participant G as geocode()<br/>(cache TTL)
    participant O as OSRM :5000
    participant R as ruta_segura.py<br/>+ riesgo_red.py
    participant P as prediccion.py<br/>(NegBin IA)
    participant C as clima.py<br/>(SENAMHI·OMeteo·COEN)

    U->>D: origen, destino, fecha/hora salida
    D->>G: geocodificar extremos
    G-->>D: lat/lon
    D->>O: /route/v1/driving
    O-->>D: geometría de la ruta + km
    par Análisis de riesgo
        D->>R: analizar(geometría, salida)
        R->>R: buffer 2 km · score_km ·<br/>factor temporal · alertas SUTRAN
        R-->>D: nivel histórico + perfil km-a-km
    and Predicción IA
        D->>P: predecir_ruta(geometría)
        P-->>D: siniestros/km esperados + cobertura
    and Clima y emergencias
        D->>C: avisos SENAMHI · pronóstico · COEN
        C-->>D: avisos activos en la ruta
    end
    D-->>U: banner semáforo · mapa con accidentes ·<br/>perfil · clima · ruta más segura · reporte HTML
```

### Flujo del reporte ciudadano

```mermaid
flowchart TD
    A[Usuario llena el formulario<br/>📣 Reporta] --> B{Foto PNG/JPG?}
    B -- sí --> C[Guardar en reportes_fotos/]
    B -- no --> D
    C --> D{Validaciones}
    D -- "coordenadas fuera de Perú" --> X["❌ Rechazado (HTTP 400)"]
    D -- "descripción demasiado corta" --> X
    D -- "duplicado: mismo tipo,<br/><150 m y <10 min" --> Y["↩️ Se omite (dedupe)"]
    D -- ok --> E["agregar_reporte()<br/>storage append-only"]
    E --> F[(reportes_ciudadanos.json)]
    E --> G[(reportes_fotos/)]
    F --> H["🗺️ Mapa de reportes<br/>(fotos embebidas base64)"]
    F --> I["reportes_en_ruta()<br/>→ aparecen en Viaja seguro"]
    F --> J["GET /reportes · POST /reportes<br/>(API FastAPI)"]
```

---

## 4. Arquitectura y diagramas interactivos

SIPAT sigue una **topología en estrella** centrada en la API FastAPI: el dashboard, el motor de
riesgo y los servicios externos no conversan entre sí, sino que todos pasan por el **nodo central**.
La API es el único punto que orquesta las capas de datos y expone endpoints a la interfaz.

```
            ┌────────────┐    Fuentes: ONSV · SUTRAN · OSITRAN · MTC · INGEMMET
            │  DATOS     │    tramos_geo.json (cKDTree) · ositran_*.csv · reportes
            └─────┬──────┘
                  │
┌──────────┐      │      ┌────────────────┐
│ OSRM     │      │      │  MOTOR RIESGO  │  riesgo_red.py · factor_temporal()
│ (Docker) │──────┼──────│  prediccion.py │  NegBin (puntual) · clima.py
└──────────┘      │      └────────────────┘
                  │
             ┌────┴───┐    ┌───────────────┐
             │  API   │────│  DASHBOARD    │  Streamlit · 7 pestañas
             └────────┘    └───────────────┘
```

**¿Por qué estrella?**
- **Límite de responsabilidades**: el dashboard solo consume payloads ya integrados; nunca
  geocodifica, modela ni consulta OSRM por su cuenta.
- **Un solo dueño del ranking**: que las 3 rutas, el score histórico y el predictivo salgan de un
  único endpoint evita versiones divergentes entre pestañas.
- **Cachés centralizadas** en la API (alertas SUTRAN, clima, avisos) con TTL y botón de refresco;
  el cacheo no se reparte entre procesos.
- **Gobernanza de datos**: todos los accesos a `tramos_geo.json`, peajes y reportes pasan por la
  API, de modo que validar (Perú + dedupe), auditar y testear (AppTest + 30 checks) es verificable
  en un solo front.

**Diagramas interactivos** (auto-contenidos, 1 fichero HTML cada uno; abren con cualquier navegador):

| Diagrama | Contenido | Ver en línea |
|---|---|---|
| **Arquitectura** | Topología estrella completa: API como hub, flujos con OSRM/OSITRAN/alertas | [sipat-architecture.html](https://htmlpreview.github.io/?https://github.com/Lobitoxxx/SIPAT/blob/main/docs/archify/sipat-architecture.html) |
| **Flujo de datos** | De las 3 fuentes geocodificadas al dataset 3,750×48 y a los servicios | [sipat-dataflow.html](https://htmlpreview.github.io/?https://github.com/Lobitoxxx/SIPAT/blob/main/docs/archify/sipat-dataflow.html) |
| **Secuencia "Viaja seguro"** | Solicitud → cálculo de riesgo (motor+IA+clima) → respuesta integrada | [sipat-sequence.html](https://htmlpreview.github.io/?https://github.com/Lobitoxxx/SIPAT/blob/main/docs/archify/sipat-sequence.html) |
| **Workflow del reporte ciudadano** | Formulario → validación+dedupe → almacén append-only → mapa | [sipat-workflow.html](https://htmlpreview.github.io/?https://github.com/Lobitoxxx/SIPAT/blob/main/docs/archify/sipat-workflow.html) |

> Los HTML viven en `docs/archify/` (preview del navegador sobre el repo) y también se guardan
> automáticamente en local dentro de la carpeta `docs/archify/` del proyecto.

---

## 5. Metodología de desarrollo: SCRUM + CRISP-DM

**SIPAT integra dos marcos complementarios**: CRISP-DM ordena el *ciclo de datos* (qué se hace con
los datos y cuándo) y SCRUM organiza la *entrega de producto* (quién hace qué y en qué sprints).

### CRISP-DM — ciclo de datos en 6 fases

```mermaid
flowchart TB
    A["1 · Entendimiento del negocio<br/>Prevenir accidentes antes de viajar"] --> B["2 · Entendimiento de los datos<br/>51,000+ siniestros en 3 fuentes"]
    B --> C["3 · Preparación de los datos<br/>Geocodificación lineal · limpieza · dataset 3,750×48"]
    C --> D["4 · Modelado<br/>NegBin por fuente → IRRs + predictor"]
    D --> E["5 · Evaluación<br/>AIC · 133 puntos · validez fuera de muestra"]
    E --> F["6 · Despliegue<br/>Datos ligeros → dashboard · API · reporte HTML"]
    F -. "lecciones → nuevo sprint" .-> A
```

Las **6 fases** aplicadas al proyecto:

| Fase CRISP-DM | Qué se hizo en SIPAT |
|---|---|
| **1. Negocio** | Productos: índice de riesgo por ruta + reporte ciudadano; usuarios: viajeros e instituciones |
| **2. Datos** | Inventario (Fase 0): 3 fuentes de siniestros + red vial MTC + peligros INGEMMET; calidad: geocodificación lineal (~14 m), cobertura SUTRAN 99.4% |
| **3. Preparación** | Limpieza (nulos, duplicados, rutas PE-XX), unificación multi-fuente por tramo, features espaciales (buffer 2 km, cKDTree), tráfico de peajes |
| **4. Modelado** | Negative Binomial por fuente con offset de exposición; predictor que empalma la ruta del usuario a los tramos |
| **5. Evaluación** | AIC NegBin 8,663 vs Poisson 11,984 (mezcla ONSV+SUTRAN); validación AppTest + 30 checks; comparación con umbrales de riesgo |
| **6. Despliegue** | Dashboard 7 pestañas, API REST, reporte HTML autocontenido, datos ligeros en `data/processed/dashboard/` |

### SCRUM — 3 sprints con entregas verificables

```mermaid
gantt
    title SIPAT — planificación por sprints
    dateFormat YYYY-MM
    section Sprint 0
    Fase 0 · inventario de datos      :a1, 2025-11, 1M
    Fase 1 · geocodificación y modelo :a2, 2025-12, 2M
    section Sprint 1
    Motor ruta segura v1              :b1, 2026-03, 1M
    Alertas SUTRAN + OSITRAN          :b2, 2026-04, 1M
    section Sprint 2
    Motor v2 · API · reporte HTML     :c1, 2026-06, 2M
    section Sprint 3
    Predicción + clima + COEN         :d1, 2026-08, 1M
    Reportes ciudadanos + dashboard   :d2, 2026-08, 1M
```

Cada sprint entregó un **incremento verificado**: batería de 30 comprobaciones, AppTest headless
del dashboard (7 pestañas + "Analizar mi ruta") y los diagramas Archify que documentan el sistema
en su estado final.

---

## 6. Estructura del proyecto

```
SIPAT/
├── api/app.py                  # API FastAPI (endpoints arriba)
├── dashboard/
│   ├── app.py                  # orquestador: datos, filtros, 7 tabs
│   ├── theme.py                # CSS moderno (Inter, gradiente, cards, pills)
│   ├── viaja_seguro.py         # pestaña principal (producto)
│   ├── reporta.py              # reportes ciudadanos con foto
│   ├── analitica.py            # mapa nacional, puntos negros, tendencias
│   └── modelo_tab.py           # rutas críticas y modelo NegBin
├── scripts/
│   ├── download_osm.py         # descarga OSM Perú
│   ├── osrm_build.py           # prepara grafo y sirve OSRM (--serve)
│   ├── osrm_router.py          # cliente OSRM local
│   ├── riesgo_red.py           # índice de riesgo espacial (cKDTree)
│   ├── ruta_segura.py          # motor: analizar(), mapa(), geocode()
│   ├── alertas_sutran.py       # alertas en vivo + histórico
│   ├── ositran_data.py         # ingesta/geocodificación OSITRAN
│   ├── clima.py                # SENAMHI WFS + Open-Meteo + COEN
│   ├── prediccion.py           # capa predictiva NegBin
│   ├── reportes_ciudadanos.py  # backend de reportes con foto
│   ├── reporte_ruta.py         # reporte HTML autocontenido
│   ├── build_dashboard_data.py # reconstruye tramos_geo.json multi-fuente
│   ├── build_puntos_negros.py  # detector de puntos negros (EB de Hauer)
│   ├── modelo_multi.py         # NegBin multi-fuente (IRRs)
│   ├── fiabilidad_fuentes.py   # auditoría: ¿son de fiar ONSV/SUTRAN/OSITRAN?
│   ├── validez_predictiva.py   # auditoría: ¿la predicción aguanta fuera de muestra?
│   ├── build_notebooks.py      # genera notebooks 01-06 con validación de sintaxis
│   ├── boot_services.py        # arranca Docker+OSRM, API y Streamlit
│   ├── verificar_proyecto.py   # batería de 30 verificaciones
│   └── apptest_check.py        # AppTest del dashboard (7 tabs + calcular)
├── tests/                      # regresiones de datos, modelo, KPIs y auditoría
├── data/
│   ├── raw/                    # archivos originales descargados
│   ├── processed/              # datasets geocodificados y modelo
│   ├── processed/dashboard/    # assets ligeros del dashboard (JSON/CSV)
│   └── osm/                    # extracto PBF de Perú
├── docs/
│   ├── informe_sipat.md             # informe técnico, matriz técnica, manual, figuras
│   ├── fiabilidad_fuentes.md        # auditoría de las tres fuentes
│   ├── validez_predictiva.md        # validación del modelo fuera de muestra
│   └── archify/                     # 4 diagramas interactivos (HTML autocontenidos)
├── notebooks/                  # 01-06: exploración, auditoría y validación
├── presentacion_sipat/         # presentación interactiva del sistema (Slidev)
└── graphify-out/               # grafo de conocimiento del código
```

---

## 7. Puesta en marcha

**Requisitos**: Windows/Linux, Python ≥ 3.10, Docker Desktop (para OSRM).
Dependencias principales: `streamlit folium plotly pandas numpy scipy statsmodels fastapi
uvicorn requests shapely`.

```bash
# 1. Preparar el grafo OSRM la primera vez (descarga + preprocesamiento, tarda)
python scripts/download_osm.py
python scripts/osrm_build.py

# 2. Arrancar todo (Docker OSRM :5000, API :8000, Dashboard :8501)
python scripts/boot_services.py

# 3. Abrir el sistema
#    http://localhost:8501  (dashboard)
#    http://localhost:8000/docs  (API interactiva)

# 4. Reconstruir datos del dashboard si cambian los datasets
python scripts/build_dashboard_data.py
python scripts/build_puntos_negros.py
python scripts/modelo_multi.py

# 5. Verificación completa (30 comprobaciones: assets, servicios, endpoints, AppTest)
python scripts/verificar_proyecto.py
```

---

## 8. Verificación y calidad

- `scripts/verificar_proyecto.py`: **30 checks** — presencia de datasets y documentos, servicios
  UP (OSRM/API/Streamlit), endpoints de API con respuesta válida, AppTest del dashboard
  (7 pestañas + botón "Analizar mi ruta" sin excepciones), exportaciones JSON/CSV y reportes HTML.
  Guarda el resultado en `data/processed/dashboard/verificacion.json`.
  **Los 30 pasan con los tres servicios encendidos**; con el stack apagado los 8 de API y
  servicios fallan y la corrida marca `all_required_ok: false`. Es dependencia de entorno, no
  una regresión.
- `scripts/apptest_check.py`: prueba headless de UI con Streamlit AppTest.
- Validaciones del módulo de reportes: coordenadas dentro de Perú, descripción mínima,
  deduplicación temporal-espacial, tipos y severidades acotados.
- `tests/` — regresiones sobre datos reales, no solo fixtures sintéticas:

  | Suite | Qué blinda |
  |---|---|
  | `test_fiabilidad_fuentes.py` | Cada afirmación de la auditoría de fuentes como regresión |
  | `test_validez_predictiva.py` | Cada veredicto de la validación fuera de muestra |
  | `test_dashboard_kpis.py` | El contrato del KPI unionado: `siniestros_union_comun` existe y la unión nunca supera la suma ingenua |
  | `test_panel_anual.py` | La construcción del panel tramo × año que usa la validación |
  | `test_deduplicacion_eventos.py` | La deduplicación ONSV/SUTRAN y la identidad contable de la unión |
  | `test_eb_tramos.py`, `test_modelo_*.py` | Detección de puntos negros y ajuste del modelo |

```bash
python -m pytest tests -q
```

---

## 9. Decisiones metodológicas y limitaciones

- **Tres fuentes, tres realidades**: ONSV registra siniestros fatales/por lesiones con calidad
  variable por departamento; SUTRAN cubre 2020-2021; OSITRAN cubre solo concesiones (sin
  coordenadas exactas, se asignan al centroide del tramo). El sistema nunca mezcla cifras como si
  fueran homogéneas: todo análisis permite separar por fuente.
- **OSITRAN no es una capa completa** (ver [2 ter](#auditoria)):
  cubre 26 de 150 rutas (17,3 %). Sirve para describir caminos concedidos, **no** para corregir el
  total nacional, porque las rutas concedidas concentran tráfico.
- **SUTRAN tiene coordenadas incompletas**: 499 de 8.155 filas (6,12 %) sin coordenada, por lo que
  su geocodificación por km es usable **con reservas**.
- **La subnotificación no es estimable con estos datos**: Lincoln-Petersen exige dos muestreos
  independientes de la misma población y ONSV/SUTRAN difieren en 56,1 % de rutas y 87,5 % de meses.
- **El riesgo histórico no es una predicción**: es exposición pasada; por eso existe la segunda
  capa predictiva (NegBin) que ajusta por longitud, tráfico y características viales.
- **La capa predictiva ordena pero no pronostica**: la validación fuera de muestra concluye que
  sirve para **priorizar** tramos, no para prever cuántos siniestros ocurrirán (devianza 0,824
  contra 1,252 de la media, pero R² de solo +0,102).
- **ONSV 2025 registra −67 %** de siniestros con tasa de mortalidad constante: es un cambio en la
  captura de la fuente, no una mejora de la seguridad vial. El holdout temporal no puede separar
  error del modelo de cambio de fuente.
- **Clima y avisos dependen de servicios externos** (SENAMHI/Open-Meteo/COEN); ante fallo el
  dashboard muestra "no disponible" sin romper la experiencia.
- **Los reportes ciudadanos son autodeclarados**: sin moderación aún; sirven como señal
  complementaria y reciente, no como dato oficial.
- Cobertura predictiva típica ≈ 42% de la longitud de la ruta (tramos con features completas).
- **El grafo de conocimiento está desactualizado**: `graphify-out/graph.json` conserva los nodos
  pero perdió las aristas en un update incremental, y el check `graph:graph_json` valida que el
  fichero exista y tenga nodos, **no que tenga aristas**.

---

## 10. Documentación ampliada

- `docs/informe_sipat.md` — informe técnico completo (Fase 0/Fase 1).
- `docs/matriz_tecnica.md` — decisiones técnicas por componente.
- `docs/modulo_ruta_segura.md` — manual del motor de ruta segura.
- `docs/fiabilidad_fuentes.md` — auditoría de ONSV, SUTRAN y OSITRAN: qué se puede afirmar y qué no.
- `docs/validez_predictiva.md` — validación del modelo fuera de muestra y sus límites.
- `docs/archify/*.html` — 4 diagramas interactivos (arquitectura, flujo de datos, secuencia y workflow).
- `notebooks/01..06` — exploración, auditoría de medición, fiabilidad de fuentes y validez predictiva.
- `presentacion_sipat/` — presentación interactiva del sistema (Slidev, 57 slides) con `npm run dev`.
- `graphify-out/GRAPH_REPORT.md` — arquitectura como grafo de conocimiento.

---

*Desarrollado como proyecto de analítica con Big Data sobre la Red Vial Nacional del Perú.*
