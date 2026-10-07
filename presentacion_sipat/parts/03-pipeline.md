---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 03 · Pipeline analítico <span class="sipat-essential">esencial</span></p>
  <h2>De «PE-1S km 45» a un mapa</h2>
  <p class="sipat-section__desc">
    El paso que lo cambia todo: <b>abscisado sobre el polilíneo</b>.
    Cada accidente se proyecta sobre la red del MTC usando el kilómetro declarado, sin depender de un geocoder externo.
  </p>
  <span class="sipat-section__num">03</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Pipeline <span class="sipat-essential">esencial</span></span>
    <h1>El pipeline completo, de las fuentes a los servicios</h1>
  </div>
  <div class="sipat-head__aside">
    3 fuentes → geocodificación → dataset<br>
    →NegBin + puntos negros → 3 servicios
  </div>
</div>

```mermaid
flowchart LR
  F["<b>Fuentes oficiales</b><br/>ONSV 5.014<br/>SUTRAN 7.656 + alertas<br/>OSITRAN 41.833 + peajes<br/>MTC 3.750 tramos<br/>INGEMMET peligros"] --> G["<b>Geocodificación lineal</b><br/>abscisado: ruta + km → lat/lon<br/>error ~14 m"]
  G --> D["<b>dataset_modelo.csv</b><br/>3.750 × 40 variables<br/>con offset de exposición"]
  D --> B["<b>Unificación multi-fuente</b><br/>build_dashboard_data.py<br/>→ tramos_geo.json"]
  D --> P["<b>Puntos negros</b><br/>EB de Hauer<br/>→ 129 puntos"]
  D --> N["<b>Modelo NegBin</b><br/>modelo_multi.py<br/>→ IRRs + predictor"]
  B & P & N --> S["<b>Servicios</b><br/>OSRM :5000<br/>FastAPI :8000<br/>Streamlit :8501"]
```

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Pipeline <span class="sipat-essential">esencial</span></span>
    <h1>Geocodificación lineal: el abscisado por kilómetro</h1>
  </div>
  <div class="sipat-head__aside">
    <code>scripts/geocode.py</code><br>
    Error típico <b>~14 m</b>
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">1 · El dato de partida</div>
      <div class="sipat-card__d">El registro dice <code>ruta: PE-1S</code> · <code>km: 45</code> · <code>fecha</code> · <code>causa</code>.<br>
      <b>Sin coordenadas.</b> Es la forma en que reportan las tres fuentes.</div>
    </div>
    <div class="sipat-card" style="margin-bottom:10px;border-left-color:#0ea5e9">
      <div class="sipat-card__t">2 · El polilíneo</div>
      <div class="sipat-card__d">Se busca la <b>carretera</b> en la red MTC y se toma su <code>LineString</code> completo,
      recorrido de extremo a extremo con su progresiva acumulada.</div>
    </div>
    <div class="sipat-card" style="border-left-color:#d97706">
      <div class="sipat-card__t">3 · La proyección</div>
      <div class="sipat-card__d">Se interpola el km sobre la distancia acumulada y se devuelve el punto
      (<code>locate()</code> en <code>geocode.py</code>). Verificado contra CGM.</div>
    </div>
  </div>
  <div>
    <div class="sipat-cards" style="grid-template-columns:1fr 1fr;margin-bottom:11px">
      <KpiCard :value="14" suffix=" m" label="Error de geocodificación" hint="Verificado contra CGM" tone="green" />
      <KpiCard :value="99.4" :decimals="1" suffix="%" label="Cobertura SUTRAN" hint="Registros con punto válido" tone="green" />
    </div>
    <ul class="sipat-list sipat-list--sm">
      <li><b>Determinista</b>: el mismo km produce siempre la misma coordenada</li>
      <li><b>Sin dependencia externa</b>: no hace falta llamar a un geocoder de pago</li>
      <li>Reutilizable para OSITRAN, que reporta por <b>tramo de concesión</b> (se asigna al centroide)</li>
    </ul>
    <div class="sipat-note" style="margin-top:11px">
      Esta decisión es la que hace posible todo lo demás: sin coordenada no hay <b>cKDTree</b>,
      ni buffer de 2 km, ni perfil de riesgo, ni nada de lo que sigue.
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Pipeline <span class="sipat-essential">esencial</span></span>
    <h1>El dataset espacial: 3.750 tramos × 40 variables</h1>
  </div>
  <div class="sipat-head__aside">
    <code>data/processed/dataset_modelo.csv</code><br>
    La tabla que alimenta el modelo
  </div>
</div>

<div class="sipat-cards">
  <div class="sipat-card">
    <div class="sipat-card__t">Exposición</div>
    <div class="sipat-card__d">longitud del tramo, <code>expo_km</code> y catalogos de la fuente dominante</div>
  </div>
  <div class="sipat-card" style="border-left-color:#dc2626">
    <div class="sipat-card__t">Siniestros</div>
    <div class="sipat-card__d">conteo por fuente (ONSV / SUTRAN / OSITRAN), <b>fallecidos</b>, lesionados, <code>fuente_dominante</code></div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">Geometría vial</div>
    <div class="sipat-card__d">topografía, superficie, <b>velocidad proyectada</b>, carriles, <b>sinuosidad</b>, <code>es_panamericana</code></div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">Entorno de riesgo</div>
    <div class="sipat-card__d">distancia a peligros <b>INGEMMET</b>, a peajes, a cinemómetros, densidad <code>c10km</code></div>
  </div>
</div>

<table class="sipat-table" style="margin-top:13px">
  <thead><tr><th style="width:20%">Grupo</th><th style="width:34%">Variables representativas</th><th>Para qué entra en el modelo</th></tr></thead>
  <tbody>
    <tr><td><b>Respuesta</b></td><td><code>n_siniestros</code>, <code>fallecidos</code>, <code>lesionados</code></td><td>La variable que el NegBin intenta explicar</td></tr>
    <tr><td><b>Exposición</b></td><td><code>expo_km</code>, longitud del tramo</td><td>Entra como <b>offset</b>: normaliza por los kilómetros expuestos</td></tr>
    <tr><td><b>Vía</b></td><td><code>vel_proy</code>, <code>carriles</code>, <code>sup_buena</code>, <code>sinuosidad</code></td><td>Capacidad real de la vía y su geometría</td></tr>
    <tr><td><b>Entorno</b></td><td><code>log_ingemmet</code>, <code>log_peajes</code>, <code>log_cine</code>, <code>cinemometros_c10km</code></td><td>Transformadas logarítmicas porque la influencia es de orden multiplicativo</td></tr>
    <tr><td><b>Contexto</b></td><td><code>es_panamericana</code>, dummies de región y topografía</td><td>Controlan diferencias no viales entre zonas, para no atribuirlas a la vía</td></tr>
  </tbody>
</table>

<div class="sipat-note sipat-note--ok" style="margin-top:12px">
  <b>Por qué el offset importa:</b> sin él, un tramo de 40 km parecería <b>más seguro</b> que uno de
  5 km solo por tener menos kms expuestos. El offset obliga a que el modelo compare
  <b>siniestros por kilómetro</b>, que es la magnitud que se quiere predecir.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Pipeline <span class="sipat-essential">esencial</span></span>
    <h1>Puntos negros: 12 en Fase 1, 129 en la versión multi-fuente</h1>
  </div>
  <div class="sipat-head__aside">
    <code>build_puntos_negros.py</code><br>
    Tres criterios, todos a la vez
  </div>
</div>

<div class="sipat-split">
  <figure class="sipat-fig">
    <img src="/figures/mapa_puntos_negros.png" alt="Mapa de puntos negros vial del Perú" />
    <figcaption>Puntos negros detectados por exceso Empirical Bayes (método de Hauer)</figcaption>
  </figure>
  <div>
    <p class="sipat-list sipat-list--sm"><b>Ventana deslizante de 1 km</b> + tres criterios simultáneos:</p>
    <v-clicks>
      <div class="sipat-card" style="margin-bottom:8px">
        <div class="sipat-card__t">1 · Percentil 95 regional</div>
        <div class="sipat-card__d">Supera el percentil 95 de su región: descarta ruido estadístico.</div>
      </div>
      <div class="sipat-card" style="margin-bottom:8px">
        <div class="sipat-card__t">2 · Exceso Empirical Bayes &gt; 1.0</div>
        <div class="sipat-card__d">Método de Hauer: corrige por <b>exposición y varianza</b> de cada tramo.</div>
      </div>
      <div class="sipat-card" style="margin-bottom:8px">
        <div class="sipat-card__t">3 · Residuos del modelo &gt; 2.0</div>
        <div class="sipat-card__d">El tramo es peor de lo que el NegBin predice: el modelo no lo explica.</div>
      </div>
      <div class="sipat-note">
        Cada punto lleva su <code>fuente_dominante</code>: qué fuente concentra el exceso.
      </div>
    </v-clicks>
  </div>
</div>

<div class="sipat-split sipat-split--even" style="margin-top:11px">
  <div class="sipat-note sipat-note--ok" style="font-size:.78rem">
    <b>12</b> = detector de <b>Fase 1</b>, solo ONSV → <code>data/processed/puntos_negros.csv</code>
  </div>
  <div class="sipat-note sipat-note--ok" style="font-size:.78rem">
    <b>129</b> = detector <b>multi-fuente</b> (ONSV+SUTRAN+OSITRAN) → <code>dashboard/puntos_negros.json</code>
  </div>
</div>
