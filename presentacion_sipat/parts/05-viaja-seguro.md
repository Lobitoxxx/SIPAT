---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 05 · Producto principal <span class="sipat-essential">esencial</span></p>
  <h2>🧭 Viaja seguro</h2>
  <p class="sipat-section__desc">
    «Preventión antes de viajar». El usuario entra origen, destino y <b>hora de salida</b>;
    el sistema responde con el riesgo de esa ruta <b>para ese momento concreto</b>.
  </p>
  <span class="sipat-section__num">05</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Viaja seguro <span class="sipat-essential">esencial</span></span>
    <h1>El flujo completo, paso a paso</h1>
  </div>
  <div class="sipat-head__aside">
    3 capas en <b>paralelo</b>:<br>
    riesgo · predicción · clima
  </div>
</div>

<div class="mermaid--narrow">

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuario
  participant D as Dashboard
  participant G as geocode()
  participant O as OSRM :5000
  participant R as ruta_segura + riesgo_red
  participant P as prediccion (NegBin)
  participant C as clima (SENAMHI·Meteo·COEN)
  U->>D: origen, destino, fecha/hora salida
  D->>G: geocodificar extremos
  G-->>D: lat/lon
  D->>O: /route/v1/driving (3 alternativas)
  O-->>D: geometría de la ruta + km
  par Análisis de riesgo
    D->>R: analizar(geometría, salida)
    R->>R: buffer 2 km · score_km · factor temporal
    R-->>D: nivel histórico + perfil km-a-km
  and Predicción IA
    D->>P: predecir_ruta(geometría)
    P-->>D: siniestros/km + cobertura
  and Clima
    D->>C: avisos · pronóstico · COEN
    C-->>D: avisos activos en la ruta
  end
  D-->>U: banner · mapa · perfil · clima · reporte
```

</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Viaja seguro <span class="sipat-essential">esencial</span></span>
    <h1>Lo que ve el usuario al analizar su ruta</h1>
  </div>
  <div class="sipat-head__aside">
    Pestaña principal del dashboard<br>
    <code>dashboard/viaja_seguro.py</code>
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:13px">
  <div class="sipat-card">
    <div class="sipat-card__t">💊 Pills de rutas populares</div>
    <div class="sipat-card__d">Lima → Huancayo, Lima → Cusco, Trujillo → Chiclayo… un clic y la ruta se calcula.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">📊 Cards KPI</div>
    <div class="sipat-card__d">Distancia · riesgo histórico · riesgo IA · <b>ruta más segura</b> · accidentes en la ruta</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">🚦 Banner semáforo</div>
    <div class="sipat-card__d">Nivel global de riesgo con el color temático — la lectura en 1 segundo.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#059669">
    <div class="sipat-card__t">🗺️ Mapa full-width</div>
    <div class="sipat-card__d">Cada accidente <b>clicable</b>: fecha, tipo, causa, gravedad, clima, superficie.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#7c3aed">
    <div class="sipat-card__t">📈 Perfil km a km</div>
    <div class="sipat-card__d">Segmentos de 5 km con su score: dónde empeora la ruta y por qué.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#dc2626">
    <div class="sipat-card__t">❓ ¿Qué puede pasar?</div>
    <div class="sipat-card__d">Top-5 tipos de incidente, top-5 causas y clima histórico en esa ruta.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0891b2">
    <div class="sipat-card__t">⛅ Clima y emergencias</div>
    <div class="sipat-card__d">Pronóstico Open-Meteo, avisos SENAMHI, emergencias COEN. Botón de refresco manual.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#64748b">
    <div class="sipat-card__t">📄 Reporte HTML</div>
    <div class="sipat-card__d">Autocontenido y descargable: mapa, perfil, clima y tipos de incidente.</div>
  </div>
</div>

<div class="sipat-note" style="margin-top:12px">
  <b>Ranking de las 3 alternativas:</b> OSRM devuelve hasta 3 rutas y el motor las ordena por
  <b>corta</b>, <b>rápida</b> y <b>segura</b>. La «segura» es la que minimiza el score penalizado
  por alertas en vivo — no la más corta, necesariamente.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Viaja seguro <span class="sipat-essential">esencial</span></span>
    <h1>Las tres capas de contexto en vivo</h1>
  </div>
  <div class="sipat-head__aside">
    Cachés con TTL<br>
    El dashboard nunca se rompe
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:13px">
  <div class="sipat-card" style="border-left-color:#0891b2">
    <div class="sipat-card__t">⛅ Open-Meteo <span style="color:#64748b;font-weight:400">~2 h</span></div>
    <div class="sipat-card__d">Temperatura, lluvia y viento <b>muestreados sobre la geometría</b> de la ruta (hasta 4 puntos).
    Pronóstico a 3 días. Sin API key.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#4f46e5">
    <div class="sipat-card__t">🌧️ SENAMHI <span style="color:#64748b;font-weight:400">~3 h</span></div>
    <div class="sipat-card__d">WFS oficial <code>g_prono_pp_24h</code>: avisos a 24 h con nivel, fecha y recomendación.
    Se cruzan contra el buffer de la ruta.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#dc2626">
    <div class="sipat-card__t">🆘 COEN-INDECI <span style="color:#64748b;font-weight:400">~6 h</span></div>
    <div class="sipat-card__d">Emergencias activas (incendios, inundaciones, <b>sismos</b>) de los últimos 7 días,
    geocodificadas y filtradas por proximidad a la ruta.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">🚧 SUTRAN <span style="color:#64748b;font-weight:400">15 min</span></div>
    <div class="sipat-card__d">Alertas de tránsito en vivo. Cada consulta <b>alimenta el histórico</b>:
    donde se repite la alerta, sube el score estructural del tramo.</div>
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div class="sipat-note">
    <b>Acumulación:</b> <code>sutran_alertas_historico.json</code> no se sobrescribe nunca.
    Es la memoria del sistema sobre <b>zonas de incidentes recurrentes</b>.
  </div>
  <div class="sipat-note sipat-note--ok">
    <b>Degradación limpia:</b> si SENAMHI, Open-Meteo o COEN fallan, el dashboard muestra
    «no disponible» en esa sección. El análisis de riesgo <b>no se interrumpe</b>.
  </div>
</div>
