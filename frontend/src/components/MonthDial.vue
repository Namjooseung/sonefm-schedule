<script setup>
// 월 이동: 연도 이동 + 12개월. 현재 달은 아래 막대로 표시하고, 확정·마감 달은 작은 글씨로 상태를 보여준다.
const props = defineProps({
  year: { type: Number, required: true },
  month: { type: Number, required: true },
  statuses: { type: Object, default: () => ({}) },   // { '2026-10': '확정', ... }
})
const emit = defineEmits(['select'])

const status = (m) => props.statuses[`${props.year}-${String(m).padStart(2, '0')}`]
</script>

<template>
  <div class="dial" role="tablist" aria-label="월 선택">
    <button class="year-btn" aria-label="이전 연도" @click="emit('select', year - 1, month)">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>
    <span class="year">{{ year }}년</span>
    <button class="year-btn" aria-label="다음 연도" @click="emit('select', year + 1, month)">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>
    <div class="months">
      <button
        v-for="m in 12" :key="m" class="m" role="tab"
        :aria-selected="m === month" :class="{ has: status(m) }"
        @click="emit('select', year, m)"
      >
        {{ m }}월<small v-if="status(m) && status(m) !== '작성중'">{{ status(m) }}</small>
      </button>
    </div>
  </div>
</template>

<style scoped>
.dial { display: flex; align-items: stretch; gap: var(--space-050); border-top: 1px solid var(--color-border-normal); }
.year { display: flex; align-items: center; font-weight: var(--font-weight-bold); padding: 0 var(--space-050); }
.year-btn {
  position: relative; display: grid; place-items: center; width: var(--control-sm); margin: auto 0; height: var(--control-sm);
  border: 0; border-radius: var(--radius-300); background: transparent; cursor: pointer; color: var(--color-foreground-normal-100);
}
.year-btn::before, .m::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.year-btn:hover::before, .m:hover::before { opacity: var(--overlay-hover); }
.months { flex: 1; display: grid; grid-template-columns: repeat(12, 1fr); margin-left: var(--space-150); }
.m {
  position: relative; height: var(--control-lg); border: 0; background: transparent; cursor: pointer;
  border-left: 1px solid var(--color-border-normal);
  font-weight: var(--font-weight-medium); color: var(--color-foreground-hint-100);
  display: flex; align-items: center; justify-content: center; gap: var(--space-050);
}
.m:first-child { border-left: 0; }
.m.has { color: var(--color-foreground-normal-100); }
.m small { font-size: var(--text-025); line-height: var(--leading-025); color: var(--color-foreground-hint-100); }
.m[aria-selected="true"] { color: var(--color-foreground-primary-200); }
.m[aria-selected="true"]::after {
  content: ""; position: absolute; left: var(--space-100); right: var(--space-100); bottom: 0; height: 3px;
  border-radius: var(--radius-pill) var(--radius-pill) 0 0; background: var(--color-background-primary-200);
}
</style>
