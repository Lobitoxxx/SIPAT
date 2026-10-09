import { chromium } from 'playwright-chromium'

const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1280, height: 720 } })
await p.goto('http://localhost:5173/1', { waitUntil: 'networkidle', timeout: 60000 })
await p.waitForTimeout(3000)

// Nº total de slides segun la navegacion de Slidev
const total = await p.evaluate(() => {
  const el = document.querySelector('#slide-content, .slidev-slide-content')
  return document.querySelectorAll('.slidev-page').length
})
console.log('slides en el DOM:', total)

// Comprobar que el contenido nuevo esta presente
const pruebas = [
  [2, 'El problema que SIPAT ataca'],
  [2, '28.918,5 km'],
  [5, 'Los dos productos que ve el usuario'],
  [20, '133 puntos negros'],
  [27, 'Cuatro preguntas, cuatro m'],
  [28, 'NO COMO CAPA COMPLETA'],
  [31, 'GroupKFold por corredor'],
  [51, '30 de 30'],
]
for (const [n, texto] of pruebas) {
  await p.goto(`http://localhost:5173/${n}`, { waitUntil: 'load' })
  await p.waitForTimeout(1400)
  const t = await p.evaluate(() => {
    let best = null, ba = -1
    for (const el of document.querySelectorAll('.slidev-page')) {
      const r = el.getBoundingClientRect()
      const w = Math.min(r.right, innerWidth) - Math.max(r.left, 0)
      const h = Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)
      const a = (w > 0 && h > 0) ? w * h : 0
      if (a > ba) { ba = a; best = el }
    }
    return (best?.innerText || '').replace(/\s+/g, ' ')
  })
  console.log(`  [${n}] ${t.includes(texto) ? 'OK  ' : 'FALTA'} ${texto}`)
}
await b.close()