---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 08 · Metodología <span class="sipat-essential">esencial</span></p>
  <h2>Dos marcos complementarios</h2>
  <p class="sipat-section__desc">
    <b>CRISP-DM</b> ordena el <i>ciclo de datos</i>: qué se hace con los datos y cuándo.
    <b>SCRUM</b> organiza la <i>entrega de producto</i>: qué se entrega en cada sprint y cómo se verifica.
  </p>
  <span class="sipat-section__num">08</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Metodología <span class="sipat-essential">esencial</span></span>
    <h1>CRISP-DM: las 6 fases y qué se hizo en cada una</h1>
  </div>
  <div class="sipat-head__aside">
    El ciclo se cierra:<br>
    las lecciones vuelven a empezar
  </div>
</div>

```mermaid
flowchart LR
  A["<b>1 · Negocio</b><br/>Prevenir accidentes<br/>antes de viajar"] --> B["<b>2 · Datos</b><br/>51.000+ siniestros<br/>3 fuentes"]
  B --> C["<b>3 · Preparación</b><br/>Geocodificación lineal<br/>dataset 3.750×48"]
  C --> D["<b>4 · Modelado</b><br/>NegBin por fuente<br/>IRRs + predictor"]
  D --> E["<b>5 · Evaluación</b><br/>AIC 8.663 vs 11.984<br/>133 puntos negros<br/>validez fuera de muestra"]
  E --> F["<b>6 · Despliegue</b><br/>Dashboard · API<br/>reporte HTML"]
  F -. "lecciones → nuevo sprint" .-> A
```

<table class="sipat-table" style="margin-top:13px;font-size:.76rem">
  <thead><tr><th style="width:19%">Fase</th><th>Qué se hizo en SIPAT</th></tr></thead>
  <tbody>
    <tr><td><b>1 · Negocio</b></td><td>Dos productos: índice de riesgo por ruta y reporte ciudadano. Usuarios: viajeros e instituciones</td></tr>
    <tr><td><b>2 · Datos</b></td><td>Inventario de 3 fuentes de siniestros + red vial MTC + peligros INGEMMET. Calidad: geocodificación lineal (~14 m), cobertura SUTRAN 99.4 %</td></tr>
    <tr><td><b>3 · Preparación</b></td><td>Limpieza (nulos, duplicados, rutas PE-XX), unificación multi-fuente por tramo, features espaciales con buffer 2 km y cKDTree, tráfico de peajes</td></tr>
    <tr><td><b>4 · Modelado</b></td><td>Negative Binomial por fuente con offset de exposición; predictor que empalma la ruta del usuario a los tramos</td></tr>
    <tr><td><b>5 · Evaluación</b></td><td>AIC NegBin 8.663 vs Poisson 11.984; validación con AppTest + 30 checks; contraste con los umbrales de riesgo</td></tr>
    <tr><td><b>6 · Despliegue</b></td><td>Dashboard de 7 pestañas, API REST, reporte HTML autocontenido, datos ligeros en <code>data/processed/dashboard/</code></td></tr>
  </tbody>
</table>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Metodología <span class="sipat-essential">esencial</span></span>
    <h1>SCRUM: 3 sprints, cada uno con entrega verificada</h1>
  </div>
  <div class="sipat-head__aside">
    Un sprint que no verifica<br>
    no está terminado
  </div>
</div>

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

<div class="sipat-cards" style="margin-top:14px">
  <div class="sipat-card">
    <div class="sipat-card__t">Definición de «hecho»</div>
    <div class="sipat-card__d">Ningún sprint se cierra sin su <b>batería de 30 comprobaciones</b> y el
    <b>AppTest headless</b> del dashboard (7 pestañas + «Analizar mi ruta» sin excepciones).</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">Documentación como entregable</div>
    <div class="sipat-card__d">Los <b>4 diagramas Archify</b> se actualizan al final de cada sprint:
    documentan el sistema <b>en su estado real</b>, no en el previsto.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">Kanban en el ETL</div>
    <div class="sipat-card__d">Tablero implícito por etapas del pipeline: cada cambio de dataset pasa por
    <code>clean → transform → data_quality → gate → publish</code>.</div>
  </div>
</div>
