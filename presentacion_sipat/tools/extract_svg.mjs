// Extrae los diagramas de Archify a SVG autocontenidos.
//
// El SVG original depende de una hoja de estilos de ~186 KB que vive en el HTML
// del visor. Sin ella los elementos caen a `fill:black` y el diagrama es
// ilegible. Aqui se reconstruye un SVG autonomous:
//
//   1) se extrae el <svg> inline
//   2) se localiza el bloque de variables de tema LIGHT
//   3) se filtran del CSS solo las reglas que tocan las clases usadas en el SVG
//   4) se inyecta todo como <style> dentro del propio <svg>
//
// Uso: node tools/extract_svg.mjs
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..', '..')
const srcDir = resolve(repoRoot, 'docs', 'archify')
const outDir = resolve(here, '..', 'public', 'svg')

mkdirSync(outDir, { recursive: true })

const files = [
  ['sipat-architecture.html', 'arquitectura.svg'],
  ['sipat-dataflow.html', 'dataflow.svg'],
  ['sipat-sequence.html', 'secuencia.svg'],
  ['sipat-workflow.html', 'workflow.svg'],
]

/** Extrae el elemento <svg>...</svg> balanceado. */
function extractSvg(html) {
  const start = html.indexOf('<svg')
  if (start === -1) return null
  let depth = 0
  let end = -1
  const re = /<svg\b|<\/svg>/g
  re.lastIndex = start
  let m
  while ((m = re.exec(html))) {
    if (m[0] === '</svg>') {
      depth--
      if (depth === 0) { end = m.index + m[0].length; break }
    } else depth++
  }
  return end === -1 ? null : html.slice(start, end)
}

/** Bloque de variables del tema claro. */
function lightVars(css) {
  const m = css.match(/\[data-theme="light"\]\s*\{([\s\S]*?)\n\s{4}\}/)
  return m ? m[1].trim() : null
}

/** Reglas del CSS que mencionan alguna clase presente en el SVG. */
function relevantRules(css, classes) {
  const out = []
  const re = /([^{}]+)\{([^{}]*)\}/g
  let m
  while ((m = re.exec(css))) {
    const sel = m[1].trim()
    if (!sel || sel.startsWith('@') || sel.startsWith(':root')) continue
    if ([...classes].some((c) => sel.includes(`.${c}`))) {
      out.push(`${sel.replace(/\s+/g, ' ')} {${m[2]}}`)
    }
  }
  return out
}

for (const [src, out] of files) {
  const html = readFileSync(resolve(srcDir, src), 'utf8')
  let svg = extractSvg(html)
  if (!svg) {
    console.error(`[skip] ${src}: no se encontro <svg>`)
    continue
  }

  if (!/xmlns=/.test(svg)) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')

  const classes = new Set(
    [...svg.matchAll(/class="([^"]+)"/g)].flatMap((m) => m[1].split(/\s+/)).filter(Boolean)
  )

  const styles = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1])
  const css = styles[styles.length - 1] || ''
  const vars = lightVars(css)
  const rules = relevantRules(css, classes)

  const injected = `<style>
svg{${vars || ''}}
${rules.join('\n')}
</style>`

  // insertar justo despues de la etiqueta de apertura del <svg>
  const gt = svg.indexOf('>')
  svg = svg.slice(0, gt + 1) + injected + svg.slice(gt + 1)

  const vb = (svg.match(/viewBox="([^"]+)"/) || [, '?'])[1]
  writeFileSync(resolve(outDir, out), svg, 'utf8')
  console.log(
    `[ok] ${src} -> public/svg/${out}  viewBox ${vb}  ` +
    `clases ${classes.size}  reglas ${rules.length}  ${(svg.length / 1024).toFixed(1)} KB`
  )
}
