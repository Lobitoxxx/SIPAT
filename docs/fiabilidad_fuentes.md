# Fiabilidad de las fuentes: ONSV, SUTRAN y OSITRAN

Módulo: `scripts/fiabilidad_fuentes.py` · Salida: `data/processed/dashboard/fiabilidad_fuentes.json`

## Qué pregunta y qué NO pregunta

Este módulo responde a **una** pregunta: *¿las fuentes con las que se mide la
siniestralidad son de fiar?*

No es lo mismo que las otras tres del proyecto:

| Pregunta | Módulo |
|---|---|
| ¿El dato tiene nulos, rangos y unicidad? | `etl-project/src/quality/dimensions.py` (DQS) |
| ¿Las métricas del ETL son defendibles? | `etl-project/src/quality/auditoria.py` |
| **¿Las fuentes son de fiar?** | **este módulo** |
| ¿La predicción aguanta fuera de muestra? | `scripts/validez_predictiva.py` |

Una fuente puede ser perfectamente fiable y aun así producir un modelo que no
pronostica, y al revés. Son preguntas independientes con consecuencias
independientes.

## Resumen de los veredictos

| Afirmación | Veredicto |
|---|---|
| Las coordenadas de ONSV sirven para geocodificar por km | **SÍ** |
| Las coordenadas de SUTRAN sirven para geocodificar por km | **CON RESERVAS** |
| El doble reporte dentro de cada fuente es marginal | **SÍ** |
| OSITRAN sirve como capa de contraste de la red nacional | **NO COMO CAPA COMPLETA** |
| Se puede estimar la subnotificación | **NO ESTIMABLE** |
| El solape ONSV/SUTRAN no es un artefacto del umbral | **SÍ** |

No se colapsan en un índice único: combinarlos exigiría decidir cuánto pesa
cada riesgo, y esa decisión no sale de estos datos.

## Coordenadas

| | ONSV | SUTRAN |
|---|---|---|
| Filas | 5.014 | 8.155 |
| Sin coordenada | 0 (0,00%) | **499 (6,12%)** |
| Fuera del Perú | 0 | 0 |
| Coincidencias km+fecha | 1 | 320 |
| + misma modalidad | 1 | **204** |

ONSV tiene las 5.014 filas con coordenada, todas dentro del bounding box del
Perú. SUTRAN deja el 6,12% sin coordenada.

### Los 3.786 puntos repetidos de SUTRAN no son un defecto

SUTRAN tiene 3.786 filas que comparten coordenada con otra, y en una primera
versión eso se contaba como "duplicados". **Es un error de lectura de la
fuente**: la coordenada de SUTRAN viene del km del tramo donde se registró el
accidente, no de un GPS del lugar del accidente. Por eso 12 accidentes
distintos del mismo km comparten punto.

Por la misma razón, las 320 coincidencias de km+fecha **tampoco son
automáticamente errores**: en el km -18,023 del 2021-02-24 hay un choque a las
19:30 y un despiste, y son dos accidentes. Al añadir la modalidad, los
candidatos a doble reporte bajan a 204.

La distinción importa porque el número accionable es 204, no 3.786.

## OSITRAN: la columna de unión importa

OSITRAN cubre **26 de las 150 rutas** de la red nacional (17,3%).

Aquí hubo un fallo real: la cobertura salía **0,0%** porque se cruzaba OSITRAN
con la red por `siglas`. OSITRAN trae dos identificadores y no son
intercambiables:

| Columna | Valores únicos | Qué es |
|---|---|---|
| `siglas` | 16 | código corto de la concesión (ASO, BAC, CHA...) |
| `ruta` | 103 | identificador de tramo en formato MTC |

La red vial usa el formato MTC (`PE-02`), o sea que corresponde a `ruta`. Unir
por `siglas` da cero coincidencias y produce un 0% que parece un hallazgo
cuando en realidad es un cruce de dos sistemas de códigos distintos.

**Y el 17,3% no dice que OSITRAN registre poca siniestralidad.** La cobertura
por ruta y el volumen de accidentes son cosas distintas: las rutas concedidas
concentran tráfico, así que registrar 41.833 accidentes en 17,3% de las rutas es
lo esperable. Sirve para describir caminos concedidos, no para corregir el
total nacional.

## Subnotificación: por qué NO es estimable

Con 26 eventos capturados por ambas fuentes, Lincoln-Petersen da
**N ≈ 153.670** (IC95 83.868–281.568).

Ese número **no se publica como estimación de subnotificación**, y la razón no
es la que se suele dar:

> *No es porque la muestra sea pequeña.* Con `n_ab`=26 el intervalo **no** es
> ancho: SE(log N) ≈ 0,29, o sea un multiplicador de ~1,77. Es un intervalo
> manejable.

El veredicto es NO ESTIMABLE por una razón estructural:

| Comprobación | Valor |
|---|---|
| Rutas no comunes | **56,1%** |
| Meses no comunes | **87,5%** |

Lincoln-Petersen exige que las dos fuentes sean **dos muestreos independientes
de la misma población**. ONSV y SUTRAN no lo son: difieren en el ámbito de red
que cubren y en la ventana temporal que registran. Aplicado aquí, el estimador
mediría **la diferencia entre dos poblaciones**, no lo que ninguna de las dos
deja fuera.

Que el intervalo Resultado sea estrecho no lo hace aplicable: una confianza
alta sobre la pregunta equivocada sigue siendo la pregunta equivocada.

## Sensitividad del emparejamiento

El solape se recalcula con el radio entre 0,1 y 1 km y la tolerancia entre 0 y 7
días. `n_ambos` se mueve de forma acotada y la unión **nunca** supera la suma
ingenua (deduplicar resta o iguala), que es la invariante que importa.

Esto sostiene una afirmación modesta y útil: el 26 no es un artefacto de haber
elegido 250 m y ±1 día. Lo que **no** sostiene es que ese solape mida
subnotificación: dos fuentes que rara vez coinciden siguen sin ser dos vistas de
la misma población.

## Cómo reproducir

```bash
python scripts/fiabilidad_fuentes.py
python -m pytest tests/test_fiabilidad_fuentes.py -q
```