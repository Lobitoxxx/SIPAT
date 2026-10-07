<script setup>
import { ref, onMounted, watch, computed } from 'vue'

const props = defineProps({
  value: { type: [Number, String], default: 0 },
  label: { type: String, required: true },
  suffix: { type: String, default: '' },
  prefix: { type: String, default: '' },
  decimals: { type: Number, default: 0 },
  tone: { type: String, default: 'indigo' }, // indigo | green | amber | red | slate
  hint: { type: String, default: '' },
  duration: { type: Number, default: 1100 },
})

const shown = ref(0)
const numeric = computed(() => {
  const n = typeof props.value === 'number' ? props.value : parseFloat(String(props.value).replace(',', '.'))
  return Number.isFinite(n) ? n : 0
})

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

let raf = null
function run() {
  const target = numeric.value
  const start = performance.now()
  cancelAnimationFrame(raf)
  const tick = (now) => {
    const p = Math.min(1, (now - start) / props.duration)
    shown.value = target * easeOutCubic(p)
    if (p < 1) raf = requestAnimationFrame(tick)
    else shown.value = target
  }
  raf = requestAnimationFrame(tick)
}

onMounted(run)
watch(numeric, run)
</script>

<template>
  <div class="kpi" :class="`kpi--${tone}`">
    <div class="kpi__value">
      <span v-if="prefix" class="kpi__affix">{{ prefix }}</span>
      <span class="kpi__num">{{ shown.toFixed(decimals) }}</span>
      <span v-if="suffix" class="kpi__affix">{{ suffix }}</span>
    </div>
    <div class="kpi__label">{{ label }}</div>
    <div v-if="hint" class="kpi__hint">{{ hint }}</div>
  </div>
</template>

<style scoped>
.kpi {
  position: relative;
  border-radius: 13px;
  padding: 14px 16px 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, .05);
  overflow: hidden;
  transition: transform .22s ease, box-shadow .22s ease;
}
.kpi::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--kpi-accent, #6366f1);
}
.kpi:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px -8px rgba(15, 23, 42, .18);
}
.kpi__value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.05;
}
.kpi__num {
  font-size: 1.75rem;
  font-variant-numeric: tabular-nums;
  color: var(--kpi-accent, #4f46e5);
}
.kpi__affix { font-size: .95rem; color: #64748b; font-weight: 600; }
.kpi__label {
  margin-top: 5px;
  font-size: .83rem;
  font-weight: 600;
  color: #334155;
  line-height: 1.3;
}
.kpi__hint {
  margin-top: 3px;
  font-size: .72rem;
  color: #64748b;
  line-height: 1.35;
}

.kpi--indigo { --kpi-accent: #4f46e5; }
.kpi--green  { --kpi-accent: #059669; }
.kpi--amber  { --kpi-accent: #d97706; }
.kpi--red    { --kpi-accent: #dc2626; }
.kpi--slate  { --kpi-accent: #475569; }
</style>
