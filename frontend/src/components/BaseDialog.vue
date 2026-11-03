<script setup>
// 공통 대화상자: 검정 32% 스크림 + 흰 패널. Esc 또는 바깥 클릭으로 닫힌다.
import { onBeforeUnmount, onMounted } from 'vue'

defineProps({
  title: { type: String, required: true },
  wide: { type: Boolean, default: false },   // 800px (목록용)
})
const emit = defineEmits(['close'])

function onKey(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="scrim" @mousedown.self="emit('close')">
    <div class="panel" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title">
      <header><h2>{{ title }}</h2></header>
      <div class="body"><slot /></div>
      <footer><slot name="footer" /></footer>
    </div>
  </div>
</template>

<style scoped>
.scrim {
  position: fixed; inset: 0; z-index: 100; background: var(--scrim);
  display: grid; place-items: center;
}
.panel.wide { width: min(800px, calc(100vw - 4rem)); }
.panel {
  width: min(500px, calc(100vw - 4rem)); max-height: 80vh; overflow: auto;
  background: var(--color-background-overlay-100); border-radius: var(--radius-300); box-shadow: var(--shadow-xl);
}
header { height: 56px; padding: 0 var(--space-300); display: flex; align-items: center; }
h2 { font-size: var(--text-200); line-height: var(--leading-200); font-weight: var(--font-weight-bold); }
.body { padding: 0 var(--space-300); display: grid; gap: var(--space-150); }
footer { padding: var(--space-200) var(--space-300); display: flex; justify-content: flex-end; gap: var(--space-100); }
</style>
