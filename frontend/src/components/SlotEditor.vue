<script setup>
// 편성 자리 표: (요일, 시각, 본방/재방, 적용 기간).
// "개편"은 기존 자리를 바꾸지 않고 '그 전날까지'로 닫은 뒤 같은 자리를 새 적용일로 하나 더 만든다.
// → 회차가 끊기지 않고 개편 이력이 남는다. 새로 생긴 줄에서 요일·시각을 바꾸면 된다.
import { ref } from 'vue'

const props = defineProps({
  slots: { type: Array, required: true },       // 부모의 draft.slots (직접 수정)
  choices: { type: Object, required: true },
  today: { type: String, required: true },
  defaultFrom: { type: String, default: '' },
})

const reformIndex = ref(-1)
const reformDate = ref('')
const reformError = ref('')

function addSlot() {
  props.slots.push({ id: null, weekday: 0, hour: 10, role: '본방',
    valid_from: props.defaultFrom || props.today, valid_to: null })
}

function removeSlot(i) {
  props.slots.splice(i, 1)
  if (reformIndex.value === i) reformIndex.value = -1
}

function dayBefore(iso) {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() - 1)
  return d.toISOString().slice(0, 10)
}

function startReform(i) {
  reformIndex.value = i
  reformDate.value = props.today
  reformError.value = ''
}

function confirmReform() {
  const s = props.slots[reformIndex.value]
  const d = reformDate.value
  if (!d) { reformError.value = '새 편성이 시작되는 날짜를 골라 주세요.'; return }
  if (d <= s.valid_from) { reformError.value = '기존 자리의 적용 시작일보다 뒤 날짜여야 합니다.'; return }
  if (s.valid_to && d > s.valid_to) { reformError.value = '기존 자리가 이미 그 전에 끝났습니다.'; return }
  const next = { id: null, weekday: s.weekday, hour: s.hour, role: s.role, valid_from: d, valid_to: s.valid_to }
  s.valid_to = dayBefore(d)
  props.slots.splice(reformIndex.value + 1, 0, next)
  reformIndex.value = -1
}

const isPast = (s) => s.valid_to && s.valid_to < props.today
</script>

<template>
  <div class="slots">
    <table v-if="slots.length">
      <thead>
        <tr><th>요일</th><th>시각</th><th>구분</th><th>적용 시작일</th><th>적용 종료일</th><th></th></tr>
      </thead>
      <tbody>
        <template v-for="(s, i) in slots" :key="s.id || `new-${i}`">
          <tr :class="{ past: isPast(s), fresh: !s.id }">
            <td>
              <select v-model.number="s.weekday" class="select select-sm" aria-label="요일">
                <option v-for="(w, wi) in choices.weekdays" :key="w" :value="wi">{{ w }}</option>
              </select>
            </td>
            <td>
              <select v-model.number="s.hour" class="select select-sm" aria-label="시각">
                <option v-for="h in choices.hours" :key="h" :value="h">{{ String(h).padStart(2, '0') }}시</option>
              </select>
            </td>
            <td>
              <select v-model="s.role" class="select select-sm" aria-label="본방 재방">
                <option v-for="r in choices.roles" :key="r" :value="r">{{ r }}</option>
              </select>
            </td>
            <td><input v-model="s.valid_from" type="date" class="input input-sm" aria-label="적용 시작일" /></td>
            <td>
              <input :value="s.valid_to || ''" type="date" class="input input-sm" aria-label="적용 종료일"
                     @input="s.valid_to = $event.target.value || null" />
            </td>
            <td class="actions">
              <button v-if="!isPast(s)" type="button" class="btn btn-ghost btn-sm" @click="startReform(i)">개편</button>
              <button type="button" class="btn btn-ghost-danger btn-sm" @click="removeSlot(i)">삭제</button>
            </td>
          </tr>
          <tr v-if="reformIndex === i" class="reform">
            <td colspan="6">
              <div class="reform-box">
                <span>새 편성 시작일</span>
                <input v-model="reformDate" type="date" class="input input-sm" aria-label="새 편성 시작일" />
                <button type="button" class="btn btn-primary btn-sm" @click="confirmReform">개편 줄 만들기</button>
                <button type="button" class="btn btn-sm" @click="reformIndex = -1">취소</button>
                <span class="muted small">이 자리는 전날까지로 닫히고, 같은 자리가 새 줄로 추가됩니다. 새 줄에서 요일·시각을 바꿔 주세요.</span>
              </div>
              <p v-if="reformError" class="err small">{{ reformError }}</p>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
    <p v-else class="muted small">편성 자리가 없습니다.</p>
    <div><button type="button" class="btn btn-outline btn-sm" @click="addSlot">자리 추가</button></div>
  </div>
</template>

<style scoped>
.slots { display: grid; gap: var(--space-100); }
table { border-collapse: collapse; width: 100%; }
th {
  text-align: left; font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100);
  font-size: var(--text-050); line-height: var(--leading-050); padding: 0 var(--space-050) var(--space-050);
}
td { padding: var(--space-050); border-top: 1px solid var(--color-border-normal); vertical-align: middle; }
td .select, td .input { width: 100%; }
tr.past td { opacity: 0.55; }
tr.fresh td:first-child { box-shadow: inset 2px 0 0 var(--color-border-primary); }
.actions { white-space: nowrap; text-align: right; width: 1%; }
.reform td { border-top: 0; padding-top: 0; }
.reform-box {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-100);
  padding: var(--space-100) var(--space-150); border-radius: var(--radius-300);
  background: var(--color-background-secondary-100); border: 1px solid var(--color-border-normal);
}
.err { color: var(--color-foreground-danger-100); margin: var(--space-050) 0 0; }
</style>
