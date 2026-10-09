// Quita el BOM UTF-8 de los ficheros de texto del deck.
// PowerShell `Set-Content -Encoding UTF8` escribe BOM, y un BOM antes del `---`
// de apertura hace que Slidev no reconozca el headmatter (cae al theme por defecto).
// Uso: node tools/strip_bom.mjs [--write]
import { readFileSync, writeFileSync, readdirSync } from 'node:fs'

const APPLY = process.argv.includes('--write')
const files = [
  'slides.md', 'README.md', 'style.css', 'docs/guion-15min.md',
  ...readdirSync('parts').map((f) => `parts/${f}`),
  ...readdirSync('components').map((f) => `components/${f}`),
]

let n = 0
for (const f of files) {
  const buf = readFileSync(f)
  if (!(buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf)) continue
  if (APPLY) writeFileSync(f, buf.slice(3))
  console.log(`${APPLY ? 'limpiado' : 'con BOM '}  ${f}`)
  n++
}
console.log(n === 0 ? 'ningun fichero con BOM' : `\n${n} fichero(s) ${APPLY ? 'limpiados' : 'pendientes'} (usa --write para aplicar)`)