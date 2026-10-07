<script setup>
import { ref, onMounted } from 'vue'

// Pesos reales de SIPAT-ETL (config/settings.yaml + quality_rules.yaml)
const dims = [
  { key: 'completitud',  label: 'Completitud',  weight: 0.22, score: 99.4, note: 'nulos por columna' },
  { key: 'validez',      label: 'Validez',      weight: 0.22, score: 97.8, note: 'rangos y patrones' },
  { key: 'integridad',   label: 'Integridad',   weight: 0.18, score: 100,  note: 'claves foráneas' },
  { key: 'unicidad',     label: 'Unicidad',     weight: 0.15, score: 100,  note: 'duplicados' },
  { key: 'consistencia', label: 'Consistencia', weight: 0.15, score: 96.9, note: 'crosstab' },
  { key: 'frescura',     label: 'Frescura',     weight: 0.08, score: 100,  note: 'antigüedad' },
]

const bars = ref(dims.map(() => 0))
onMounted(() => {
  dims.forEach((_, i) => {
    setTimeout(() => { bars.value[i] = dims[i].score }, 120 + i * 130)
  })
})

function tone(score) {
  if (score >= 97) return 'ok'
  if (score >= 90) return 'warn'
  return 'bad'
}
</script>

<template>
  <div class="dqs">
    <div class="dqs__head">
      <div>
        <div class="dqs__title">Data Quality Score ponderado</div>
        <div class="dqs__sub">DQS = Σ (dimensión × peso) · pesos en <code>config/settings.yaml</code></div>
      </div>
      <div class="dqs__total">92.07<span>/100</span></div>
    </div>

    <div class="dqs__rows">
      <div v-for="(d, i) in dims" :key="d.key" class="dqs__row">
        <div class="dqs__meta">
          <span class="dqs__name">{{ d.label }}</span>
          <span class="dqs__note">{{ d.note }}</span>
        </div>
        <div class="dqs__weight">×{{ d.weight.toFixed(2) }}</div>
        <div class="dqs__track">
          <div
            class="dqs__fill"
            :class="`dqs__fill--${tone(d.score)}`"
            :style="{ width: bars[i] + '%' }"
          />
        </div>
        <div class="dqs__score">{{ d.score.toFixed(1) }}</div>
      </div>
    </div>

    <div class="dqs__foot">
      <span class="dqs__gate">Gate: <code>min_quality_score: 90</code></span>
      <span class="dqs__res">✅ PASSED · 0 críticas · 0 cuarentena</span>
    </div>
  </div>
</template>

<style scoped>
.dqs {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(15,23,42,.05);
}
.dqs__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.dqs__title { font-weight: 700; color: #0f172a; font-size: 1.02rem; }
.dqs__sub { font-size: .76rem; color: #64748b; margin-top: 2px; }
.dqs__sub code, .dqs__gate code {
  background: #eef2ff;
  color: #4338ca;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: .72rem;
}
.dqs__total {
  font-size: 1.7rem;
  font-weight: 700;
  color: #059669;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.dqs__total span { font-size: .82rem; color: #94a3b8; font-weight: 600; }

.dqs__rows { display: flex; flex-direction: column; gap: 7px; }
.dqs__row {
  display: grid;
  grid-template-columns: 132px 46px 1fr 46px;
  align-items: center;
  gap: 10px;
}
.dqs__meta { display: flex; flex-direction: column; line-height: 1.15; }
.dqs__name { font-size: .82rem; font-weight: 600; color: #1e293b; }
.dqs__note { font-size: .66rem; color: #94a3b8; }
.dqs__weight {
  font-size: .74rem;
  color: #6366f1;
  font-weight: 700;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.dqs__track {
  height: 9px;
  border-radius: 999px;
  background: #f1f5f9;
  overflow: hidden;
}
.dqs__fill {
  height: 100%;
  border-radius: 999px;
  transition: width 900ms cubic-bezier(.4,0,.2,1);
}
.dqs__fill--ok { background: linear-gradient(90deg, #10b981, #059669); }
.dqs__fill--warn { background: linear-gradient(90deg, #fbbf24, #d97706); }
.dqs__fill--bad { background: linear-gradient(90deg, #f87171, #dc2626); }
.dqs__score {
  font-size: .78rem;
  font-weight: 700;
  color: #334155;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.dqs__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding-top: 11px;
  border-top: 1px dashed #e2e8f0;
  font-size: .76rem;
}
.dqs__gate { color: #475569; }
.dqs__res { color: #047857; font-weight: 600; }
</style>
