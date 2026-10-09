---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 01 · Contexto <span class="sipat-essential">esencial</span></p>
  <h2>El problema que SIPAT ataca</h2>
  <p class="sipat-section__desc">
    Una red vial de ~28.918,5 km reparte entre 3 fuentes oficiales que no hablan entre sí.
    Ninguna fuente, por sí sola, permite responder la pregunta que se hace un viajero:
    <b>«¿por dónde me conviene ir, y qué me va a pasar por el camino?»</b>
  </p>
  <span class="sipat-section__num">01</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Contexto <span class="sipat-essential">esencial</span></span>
    <h1>Una red nacional, tres realidades</h1>
  </div>
  <div class="sipat-head__aside">
    Fuentes 100 % públicas<br>
    Volúmenes verificados sobre los CSV procesados
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:14px">
  <KpiCard :value="51000" suffix="+" label="Siniestros analizados" hint="ONSV + SUTRAN + OSITRAN" tone="indigo" />
  <KpiCard :value="28918" suffix=" km" label="Red Vial Nacional" hint="Segmentada en 3.750 tramos" tone="sky" />
  <KpiCard :value="3750" label="Tramos con features" hint="48 variables por tramo" tone="green" />
  <KpiCard :value="3" label="Fuentes oficiales" hint="Con datos de 2019 a 2025" tone="amber" />
</div>

<div class="sipat-split">
  <figure class="sipat-fig">
    <img src="/figures/contexto_espacial.png" alt="Red vial nacional del Perú y distribución espacial de los siniestros" />
    <figcaption>Contexto espacial: red vial nacional y densidad de siniestros por tramo</figcaption>
  </figure>
  <div>
    <ul class="sipat-list sipat-list--sm">
      <li><b>ONSV</b> — 5.014 siniestros fatales/lesionados 2021-2025 geocodificados</li>
      <li><b>SUTRAN</b> — 7.656 accidentes 2020-2021 <b>+ alertas en vivo</b> (interrumpido / restringido)</li>
      <li><b>OSITRAN</b> — 41.833 accidentes en 16 concesiones 2019-2025 + <b>AADT por peaje</b></li>
      <li><b>MTC</b> — red vial nacional segmentada por kilómetro</li>
      <li><b>INGEMMET</b> — peligros geológicos para distancia a zonas de riesgo</li>
    </ul>
    <div class="sipat-note" style="margin-top:12px">
      <b>El problema de fondo:</b> los accidentes llegan como <code>«PE-1S km 45»</code>, no como coordenadas.
      Sin georreferenciar no hay mapa, no hay ruta, no hay análisis espacial.
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Contexto <span class="sipat-essential">esencial</span></span>
    <h1>SIPAT son dos subsistemas que se respetan</h1>
  </div>
  <div class="sipat-head__aside">
    Dos repos Git<br>
    Dos garantías distintas
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div class="sipat-card" style="border-left-width:5px">
    <div class="sipat-card__t" style="font-size:1.05rem">📥 SIPAT-ETL · <code style="font-size:.72rem">etl-project/</code></div>
    <div class="sipat-card__d" style="margin-top:8px">
      <b>Verifica que los datos merecen confianza</b><br>
      Extrae, limpia, valida y mide la calidad. Si algo falla, <b>bloquea la publicación</b>.
    </div>
    <ul class="sipat-list sipat-list--tight sipat-list--sm" style="margin-top:10px">
      <li>Arquitectura Medallion (Bronze → Silver → Gold)</li>
      <li>Data Quality Score ponderado + <b>quality gate</b></li>
      <li>Cuarentena de críticos, lineage en DuckDB</li>
      <li>87 tests · 3 notebooks sobre datos reales</li>
    </ul>
  </div>
  <div class="sipat-card" style="border-left-width:5px;border-left-color:#0ea5e9">
    <div class="sipat-card__t" style="font-size:1.05rem">🧭 SIPAT · <code style="font-size:.72rem">raíz</code></div>
    <div class="sipat-card__d" style="margin-top:8px">
      <b>Convierte datos buenos en decisiones de viaje</b><br>
      Geocodifica, modela y responde «¿por dónde voy y qué riesgo llevo?».
    </div>
    <ul class="sipat-list sipat-list--tight sipat-list--sm" style="margin-top:10px">
      <li>Geocodificación lineal por km (~14 m de error)</li>
      <li>Índice de riesgo histórico + <b>capa predictiva</b> (NegBin)</li>
      <li>Dashboard 7 pestañas, API REST, reporte HTML</li>
      <li>30/30 verificaciones automáticas en verde</li>
    </ul>
  </div>
</div>

<div class="sipat-note sipat-note--ok" style="margin-top:14px">
  <b>El contrato entre ambos:</b> SIPAT-ETL <b>publica o bloquea</b>; SIPAT <b>consume solo lo que pasó el gate</b>.
  Ningún análisis se apoya en un dataset sin verificar.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Contexto <span class="sipat-optional">detalle</span></span>
    <h1>Los dos productos que ve el usuario</h1>
  </div>
</div>

<div class="sipat-cards">
  <div class="sipat-card">
    <div class="sipat-card__t" style="font-size:1.02rem">🧭 1 · Viaja seguro</div>
    <div class="sipat-card__d" style="margin-top:6px">
      Elige origen, destino y <b>hora de salida</b>; obtén <b>antes de partir</b>:
      <ul class="sipat-list sipat-list--tight sipat-list--sm" style="margin-top:7px">
        <li>Mapa de la ruta con cada accidente, clicable</li>
        <li>Riesgo <b>histórico</b> y <b>predictivo (IA)</b></li>
        <li>Clima, avisos SENAMHI, emergencias COEN</li>
        <li>Alertas de tráfico en vivo</li>
        <li>Reporte HTML descargable</li>
      </ul>
    </div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t" style="font-size:1.02rem">📣 2 · Reporta un incidente</div>
    <div class="sipat-card__d" style="margin-top:6px">
      Cualquier ciudadano reporta accidentes, derrumbes o congestión <b>con foto y contexto</b>, ubicándolos sobre su propia ruta:
      <ul class="sipat-list sipat-list--tight sipat-list--sm" style="margin-top:7px">
        <li>Foto PNG/JPG opcional</li>
        <li>Tipo, severidad, descripción</li>
        <li>Ubicación por km sobre la ruta calculada</li>
        <li>Aparece en los mapas de otros viajeros</li>
      </ul>
    </div>
  </div>
</div>

<div class="sipat-note" style="margin-top:12px">
  Ambos se apoyan en la misma capa de riesgo. El reporte ciudadano es una <b>señal complementaria y reciente</b>,
  no un dato oficial: por eso se separa siempre de las tres fuentes institucionales.
</div>
