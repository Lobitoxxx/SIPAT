---
theme: seriph
title: SIPAT — Sistema de Prevención de Accidentes de Tránsito
info: >
  Analítica de siniestralidad vial y prevención antes de viajar para la Red Vial Nacional del Perú.
  57 slides · 4 módulos (calidad del dato, analítica, fiabilidad de fuentes, validez predictiva) ·
  51.000+ siniestros de 3 fuentes oficiales.
author: SIPAT
keywords: siniestralidad vial, Peru, OSRM, Negative Binomial, Streamlit, FastAPI, ETL, medallion
transition: slide-left
mdc: true
lineNumbers: false
monaco: false
drawings:
  persist: false
layout: default
class: text-left
canvasWidth: 1180
aspectRatio: 16/9
fonts:
  sans: 'Inter'
  serif: 'Inter'
  local: ''
  provider: none
---

<div class="sipat-cover">

<div class="sipat-shield" v-motion :initial="{ y: -30, opacity: 0 }" :enter="{ y: 0, opacity: 1, transition: { duration: 700 } }">🛡️</div>

<h1 v-motion :initial="{ y: 40, opacity: 0 }" :enter="{ y: 0, opacity: 1, transition: { duration: 800, delay: 120 } }">
  SIPAT
</h1>

<p class="sipat-cover__sub" v-motion :initial="{ y: 30, opacity: 0 }" :enter="{ y: 0, opacity: 1, transition: { duration: 800, delay: 320 } }">
  Sistema de Prevención de Accidentes de Tránsito.<br>
  Analítica de siniestralidad vial y prevención <b>antes de viajar</b> para la Red Vial Nacional del Perú.
  Cruza <b>51.000+ siniestros reales</b> de tres fuentes oficiales con la red vial georreferenciada.
</p>

<div class="sipat-cover__meta" v-motion :initial="{ y: 24, opacity: 0 }" :enter="{ y: 0, opacity: 1, transition: { duration: 800, delay: 520 } }">
  <span class="sipat-chip sipat-chip--accent">ONSV · SUTRAN · OSITRAN</span>
  <span class="sipat-chip">28.918,5 km de red</span>
  <span class="sipat-chip">3.750 tramos · 48 variables</span>
  <span class="sipat-chip">Modelo Negative Binomial</span>
  <span class="sipat-chip">4 módulos de auditoría</span>
</div>

<div class="sipat-hero" aria-hidden="true" v-motion :initial="{ opacity: 0, x: 30 }" :enter="{ opacity: 1, x: 0, transition: { duration: 900, delay: 700 } }">
  <img src="/gif/hero-arquitectura.gif" alt="" />
  <span class="sipat-hero__cap">Topología en estrella · la API como hub</span>
</div>

</div>

<!--
  ═══════════════════════════════════════════════════════════════════════
  SIPAT · Presentación
  Estructura modular: cada bloque es un fichero en parts/
  Las slides marcadas con <span class="sipat-essential">esencial</span>
  forman la ruta de exposición de 15 min (ver docs/guion-15min.md).
  ═══════════════════════════════════════════════════════════════════════
-->

---
src: ./parts/01-problema.md
---

---
src: ./parts/02-etl.md
---

---
src: ./parts/03-pipeline.md
---

---
src: ./parts/04-motor.md
---

---
src: ./parts/04b-auditoria.md
---

---
src: ./parts/05-viaja-seguro.md
---

---
src: ./parts/06-analitica.md
---

---
src: ./parts/07-arquitectura.md
---

---
src: ./parts/08-metodologia.md
---

---
src: ./parts/09-cierre.md
---
