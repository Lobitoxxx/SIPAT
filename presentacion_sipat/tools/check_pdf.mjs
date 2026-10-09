import { readFileSync } from 'node:fs'
import { inflateSync } from 'node:zlib'

const buf = readFileSync('sipat-presentacion.pdf')
let idx = 0
let all = ''
const m = Buffer.from('stream')
while (true) {
  const i = buf.indexOf(m, idx)
  if (i === -1) break
  let st = i + m.length
  if (buf[st] === 13) st++
  if (buf[st] === 10) st++
  const en = buf.indexOf(Buffer.from('endstream'), st)
  if (en === -1) break
  try { all += inflateSync(buf.slice(st, en)).toString('latin1') } catch {}
  idx = en + 9
}
const pages = (all.match(/\/Type\s*\/Page(?![s])/g) || []).length
const kb = (buf.length / 1024).toFixed(0)
const blank = kb < 200
console.log('cabecera :', buf.slice(0, 8).toString())
console.log('paginas  :', pages)
console.log('tamano   :', (buf.length / 1024 / 1024).toFixed(2), 'MB')
console.log(blank ? 'AVISO: demasiado pequeño, puede estar en blanco' : 'OK: tamaño coherente con contenido real')