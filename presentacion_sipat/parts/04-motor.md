---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 04 · Motor de riesgo <span class="sipat-essential">esencial</span></p>
  <h2>Dos indicadores, nunca uno solo</h2>
  <p class="sipat-section__desc">
    El <b>riesgo histórico</b> es exposición pasada. La <b>capa predictiva</b> es un modelo que ajusta por
    longitud, tráfico y características viales. Presentarlos juntos es lo que evita que el sistema
    <b>vende como «predicción» lo que solo es historia</b>.
  </p>
  <span class="sipat-section__num">04</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Motor de riesgo <span class="sipat-essential">esencial</span></span>
    <h1>La fórmula del score por kilómetro</h1>
  </div>
  <div class="sipat-head__aside">
    <code>scripts/riesgo_red.py</code><br>
    3 índices <b>cKDTree</b> independientes
  </div>
</div>

<div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px 20px;font-size:.86rem;line-height:1.85;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#0f172a">
  <div>
    <span style="color:#4f46e5;font-weight:700">score_km</span> = (n_siniestros + <span style="color:#d97706">0.5</span> · gravedad) / km
  </div>
  <div style="padding-left:26px;color:#64748b">
    + alertas_históricas_SUTRAN / km <span style="color:#94a3b8">// zonas de incidentes recurrentes</span>
  </div>
  <div style="padding-left:26px;color:#64748b">
    + Σ tráfico_peajes(≤ 15 km) <span style="color:#94a3b8">// min(AADT / 100 000, 0.5)</span>
  </div>
  <div style="margin-top:9px;padding-top:9px;border-top:1px dashed #e2e8f0">
    <span style="color:#059669;font-weight:700">score_final</span> = score_km · <span style="color:#7c3aed">factor_temporal</span>(hora/día) + penalización_alertas_en_vivo
  </div>
</div>

<div class="sipat-cards" style="margin-top:13px">
  <div class="sipat-card">
    <div class="sipat-card__t">① Densidad de siniestros</div>
    <div class="sipat-card__d">Conteo normalizado por longitud. La gravedad pondera:
    <code>fallecidos × 3.0 + lesionados × 1.0 + 1.0</code></div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">② Señal recurrente</div>
    <div class="sipat-card__d">Archivo acumulativo <code>sutran_alertas_historico.json</code>.
    Pesa: <code>INTERRUMPIDO 2.0</code> · <code>RESTRINGIDO 1.0</code> · <code>NORMAL 0.3</code></div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">③ Exposición al tráfico</div>
    <div class="sipat-card__d">AADT de los peajes a ≤ 15 km, acotado a 0.5 para que un peaje enorme no domine el score</div>
  </div>
  <div class="sipat-card" style="border-left-color:#7c3aed">
    <div class="sipat-card__t">④ Momento del viaje</div>
    <div class="sipat-card__d"><code>factor_temporal()</code> y penalización por alerta en vivo dentro de ±2 km</div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Motor de riesgo <span class="sipat-essential">esencial</span></span>
    <h1>Factor temporal y umbrales que ve el usuario</h1>
  </div>
  <div class="sipat-head__aside">
    Mismo score, lectura distinta<br>
    según cuándo se viaja
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">🌙 Noche (19 h – 05 h) <span style="color:#dc2626">× 1.30</span></div>
      <div class="sipat-card__d">El factor más alto: menos visibilidad, más fatiga, más velocidad media.</div>
    </div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">📅 Sábado <span style="color:#d97706">× 1.25</span></div>
      <div class="sipat-card__d">Fin de semana: más viajes de ocio, más conductor fatigado o recreativo.</div>
    </div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">🗓️ Domingo <span style="color:#d97706">× 1.10</span></div>
      <div class="sipat-card__d">Retorno a la costa, mismo efecto con menor intensidad.</div>
    </div>
    <div class="sipat-card">
      <div class="sipat-card__t">🌅 Madrugada (05 h – 08 h) <span style="color:#4f46e5">× 1.05</span></div>
      <div class="sipat-card__d">Hora de entrada al trabajo: efecto leve.</div>
    </div>
  </div>
  <div>
    <div class="sipat-card" style="margin-bottom:11px">
      <div class="sipat-card__t">Umbrales del indicador <b>histórico</b> (score/km)</div>
      <div style="display:flex;gap:7px;align-items:center;margin-top:9px;flex-wrap:wrap">
        <Semaforo nivel="bajo" score="< 4" compact />
        <Semaforo nivel="medio" score="4 – 8" compact />
        <Semaforo nivel="alto" score="> 8" compact />
      </div>
    </div>
    <div class="sipat-card" style="margin-bottom:11px">
      <div class="sipat-card__t">Umbrales del indicador <b>predictivo</b> (siniestros/km)</div>
      <div style="display:flex;gap:7px;align-items:center;margin-top:9px;flex-wrap:wrap">
        <Semaforo nivel="bajo" score="< 0.5" compact />
        <Semaforo nivel="medio" score="0.5 – 1.2" compact />
        <Semaforo nivel="alto" score="> 1.2" compact />
      </div>
    </div>
    <div class="sipat-note" style="font-size:.79rem">
      <b>Alertas en vivo</b> (± 2 km de la ruta): <code>INTERRUMPIDO</code> <b>+5</b> ·
      <code>RESTRINGIDO</code> <b>+1</b>, y el total se multiplica por el factor temporal.
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Motor de riesgo <span class="sipat-essential">esencial</span></span>
    <h1>La capa predictiva: Negative Binomial sobre la ruta</h1>
  </div>
  <div class="sipat-head__aside">
    <code>scripts/prediccion.py</code><br>
   (statsmodels + cKDTree)
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <ol class="sipat-list sipat-list--sm">
      <li><b>Reentrena</b> el NegBin de Fase 1 sobre las 3.750 filas, replicando la <b>misma especificación</b>
      de features (carriles, velocidad proyectada, sinuosidad, <code>log_ingemmet</code>, <code>log_peajes</code>,
      cinemómetros, dummy de región y topografía).</li>
      <li><b>Empalma</b> la geometría OSRM de la ruta a los tramos del modelo con un árbol <b>cKDTree</b>
      (distancia máxima de ajuste: 2 km).</li>
      <li><b>Devuelve</b> siniestros esperados por km a lo largo de la ruta y el <b>% de cobertura</b>
      (longitud de ruta con features completas).</li>
      <li><b>¿Qué puede pasar?</b> <code>tipos_incidente()</code> agrega tipos, causas y clima
      de los accidentes históricos en el buffer → top-5 tipos, top-5 causas, top-3 condiciones.</li>
    </ol>
    <div class="sipat-note" style="margin-top:11px">
      <b>El predictor nunca inventa tramos:</b> si un punto de la ruta no cae cerca de un tramo
      con features, se marca como <b>no cubierto</b> y no se le asigna riesgo.
    </div>
  </div>
  <div>
    <div class="sipat-card" style="margin-bottom:10px">
      <div class="sipat-card__t">¿Por qué NegBin y no Poisson?</div>
      <div class="sipat-card__d">Los siniestros están <b>sobre-dispersos</b>: hay tramos que concentran
      mucho más de lo que el modelo predice. Poisson asumdría varianza = media y <b>subestimaría el riesgo</b>tails.</div>
    </div>
    <div class="sipat-cards" style="grid-template-columns:1fr 1fr">
      <KpiCard :value="8663" label="AIC · NegBin" hint="Mezcla ONSV + SUTRAN" tone="green" />
      <KpiCard :value="11984" label="AIC · Poisson" hint="Modelo simple, peor ajuste" tone="red" />
    </div>
    <div class="sipat-note sipat-note--ok" style="margin-top:10px;font-size:.79rem">
      <b>Diferencia de AIC: 3.321 a favor del NegBin.</b> Es la evidencia de que la
      sobre-dispersión no era una suposición, sino que está en los datos.
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Motor de riesgo <span class="sipat-essential">esencial</span></span>
    <h1>Ejemplo real y verificado: Lima → Huancayo</h1>
  </div>
  <div class="sipat-head__aside">
    Valor leído de <code>verificacion.json</code><br>
    Check <code>api:ruta_segura_completa</code>
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:14px">
  <KpiCard :value="8.5726" :decimals="4" label="Riesgo histórico" hint="score/km → nivel Alto" tone="red" />
  <KpiCard :value="0.6733" :decimals="4" label="Riesgo predictivo" hint="siniestros/km esperados → Medio" tone="amber" />
  <KpiCard :value="41.6" :decimals="1" suffix="%" label="Cobertura de la ruta" hint="longitud con features completas" tone="slate" />
  <KpiCard :value="18807" label="Puntos de riesgo cargados" hint="en el índice en memoria" tone="indigo" />
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:11px;flex-wrap:wrap">
      <span style="font-size:.8rem;font-weight:700;color:#334155">Indicador histórico</span>
      <Semaforo nivel="alto" score="8.5726 score/km" caption="por encima del umbral 8" />
    </div>
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:11px;flex-wrap:wrap">
      <span style="font-size:.8rem;font-weight:700;color:#334155">Indicador predictivo</span>
      <Semaforo nivel="medio" score="0.6733 sini/km" caption="dentro del rango 0.5 – 1.2" />
    </div>
    <ul class="sipat-list sipat-list--sm">
      <li>Los dos indicadores <b>no coinciden</b> a propósito: el histórico mide exposición pasada, el predictivo estima.</li>
      <li>El predictivo marca <b>41.6 % de cobertura</b>: casi 6 de cada 10 km <b>no se puntúan</b>.</li>
    </ul>
  </div>
  <div>
    <div class="sipat-note sipat-note--warn">
      <b>Decisión de honestidad metodológica:</b> el sistema <b>muestra la cobertura en pantalla</b>
      en vez de rellenar el hueco. Un 58 % del tramo sin dato se dice, no se disimula.
    </div>
    <div class="sipat-note" style="margin-top:10px">
      Ese mismo caso también devolvió <b>clima disponible</b> y <b>2 alertas SUTRAN en vivo</b> en la
      misma llamada, lo que confirma que las tres capas (riesgo, predicción, clima) se resuelven
      en paralelo.
    </div>
  </div>
</div>
