---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 07 · Arquitectura <span class="sipat-essential">esencial</span></p>
  <h2>Topología en estrella</h2>
  <p class="sipat-section__desc">
    El dashboard, el motor de riesgo y los servicios externos <b>no conversan entre sí</b>.
    Todo pasa por un único nodo central: la API FastAPI.
  </p>
  <span class="sipat-section__num">07</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Arquitectura <span class="sipat-essential">esencial</span></span>
    <h1>Por qué una estrella y no una malla</h1>
  </div>
  <div class="sipat-head__aside">
    Topología documentada en<br>
    <code>docs/archify/</code>
  </div>
</div>

<ArchifyDiagram src="/svg/arquitectura.svg" alt="Topología en estrella de SIPAT con la API FastAPI como nodo central" :height="360" />

<div class="sipat-cards" style="margin-top:11px">
  <div class="sipat-card">
    <div class="sipat-card__t">1 · Límite de responsabilidades</div>
    <div class="sipat-card__d">El dashboard solo consume payloads ya integrados. <b>Nunca</b> geocodifica,
    modela ni consulta OSRM por su cuenta.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">2 · Un solo dueño del ranking</div>
    <div class="sipat-card__d">Que las 3 rutas, el score histórico y el predictivo salgan de un único
    endpoint <b>evita versiones divergentes entre pestañas</b>.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">3 · Cachés centralizadas</div>
    <div class="sipat-card__d">Alertas SUTRAN, clima y avisos se cachean <b>en la API</b> con TTL y botón de
    refresco. El cacheo no se reparte entre procesos.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#059669">
    <div class="sipat-card__t">4 · Gobernanza de datos</div>
    <div class="sipat-card__d">Todo acceso a <code>tramos_geo.json</code>, peajes y reportes pasa por la API:
    validar, auditar y testear queda <b>verificable en un solo front</b>.</div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Arquitectura <span class="sipat-essential">esencial</span></span>
    <h1>Los 3 servicios y sus 7 endpoints</h1>
  </div>
  <div class="sipat-head__aside">
    Arranque con<br>
    <code>python scripts/boot_services.py</code>
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:13px">
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">🧭 OSRM · <code>:5000</code></div>
    <div class="sipat-card__d">Router vial en <b>Docker</b>, perfil <code>car</code>, sobre el extracto de
    OSM de Perú completo. Calcula la geometría de hasta 3 alternativas.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#4f46e5">
    <div class="sipat-card__t">🔌 FastAPI · <code>:8000</code></div>
    <div class="sipat-card__d">Hub de la topología en estrella. Sirve <code>/docs</code> interactivo
    (OpenAPI/Swagger) sin escribir una línea de documentación adicional.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0891b2">
    <div class="sipat-card__t">📺 Streamlit · <code>:8501</code></div>
    <div class="sipat-card__d">Dashboard de <b>7 pestañas</b>, tema claro fijado, consumiendo datos ligeros
    de <code>data/processed/dashboard/</code>.</div>
  </div>
</div>

<table class="sipat-table" style="font-size:.76rem">
  <thead><tr><th style="width:9%">Método</th><th style="width:26%">Endpoint</th><th>Qué devuelve</th></tr></thead>
  <tbody>
    <tr><td><code>GET</code></td><td><code>/health</code></td><td>Estado del servicio, <b>18.807</b> puntos de riesgo cargados, alertas históricas, uptime de OSRM</td></tr>
    <tr><td><code>POST</code></td><td><code>/ruta_segura</code></td><td>Análisis completo de rutas: geometría, score, perfil, alertas, accidentes</td></tr>
    <tr><td><code>POST</code></td><td><code>/ruta_segura_completa</code></td><td>Lo anterior <b>+ resumen de riesgo</b> (histórico y predictivo) <b>+ clima</b> + avisos</td></tr>
    <tr><td><code>GET</code></td><td><code>/alertas</code></td><td>Alertas SUTRAN actuales (caché de 15 min; <code>?force=true</code> refresca)</td></tr>
    <tr><td><code>GET</code></td><td><code>/avisos</code></td><td>Avisos SENAMHI + emergencias COEN, con caché propia</td></tr>
    <tr><td><code>GET</code></td><td><code>/reportes</code></td><td>Reportes ciudadanos de los últimos N días</td></tr>
    <tr><td><code>POST</code></td><td><code>/reportes</code></td><td>Registra un reporte ciudadano con validación de Perú + deduplicación</td></tr>
  </tbody>
</table>

<div class="sipat-note sipat-note--ok" style="margin-top:11px">
  <b>Comprobado en vivo:</b> <code>POST /ruta_segura_completa</code> con Lima→Huancayo devolvió
  <code>HTTP 200 | hist=8.5726 [Alto] pred=0.6733 [Medio] cov=41.6% clima=True</code>.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Arquitectura <span class="sipat-optional">detalle</span></span>
    <h1>Flujo de datos: de las 3 fuentes al dataset y a los servicios</h1>
  </div>
  <div class="sipat-head__aside">
    Diagrama interactivo en<br>
    <code>docs/archify/sipat-dataflow.html</code>
  </div>
</div>

<ArchifyDiagram src="/svg/dataflow.svg" alt="Flujo de datos desde las tres fuentes oficiales hasta el dataset y los servicios" :height="430" />

<div class="sipat-note" style="margin-top:11px">
  Cada flecha del diagrama corresponde a un <b>script concreto</b> del repositorio:
  <code>geocode.py</code> · <code>features_engine.py</code> · <code>build_dashboard_data.py</code> ·
  <code>build_puntos_negros.py</code> · <code>modelo_multi.py</code>.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Arquitectura <span class="sipat-optional">detalle</span></span>
    <h1>Los 4 diagramas interactivos del proyecto</h1>
  </div>
  <div class="sipat-head__aside">
    HTML autocontenido, 1 por diagrama<br>
    Abren en cualquier navegador
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">🏗️ Arquitectura</div>
      <div class="sipat-card__d">Topología en estrella completa: la API como hub y los flujos con OSRM, OSITRAN y alertas.</div>
    </div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">🔀 Flujo de datos</div>
      <div class="sipat-card__d">De las 3 fuentes geocodificadas al dataset 3.750 × 40 y de ahí a los servicios.</div>
    </div>
  </div>
  <div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">🔢 Secuencia «Viaja seguro»</div>
      <div class="sipat-card__d">Solicitud → cálculo de riesgo (motor + IA + clima) → respuesta integrada.</div>
    </div>
    <div class="sipat-card">
      <div class="sipat-card__t">📣 Workflow del reporte ciudadano</div>
      <div class="sipat-card__d">Formulario → validación y dedupe → almacén append-only → mapa con fotos.</div>
    </div>
  </div>
</div>

<div class="sipat-note" style="margin-top:12px">
  <b>Dónde están:</b> <code>docs/archify/sipat-{architecture,dataflow,sequence,workflow}.html</code>.
  Se pueden abrir en local o vía <code>htmlpreview.github.io</code> sobre el repositorio.
  <b>En esta presentación</b> se muestran como SVG animados: las aristas se dibujan y los nodos
  aparecen en cascada.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Arquitectura <span class="sipat-optional">detalle</span></span>
    <h1>El stack, por capas</h1>
  </div>
  <div class="sipat-head__aside">
    Python en el 100 % del sistema<br>
    (la presentación es Node, aparte)
  </div>
</div>

<StackGrid :capas="[
  { capa: 'Datos', items: [
    { name: 'Pandas', note: 'DataFrames y CSV', tone: 'data' },
    { name: 'Parquet', note: 'Bronze · Silver · Gold', tone: 'data' },
    { name: 'DuckDB', note: 'SQL + lineage', tone: 'data' },
    { name: 'GeoJSON', note: 'red vial y puntos', tone: 'data' },
  ]},
  { capa: 'Geoespacial', items: [
    { name: 'Shapely', note: 'buffers y geometría', tone: 'web' },
    { name: 'scipy cKDTree', note: 'índice O(log n)', tone: 'web' },
    { name: 'pyshp', note: 'shapefiles MTC', tone: 'web' },
    { name: 'Folium', note: 'mapas Leaflet', tone: 'web' },
  ]},
  { capa: 'Modelado', items: [
    { name: 'Statsmodels', note: 'NegBin + IRRs', tone: 'stats' },
    { name: 'NumPy', note: 'cálculo numérico', tone: 'python' },
    { name: 'SciPy', note: 'estadística y árboles', tone: 'stats' },
    { name: 'Matplotlib', note: 'gráficos del reporte', tone: 'stats' },
  ]},
  { capa: 'Servicios', items: [
    { name: 'FastAPI', note: 'API REST :8000', tone: 'python' },
    { name: 'uvicorn', note: 'servidor ASGI', tone: 'python' },
    { name: 'Streamlit', note: 'dashboard :8501', tone: 'web' },
    { name: 'Plotly', note: 'gráficos interactivos', tone: 'web' },
  ]},
  { capa: 'Infra', items: [
    { name: 'Docker', note: 'contenedor OSRM', tone: 'infra' },
    { name: 'OSM / OSRM', note: 'grafo vial de Perú', tone: 'infra' },
    { name: 'Requests', note: 'APIs externas', tone: 'infra' },
    { name: 'Prefect 3', note: 'orquestación ETL', tone: 'ml' },
  ]},
  { capa: 'ETL', items: [
    { name: 'PyYAML', note: 'config declarativa', tone: 'ml' },
    { name: 'Parquet writers', note: 'capas medallion', tone: 'ml' },
    { name: 'Pytest', note: '87 tests', tone: 'ml' },
    { name: 'nbclient', note: 'notebooks verificados', tone: 'ml' },
  ]},
]" />
