# Guion de exposición · 15 minutos

Ruta esencial de la presentación. Las 26 slides marcadas con la insignia
**ESENCIAL** en la esquina superior derecha son las que se exponen; el resto
queda como documentación para preguntas.

**Regla**: si una slide no está en esta lista, se salta con `→` sin anunciarlo.

---

## Bloque 0 · Apertura (0:00 – 0:45) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 1 · Portada | «SIPAT cruza 51.000+ siniestros reales de tres fuentes oficiales con la red vial nacional, y los convierte en una decisión de viaje: por dónde ir y qué riesgo llevo.» | 0:30 |
| 2 · Bloque 01 | Transición. «Primero el problema.» | 0:15 |

---

## Bloque 1 · Contexto (0:45 – 2:15) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 3 · Una red nacional, tres realidades | Los 3 números: 51.000+, 28.900 km, 3.750 tramos. **Frase clave**: «los accidentes llegan como *PE-1S km 45*, no como coordenadas. Sin georreferenciar no hay mapa ni ruta.» | 0:50 |
| 4 · Dos subsistemas | **Esta es la slide que más importa.** «Antes de analizar, hay que verificar.» El contrato: el ETL publica o bloquea; SIPAT consume solo lo que pasó el gate. | 0:40 |

---

## Bloque 2 · SIPAT-ETL (2:15 – 5:15) · 4 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 6 · Sección ETL | «La mitad del sistema es verificación de datos.» | 0:10 |
| 7 · Medallion | Bronze inmutable / Silver canónico / Gold derivado. **Regla**: los datos crudos nunca se borran. | 0:35 |
| 9 · DQS ponderado | Las 6 dimensiones con su peso. **Insistir**: «el DQS no es una probabilidad de que los datos sean verdad; es un indicador interno de calidad.» Gate en 90. | 0:50 |
| 11 · Resultado real | DQS 92.07 y 92.00, 0 críticas, 0 cuarentena. | 0:35 |
| 12 · 12 problemas reales | **Slide de credibilidad.** «Nada de esto es hipotético: se encontró ejecutando.» Ejemplos: preámbulo del XLSX, 5.463 NaT por fechas DD/MM, coordenadas negativas de Perú puntuando 0 % en validez. **Frase**: «ningún defecto se parcheó en el código; todos viven como regla de configuración auditable.» | 1:00 |
| 13 · 87 tests | Por qué existe `test_regressions.py`: los fixtures sintéticos no detectaban los fallos reales. | 0:20 |

---

## Bloque 3 · Pipeline (5:15 – 6:30) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 16 · Pipeline completo | Recorrido visual de fuentes → geocodificación → dataset → servicios. | 0:30 |
| 18 · Puntos negros | Los 3 criterios. **Aclarar el 12 vs 129** si preguntan: 12 es Fase 1 (solo ONSV), 129 es el detector multi-fuente. | 0:45 |

---

## Bloque 4 · Motor de riesgo (6:30 – 9:00) · 3 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 20 · Sección | «Ahora la parte que responde al viajero.» | 0:05 |
| 21 · Fórmula del score | Los 4 términos, uno a uno. `score_km` + alertas históricas + tráfico de peajes, y luego el factor temporal. | 0:55 |
| 22 · Factor temporal y umbrales | Noche ×1.30, sábado ×1.25. Los dos juegos de umbrales (histórico y predictivo son escalas distintas). | 0:35 |
| 24 · Ejemplo real Lima→Huancayo | **Slide ancla.** 8.5726 [Alto] histórico, 0.6733 [Medio] predictivo, 41.6 % de cobertura. **Frase clave**: «los dos indicadores no coinciden a propósito, y el sistema enseña la cobertura en vez de rellenar el hueco.» | 0:55 |

---

## Bloque 5 · Viaja seguro (9:00 – 10:45) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 25 · Sección | | 0:05 |
| 26 · Flujo completo | Las 3 capas en paralelo. | 0:40 |
| 27 · Lo que ve el usuario | Recorrer las cards con un clic cada una. | 0:60 |

---

## Bloque 6 · Analítica nacional (10:45 – 11:30) · 1 slide

| Slide | Qué decir | Tiempo |
|---|---|---|
| 30 · Mapa nacional | «Esto ya no es una persona, es una institución.» | 0:45 |

---

## Bloque 7 · Arquitectura (11:30 – 13:00) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 33 · Topología en estrella | El diagrama se dibuja solo. **Las 4 justificaciones**: límite de responsabilidades, un solo dueño del ranking, cachés centralizadas, gobernanza. | 0:55 |
| 35 · 3 servicios y 7 endpoints | El caso real de la API: `hist=8.5726 [Alto] pred=0.6733 [Medio] cov=41.6%`. | 0:35 |

---

## Bloque 8 · Metodología (13:00 – 13:40) · 1 slide

| Slide | Qué decir | Tiempo |
|---|---|---|
| 40 · CRISP-DM | Las 6 fases en una línea. | 0:40 |

---

## Bloque 9 · Cierre (13:40 – 15:00) · 3 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 43 · 30 de 30 en verde | Las 4 familias de checks. | 0:30 |
| 46 · Riesgos técnicos | **No saltarse esta slide.** Grafo de conocimiento roto (456 nodos, 0 aristas) y por qué la verificación no lo detectó. Señala honestidad metodológica. | 0:30 |
| 49 · Gracias | Cierre. «La idea en una frase: el riesgo histórico no es una predicción, y un sistema que lo dice en voz alta vale más que uno que no lo dice.» | 0:20 |

---

## Reserve (1:00)

- Preguntas sobre el ETL: slides 7, 9, 12, 13
- Geocodificación y dataset: slides 17, 18
- Reporte ciudadano: slide 44
- Limitaciones completas: slide 45
- Stack tecnológico: slide 38
- Diagramas Archify interactivos: slide 37

---

## Preguntas que suelen llegar

| Pregunta | Slide de respuesta |
|---|---|
| «¿Cómo sabéis que el riesgo es real y no inventado?» | 21 (fórmula) y 24 (dos indicadores + cobertura) |
| «¿Los datos de las 3 fuentes son comparables?» | 3 y 45 — **no**, y el sistema nunca los mezcla |
| «¿Qué pasa si llueve?» | 21 (clima como término) y 28 (SENAMHI / Open-Meteo) |
| «¿Y si un reporte ciudadano es falso?» | 44 — son autodeclarados, sin moderación, y separados de las fuentes oficiales |
| «¿Cómo garantizáis la calidad del dato?» | 9 (DQS), 11 (gate), 12 (12 defectos reales) |
| «¿Por qué NegBin y no Poisson?» | 23 — AIC 8.663 vs 11.984 |
| «¿Escalable?» | 33 — la API es el único nodo que orchestra; añadir un servicio no toca el dashboard |
| «¿Cuánto cubre el modelo?» | 24 — 41.6 %, y se muestra en pantalla en vez de rellenarse |
