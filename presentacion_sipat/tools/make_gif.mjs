// Genera 2 GIF animados a partir de los SVG de Archify, sin re-autorarlos.
//
// En vez de manipulating el reloj de las animaciones CSS (fragil al reutilizar la
// pagina), cada frame calcula el estado de cada elemento de forma determinista:
// las aristas se dibujan progresivamente (stroke-dashoffset) y los nodos entran
// en cascada (opacity + escala). Despues ffmpeg ensambla el GIF.
//
// Uso: node tools/make_gif.mjs
import { readFileSync, mkdirSync, rmSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-chromium'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const svgDir = resolve(root, 'public', 'svg')
const outDir = resolve(root, '.gif-frames')

const JOBS = [
  { out: 'hero-arquitectura', svg: 'arquitectura.svg', width: 1320, height: 680, duration: 2600 },
  { out: 'transicion-dataflow', svg: 'dataflow.svg', width: 1080, height: 660, duration: 2600 },
]

const FRAMES = 50

// Estado determinista para el frame f de FRAMES.
// times: milisegundos transcurridos desde el inicio de cada animacion.
function frameScript(duration) {
  return `
    const DURATION = ${duration};
    const N = ${FRAMES};
    const clamp01 = (x) => x < 0 ? 0 : (x > 1 ? 1 : x);
    const easeOut = (x) => 1 - Math.pow(1 - clamp01(x), 3);
    const easeBack = (x) => {
      const c1 = 1.70158, c3 = c1 + 1, u = clamp01(x) - 1;
      return 1 + c3 * u * u * u + c1 * u * u;
    };

    const svgEl = document.querySelector('svg');
    const edges = [...svgEl.querySelectorAll('path.a-default, path.a-emphasis, path.a-dashed')];
    const nodes = [...svgEl.querySelectorAll('g[data-node-id]')];
    const frames = [...svgEl.querySelectorAll('[data-graph-role="structural-frame"], .c-lane')];

    // longitudes reales de cada arista
    const lens = edges.map(p => { try { return p.getTotalLength() } catch { return 400 } });

    // ventanas de animacion
    const EDGE_STEP = 70, EDGE_DUR = 900;
    const NODE_START = 250, NODE_SPAN = 1500, NODE_DUR = 550;
    const FRAME_DUR = 600;

    window.__setFrame = (f) => {
      const t = (f / (N - 1)) * DURATION;

      edges.forEach((p, i) => {
        const d = i * EDGE_STEP;
        const k = easeOut((t - d) / EDGE_DUR);
        const len = lens[i];
        p.style.strokeDasharray = len + ' ' + len;
        p.style.strokeDashoffset = String(len * (1 - k));
        p.style.opacity = k > 0 ? '1' : '0';
      });

      nodes.forEach((n, i) => {
        const d = NODE_START + (nodes.length > 1 ? (i / (nodes.length - 1)) * NODE_SPAN : 0);
        const raw = (t - d) / NODE_DUR;
        const k = clamp01(raw);
        const s = 0.9 + 0.1 * easeBack(raw);
        n.style.opacity = String(k);
        n.style.transform = 'scale(' + s.toFixed(4) + ')';
      });

      frames.forEach((el, i) => {
        const d = 50 + i * 120;
        el.style.opacity = String(easeOut((t - d) / FRAME_DUR));
      });
    };
  `
}

function buildHtml(svg, w, h) {
  return `<!doctype html>
<html><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html, body { width:${w}px; height:${h}px; background:#ffffff; overflow:hidden; }
  #stage { width:${w}px; height:${h}px; }
  #stage svg { display:block; width:100%; height:100%; }
  /* estado inicial: invisible; __setFrame escribe cada frame */
  path.a-default, path.a-emphasis, path.a-dashed { stroke-dashoffset: 1200; opacity: 0; }
  g[data-node-id] { opacity: 0; transform-box: fill-box; transform-origin: center; }
  [data-graph-role="structural-frame"], .c-lane { opacity: 0; }
</style></head>
<body><div id="stage"></div>
<script>
  const raw = ${JSON.stringify(svg)};
  document.getElementById('stage').innerHTML = raw;
  ${frameScript(2600)}
  window.__setFrame(0);
</script>
</body></html>`
}

const browser = await chromium.launch()

for (const job of JOBS) {
  console.log(`\n[gif] ${job.out}`)
  const jobDir = resolve(outDir, job.out)
  rmSync(jobDir, { recursive: true, force: true })
  mkdirSync(jobDir, { recursive: true })

  const svg = readFileSync(resolve(svgDir, job.svg), 'utf8')
  const html = buildHtml(svg, job.width, job.height)

  // pagina nueva por job: evita estado residual
  const page = await browser.newPage({ viewport: { width: job.width, height: job.height } })
  await page.setContent(html, { waitUntil: 'load' })
  await page.waitForFunction(() => typeof window.__setFrame === 'function')

  const sizes = []
  for (let f = 0; f < FRAMES; f++) {
    await page.evaluate((n) => window.__setFrame(n), f)
    const file = resolve(jobDir, `f${String(f).padStart(3, '0')}.png`)
    await page.screenshot({ path: file })
    sizes.push(f)
  }
  await page.close()
  console.log(`  ${FRAMES} frames -> .gif-frames/${job.out}/`)
}

await browser.close()
console.log('\n[gif] listo. Ahora ejecuta tools/build_gif.ps1')
