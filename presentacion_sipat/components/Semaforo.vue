<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 'bajo' | 'medio' | 'alto'
  nivel: { type: String, default: 'medio' },
  score: { type: String, default: '' },
  caption: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})

const idx = computed(() => ({ bajo: 0, medio: 1, alto: 2 }[props.nivel] ?? 1))
const label = computed(() => ['Bajo', 'Medio', 'Alto'][idx.value])
</script>

<template>
  <div class="sem" :class="[`sem--${nivel}`, { 'sem--compact': compact }]">
    <div class="sem__lights">
      <span class="sem__light sem__light--bajo" :class="{ 'is-on': idx >= 0 }" />
      <span class="sem__light sem__light--medio" :class="{ 'is-on': idx >= 1 }" />
      <span class="sem__light sem__light--alto" :class="{ 'is-on': idx >= 2 }" />
    </div>
    <div class="sem__body">
      <div class="sem__label">{{ label }}</div>
      <div v-if="score" class="sem__score">{{ score }}</div>
      <div v-if="caption" class="sem__caption">{{ caption }}</div>
    </div>
  </div>
</template>

<style scoped>
.sem {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px 10px 12px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15,23,42,.06);
}
.sem__lights { display: flex; gap: 5px; }
.sem__light {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #e2e8f0;
  transition: background .3s ease, box-shadow .3s ease;
}
.sem__light--bajo.is-on  { background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,.18); }
.sem__light--medio.is-on { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,.18); }
.sem__light--alto.is-on  { background: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,.18); }
.sem__label { font-weight: 700; font-size: 1.02rem; line-height: 1.1; }
.sem__score {
  font-size: .8rem;
  color: #475569;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.sem__caption { font-size: .7rem; color: #64748b; }

.sem--bajo  .sem__label { color: #15803d; }
.sem--medio .sem__label { color: #b45309; }
.sem--alto  .sem__label { color: #b91c1c; }
.sem--bajo  { border-color: #bbf7d0; background: #f0fdf4; }
.sem--medio { border-color: #fde68a; background: #fffbeb; }
.sem--alto  { border-color: #fecaca; background: #fef2f2; }
.sem--compact { padding: 6px 12px 6px 9px; }
.sem--compact .sem__light { width: 10px; height: 10px; }
.sem--compact .sem__label { font-size: .86rem; }
</style>
