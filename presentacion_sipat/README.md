# SIPAT · Presentación interactiva

Presentación de 57 slides sobre **SIPAT — Sistema de Prevención de Accidentes de Tránsito**,
construida con [Slidev](https://sli.dev/).

Documenta los **cuatro módulos** del proyecto: la capa de ingesta y calidad
(`etl-project/`), la de analítica y rutas seguras (raíz del repo), y los dos de
auditoría que se auditan a sí mismos (`fiabilidad_fuentes.py` y
`validez_predictiva.py`).

> Esta carpeta es **autocontenida**: no modifica nada del código de SIPAT ni de `etl-project/`.

---

## 1. Puesta en marcha

Requisitos: **Node.js ≥ 20** (probado con 26.5.0) y, solo para el PDF, Chromium vía Playwright.

```bash
cd presentacion_sipat

npm install     # dependencias (slidev, theme-seriph, playwright-chromium)
npm run dev     # abre http://localhost:5173
```

> **Windows / PowerShell**: la ExecutionPolicy bloquea los wrappers `.ps1` de npm.
> Si `npm` no responde, usa el ejecutable directo:
> `& "C:\Program Files\nodejs\npm.cmd" install`

### Otros comandos

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo con recarga en caliente |
| `npm run build` | Build estático en `dist/` (publicable en cualquier hosting) |
| `npm run export` | **PDF** de las 57 slides incluyendo los pasos de animación |
| `npm run export:dark` | PDF en modo oscuro |

El PDF se genera en la raíz del proyecto como `sipat-presentacion.pdf`.
La exportación necesita `playwright-chromium` (ya está en `devDependencies`) y su binario:

```bash
npx playwright install chromium    # solo si `npm run export` falla por falta de navegador
```

---

## 2. Estructura

```
presentacion_sipat/
├── slides.md                  # entry: headmatter + portada + imports de parts/
├── style.css                  # tema SIPAT (paleta indigo del dashboard)
├── parts/                     # el deck, dividido en 10 bloques
│   ├── 01-problema.md         #  4 slides · contexto y las 2 columnas
│   ├── 02-etl.md              #  9 slides · SIPAT-ETL (medallion, DQS, gate, tests)
│   ├── 03-pipeline.md         #  6 slides · geocodificación, dataset, KPI unionado, puntos negros
│   ├── 04-motor.md            #  5 slides · score_km, NegBin, umbrales
│   ├── 04b-auditoria.md       #  7 slides · las 4 preguntas, fiabilidad, validez predictiva
│   ├── 05-viaja-seguro.md     #  4 slides · el producto principal
│   ├── 06-analitica.md        #  4 slides · mapa, tendencias, IRRs
│   ├── 07-arquitectura.md     #  6 slides · estrella, API, stack, diagramas
│   ├── 08-metodologia.md      #  3 slides · CRISP-DM y SCRUM
│   └── 09-cierre.md           #  8 slides · verificación, límites, cierre
├── components/                # 5 componentes Vue propios
│   ├── ArchifyDiagram.vue     # inyecta un SVG y lo anima (aristas + cascada)
│   ├── KpiCard.vue            # indicador con contador animado
│   ├── DqsBar.vue             # las 6 dimensiones del DQS con su peso
│   ├── Semaforo.vue           # semáforo Bajo / Medio / Alto
│   └── StackGrid.vue          # el stack por capas
├── public/
│   ├── figures/               # 6 PNG de docs/figuras/ del proyecto
│   ├── svg/                   # 4 SVG extraídos de docs/archify/
│   └── gif/                   # 2 GIF animados (portada y transición)
├── tools/                     # utilidades de generación (ver abajo)
└── docs/guion-15min.md        # ruta esencial con tiempos
```

### Componentes

| Componente | Para qué |
|---|---|
| `<KpiCard :value="92.07" :decimals="2" suffix="/100" label="DQS" tone="green" />` | Cifra que cuenta desde 0 al entrar |
| `<DqsBar />` | Las 6 dimensiones ponderadas con barra animada y gate |
| `<Semaforo nivel="alto" score="8.5726" />` | Estado Bajo / Medio / Alto |
| `<ArchifyDiagram src="/svg/arquitectura.svg" :height="360" />` | Diagrama Archify con animación de dibujado |
| `<StackGrid :capas="[...]" />` | Stack tecnológico agrupado por capas |

---

## 3. Imágenes en movimiento

Hay **dos técnicas distintas**, elegidas a propósito:

| Recurso | Técnica | Por qué |
|---|---|---|
| 4 diagramas de Archify (arquitectura, dataflow) | **SVG animado en línea** | Vectorial: nítido en proyector 4K, pesa ~30 KB, y la cascada de nodos se puede dirigir con la voz. Sobrevive al export a PDF |
| Portada y transición | **GIF** (50 frames, ~1 MB) | Movimiento autónomo y en bucle, donde la animación es decorativa y no necesita dirección |

Los GIF **no** son capturas del deck: se generan animando el SVG original
(las aristas se dibujan con `stroke-dashoffset` y los nodos entran en cascada).

### Regenerar los assets

```bash
# 1. Extraer los SVG de los HTML de Archify (reconstruye un SVG autocontenido:
#    inyecta el tema claro y solo las reglas CSS que usa el diagrama)
node tools/extract_svg.mjs

# 2. Capturar los frames de los 2 GIF (Playwright)
node tools/make_gif.mjs

# 3. Ensamblar los GIF con paleta optimizada (ffmpeg 8+)
powershell -ExecutionPolicy Bypass -File tools/build_gif.ps1
```

> **Requisito de `extract_svg.mjs`**: los HTML de `docs/archify/` deben existir.
> El SVG por sí solo **no** se ve: depende de ~186 KB de CSS del visor, y el script
> se queda solo con las 28-34 reglas que el diagrama usa realmente.

---

## 4. Verificación

```bash
npm run dev                       # en una terminal
node tools/verify_render.mjs      # en otra: recorre las 57 slides y mide
```

`verify_render.mjs` abre cada slide en Chromium y reporta:

- **desbordes**: elementos que se salen del alto de la slide
- **imágenes rotas** (`naturalWidth === 0`)
- **errores de página**
- guarda capturas de las slides indicadas en `.verify/`

Estado actual de la última pasada:

```
slides revisadas   : 57
con desborde > 8px : 0
con imagen rota    : 0
errores de pagina  : 0
```

---

## 5. Rutas de exposición

Hay **dos formas** de usar el material, según la audiencia:

| Uso | Cómo |
|---|---|
| **Exposición de 15 min** | Las slides con la insignia <span>ESENCIAL</span> (visible en la esquina superior). Ver [`docs/guion-15min.md`](docs/guion-15min.md) |
| **Documentación / sustentación** | Las 57 slides se leen seguidas: es el manual visual del sistema |

### Controles de Slidev

| Atajo | Acción |
|---|---|
| `Espacio` / `→` | Siguiente (los `v-click` se revelan paso a paso) |
| `←` | Anterior |
| `o` | Vista general de todas las slides |
| `d` | Modo oscuro |
| `f` | Pantalla completa |
| `g` | Ir a una slide concreta |

---

## 6. Origen de los datos

Las cifras del deck **no** están escritas a mano: se leyeron de los artefactos reales.

| Dato | Fuente |
|---|---|
| 30/30 checks, 18.807 puntos de riesgo, Lima→Huancayo `hist=8.5726 pred=0.6733 cov=41.6%` | `data/processed/dashboard/verificacion.json` |
| **Veredictos de fiabilidad de fuentes** (6 afirmaciones) | `data/processed/dashboard/fiabilidad_fuentes.json` · `docs/fiabilidad_fuentes.md` |
| **Validez predictiva**: MAE/RMSE/R²/deviancia, −67 % ONSV 2025 | `data/processed/dashboard/validez_predictiva.json` · `docs/validez_predictiva.md` |
| **Significado de cada columna** y por qué no hay un total | `data/processed/dashboard/tramos_geo_meta.json` |
| DQS 92.07 / 92.00, 87 tests, 15 etapas, pesos del DQS | `etl-project/README.md` y `config/*.yaml` |
| 133 puntos negros | `dashboard/puntos_negros.csv` y `puntos_negros.json` (coinciden) |
| 28.918,5 km, 3.750 × 48, AIC 8.663 vs 11.984 | `README.md` raíz · `docs/informe_sipat.md` |
| 6 figuras | `docs/figuras/*.png` |
| 4 diagramas | `docs/archify/*.html` → SVG |

**Nota 1**: el grafo de conocimiento (`graphify-out/graph.json`) tiene 456 nodos pero
**0 aristas** (un update incremental colapsó las relaciones). Por eso la presentación
se construyó leyendo los README y el código, y **no** el grafo. Es un riesgo técnico
documentado en la slide de riesgos.

**Nota 2**: `verificacion.json` marca **30/30** cuando los tres servicios están
encendidos y **22/30** con el stack caído (los 8 que fallan son de API y servicios).
La presentación explica ambos números en lugar de enseñar solo el favorable.

**Nota 3**: la presentación se construyó con 57 slides; el PDF sale con ~61 páginas
porque `--with-clicks` genera una página extra por cada paso de animación.
