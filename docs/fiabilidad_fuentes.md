# Fiabilidad de las fuentes: ¿son de fiar ONSV, SUTRAN y OSITRAN?

Módulo: [`scripts/fiabilidad_fuentes.py`](../scripts/fiabilidad_fuentes.py) ·
Salida: `data/processed/dashboard/fiabilidad_fuentes.json`

Este documento cubre **una sola** de las cuatro preguntas del proyecto. Las otras
tres viven en otros módulos y no se mezclan:

| Pregunta | Módulo |
|---|---|
| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` |
| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |
| **¿Las fuentes ONSV/SUTRAN/OSITRAN son de fiar?** | **este documento** |
| ¿La predicción aguanta fuera de muestra? | [`validez_predictiva.md`](validez_predictiva.md) |

**No hay un índice de confiabilidad.** Ponderar cuatro riesgos distintos en un
número exigiría decidir cuánto pesa cada uno, y esa decisión no sale de estos
datos. Lo que hay es una tabla de afirmaciones con veredicto, evidencia y límite.

Todas las cifras se leen de los ficheros del workspace. Reproducir:

```
python scripts/fiabilidad_fuentes.py
```

## 1. Ventanas temporales: las fuentes no cubren lo mismo

| Fuente | Ventana observada |
|---|---|
| ONSV | 2021-01-01 → 2025-12-28 |
| SUTRAN | 2020-01-01 → 2021-09-30 |
| OSITRAN | 2019 → 2026 (agregado anual) |

El solape ONSV ∩ SUTRAN son **8,9 meses** (2021-01-01 a 2021-09-30). Cualquier
comparación entre ambas fuentes está restringida a esa ventana; fuera de ella no
hay información de solape. Sumar sus totales sin más mezcla periodos distintos y
no describe ninguna ventana concreta.

## 2. Coordenadas

| | n | Sin coordenada | Fuera de Perú | Duplicados exactos de posición |
|---|---|---|---|---|
| ONSV | 5.014 | 0 (0%) | 0 (0%) | 2 (0,04%) |
| SUTRAN | 8.155 | 499 (6,1%) | 0 (0%) | 3.786 (**46,4%**) |

Dos precisiones que cambian la lectura:

- **Ausencia de dato y error de geocodificación son defectos distintos.** Las 499
  filas sin coordenada de SUTRAN no están mal situadas: no están situadas. Se
  reportan aparte para no inflar el error de geocodificación.
- **SUTRAN repite coordenada.** Casi la mitad de sus filas comparte posición con
  otra. Cualquier agregado por posición sin deduplicar cuenta el mismo lugar
  varias veces.

Lo que se ha medido es plausibilidad geográfica: las coordenadas que sí existen
caen dentro del Perú. **El error de posición contra una fuente de verdad no se ha
auditado**; que una coordenada esté dentro del país no significa que esté en la
carretera correcta.

## 3. OSITRAN: la atribución de ruta

OSITRAN son **41.833 accidentes** en 8 años, de **16 concesiones**.

| Medida | Valor |
|---|---|
| Sin atribución de ruta (`SIN INFO`) | 16.544 (**39,5%**) |
| Con ruta | 25.289 |
| Rutas distintas con atribución | 102 |
| De esas, coinciden con `tramos_red` | 26 |
| Accidentes sobre ruta de la red | 17.943 |
| **Cobertura sobre el total publicado** | **42,9%** |
| **Cobertura sobre lo utilizable (con ruta)** | **71,0%** |

Las dos cifras de cobertura son necesarias. Publicar solo el 42,9% hace creer que
se pierde el 57% de la fuente; publicar solo el 71% oculta que casi 4 de cada 10
registros no se pueden atribuir a ningún tramo. La pérdida real es el 39,5% sin
ruta más el 29% con ruta que no está en la red.

Esto resuelve la discrepancia del README: las "16 concesiones" son **empresas**;
las 103 rutas que agrupa el modelo son **rutas** (102 con atribución, 26 de ellas
en la red del estudio). Son dos recuentos de cosas distintas, no una contradicción.

Límite estructural: es un agregado por concesión y año, **sin fecha de evento ni
fallecidos separados**. Sirve como carga relativa por tramo, no como serie de
siniestros — por eso `deduplicacion_eventos.py` lo excluye de `y_total`.

## 4. Solape ONSV–SUTRAN y Lincoln-Petersen

Dentro de la ventana común, con `radio_km=0.25` y `tolerancia_dias=1`:

| | Valor |
|---|---|
| n_a (ONSV, marginal inclusivo) | 996 |
| n_b (SUTRAN, marginal inclusivo) | 4.145 |
| n_ab (vistos por ambas) | **26** |
| Únicos en la unión | 5.115 |
| Suma ingenua | 5.141 |

Lincoln-Petersen da N ≈ 158.785 (IC95 87.516 – 288.093; SE(log N) ≈ 0,30), un
**factor de 31× sobre lo observado**.

### El veredicto es NO ESTIMABLE, y no por falta de muestra

El intervalo no es absurdamente ancho: un factor ~1,34 sobre el estimador es
manejable. El problema es otro.

Lincoln-Petersen requiere que ambas fuentes enumeren **la misma población** de
siniestros y que las capturas sean independientes. Aquí:

- Las **rutas sí se solapan**: Jaccard 0,44, 93 rutas comunes de 305.
- Los **eventos no**: solo coincide el **0,51%**.

Que coincidan las carreteras y no los accidentes significa que SUTRAN **captura
las mismas carreteras de otra manera**: su unidad de registro es la alerta del
operador, no el siniestro. Un factor 31× no mide subnotificación, mide dos fuentes
no comparables sumadas. Por eso se reporta "no estimable" en lugar de publicar un
número que alguien acabaría usando como factor de corrección.

### Sensitividad: n_ab es un parámetro, no una medida

| radio_km \ tolerancia_días | 0 | 1 | 3 |
|---|---|---|---|
| 0,1 | 13 | 15 | 16 |
| 0,25 | 22 | **26** | 29 |
| 0,5 | 44 | 50 | 53 |
| 1,0 | 75 | 85 | 95 |

`n_ab` va de 13 a 95: **un factor 7** por decidir el criterio de emparejamiento.
Parte de ese "solape" son accidentes distintos en la misma carretera que caen
dentro del radio. El valor de referencia (26 a 0,25 km) es una decisión de
parámetro, y por eso importa que quede escrito.

## 5. Tabla de afirmaciones

| Afirmación | Veredicto |
|---|---|
| Las coordenadas de ONSV y SUTRAN sirven para geolocalizar sobre la red vial | ONSV sí / SUTRAN con reservas |
| ONSV y SUTRAN registran los mismos siniestros | **No** |
| Se puede estimar la subnotificación con Lincoln-Petersen | **No estimable** |
| El solape de eventos es estable al criterio de emparejamiento | **No** |
| OSITRAN aporta una señal espacial comparable a ONSV | Parcial |

La evidencia y el límite de cada una están en `fiabilidad_fuentes.json`, clave
`afirmaciones`.

## 6. Límites de este análisis

- El solape se mide con geocodificación lineal sobre `tramos_red`, no con
  coincidencia de identificadores de evento. Ninguna de las dos fuentes publica un
  ID común, así que el emparejamiento es espacial y por eso es sensible al radio.
- La ventana común son 8,9 meses. Fuera de ella no hay nada que comparar.
- OSITRAN no se puede deduplicar contra nada (no tiene fecha de evento ni
  coordenadas), así que queda fuera de todo total unionado.
- No se evalúa la **exactitud** de la posición de los accidentes, solo que la
  coordenada sea plausible.
