---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 06 · Analítica nacional <span class="sipat-essential">esencial</span></p>
  <h2>Del caso particular a la política pública</h2>
  <p class="sipat-section__desc">
    La ruta segura responde a <b>una</b> pregunta de <b>una</b> persona.
    La analítica nacional responde a las preguntas de <b>una institución</b>:
    dónde está el riesgo estructural y qué lo explica.
  </p>
  <span class="sipat-section__num">06</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Analítica nacional <span class="sipat-essential">esencial</span></span>
    <h1>Mapa nacional multi-fuente</h1>
  </div>
  <div class="sipat-head__aside">
    <code>tramos_geo.json</code><br>
    con capas conmutables
  </div>
</div>

<figure class="sipat-fig">
  <img src="/figures/mapa_siniestros_tramos.png" alt="Mapa nacional de la red vial coloreada por densidad de siniestros" />
  <figcaption>Red vial coloreada por siniestros/km (amarillo → rojo). Capas: tramos · puntos negros · alertas históricas SUTRAN</figcaption>
</figure>

<div class="sipat-note" style="margin-top:12px">
  <b>Unificación multi-fuente</b> (<code>build_dashboard_data.py</code>): suma ONSV + SUTRAN + OSITRAN por tramo,
  <b>distribuye</b> los accidentes OSITRAN que llegan por tramo de concesión, añade alertas históricas y
  tráfico de peajes, y exporta además los eventos por fuente como CSV ligeros para el dashboard.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Analítica nacional <span class="sipat-essential">esencial</span></span>
    <h1>Tendencias y rutas críticas</h1>
  </div>
  <div class="sipat-head__aside">
    Separado siempre por fuente<br>
    Las cifras no se mezclan
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <figure class="sipat-fig">
    <img src="/figures/tendencia_temporal.png" alt="Series temporales de siniestros por año, mes, día y hora" />
    <figcaption>Series por año · mes · día · hora, y fallecidos por siniestro</figcaption>
  </figure>
  <figure class="sipat-fig">
    <img src="/figures/ranking_rutas.png" alt="Ranking de las rutas y departamentos con mayor siniestralidad" />
    <figcaption>Top 15 de rutas y departamentos con más siniestros</figcaption>
  </figure>
</div>

<div class="sipat-cards" style="margin-top:13px">
  <div class="sipat-card" style="border-left-color:#dc2626">
    <div class="sipat-card__t">📈 Tendencias</div>
    <div class="sipat-card__d">Año, mes, día de la semana y hora. La hora es la lectura más accionable:
    el riesgo no es uniforme, y el <b>factor temporal</b> lo formaliza.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">🏆 Rutas críticas</div>
    <div class="sipat-card__d">    Top 15 de rutas y de departamentos, más los tipos y causas más frecuentes.
    Entrada directa para priorizar <b>intervenciones</b>.</div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Analítica nacional <span class="sipat-essential">esencial</span></span>
    <h1>El modelo NegBin: qué factor sube o baja el riesgo</h1>
  </div>
  <div class="sipat-head__aside">
    IRRs con IC 95 %<br>
    por fuente: ONSV · SUTRAN · COMBINADO
  </div>
</div>

<div class="sipat-split">
  <figure class="sipat-fig">
    <img src="/figures/irr_modelo.png" alt="Incidence Rate Ratios del modelo Negative Binomial con intervalos de confianza" />
    <figcaption>Incidence Rate Ratios (IRR) con intervalos de confianza al 95 %</figcaption>
  </figure>
  <div>
    <div class="sipat-card" style="margin-bottom:11px">
      <div class="sipat-card__t">Cómo leer un IRR</div>
      <div class="sipat-card__d">
        <code>IRR = 1.8</code> significa que el factor multiplica por 1,8 la tasa de siniestros
        manteniendo lo demás constante. <code>IRR &lt; 1</code> es un factor protector.
      </div>
    </div>
    <div class="sipat-card" style="margin-bottom:11px">
      <div class="sipat-card__t">Tres modelos, no uno</div>
      <div class="sipat-card__d">Se ajusta el NegBin <b>por fuente</b> (ONSV, SUTRAN, COMBINADO) con
      <b>offset de exposición</b>. Así el sistema nunca sugiere que los registros de una fuente
      son comparables con los de otra.</div>
    </div>
    <div class="sipat-card">
      <div class="sipat-card__t">Explorador de 3.750 tramos</div>
      <div class="sipat-card__d">La pestaña 📊 Modelo permite recorrer los tramos y ver sus valores de
      riesgo esperado frente a los reales: dónde el modelo acierta y dónde falla.</div>
    </div>
  </div>
</div>
