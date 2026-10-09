---
layout: default
transition: slide-left
---

<div class="sipat-section">
  <p class="sipat-section__kicker">Bloque 04b · Auditoría <span class="sipat-essential">esencial</span></p>
  <h2>¿Sirve de algo, o solo parece que sí?</h2>
  <p class="sipat-section__desc">
    Un modelo con buen ajuste en entrenamiento y un DQS de 92 pueden seguir sin servir para nada.
    Aquí el sistema se audita <b>a sí mismo</b>: dos módulos que no construyen el producto, sino que
    lo someten a prueba y declaran lo que encuentra.
  </p>
  <span class="sipat-section__num">04b</span>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Auditoría <span class="sipat-essential">esencial</span></span>
    <h1>Cuatro preguntas, cuatro módulos</h1>
  </div>
  <div class="sipat-head__aside">
    <code>fiabilidad_fuentes.py</code> · <code>validez_predictiva.py</code><br>
    <b>No se sustituyen entre sí</b>
  </div>
</div>

<table class="sipat-table" style="font-size:.76rem">
  <thead><tr><th style="width:34%">Pregunta</th><th style="width:30%">Dónde se responde</th><th>Qué NO contesta</th></tr></thead>
  <tbody>
    <tr>
      <td>¿El dato tiene nulos, rangos y unicidad?</td>
      <td><code>etl-project/src/quality/dimensions.py</code><br><span style="color:#64748b">Data Quality Score</span></td>
      <td>No dice si la fuente es de fiar, ni si el modelo predice</td>
    </tr>
    <tr>
      <td>¿Las métricas del ETL son defendibles?</td>
      <td><code>etl-project/src/quality/auditoria.py</code></td>
      <td>Audita el <b>proceso</b>, no el resultado estadístico</td>
    </tr>
    <tr style="background:#fafbff">
      <td><b>¿Las fuentes ONSV/SUTRAN/OSITRAN son de fiar?</b></td>
      <td><code>scripts/fiabilidad_fuentes.py</code> <span style="color:#4f46e5">· nuevo</span></td>
      <td>Una fuente puede ser fiable y aun así el modelo no predecir</td>
    </tr>
    <tr style="background:#fafbff">
      <td><b>¿La predicción aguanta fuera de muestra?</b></td>
      <td><code>scripts/validez_predictiva.py</code> <span style="color:#4f46e5">· nuevo</span></td>
      <td>Un mal R² aquí no dice que los datos sean malos</td>
    </tr>
  </tbody>
</table>

<div class="sipat-note" style="margin-top:12px">
  <b>El patrón es el mismo en los dos módulos nuevos:</b> una tabla de afirmaciones con
  <b>veredicto + evidencia + límite</b>, y ninguna se colapsa en un índice único. Combinarlas exigiría
  decidir cuánto pesa cada riesgo, y <b>esa decisión no sale de estos datos</b>.
</div>

<div class="sipat-cards" style="margin-top:12px">
  <div class="sipat-card">
    <div class="sipat-card__t">🔍 Fiabilidad · 6 afirmaciones</div>
    <div class="sipat-card__d">Veredicto + evidencia + límite por fuente. <b>4 de 6 no son un sí limpio.</b></div>
  </div>
  <div class="sipat-card" style="border-left-color:#dc2626">
    <div class="sipat-card__t">📉 Validez · 4 afirmaciones</div>
    <div class="sipat-card__d">Protocolo espacial y temporal. Concluye: <b>priorizar sí, pronosticar no</b>.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">🧪 Cobertura de las pruebas</div>
    <div class="sipat-card__d">
      <code>tests/test_fiabilidad_fuentes.py</code> y <code>tests/test_validez_predictiva.py</code>
      ejecutan cada afirmación como regresión. Notebooks <code>05</code> y <code>06</code> sobre datos reales.
    </div>
  </div>
  <div class="sipat-card" style="border-left-color:#059669">
    <div class="sipat-card__t">🔁 Reproducible</div>
    <div class="sipat-card__d">
      <code>python scripts/fiabilidad_fuentes.py</code> y
      <code>python scripts/validez_predictiva.py</code> regeneran ambos JSON desde cero.
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Auditoría <span class="sipat-essential">esencial</span></span>
    <h1>¿Las fuentes son de fiar?</h1>
  </div>
  <div class="sipat-head__aside">
    <code>docs/fiabilidad_fuentes.md</code><br>
    Salida: <code>fiabilidad_fuentes.json</code>
  </div>
</div>

<table class="sipat-table sipat-table--tight">
  <thead><tr><th style="width:44%">Afirmación</th><th style="width:20%">Veredicto</th><th>Límite</th></tr></thead>
  <tbody>
    <tr><td>Las coordenadas de ONSV sirven para geocodificar por km</td><td style="color:#059669;font-weight:700">SÍ</td><td>5.014 filas, <b>0</b> sin coordenada y 0 fuera del Perú</td></tr>
    <tr><td>Las coordenadas de SUTRAN sirven para geocodificar por km</td><td style="color:#b45309;font-weight:700">CON RESERVAS</td><td><b>499 filas (6,12 %)</b> sin coordenada</td></tr>
    <tr><td>El doble reporte dentro de cada fuente es marginal</td><td style="color:#059669;font-weight:700">SÍ</td><td>204 candidatos tras añadir modalidad, no 3.786</td></tr>
    <tr><td>OSITRAN sirve como capa de contraste de la red nacional</td><td style="color:#b91c1c;font-weight:700">NO COMO CAPA COMPLETA</td><td>Cubre <b>26 de 150 rutas (17,3 %)</b> y solo en vías concedidas</td></tr>
    <tr><td>Se puede estimar la subnotificación</td><td style="color:#b91c1c;font-weight:700">NO ESTIMABLE</td><td>Los dos muestreos no son de la misma población</td></tr>
    <tr><td>El solape ONSV/SUTRAN no es un artefacto del umbral</td><td style="color:#059669;font-weight:700">SÍ</td><td>Estable con radio 0,1–1 km y tolerancia 0–7 días</td></tr>
  </tbody>
</table>

<div class="sipat-note sipat-note--warn" style="margin-top:12px">
  <b>El 17,3 % no dice que OSITRAN registre poca siniestralidad.</b> Las rutas concedidas concentran
  tráfico, así que registrar 41.833 accidentes en el 17,3 % de los caminos es <b>lo esperable</b>.
  Sirve para describir caminos concedidos, no para corregir el total nacional.
</div>

<div class="sipat-cards" style="margin-top:12px">
  <div class="sipat-card">
    <div class="sipat-card__t">📊 Coordenadas</div>
    <div class="sipat-card__d">
      <b>ONSV:</b> 5.014 filas · 0 sin coordenada · 0 fuera del Perú.<br>
      <b>SUTRAN:</b> 8.155 filas · <b>499 sin coordenada (6,12 %)</b> · 0 fuera del país.
    </div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">🔗 Solape entre fuentes</div>
    <div class="sipat-card__d">
      320 coincidencias de km+fecha → <b>204</b> al añadir la modalidad. El solape se recalcula con radio
      0,1–1 km y tolerancia 0–7 días: se mueve de forma acotada.
    </div>
  </div>
  <div class="sipat-card" style="border-left-color:#059669">
    <div class="sipat-card__t">✅ La invariante que importa</div>
    <div class="sipat-card__d">
      Deduplicar <b>resta o iguala</b>: la unión de eventos nunca puede superar la suma ingenua.
      Por eso el solape no es un artefacto del umbral elegido.
    </div>
  </div>
  <div class="sipat-card" style="border-left-color:#7c3aed">
    <div class="sipat-card__t">🚫 Lo que NO se afirma</div>
    <div class="sipat-card__d">
      Que el solape mida subnotificación. Dos fuentes que rara vez coinciden
      <b>siguen sin ser dos vistas de la misma población</b>.
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Auditoría <span class="sipat-essential">esencial</span></span>
    <h1>Dos errores que casi llegan a conclusiones falsas</h1>
  </div>
  <div class="sipat-head__aside">
    Ninguno de los dos era un problema<br>
    del dato, sino de la <b>lectura</b>
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-card" style="margin-bottom:11px">
      <div class="sipat-card__t" style="color:#b91c1c">❌ «SUTRAN tiene 3.786 duplicados»</div>
      <div class="sipat-card__d">
        <b>Es un error de lectura de la fuente.</b> La coordenada de SUTRAN viene del <b>kilómetro
        del tramo</b> donde se registró el accidente, no de un GPS del lugar. Por eso 12 accidentes
        distintos del mismo km comparten punto.
        <div class="sipat-note sipat-note--ok" style="margin-top:9px;font-size:.75rem">
          Añadiendo modalidad, los candidatos a doble reporte bajan a <b>204</b>.<br>
          <b>El número accionable es 204, no 3.786.</b>
        </div>
      </div>
    </div>
    <div class="sipat-card">
      <div class="sipat-card__t" style="font-size:.72rem;color:#64748b">ejemplo real</div>
      <div class="sipat-card__d">
        En el km −18,023 del 2021-02-24 hay un <b>choque a las 19:30</b> y un <b>despiste</b>.
        Son dos accidentes distintos, no uno duplicado.
      </div>
    </div>
  </div>
  <div>
    <div class="sipat-card" style="margin-bottom:11px">
      <div class="sipat-card__t" style="color:#b91c1c">❌ «OSITRAN cubre el 0,0 % de la red»</div>
      <div class="sipat-card__d">
        La cobertura salía en cero por un <b>fallo real de cruce</b>: se unía OSITRAN con la red por
        <code>siglas</code>, y esos identificadores <b>no son intercambiables</b>.
      </div>
    </div>
    <table class="sipat-table sipat-table--tight" style="margin-bottom:11px">
      <thead><tr><th>Columna</th><th class="num">Únicos</th><th>Qué es</th></tr></thead>
      <tbody>
        <tr><td><code>siglas</code></td><td class="num">16</td><td>Código corto de concesión (ASO, BAC, CHA…)</td></tr>
        <tr><td><code>ruta</code></td><td class="num">103</td><td><b>Identificador de tramo en formato MTC</b></td></tr>
      </tbody>
    </table>
    <div class="sipat-note" style="font-size:.75rem">
      La red vial usa el formato MTC (<code>PE-02</code>), o sea que corresponde a <code>ruta</code>.
      Unir por <code>siglas</code> da cero coincidencias y produce un <b>0 % que parece un hallazgo</b>
      cuando en realidad es un cruce de dos sistemas de códigos distintos.
    </div>
  </div>
</div>

<div class="sipat-note sipat-note--ok" style="margin-top:11px">
  <b>La lección que ambos errores encierran:</b> un 0 % o un 3.786 «duplicados» no son un hallazgo
  sobre los datos, sino sobre <b>la lectura que hacemos de ellos</b>. Ninguno de los dos se corrigió
  a ojo: se detectó porque alguien se preguntó qué significaba el número, y ambos quedaron cubiertos
  por tests de regresión.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Auditoría <span class="sipat-essential">esencial</span></span>
    <h1>Por qué la subnotificación <i>no</i> es estimable</h1>
  </div>
  <div class="sipat-head__aside">
    Es el caso donde el intervalo<br>
    <b>engaña</b>: es estrecho y no sirve
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:12px">
  <KpiCard :value="26" label="Eventos capturados por ambas" hint="n_ab · la muestra de Lincoln-Petersen" tone="slate" />
  <KpiCard :value="153670" label="N estimado por L-P" hint="IC95: 83.868 – 281.568" tone="red" />
  <KpiCard :value="1.77" :decimals="2" label="Multiplicador del intervalo" hint="SE(log N) ≈ 0,29 → intervalo manejable" tone="amber" />
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-note sipat-note--bad">
      <b>Ese N no se publica como estimación de subnotificación, y no es por la muestra pequeña.</b>
      Con <code>n_ab = 26</code> el intervalo <b>no</b> es ancho: el multiplicador ronda 1,77. Es un intervalo manejable.
    </div>
    <div class="sipat-note" style="margin-top:10px">
      Lincoln-Petersen exige que las dos fuentes sean <b>dos muestreos independientes de la misma
      población</b>. ONSV y SUTRAN no lo son: difieren en el <b>ámbito de red</b> que cubren y en la
      <b>ventana temporal</b> que registran.
    </div>
  </div>
  <div>
    <table class="sipat-table sipat-table--tight">
      <thead><tr><th>Comprobación estructural</th><th class="num">Valor</th><th>Veredicto</th></tr></thead>
      <tbody>
        <tr><td>Rutas no comunes entre ONSV y SUTRAN</td><td class="num">56,1 %</td><td style="color:#b91c1c">Falla</td></tr>
        <tr><td>Meses no comunes entre ambas</td><td class="num">87,5 %</td><td style="color:#b91c1c">Falla</td></tr>
      </tbody>
    </table>
    <div class="sipat-note sipat-note--warn" style="margin-top:11px">
      Aplicado aquí, el estimador mediría <b>la diferencia entre dos poblaciones</b>, no lo que ninguna
      de las dos deja fuera.
    </div>
    <div class="sipat-note sipat-note--ok" style="margin-top:10px;font-size:.78rem">
      <b>La lección metodológica:</b> que el intervalo sea estrecho no lo hace aplicable.
      <b>Una confianza alta sobre la pregunta equivocada sigue siendo la pregunta equivocada.</b>
    </div>
  </div>
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Auditoría <span class="sipat-essential">esencial</span></span>
    <h1>¿La predicción aguanta fuera de muestra?</h1>
  </div>
  <div class="sipat-head__aside">
    <code>docs/validez_predictiva.md</code><br>
    Panel de <b>18.750 celdas</b> (3.750 × 5 años)
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:11px">
  <div class="sipat-card">
    <div class="sipat-card__t">86,4 % de celdas en cero</div>
    <div class="sipat-card__d">Con esa mayoría, el MAE premia predecir cero y el R² se apoya en la varianza de unos pocos tramos con eventos.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#0ea5e9">
    <div class="sipat-card__t">GroupKFold por corredor</div>
    <div class="sipat-card__d"><code>PE-1N</code> y <code>PE-1S</code> son la misma Panamericana en sentidos opuestos. Agrupados por tramo, el test sería <b>copia del train</b> y cualquier R² alto mediría memoria, no capacidad de extrapolar.</div>
  </div>
  <div class="sipat-card" style="border-left-color:#d97706">
    <div class="sipat-card__t">El panel se construye con la misma función</div>
    <div class="sipat-card__d"><code>panel_anual.construir_panel</code>, la que alimenta <code>dataset_modelo.csv</code>. Usar otra asignación de eventos sería medir un dataset que nadie consume.</div>
  </div>
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-card__t" style="margin-bottom:7px">Protocolo espacial · «¿sirve en una carretera nueva?»</div>
    <table class="sipat-table sipat-table--tight">
      <thead><tr><th>Modelo</th><th class="num">MAE</th><th class="num">R²</th><th class="num">Dev. Poisson</th></tr></thead>
      <tbody>
        <tr><td>Media de entrenamiento</td><td class="num">0,464</td><td class="num">−0,009</td><td class="num">1,252</td></tr>
        <tr><td>Mediana de entrenamiento</td><td class="num">0,267</td><td class="num">−0,079</td><td class="num">n/d</td></tr>
        <tr><td><b>NegBin con offset</b></td><td class="num"><b>0,370</b></td><td class="num"><b>+0,102</b></td><td class="num"><b>0,824</b></td></tr>
      </tbody>
    </table>
  </div>
  <div>
    <div class="sipat-card__t" style="margin-bottom:7px">Protocolo temporal · «¿sirve mañana?»</div>
    <table class="sipat-table sipat-table--tight">
      <thead><tr><th>Modelo</th><th class="num">MAE</th><th class="num">R²</th><th class="num">Dev. Poisson</th></tr></thead>
      <tbody>
        <tr><td>Media</td><td class="num">0,371</td><td class="num">−0,133</td><td class="num">0,804</td></tr>
        <tr><td>NegBin con offset</td><td class="num">0,362</td><td class="num">−1,490</td><td class="num">0,728</td></tr>
        <tr><td>Persistencia (año anterior)</td><td class="num">0,212</td><td class="num">−0,888</td><td class="num">n/d</td></tr>
      </tbody>
    </table>
  </div>
</div>

<div class="sipat-note sipat-note--warn" style="margin-top:11px">
  <b>MAE y devianza de Poisson discordan, y no se fuerza un ganador.</b> La persistencia «gana» por MAE
  (0,212 contra 0,362) porque premia predecir cero en las celdas mayoritarias, pero se queda
  <b>sin devianza definida</b>; el NegBin gana por devianza (0,728 contra 0,804). Cuando las métricas
  no coinciden el veredicto es <b>AMBIGUO</b>.
</div>

---

<div class="sipat-head">
  <div>
    <span class="sipat-head__kicker">Auditoría <span class="sipat-essential">esencial</span></span>
    <h1>El −67 % de 2025 no es una mejora</h1>
  </div>
  <div class="sipat-head__aside">
    El límite que estos datos<br>
    <b>no pueden sortear</b>
  </div>
</div>

<div class="sipat-cards" style="margin-bottom:12px">
  <KpiCard :value="-67" suffix="%" label="Siniestros ONSV en 2025" hint="Frente al promedio 2021–2024" tone="red" />
  <KpiCard :value="12" label="Meses cubiertos" hint="No es un año incompleto" tone="slate" />
  <KpiCard :value="1.24" :decimals="2" label="Tasa de mortalidad 2021" hint="Fallecidos por siniestro" tone="green" />
  <KpiCard :value="1.21" :decimals="2" label="Tasa de mortalidad 2025" hint="Prácticamente constante" tone="green" />
</div>

<div class="sipat-split sipat-split--even">
  <div>
    <div class="sipat-note sipat-note--bad">
      Un <b>descenso del volumen acompañado de una tasa de mortalidad constante</b> no es un patrón de
      mejora de la seguridad vial: si bajaran los accidentes graves, la tasa de mortalidad subiría
      ligeramente. Lo más consistente con los datos es un <b>cambio en la captura de la fuente</b>.
    </div>
    <div class="sipat-note" style="margin-top:10px">
      <b>Consecuencia directa:</b> el error del holdout temporal <b>mezcla</b> error del modelo y
      cambio de la fuente, y estos datos <b>no permiten separarlos</b>. Por eso el veredicto
      «el holdout temporal mide capacidad de predecir a futuro» es <b>NO</b>.
    </div>
  </div>
  <div>
    <table class="sipat-table sipat-table--tight">
      <thead><tr><th>Afirmación</th><th style="width:20%">Veredicto</th></tr></thead>
      <tbody>
        <tr><td>El modelo usa las covariables para predecir mejor que la media</td><td style="color:#059669;font-weight:700">SÍ</td></tr>
        <tr><td>El R² justifica usarlo como pronóstico</td><td style="color:#b91c1c;font-weight:700">NO</td></tr>
        <tr><td>El modelo supera a la persistencia en el holdout</td><td style="color:#b45309;font-weight:700">AMBIGUO</td></tr>
        <tr><td>El holdout temporal mide capacidad de predecir a futuro</td><td style="color:#b91c1c;font-weight:700">NO</td></tr>
      </tbody>
    </table>
    <div class="sipat-note sipat-note--warn" style="margin-top:11px">
      <b>Conclusión operativa:</b> el modelo sirve para <b>priorizar</b> tramos —ordena mejor que la
      media— y <b>no</b> para <b>prever cuántos siniestros</b> ocurrirán. El dashboard debe decirlo así
      en lugar de mostrar un número como si fuera un pronóstico.
    </div>
  </div>
</div>