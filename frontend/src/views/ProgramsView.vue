<script setup>
// 프로그램 화면: 왼쪽 목록(검색·종영 포함) + 오른쪽 상세 편집.
import { computed, onActivated, onDeactivated, onMounted, ref } from 'vue'
import * as api from '../api.js'
import ProgramForm from '../components/ProgramForm.vue'
import BaseDialog from '../components/BaseDialog.vue'

const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10)

const choices = ref(null)
const items = ref([])
const query = ref('')
const includeEnded = ref(false)
const loadError = ref('')

const selectedId = ref(null)
const draft = ref(null)
const original = ref('')          // 마지막으로 불러온/저장한 상태 (변경 여부 비교용)
const errors = ref([])
const notice = ref('')
const busy = ref(false)
const pending = ref(null)          // 저장 안 한 변경이 있을 때 이동하려던 대상

const dirty = computed(() => draft.value !== null && snapshot(draft.value) !== original.value)

function blank() {
  return {
    id: null, name: '', category: '교양', is_listener_participation: false, producer_type: '자체',
    cycle_type: 'weekly', cycle_anchor_date: '', monthly_nth: null, offweek_policy: '',
    start_episode: 1, start_date: today, end_date: null, host: '', cohort: '', memo: '',
    aliases: [], slots: [], is_special: false, show_episode: true,
  }
}

function fromServer(p) {
  return {
    ...blank(), ...p,
    cycle_anchor_date: p.cycle_anchor_date || '', offweek_policy: p.offweek_policy || '',
    start_date: p.start_date || '', host: p.host || '', cohort: p.cohort || '', memo: p.memo || '',
    aliases: [...(p.aliases || [])], slots: (p.slots || []).map((s) => ({ ...s })),
  }
}

function snapshot(d) { return JSON.stringify(d) }

function setDraft(d) {
  draft.value = d
  original.value = snapshot(d)
  errors.value = []
}

async function loadList() {
  const r = await api.listPrograms(query.value, includeEnded.value)
  if (!r.ok) { loadError.value = r.errors[0]; return }
  loadError.value = ''
  items.value = r.items
}

let searchTimer = 0
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadList, 200)
}

// 저장 안 한 변경이 있으면 바로 이동하지 않고 확인 줄을 띄운다
function guard(target) {
  if (dirty.value) { pending.value = target; return false }
  return true
}

async function open(id) {
  if (id === selectedId.value && draft.value) return
  if (!guard({ kind: 'open', id })) return
  const r = await api.getProgram(id)
  if (!r.ok) { errors.value = r.errors; return }
  selectedId.value = id
  setDraft(fromServer(r.program))
  notice.value = ''
}

function startNew() {
  if (!guard({ kind: 'new' })) return
  selectedId.value = null
  setDraft(blank())
  notice.value = ''
}

async function discardAndGo() {
  const target = pending.value
  pending.value = null
  original.value = snapshot(draft.value)   // 변경 버림
  if (target.kind === 'open') { selectedId.value = null; await open(target.id) } else startNew()
}

function revert() {
  if (!draft.value.id) { draft.value = null; selectedId.value = null; return }
  draft.value = JSON.parse(original.value)
  errors.value = []
}

let noticeTimer = 0
function flash(msg) {
  clearTimeout(noticeTimer)
  notice.value = msg
  noticeTimer = setTimeout(() => { notice.value = '' }, 3000)
}

async function apply(promise, msg) {
  busy.value = true
  errors.value = []
  const r = await promise
  busy.value = false
  if (!r.ok) { errors.value = r.errors; return null }
  await loadList()
  flash(msg)
  return r
}

async function save() {
  const payload = { ...draft.value, offweek_policy: draft.value.offweek_policy || null }
  const r = await apply(api.saveProgram(payload), '저장했습니다.')
  if (r) { selectedId.value = r.program.id; setDraft(fromServer(r.program)) }
}

async function end(endDate) {
  const r = await apply(api.endProgram(draft.value.id, endDate), '종영 처리했습니다.')
  if (r) setDraft(fromServer(r.program))
}

async function resume() {
  const r = await apply(api.resumeProgram(draft.value.id), '종영을 취소했습니다. 필요하면 편성 자리를 새로 추가해 주세요.')
  if (r) setDraft(fromServer(r.program))
}

async function remove() {
  const r = await apply(api.deleteProgram(draft.value.id), '삭제했습니다.')
  if (r) { draft.value = null; selectedId.value = null }
}

// ── 특집 빠른 등록 ──
const specialOpen = ref(false)
const special = ref({ name: '', category: '오락', is_listener_participation: false })
const specialErrors = ref([])

function openSpecial() {
  special.value = { name: '', category: '오락', is_listener_participation: false }
  specialErrors.value = []
  specialOpen.value = true
}

async function saveSpecial() {
  const r = await api.createSpecial(special.value)
  if (!r.ok) { specialErrors.value = r.errors; return }
  specialOpen.value = false
  await loadList()
  flash('특집을 등록했습니다.')
  if (guard({ kind: 'open', id: r.program.id })) { selectedId.value = r.program.id; setDraft(fromServer(r.program)) }
}

// Ctrl+F: 목록 검색 칸으로
const searchInput = ref(null)
function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'f') {
    e.preventDefault()
    searchInput.value?.focus()
    searchInput.value?.select()
  }
}
function clearQuery() {
  query.value = ''
  loadList()
}
onActivated(() => window.addEventListener('keydown', onKey))
onDeactivated(() => window.removeEventListener('keydown', onKey))

onMounted(async () => {
  const c = await api.programChoices()
  if (c.ok) choices.value = c
  else loadError.value = c.errors[0]
  await loadList()
})
</script>

<template>
  <div class="page">
    <aside class="list card">
      <div class="list-head">
        <h1>프로그램</h1>
        <div class="row">
          <button class="btn btn-primary btn-sm" @click="startNew">새 프로그램</button>
          <button class="btn btn-outline btn-sm" @click="openSpecial">특집 등록</button>
        </div>
        <input ref="searchInput" v-model="query" class="input" placeholder="이름·별칭 검색 (Ctrl+F)" @input="onSearch" @keydown.esc="clearQuery" />
        <label class="check small"><input v-model="includeEnded" type="checkbox" @change="loadList" /> 종영 포함</label>
      </div>
      <p v-if="loadError" class="callout callout-danger small">{{ loadError }}</p>
      <ul class="items">
        <li v-for="p in items" :key="p.id">
          <button class="item" :aria-current="p.id === selectedId ? 'true' : undefined" @click="open(p.id)">
            <span class="name">{{ p.name }}</span>
            <span class="meta">
              <span class="badge" :class="p.category === '교양' ? 'badge-edu' : 'badge-ent'">{{ p.category }}</span>
              <span v-if="p.is_special" class="badge badge-special">특집</span>
              <span v-else class="badge">{{ p.cycle_label }}</span>
              <span v-if="p.is_ended" class="badge badge-danger">종영</span>
              <span v-else-if="p.end_date" class="badge badge-danger">{{ p.end_date }} 종영 예정</span>
              <span v-if="!p.is_special" class="muted small">자리 {{ p.slot_count }}</span>
            </span>
          </button>
        </li>
        <li v-if="!items.length && !loadError" class="empty muted small">
          {{ query ? '검색 결과가 없습니다.' : '등록된 프로그램이 없습니다. "새 프로그램"으로 등록해 주세요.' }}
        </li>
      </ul>
    </aside>

    <section class="detail card">
      <ProgramForm
        v-if="draft && choices" :draft="draft" :choices="choices" :today="today" :dirty="dirty" :busy="busy"
        @save="save" @revert="revert" @end="end" @resume="resume" @delete="remove"
      >
        <template #messages>
          <div v-if="pending" class="callout callout-warning confirm-bar">
            <span>저장하지 않은 변경이 있습니다.</span>
            <button class="btn btn-sm" @click="discardAndGo">저장하지 않고 이동</button>
            <button class="btn btn-sm" @click="pending = null">계속 편집</button>
          </div>
          <div v-if="errors.length" class="callout callout-danger" role="alert">
            <ul><li v-for="e in errors" :key="e">{{ e }}</li></ul>
          </div>
          <div v-if="notice" class="callout callout-success" role="status">{{ notice }}</div>
        </template>
      </ProgramForm>
      <div v-else class="empty-detail muted">
        <p v-if="notice" class="callout callout-success">{{ notice }}</p>
        <p>왼쪽 목록에서 프로그램을 고르거나 "새 프로그램"을 눌러 주세요.</p>
      </div>
    </section>

    <BaseDialog v-if="specialOpen" title="특집 등록" @close="specialOpen = false">
      <p class="muted small">특집은 편성 자리 없이 편성표의 칸에 직접 넣는 단발 프로그램입니다. 나중에 정규 프로그램으로 바꿀 수 있습니다.</p>
      <div v-if="specialErrors.length" class="callout callout-danger small">
        <ul><li v-for="e in specialErrors" :key="e">{{ e }}</li></ul>
      </div>
      <label class="field">
        <span>특집 이름</span>
        <input v-model="special.name" class="input" placeholder="예: 가을 음악회 실황 특집" @keydown.enter="saveSpecial" />
      </label>
      <div class="field">
        <span>분야</span>
        <div class="row">
          <label class="check"><input v-model="special.category" type="radio" value="교양" /> 교양</label>
          <label class="check"><input v-model="special.category" type="radio" value="오락" /> 오락</label>
        </div>
      </div>
      <label class="check"><input v-model="special.is_listener_participation" type="checkbox" /> 청취자 참여 프로그램</label>
      <template #footer>
        <button class="btn" @click="specialOpen = false">취소</button>
        <button class="btn btn-primary" @click="saveSpecial">등록</button>
      </template>
    </BaseDialog>
  </div>
</template>

<style scoped>
.page {
  display: grid; grid-template-columns: 320px 1fr; gap: var(--space-200);
  padding: var(--space-200); height: 100%; min-height: 0;
}
.list { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.list-head { display: grid; gap: var(--space-100); padding: var(--space-200); border-bottom: 1px solid var(--color-border-normal); }
h1 { font-size: var(--text-300); line-height: var(--leading-300); font-weight: var(--font-weight-bold); }
.row { display: flex; gap: var(--space-100); flex-wrap: wrap; }
.items { list-style: none; margin: 0; padding: var(--space-050); overflow: auto; flex: 1; }
.item {
  position: relative; display: grid; gap: var(--space-050); width: 100%; text-align: left;
  padding: var(--space-100) var(--space-150); border: 0; border-radius: var(--radius-300);
  background: transparent; cursor: pointer;
}
.item::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.item:hover::before { opacity: var(--overlay-hover-dense); }
.item[aria-current="true"] { background: var(--color-background-primary-100); }
.name { font-weight: var(--font-weight-medium); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { display: flex; gap: var(--space-050); align-items: center; flex-wrap: wrap; }
.empty { padding: var(--space-200); }
.detail { min-height: 0; overflow: hidden; }
.empty-detail { height: 100%; display: grid; place-content: center; gap: var(--space-150); text-align: center; }
.confirm-bar { display: flex; align-items: center; gap: var(--space-100); flex-wrap: wrap; }
.field { display: grid; gap: var(--space-050); }
.field > span { font-size: var(--text-050); line-height: var(--leading-050); font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100); }
</style>
