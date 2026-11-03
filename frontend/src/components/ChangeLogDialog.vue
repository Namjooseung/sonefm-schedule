<script setup>
// 변경 기록: 언제, 무엇을, 어떻게 바꿨는지 (최근 200건).
import { onMounted, ref } from 'vue'
import * as api from '../api.js'
import BaseDialog from './BaseDialog.vue'

const emit = defineEmits(['close'])
const items = ref(null)
const error = ref('')

const ENTITY = { cell: '칸', month: '월', program: '프로그램', undo: '되돌리기' }

function when(iso) {
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function describe(it) {
  if (it.note) return it.note
  if (it.entity === 'program') return `프로그램 ${it.action}`
  return it.action
}

onMounted(async () => {
  const r = await api.listChangeLog(200)
  if (r.ok) items.value = r.items
  else error.value = r.errors[0]
})
</script>

<template>
  <BaseDialog title="변경 기록" wide @close="emit('close')">
    <p v-if="error" class="callout callout-danger">{{ error }}</p>
    <p v-else-if="!items" class="muted">불러오는 중입니다…</p>
    <p v-else-if="!items.length" class="muted">아직 기록이 없습니다.</p>
    <div v-else class="wrap">
      <table>
        <thead><tr><th>시각</th><th>구분</th><th>동작</th><th>내용</th></tr></thead>
        <tbody>
          <tr v-for="(it, i) in items" :key="i">
            <td class="nowrap">{{ when(it.at) }}</td>
            <td class="nowrap">{{ ENTITY[it.entity] || it.entity }}</td>
            <td class="nowrap">{{ it.action }}</td>
            <td>{{ describe(it) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <template #footer><button class="btn" @click="emit('close')">닫기</button></template>
  </BaseDialog>
</template>

<style scoped>
.wrap { max-height: 60vh; overflow: auto; }
table { border-collapse: collapse; width: 100%; font-size: var(--text-050); line-height: var(--leading-050); }
th { text-align: left; font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100); position: sticky; top: 0; background: var(--color-background-overlay-100); }
th, td { padding: var(--space-075) var(--space-100); border-bottom: 1px solid var(--color-border-normal); vertical-align: top; }
.nowrap { white-space: nowrap; }
</style>
