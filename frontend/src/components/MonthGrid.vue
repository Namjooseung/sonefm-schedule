<script setup>
// 한 달 = 참고 줄(직전 달 마지막 주) + 그 달 소속 주들.
import WeekRow from './WeekRow.vue'

defineProps({
  data: { type: Object, required: true },
  today: { type: String, required: true },
  selected: { type: String, default: '' },
})
const emit = defineEmits(['goto-month', 'select'])
</script>

<template>
  <div class="month">
    <WeekRow
      :week="data.reference_week" :cells="data.cells" :hours="data.hours" :today="today"
      @goto-month="(m) => emit('goto-month', m)"
    />
    <WeekRow
      v-for="w in data.weeks" :key="w.monday" :week="w" :cells="data.cells" :hours="data.hours"
      :today="today" :selected="selected" @select="(k) => emit('select', k)"
    />
  </div>
</template>

<style scoped>
.month { display: grid; gap: var(--space-150); }
</style>
