<script setup>
// 편성표 화면: 월 이동 + 버튼(첫 주 불러오기 / 월단위 생성) + 주 줄 그리드 + 오른쪽 패널.
// 칸을 누르면 칸 팝업, 고정 편성 띠를 누르면 날짜 고르기. Ctrl+Z로 이번 실행 중 작업을 되돌린다.
import { computed, nextTick, onActivated, onDeactivated, onMounted, onBeforeUnmount, ref } from 'vue'
import * as api from '../api.js'
import MonthDial from '../components/MonthDial.vue'
import MonthGrid from '../components/MonthGrid.vue'
import ValidationPanel from '../components/ValidationPanel.vue'
import BaseDialog from '../components/BaseDialog.vue'
import CellPopup from '../components/CellPopup.vue'
import ChangeLogDialog from '../components/ChangeLogDialog.vue'

const now = new Date()
const today = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)

const year = ref(now.getFullYear())
const month = ref(now.getMonth() + 1)
const data = ref(null)
const errors = ref([])
const notice = ref('')
const busy = ref(false)
const selected = ref('')
const statusDialog = ref(null)     // { action, title, text, reason }
const manualConfirm = ref(null)     // { scope, rows }
const panelOpen = ref(true)
const popup = ref(null)             // { key, rect }
const bandPick = ref(null)          // { hour, days, rect }
const canUndo = ref(false)
const logOpen = ref(false)

// 접힌 주 (이 PC에서만 기억, 월요일 날짜 목록)
const FOLD_KEY = 'sonefm.folded'
const folded = ref(readFolded())
function readFolded() {
  try { return Object.fromEntries(JSON.parse(localStorage.getItem(FOLD_KEY) || '[]').map((m) => [m, true])) } catch { return {} }
}
function saveFolded() {
  try { localStorage.setItem(FOLD_KEY, JSON.stringify(Object.keys(folded.value).slice(-300))) } catch { /* 무시 */ }
}
function toggleWeek(monday) {
  const next = { ...folded.value }
  if (next[monday]) delete next[monday]; else next[monday] = true
  folded.value = next
  saveFolded()
}
function setAllFolded(fold) {
  const next = { ...folded.value }
  for (const w of [data.value.reference_week, ...data.value.weeks]) {
    if (fold) next[w.monday] = true; else delete next[w.monday]
  }
  folded.value = next
  saveFolded()
}

// 보기 밀도 (이 PC에서만 기억)
const DENSITY_KEY = 'sonefm.density'
const density = ref(readDensity())
function readDensity() { try { return localStorage.getItem(DENSITY_KEY) || 'normal' } catch { return 'normal' } }
function setDensity(v) { density.value = v; try { localStorage.setItem(DENSITY_KEY, v) } catch { /* 무시 */ } }

const fmtKey = (k) => {
  const [d, h] = k.split('|')
  const [, m, day] = d.split('-')
  return `${Number(m)}/${Number(day)} ${h}시`
}

const issues = computed(() => data.value?.issues || [])

// ── 월 상태 (작성 중 → 확정 → 마감) ──
const STATUS_ACTIONS = {
  confirm: { title: '편성 확정', button: '확정' },
  reopen: { title: '확정 취소', button: '확정 취소' },
  close: { title: '마감', button: '마감' },
  unlock: { title: '마감 잠금 해제', button: '잠금 해제' },
}
function askStatus(action) {
  const n = issues.value.length
  const texts = {
    confirm: n ? `확인할 것이 ${n}건 남아 있습니다. 그래도 확정할까요? 확정 후에도 편집할 수 있고, 바꾼 내용은 변경 기록에 '확정 후 변경'으로 남습니다.` : '이 달 편성을 확정할까요? 확정 후에도 편집할 수 있고, 바꾼 내용은 변경 기록에 표시됩니다.',
    reopen: '확정을 취소하고 작성 중으로 돌립니다.',
    close: '보고서를 제출한 달을 마감합니다. 마감하면 편집과 다시 생성이 잠깁니다. 풀려면 사유를 적어야 합니다.',
    unlock: '마감을 풀면 편집할 수 있게 됩니다. 사유를 적어 주세요. 변경 기록에 남습니다.',
  }
  statusDialog.value = { action, title: STATUS_ACTIONS[action].title, text: texts[action], reason: '', error: '' }
}
async function applyStatus() {
  const d = statusDialog.value
  const r = await api.monthStatus(year.value, month.value, d.action, d.reason)
  if (!r.ok) { d.error = r.errors[0]; return }
  statusDialog.value = null
  await load()
  flash(r.message)
}

// 그 달 소속 주에 칸이 하나도 없으면 안내 문구를 보여준다
const monthEmpty = computed(() => data.value && !Object.keys(data.value.cells).some((k) => k >= data.value.weeks[0].monday))

const statusBadge = computed(() => {
  const s = data.value?.status
  return s === '마감' ? 'badge-danger' : s === '확정' ? 'badge-success' : ''
})
const statusLabel = computed(() => (data.value?.status === '작성중' ? '작성 중' : data.value?.status))

async function load() {
  const r = await api.getMonth(year.value, month.value)
  if (!r.ok) { errors.value = r.errors; return }
  errors.value = []
  data.value = r
  canUndo.value = !!r.can_undo
}

async function go(y, m) {
  year.value = y
  month.value = m
  selected.value = ''
  popup.value = null
  bandPick.value = null
  notice.value = ''
  await load()
}

function gotoPrevMonth() {
  const m = month.value === 1 ? 12 : month.value - 1
  const y = month.value === 1 ? year.value - 1 : year.value
  go(y, m)
}

let noticeTimer = 0
const noticeWarn = ref(false)
function flash(msg, warn = false) {
  clearTimeout(noticeTimer)
  notice.value = msg
  noticeWarn.value = warn
  noticeTimer = setTimeout(() => { notice.value = '' }, warn ? 9000 : 4000)
}

async function generate(scope, overwrite = false) {
  busy.value = true
  const r = await api.generateMonth(year.value, month.value, scope, overwrite)
  busy.value = false
  if (!r.ok) { errors.value = r.errors; return }
  errors.value = []
  canUndo.value = !!r.can_undo
  await load()
  if (r.manual_conflicts.length && !r.overwritten) {
    manualConfirm.value = { scope, rows: r.manual_conflicts }
  }
  flash(r.changed ? `${r.changed}칸을 채웠습니다.` : '바뀐 칸이 없습니다.')
}

async function overwriteManual() {
  const { scope } = manualConfirm.value
  manualConfirm.value = null
  await generate(scope, true)
}

async function jump(key) {
  const day = key.split('|')[0]
  if (data.value.reference_week.days.some((d) => d.date === day)) {
    // 다른 달 소속 주(참고 줄)의 칸은 그 달 화면으로 가서 보여준다
    const [y, m] = data.value.reference_week.monday.split('-').map(Number)
    await go(y, m)
  }
  const week = data.value.weeks.find((w) => w.days.some((d) => d.date === day))
  if (week && folded.value[week.monday]) toggleWeek(week.monday)
  selected.value = key
  await nextTick()
  const el = document.querySelector('.c.sel')
  if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

// ── 칸 팝업 ──
function openCell(key, rect) {
  bandPick.value = null
  selected.value = key
  popup.value = { key, rect }
}
function closePopup() { popup.value = null }
async function onCellChanged(message, undoable, warnings = []) {
  canUndo.value = !!undoable
  await load()
  if (warnings.length) flash(`${message} — ${warnings.join(' ')}`, true)
  else if (message) flash(message)
}

// 고정 편성 띠 → 날짜 고르기 → 그 칸 팝업
function openBand(b) { popup.value = null; bandPick.value = b }
function pickBandDay(d) {
  const b = bandPick.value
  bandPick.value = null
  openCell(`${d.date}|${b.hour}`, b.rect)
}

// ── 되돌리기 (Ctrl+Z) ──
async function doUndo() {
  if (busy.value) return
  busy.value = true
  const r = await api.undo()
  busy.value = false
  canUndo.value = !!r.can_undo
  if (!r.ok) { flash(r.errors[0]); return }
  popup.value = null
  await load()
  flash(r.message)
}
function onKey(e) {
  const t = e.target
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') { e.preventDefault(); doUndo() }
}
function onScroll() { popup.value = null; bandPick.value = null }

onMounted(async () => { window.addEventListener('keydown', onKey); await load() })
onActivated(() => { window.addEventListener('keydown', onKey); if (data.value) load() })   // 프로그램 화면에서 바꾼 내용 반영
onDeactivated(() => { window.removeEventListener('keydown', onKey); popup.value = null })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="view" :class="{ compact: density === 'compact', 'panel-closed': !panelOpen }">
    <div class="main">
      <header class="top">
        <div class="row1">
          <h1>{{ year }}년 {{ month }}월 편성표</h1>
          <span v-if="data" class="badge" :class="statusBadge">{{ statusLabel }}</span>
          <template v-if="data">
            <button v-if="data.status === '작성중'" class="btn btn-outline btn-sm" @click="askStatus('confirm')">확정</button>
            <template v-else-if="data.status === '확정'">
              <button class="btn btn-sm" @click="askStatus('reopen')">확정 취소</button>
              <button class="btn btn-outline btn-sm" @click="askStatus('close')">마감</button>
            </template>
            <button v-else-if="data.status === '마감'" class="btn btn-danger-outline btn-sm" @click="askStatus('unlock')">잠금 해제</button>
          </template>
          <div class="spacer" />
          <div class="seg" role="group" aria-label="보기 밀도">
            <button :aria-pressed="density === 'normal'" @click="setDensity('normal')">기본</button>
            <button :aria-pressed="density === 'compact'" @click="setDensity('compact')">압축</button>
          </div>
          <button
            class="btn" :class="{ 'btn-primary': data && !data.first_week_filled }"
            :disabled="busy || !data || data.status === '마감'" @click="generate('first_week')"
          >첫 주 불러오기</button>
          <button
            class="btn" :class="{ 'btn-primary': data && data.first_week_filled }"
            :disabled="busy || !data || data.status === '마감'" @click="generate('rest')"
          >월단위 생성</button>
          <button class="btn" :disabled="busy || !canUndo" title="Ctrl+Z" @click="doUndo">되돌리기</button>
          <button class="btn" @click="logOpen = true">변경 기록</button>
          <button class="btn btn-sm panel-toggle" :aria-pressed="panelOpen" @click="panelOpen = !panelOpen">
            {{ panelOpen ? '패널 닫기' : '패널 열기' }}
          </button>
        </div>
        <MonthDial :year="year" :month="month" :statuses="data?.year_statuses || {}" @select="go" />
      </header>

      <div class="scroll" @scroll.passive="onScroll">
        <div v-if="data && !monthEmpty" class="toolbar">
          <span class="muted small">칸을 누르면 결방·교체·특집 등을 할 수 있습니다. 주 이름을 누르면 접고 펼칩니다.</span>
          <span class="spacer" />
          <button class="btn btn-ghost btn-sm" @click="setAllFolded(false)">모두 펼치기</button>
          <button class="btn btn-ghost btn-sm" @click="setAllFolded(true)">모두 접기</button>
        </div>
        <div v-if="errors.length" class="callout callout-danger" role="alert">
          <ul><li v-for="e in errors" :key="e">{{ e }}</li></ul>
        </div>
        <div v-if="data?.status === '마감'" class="callout callout-warning small">
          마감된 달입니다. 편집과 다시 생성이 잠겨 있습니다. 고쳐야 하면 위쪽 <b>잠금 해제</b>를 눌러 사유를 적어 주세요.
        </div>
        <p v-if="monthEmpty" class="hint">
          아직 비어 있는 달입니다. <b>첫 주 불러오기</b>로 첫 주를 채운 뒤 개편 사항을 고치고, <b>월단위 생성</b>으로 나머지 주를 채워 주세요.
        </p>
        <MonthGrid v-if="data" :data="data" :today="today" :selected="selected" :folded="folded"
                   @goto-month="gotoPrevMonth" @select="openCell" @toggle="toggleWeek" @band="openBand" />
      </div>
    </div>

    <ValidationPanel v-if="data && panelOpen" :month="month" :totals="data.totals" :issues="issues" @jump="jump" />

    <BaseDialog v-if="statusDialog" :title="statusDialog.title" @close="statusDialog = null">
      <p>{{ statusDialog.text }}</p>
      <textarea v-if="statusDialog.action === 'unlock'" v-model="statusDialog.reason" class="textarea" rows="3"
                placeholder="예: 보고서 수정 제출로 11/10 편성 정정" />
      <p v-if="statusDialog.error" class="callout callout-danger small">{{ statusDialog.error }}</p>
      <template #footer>
        <button class="btn" @click="statusDialog = null">취소</button>
        <button class="btn" :class="statusDialog.action === 'unlock' || statusDialog.action === 'close' ? 'btn-danger' : 'btn-primary'"
                @click="applyStatus">{{ STATUS_ACTIONS[statusDialog.action].button }}</button>
      </template>
    </BaseDialog>

    <div v-if="notice" class="toast" :class="{ warn: noticeWarn }" role="status">{{ notice }}</div>

    <CellPopup v-if="popup" :cell-key="popup.key" :anchor="popup.rect" @close="closePopup" @changed="onCellChanged" />

    <div v-if="bandPick" class="band-pick" :style="{ left: `${bandPick.rect.left + 120}px`, top: `${Math.min(bandPick.rect.bottom + 4, 9999)}px` }">
      <p class="small">어느 날만 바꿀까요?</p>
      <div class="days">
        <button v-for="d in bandPick.days" :key="d.date" class="btn btn-sm" @click="pickBandDay(d)">{{ d.month }}/{{ d.day }} {{ d.weekday }}</button>
      </div>
      <button class="btn btn-ghost btn-sm" @click="bandPick = null">닫기</button>
    </div>

    <ChangeLogDialog v-if="logOpen" @close="logOpen = false" />

    <BaseDialog v-if="manualConfirm" title="직접 수정한 칸이 있습니다" @close="manualConfirm = null">
      <p>아래 칸은 사람이 직접 고친 칸이라 그대로 두었습니다. 규칙대로 덮어쓸까요?</p>
      <ul class="conflicts">
        <li v-for="r in manualConfirm.rows" :key="`${r.date}|${r.hour}`">
          <b>{{ fmtKey(`${r.date}|${r.hour}`) }}</b> {{ r.current }} → {{ r.rule }}
        </li>
      </ul>
      <template #footer>
        <button class="btn" @click="manualConfirm = null">그대로 두기</button>
        <button class="btn btn-danger" @click="overwriteManual">덮어쓰기</button>
      </template>
    </BaseDialog>
  </div>
</template>

<style scoped>
.view { display: grid; grid-template-columns: minmax(0, 1fr) 260px; height: 100%; min-height: 0; --row-height: var(--cell-height); }
.view.panel-closed { grid-template-columns: minmax(0, 1fr); }
.view.compact { --row-height: var(--cell-height-compact); }
.main { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.top { background: var(--color-background-canvas-100); border-bottom: 1px solid var(--color-border-normal); padding: var(--space-150) var(--space-300) 0; }
.row1 { display: flex; align-items: center; gap: var(--space-150); padding-bottom: var(--space-150); flex-wrap: wrap; }
h1 { font-size: var(--text-400); line-height: var(--leading-400); font-weight: var(--font-weight-bold); }
.spacer { flex: 1; }
.seg {
  display: inline-flex; padding: var(--space-025); gap: var(--space-025); border-radius: var(--radius-300);
  background: var(--color-background-secondary-200);
}
.seg button {
  height: 28px; padding: 0 var(--space-150); border: 0; border-radius: var(--radius-200); cursor: pointer;
  background: transparent; font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100);
}
.seg button[aria-pressed="true"] { background: var(--color-background-canvas-100); color: var(--color-foreground-normal-200); box-shadow: var(--shadow-sm); }
.scroll { flex: 1; overflow: auto; padding: var(--space-200) var(--space-300) var(--space-500); display: grid; gap: var(--space-150); align-content: start; }
.hint { margin: 0; color: var(--color-foreground-normal-100); }
.toolbar { display: flex; align-items: center; gap: var(--space-050); }
.toolbar .spacer { flex: 1; }
.band-pick {
  position: fixed; z-index: 60; display: grid; gap: var(--space-100); padding: var(--space-150) var(--space-200);
  background: var(--color-background-overlay-100); border: 1px solid var(--color-border-normal);
  border-radius: var(--radius-300); box-shadow: var(--shadow-md);
}
.band-pick p { margin: 0; font-weight: var(--font-weight-medium); }
.band-pick .days { display: flex; gap: var(--space-050); flex-wrap: wrap; }
.toast.warn { background: var(--color-background-warning-200); max-width: 560px; }
.toast {
  position: fixed; left: 50%; bottom: var(--space-300); transform: translateX(-50%); z-index: 50;
  max-width: 400px; padding: var(--space-150) var(--space-200); border-radius: var(--radius-300);
  background: var(--color-background-contrast-200); color: var(--color-foreground-inverse);
  box-shadow: var(--shadow-md); font-weight: var(--font-weight-medium);
}
.conflicts { margin: 0; padding-left: var(--space-250); max-height: 240px; overflow: auto; }
.conflicts li { padding: var(--space-025) 0; }
</style>
