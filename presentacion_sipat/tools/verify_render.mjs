// Verificacion visual del deck: recorre todas las slides, mide desbordes,
// detecta imagenes rotas y guarda capturas de las indicadas.
//
// Slidev mantiene varias paginas en el DOM (actual, anterior, siguiente), asi que
// para medir hay que selecting la pagina VISIBLE, no la primera del DOM.
// Uso: node tools/verify_render.mjs [http://localhost:3030] [total]
import { chromium } from 'playwright-chromium'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const outDir = resolve(here, '..', '.verify')
const base = process.argv[2] || 'http://localhost:3030'
const total = Number(process.argv[3] || 49)
const shots = (process.argv[4] || '1,9,10,14,20,25,28,34,36,44,49')
  .split(',').map(Number)

mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })

const errors = []
page.on('pageerror', (e) => {
  const t = e.message
  if (!/Wake Lock/i.test(t)) errors.push(t)
})

// Slidev mantiene varias paginas en el DOM (actual, anterior, siguiente). Medir
// "la primera que aparece" da resultados erroneos, asi que se elige la pagina
// con mayor area visible dentro del viewport.
const PROBE = `(() => {
  const vh = window.innerHeight, vw = window.innerWidth;
  let best = null, bestArea = -1;
  for (const el of document.querySelectorAll('.slidev-page')) {
    const r = el.getBoundingClientRect();
    const w = Math.min(r.right, vw) - Math.max(r.left, 0);
    const h = Math.min(r.bottom, vh) - Math.max(r.top, 0);
    const area = w > 0 && h > 0 ? w * h : 0;
    if (area > bestArea) { bestArea = area; best = el; }
  }
  const host = best;
  if (!host) return null;
  const inner = host.querySelector('.slidev-layout') || host;
  const sr = inner.getBoundingClientRect();
  let overflow = 0, worst = '';
  inner.querySelectorAll('*').forEach((n) => {
    const r = n.getBoundingClientRect();
    if (r.height > 4 && r.bottom > sr.bottom + 6) {
      const d = r.bottom - sr.bottom;
      if (d > overflow) { overflow = d; worst = n.tagName.toLowerCase() + '.' + String(n.getAttribute('class') || '').slice(0, 34); }
    }
  });
  const imgs = [...inner.querySelectorAll('img')];
  const broken = imgs.filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.getAttribute('src'));
  return {
    title: (inner.innerText || '').split('\\n').filter(Boolean)[0] || '(sin texto)',
    overflow: Math.round(overflow),
    worst,
    broken,
    svgs: inner.querySelectorAll('svg').length,
    kpi: inner.querySelectorAll('.kpi').length,
    tables: inner.querySelectorAll('table').length
  };
})()`

await page.goto(`${base}/1`, { waitUntil: 'networkidle', timeout: 60000 })
await page.waitForTimeout(3500)

const rows = []
for (let i = 1; i <= total; i++) {
  await page.goto(`${base}/${i}`, { waitUntil: 'load', timeout: 30000 })
  await page.waitForTimeout(shots.includes(i) ? 3800 : 1500)

  const info = await page.evaluate(PROBE)

  if (info) rows.push({ i, ...info })
  if (shots.includes(i)) {
    await page.screenshot({ path: resolve(outDir, `slide-${String(i).padStart(2, '0')}.png`) })
  }
}

console.log(' #  overflow  rotas  svg kpi tbl  título')
for (const r of rows) {
  const warn = r.overflow > 8 ? ' << ' + r.worst : ''
  console.log(
    `${String(r.i).padStart(2)}  ${String(r.overflow).padStart(8)}  ${String(r.broken.length).padStart(5)}  ` +
    `${String(r.svgs).padStart(3)} ${String(r.kpi).padStart(3)} ${String(r.tables).padStart(3)}  ${r.title.slice(0, 40)}${warn}`
  )
}

const over = rows.filter((r) => r.overflow > 8)
const broken = rows.filter((r) => r.broken.length)
const noSvg = rows.filter((r) => r.svgs === 0 && r.kpi === 0 && r.tables === 0)

console.log('\n--- resumen ---')
console.log('slides revisadas       :', rows.length)
console.log('con desborde > 8px     :', over.length, over.map((r) => `${r.i}(${r.overflow}px)`).join(' '))
console.log('con imagen rota        :', broken.length, broken.map((r) => `${r.i}:${r.broken.join(',')}`).join(' '))
console.log('sin svg/kpi/tabla      :', noSvg.length, noSvg.map((r) => r.i).join(','))
console.log('errores de pagina      :', errors.length)
errors.slice(0, 8).forEach((e) => console.log('   !', e.slice(0, 160)))

await browser.close()
