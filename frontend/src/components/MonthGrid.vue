<script setup>
// 한 달 = 참고 줄(직전 달 마지막 주) + 그 달 소속 주들.
import WeekRow from './WeekRow.vue'

defineProps({
  data: { type: Object, required: true },
  today: { type: String, required: true },
  selected: { type: String, default: '' },
  folded: { type: Object, default: () => ({}) },   // { 월요일날짜: true }
  refOpen: { type: Boolean, default: false },      // 참고 줄(전달 마지막 주)은 기본 접힘
})
const emit = defineEmits(['goto-month', 'select', 'toggle', 'toggle-ref', 'band'])
</script>

<template>
  <div class="month">
    <WeekRow
      :week="data.reference_week" :cells="data.cells" :hours="data.hours" :today="today"
      :selected="selected" :folded="!refOpen"
      @goto-month="(m) => emit('goto-month', m)" @toggle="emit('toggle-ref')"
    />
    <WeekRow
      v-for="w in data.weeks" :key="w.monday" :week="w" :cells="data.cells" :hours="data.hours"
      :today="today" :selected="selected" :folded="!!folded[w.monday]"
      @select="(k, rect) => emit('select', k, rect)" @toggle="emit('toggle', w.monday)" @band="(b) => emit('band', b)"
    />
  </div>
</template>

<style scoped>
.month { display: grid; gap: var(--space-150); }
</style>
