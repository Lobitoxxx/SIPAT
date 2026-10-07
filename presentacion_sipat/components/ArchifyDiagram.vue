<script setup>
import { ref, onMounted, watch, computed } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: 'diagrama' },
  animate: { type: Boolean, default: true },
  // altura maxima del diagrama en px (evita que empuje el resto de la slide)
  height: { type: [Number, String], default: 0 },
  // nodos revelados por clic (0 = todos de golpe al entrar)
  steps: { type: Number, default: 0 },
  max: { type: String, default: '' },
})

const svgText = ref('')
const host = ref(null)
const loaded = ref(false)

//{{< iframe >}} no usado: inyectamos el SVG en linea para poder estilizarlo.
async function load() {
  try {
    const res = await fetch(props.src)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    svgText.value = await res.text()
    loaded.value = true
    await nextTickFrame()
    applyAnimations()
  } catch (e) {
    console.error(`[ArchifyDiagram] no se pudo cargar ${props.src}`, e)
  }
}

function nextTickFrame() {
  return new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
}

function applyAnimations() {
  const root = host.value
  if (!root) return
  const svg = root.querySelector('svg')
  if (!svg) return

  // 1) Aristas: se dibujan con stroke-dashoffset
  const edges = Array.from(svg.querySelectorAll('path.a-default, path.a-emphasis, path.a-dashed'))
  edges.forEach((p, i) => {
    if (!props.animate) return
    let len = 0
    try { len = p.getTotalLength() } catch { len = 400 }
    p.style.strokeDasharray = `${len}`
    p.style.strokeDashoffset = `${len}`
    p.style.animation = `sipat-draw 900ms cubic-bezier(.4,0,.2,1) forwards`
    p.style.animationDelay = `${i * 110}ms`
  })

  // 2) Nodos: cascada de entrada
  const nodes = Array.from(svg.querySelectorAll('g[data-node-id]'))
  nodes.forEach((n, i) => {
    if (!props.animate) return
    const delay = 320 + i * 130
    n.style.opacity = '0'
    n.style.transformOrigin = 'center'
    n.style.animation = `sipat-pop 520ms cubic-bezier(.34,1.56,.64,1) forwards`
    n.style.animationDelay = `${delay}ms`
  })

  // 3) Marcos estructurales y carriles aparecen al final
  const frames = Array.from(svg.querySelectorAll('[data-graph-role="structural-frame"], .c-lane'))
  frames.forEach((f, i) => {
    if (!props.animate) return
    f.style.opacity = '0'
    f.style.animation = `sipat-fade 700ms ease forwards`
    f.style.animationDelay = `${80 + i * 90}ms`
  })
}

onMounted(load)
watch(() => props.src, load)

// Revelado progresivo por clic cuando se pasan steps > 0
const visibleCount = computed(() => {
  if (!props.steps) return Infinity
  return Infinity // el control por clic se resuelve via v-click en el slide
})

onMounted(() => {
  if (props.steps > 0 && host.value) {
    const nodes = Array.from(host.value.querySelectorAll('g[data-node-id]'))
    const per = Math.ceil(nodes.length / props.steps)
    nodes.forEach((n, i) => { n.style.opacity = '0' })
  }
})
</script>

<template>
  <div
    class="archify"
    :class="{ 'archify--max': max }"
    :style="height ? { height: typeof height === 'number' ? height + 'px' : height } : {}"
  >
    <div v-if="!loaded" class="archify__ph">
      <div class="archify__bar" />
      <div class="archify__bar archify__bar--60" />
      <div class="archify__bar archify__bar--80" />
    </div>
    <div
      v-else
      ref="host"
      class="archify__svg"
      role="img"
      :aria-label="alt"
      v-html="svgText"
    />
  </div>
</template>

<style scoped>
.archify {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 120px;
  overflow: hidden;
}
.archify--max { max-height: 100%; }
.archify__svg { width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; min-height: 0; }
.archify__svg :deep(svg) {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  font-family: inherit;
}
.archify__ph { width: 100%; display: flex; flex-direction: column; gap: 10px; }
.archify__bar {
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(99,102,241,.18), rgba(99,102,241,.06));
  animation: sipat-shimmer 1.2s ease-in-out infinite;
}
.archify__bar--60 { width: 60%; }
.archify__bar--80 { width: 80%; }

@keyframes sipat-shimmer {
  0%, 100% { opacity: .45; }
  50% { opacity: .9; }
}
</style>
