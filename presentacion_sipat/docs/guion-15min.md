# Guion de exposición · 15 minutos

Ruta esencial de la presentación. Las 33 slides marcadas con la insignia
**ESENCIAL** en la esquina superior derecha son las que se exponen; el resto
queda como documentación para preguntas.

**Regla**: si una slide no está en esta lista, se salta con `→` sin anunciarlo.

> **Nota sobre la numeración**: el bloque 04b (Auditoría) se insertó después del
> bloque 04 (Motor de riesgo), así que las slides a partir de ahí van desplazadas
> respecto a la última versión. Los números de este guion son los actuales.

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
| 3 · Una red nacional, tres realidades | Los 3 números: 51.000+, 28.918 km, 3.750 tramos. **Frase clave**: «los accidentes llegan como *PE-1S km 45*, no como coordenadas. Sin georreferenciar no hay mapa ni ruta.» | 0:50 |
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
| 24 · Ejemplo real Lima→Huancayo | **Slide ancla.** 8.5726 [Alto] histórico, 0.6733 [Medio] predictivo, 41.6 % de cobertura. **Frase clave**: «los dos indicadores no coinciden a propósito, y el sistema enseña la cobertura en vez de rellenar el hueco.» | 0:40 |

---

## Bloque 4b · Auditoría (8:00 – 10:15) · 4 slides ← **el bloque que más suma**

| Slide | Qué decir | Tiempo |
|---|---|---|
| 25 · Sección | «Antes de mostrar nada más, el sistema se audita a sí mismo.» | 0:05 |
| 26 · **Las cuatro preguntas, cuatro módulos** | **Slide ancla.** DQS · auditoría del ETL · **fiabilidad de fuentes** · **validez predictiva**. «Son preguntas distintas que no se sustituyen: una fuente puede ser fiable y aun así el modelo no predecir.» | 0:40 |
| 28 · ¿Las fuentes son de fiar? | Los 6 veredictos. **Insistir en SUTRAN CON RESERVAS** (6,12 % sin coordenada) y en que OSITRAN cubre 26 de 150 rutas. | 0:40 |
| 29 · Los dos errores de lectura | Los **3.786 «duplicados» que no lo son** (204 es el número accionable) y OSITRAN al 0,0 % por cruzar por `siglas` en vez de `ruta`. | 0:35 |
| 31 · La validez predictiva | Devianza 0,824 vs 1,252 (**SÍ** ordena) · R² +0,102 (**NO** pronostica) · persistencia vs NegBin (**AMBIGUO**). Y el **−67 % de ONSV en 2025**. **Frase de cierre del bloque**: «priorizar no es pronosticar.» | 1:10 |

**Si solo hay tiempo para 1 slide de este bloque, es la 26.**

---

## Bloque 5 · Viaja seguro (10:15 – 11:45) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 32 · Sección | | 0:05 |
| 33 · Flujo completo | Las 3 capas en paralelo. | 0:30 |
| 34 · Lo que ve el usuario | Recorrer las cards con un clic cada una. | 0:45 |

---

## Bloque 6 · Analítica nacional (11:45 – 12:20) · 1 slide

| Slide | Qué decir | Tiempo |
|---|---|---|
| 37 · Mapa nacional | «Esto ya no es una persona, es una institución.» | 0:35 |

---

## Bloque 7 · Arquitectura (11:30 – 13:00) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 33 · Topología en estrella | El diagrama se dibuja solo. **Las 4 justificaciones**: límite de responsabilidades, un solo dueño del ranking, cachés centralizadas, gobernanza. | 0:55 |
| 35 · 3 servicios y 7 endpoints | El caso real de la API: `hist=8.5726 [Alto] pred=0.6733 [Medio] cov=41.6%`. | 0:35 |

---

## Bloque 7 · Arquitectura (12:20 – 13:00) · 2 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 40 · Topología en estrella | El diagrama se dibuja solo. **Las 4 justificaciones**: límite de responsabilidades, un solo dueño del ranking, cachés centralizadas, gobernanza. | 0:30 |
| 42 · 3 servicios y 7 endpoints | El caso real de la API: `hist=8.5726 [Alto] pred=0.6733 [Medio] cov=41.6%`. | 0:10 |

---

## Bloque 8 · Metodología (13:00 – 13:20) · 1 slide

| Slide | Qué decir | Tiempo |
|---|---|---|
| 47 · CRISP-DM | Las 6 fases en una línea. | 0:20 |

---

## Bloque 9 · Cierre (13:20 – 15:00) · 3 slides

| Slide | Qué decir | Tiempo |
|---|---|---|
| 50 · Las 30 comprobaciones | Las 4 familias. **Mencionar el matiz**: 30/30 con el stack activo; 22/30 con el stack caído, y eso es dependencia de entorno, no regresión. | 0:35 |
| 53 · Riesgos técnicos | **No saltarse esta slide.** Grafo de conocimiento roto (456 nodos, 0 aristas) y por qué la verificación no lo detectó. Señala honestidad metodológica. | 0:35 |
| 56 · Gracias | Cierre. «El riesgo histórico no es una predicción, y el modelo ordena tramos pero no pronostica cantidades. Un sistema que dice las dos cosas en voz alta vale más que uno que solo muestra la primera.» | 0:30 |

---

## Reserve (1:00)

- **Auditoría completa**: slides 26 (4 preguntas), 27 (los 6 veredictos), 29 (los dos errores), 30 (Lincoln-Petersen), 32 (−67 % de 2025)
- Preguntas sobre el ETL: slides 8, 10, 13, 14
- Geocodificación y dataset: slides 18, 19
- **KPI unionado / por qué no hay un total**: slide 20
- Reporte ciudadano: slide 51
- Limitaciones completas: slide 52
- Stack tecnológico: slide 45
- Diagramas Archify interactivos: slide 44

---

## Preguntas que suelen llegar

| Pregunta | Slide de respuesta |
|---|---|
| «¿Cómo sabéis que el riesgo es real y no inventado?» | 21 (fórmula), 24 (dos indicadores) y **26 (las cuatro preguntas)** |
| «¿El modelo predice?» | **31 y 32** — ordena mejor que la media (devianza 0,824 vs 1,252) pero **no** pronostica cantidades; R² +0,102 |
| «¿Los datos de las 3 fuentes son comparables?» | 3, 27 y 52 — **no**, y el sistema nunca los mezcla. OSITRAN solo cubre el 17,3 % de las rutas |
| «¿Cuántos siniestros se dejan sin registrar?» | **30** — no estimable: Lincoln-Petersen exige dos muestreos de la misma población y aquí difieren en 56,1 % de rutas y 87,5 % de meses |
| «¿Por qué no publicáis un total de siniestros?» | 20 — suma ingenua 9.129 contra unión deduplicada 5.115; las fuentes cubren periodos distintos |
| «¿Qué pasa si llueve?» | 21 (clima como término) y 35 (SENAMHI / Open-Meteo) |
| «¿Y si un reporte ciudadano es falso?» | 51 — son autodeclarados, sin moderación, y separados de las fuentes oficiales |
| «¿Cómo garantizáis la calidad del dato?» | 10 (DQS), 11 (gate), 13 (12 defectos reales) |
| «¿Por qué NegBin y no Poisson?» | 23 — AIC 8.663 vs 11.984 |
| «¿Escalable?» | 40 — la API es el único nodo que orquesta; añadir un servicio no toca el dashboard |
| «¿Cuánto cubre el modelo?» | 24 — 41.6 %, y se muestra en pantalla en vez de rellenarse |
