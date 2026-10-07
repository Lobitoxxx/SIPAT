<script setup>
defineProps({
  capas: { type: Array, required: true },
  // capa: string, items: [{ name, note, tone? }]
})
</script>

<template>
  <div class="stack">
    <div v-for="(c, i) in capas" :key="c.capa" class="stack__row">
      <div class="stack__label">
        <span class="stack__idx">{{ String(i + 1).padStart(2, '0') }}</span>
        {{ c.capa }}
      </div>
      <div class="stack__items">
        <div
          v-for="it in c.items"
          :key="it.name"
          class="stack__item"
          :class="it.tone ? `stack__item--${it.tone}` : ''"
        >
          <div class="stack__name">{{ it.name }}</div>
          <div v-if="it.note" class="stack__note">{{ it.note }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stack {
  display: flex;
  flex-direction: column;
  gap: 9px;
  width: 100%;
}
.stack__row {
  display: grid;
  grid-template-columns: 132px 1fr;
  gap: 14px;
  align-items: stretch;
}
.stack__label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: .8rem;
  font-weight: 700;
  color: #334155;
  text-transform: uppercase;
  letter-spacing: .03em;
  border-right: 2px solid #e0e7ff;
  padding-right: 12px;
}
.stack__idx {
  font-size: .68rem;
  color: #6366f1;
  font-variant-numeric: tabular-nums;
}
.stack__items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(122px, 1fr));
  gap: 8px;
}
.stack__item {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 9px;
  padding: 7px 10px;
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}
.stack__item:hover {
  transform: translateY(-2px);
  border-color: #c7d2fe;
  box-shadow: 0 6px 14px -6px rgba(79,70,229,.28);
}
.stack__name { font-size: .79rem; font-weight: 600; color: #1e293b; }
.stack__note { font-size: .67rem; color: #64748b; margin-top: 1px; line-height: 1.3; }

.stack__item--python { border-left: 3px solid #4f46e5; }
.stack__item--web    { border-left: 3px solid #0ea5e9; }
.stack__item--data   { border-left: 3px solid #10b981; }
.stack__item--infra  { border-left: 3px solid #f59e0b; }
.stack__item--stats  { border-left: 3px solid #a855f7; }
.stack__item--ml     { border-left: 3px solid #ec4899; }
</style>
