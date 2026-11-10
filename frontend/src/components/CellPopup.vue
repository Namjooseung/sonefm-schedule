<script setup>
// 칸 팝업: 칸 정보 + 동작(본방/재방, 결방, 교체, 특집, 재방 회차, 실제 변경, 송출 준비, 원래대로).
// 편성 자리를 바꾸는 동작(교체, 본방/재방 전환)은 '이번만 / 이후 전부'를 고른다.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as api from '../api.js'

const props = defineProps({
  cellKey: { type: String, required: true },     // 'YYYY-MM-DD|시'
  anchor: { type: Object, required: true },      // 칸의 화면 위치 (DOMRect)
})
const emit = defineEmits(['close', 'changed', 'pending', 'preview'])

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const date = computed(() => props.cellKey.split('|')[0])
const hour = computed(() => Number(props.cellKey.split('|')[1]))
const when = computed(() => {
  const d = new Date(`${date.value}T00:00:00`)
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEKDAYS[d.getDay()]}) ${String(hour.value).padStart(2, '0')}:00`
})

const info = ref(null)
const programs = ref([])
const mode = ref('')           // '' | kind | cancel | replace | special | actual
const errors = ref([])
const busy = ref(false)
const el = ref(null)
const pos = ref({ left: 0, top: 0 })

const cell = computed(() => info.value?.cell)

async function load() {
  const r = await api.getCell(date.value, hour.value)
  if (!r.ok) { errors.value = r.errors; return }
  info.value = r
}

async function loadPrograms() {
  if (programs.value.length) return
  const r = await api.listPrograms('', false)
  if (r.ok) programs.value = r.items
}

// ── 위치: 칸 오른쪽, 넘치면 왼쪽. 화면 아래로 넘치지 않게 ──
async function place() {
  await nextTick()
  const w = el.value?.offsetWidth || 312
  const h = el.value?.offsetHeight || 400
  const a = props.anchor
  let left = a.right + 8
  if (left + w > window.innerWidth - 8) left = Math.max(8, a.left - w - 8)
  const top = Math.min(Math.max(8, a.top - 40), Math.max(8, window.innerHeight - h - 8))
  pos.value = { left, top }
}

watch(() => props.cellKey, async (_new, old) => {
  flushStep(old)
  reset()
  info.value = null
  await load()
  place()
})
watch([info, mode], place)

function reset() { mode.value = ''; errors.value = []; pendingKind.value = '' }

async function run(promise, keepOpen = false) {
  busy.value = true
  errors.value = []
  const r = await promise
  if (!r.ok) { busy.value = false; errors.value = r.errors; await load(); return }
  emit('changed', r.message, r.can_undo, r.warnings || [])
  if (keepOpen) { reset(); await load() } else emit('close')
  busy.value = false
}

// ── 본방/재방 ──
const pendingKind = ref('')
function chooseKind(k) {
  if (!cell.value || cell.value.kind === k) return
  if (info.value.kind_scope_available) { pendingKind.value = k; mode.value = 'kind' } else run(api.cellSetKind(date.value, hour.value, k, 'once'), true)
}

// ── 결방 ──
const cancelReason = ref('')

// ── 교체 ──
const query = ref('')
const pick = ref(null)
const pickKind = ref('재방')
const filtered = computed(() => {
  const q = query.value.trim()
  return programs.value
    .filter((p) => !p.is_special && (!cell.value || p.id !== cell.value.program_id))
    .filter((p) => !q || p.name.includes(q))
    .slice(0, 30)
})
function openReplace() { mode.value = 'replace'; pick.value = null; query.value = ''; pickKind.value = cell.value ? '재방' : '본방'; loadPrograms() }

// ── 특집 ──
const specials = computed(() => programs.value.filter((p) => p.is_special))
const special = ref({ program_id: '', name: '', category: '오락', is_listener_participation: false })
function openSpecial() {
  mode.value = 'special'
  special.value = { program_id: '', name: '', category: '오락', is_listener_participation: false }
  loadPrograms()
}
function submitSpecial() {
  const s = special.value
  const payload = s.program_id ? { program_id: s.program_id } : { name: s.name, category: s.category, is_listener_participation: s.is_listener_participation }
  run(api.cellSpecial(date.value, hour.value, payload))
}

// ── 재방 회차 / 실제 변경 ──
// 회차 − / + : 본방은 다음 본방이 여기서 이어지고, 재방은 그 칸만 바뀐다
const canStep = computed(() => {
  const c = cell.value
  return c && !c.is_fixed && !c.is_special && c.show_episode !== false
})
// 숫자는 누르는 즉시 바꾸고, 연달아 누르면 멈춘 뒤 한 번만 저장한다 (Ctrl+Z도 한 번에 되돌아감)
const STEP_DELAY = 200
let stepTimer = 0
let stepValue = null
function stepEpisode(delta) {
  const c = cell.value
  const next = (c.episode ?? 0) + delta
  if (next < 1) return
  c.episode = next
  c.rerun_episode_override = next
  c.waiting = false
  stepValue = next
  emit('preview', props.cellKey, next)     // 뒤쪽 편성표 칸도 바로 바꾼다
  clearTimeout(stepTimer)
  stepTimer = setTimeout(saveStep, STEP_DELAY)
}
function saveStep() {
  clearTimeout(stepTimer)
  const v = stepValue
  stepValue = null
  if (v != null) run(api.cellOverride(date.value, hour.value, v), true)
}
const actualNote = ref('')
function openActual() { mode.value = 'actual'; actualNote.value = cell.value?.actual_change_note || '' }

const canRevert = computed(() => info.value && (
  (cell.value && cell.value.source === 'manual') || info.value.cancellations.length
  || (!cell.value && info.value.rule) || (cell.value && !info.value.rule)
))

const episodeText = computed(() => {
  const c = cell.value
  if (!c) return ''
  if (c.waiting) return '본방 대기'
  if (c.is_fixed || c.is_special || c.show_episode === false || c.episode == null) return ''
  return `${c.episode}화${c.rerun_episode_override ? ' (지정)' : ''}`
})

const updatedText = computed(() => {
  const u = cell.value?.updated_at
  if (!u) return ''
  const d = new Date(u)
  return `마지막 수정 ${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

// ── 닫기: Esc, 바깥 누르기 ──
function onKey(e) { if (e.key === 'Escape') { if (mode.value) reset(); else emit('close') } }
function onDown(e) {
  if (el.value && !el.value.contains(e.target) && !e.target.closest?.('.c, .band')) emit('close')
}
onMounted(async () => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('mousedown', onDown)
  await load()
  place()
})
// 저장 전에 팝업을 닫거나 다른 칸을 누르면 그 값을 바로 저장한다 (결과는 부모가 받아 화면을 새로 고침)
function flushStep(key) {
  if (stepValue == null) return
  clearTimeout(stepTimer)
  const [d, h] = key.split('|')
  emit('pending', api.cellOverride(d, Number(h), stepValue))
  stepValue = null
}
onBeforeUnmount(() => {
  flushStep(props.cellKey)
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('mousedown', onDown)
})
</script>

<template>
  <div ref="el" class="pop" role="dialog" :aria-label="`${when} 칸`" :style="{ left: `${pos.left}px`, top: `${pos.top}px` }">
    <header>
      <div class="pn">{{ !info ? '불러오는 중…' : cell ? cell.name : '빈칸' }}</div>
      <div class="pm">
        {{ when }}<template v-if="cell"> · {{ cell.category }}<template v-if="episodeText"> · {{ episodeText }}</template></template>
      </div>
      <div v-if="info" class="tags">
        <span v-if="cell?.source === 'manual'" class="badge">직접 수정</span>
        <span v-else-if="cell" class="badge">편성 자리대로</span>
        <span v-if="cell?.exception_type" class="badge badge-special">{{ cell.exception_type }}</span>
      </div>
      <p v-if="cell?.original_name" class="orig">원래 편성: {{ cell.original_name }} → 결방</p>
      <p v-else-if="!cell && info?.rule" class="orig">원래 편성: {{ info.rule.name }} ({{ info.rule.kind }})</p>
      <p v-for="(c, i) in info?.cancellations || []" v-show="!cell?.original_name" :key="i" class="orig">
        결방 기록: {{ c.name }}<template v-if="c.reason"> — {{ c.reason }}</template>
      </p>
      <p v-if="cell?.actual_change_note" class="actual">실제 변경: {{ cell.actual_change_note }}</p>
    </header>

    <div v-if="errors.length" class="callout callout-danger small err"><ul><li v-for="e in errors" :key="e">{{ e }}</li></ul></div>

    <p v-if="info?.locked" class="locked muted small">마감된 달입니다. 편집하려면 먼저 잠금을 풀어 주세요.</p>

    <template v-else-if="info">
      <!-- 본방/재방 -->
      <div v-if="cell && !cell.is_fixed && !cell.is_special" class="tog">
        <button v-for="k in ['본방', '재방']" :key="k" :aria-pressed="cell.kind === k" :disabled="busy" @click="chooseKind(k)">{{ k }}</button>
      </div>

      <!-- 이번만 / 이후 전부 (본방/재방) -->
      <div v-if="mode === 'kind'" class="sub">
        <p class="small">{{ pendingKind }}으로 바꿉니다. 어떻게 할까요?</p>
        <div class="row">
          <button class="btn btn-sm" :disabled="busy" @click="run(api.cellSetKind(date, hour, pendingKind, 'once'), true)">이번만</button>
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="run(api.cellSetKind(date, hour, pendingKind, 'after'))">이후 전부</button>
          <button class="btn btn-ghost btn-sm" @click="reset">취소</button>
        </div>
        <p class="muted small">이후 전부: 이 날짜부터 편성 자리가 {{ pendingKind }}으로 바뀌고, 이미 만든 칸도 다시 맞춥니다.</p>
      </div>

      <!-- 결방 -->
      <div v-else-if="mode === 'cancel'" class="sub">
        <input v-model="cancelReason" class="input input-sm" placeholder="결방 사유 (선택)" />
        <div class="row">
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="run(api.cellCancel(date, hour, 'rerun', cancelReason))">재방으로 대체</button>
          <button class="btn btn-sm" :disabled="busy" @click="run(api.cellCancel(date, hour, 'empty', cancelReason))">비워두기</button>
          <button class="btn btn-ghost btn-sm" @click="reset">취소</button>
        </div>
        <p class="muted small">결방한 본방은 회차에 세지 않아 다음 본방이 이 회차를 이어받습니다.</p>
      </div>

      <!-- 교체 / 빈칸 채우기 -->
      <div v-else-if="mode === 'replace'" class="sub">
        <input v-model="query" class="input input-sm" placeholder="프로그램 검색" />
        <ul class="choices">
          <li v-for="p in filtered" :key="p.id">
            <button :aria-pressed="pick === p.id" @click="pick = p.id">
              <span>{{ p.name }}</span><span class="muted small">{{ p.cycle_label }}</span>
            </button>
          </li>
          <li v-if="!filtered.length" class="muted small empty">맞는 프로그램이 없습니다.</li>
        </ul>
        <div class="row">
          <label class="check small"><input v-model="pickKind" type="radio" value="본방" /> 본방</label>
          <label class="check small"><input v-model="pickKind" type="radio" value="재방" /> 재방</label>
        </div>
        <div class="row">
          <button class="btn btn-sm" :class="{ 'btn-primary': !info.scope_available }" :disabled="busy || !pick" @click="run(api.cellReplace(date, hour, pick, pickKind, 'once'))">이번만</button>
          <button v-if="info.scope_available" class="btn btn-primary btn-sm" :disabled="busy || !pick" @click="run(api.cellReplace(date, hour, pick, pickKind, 'after'))">이후 전부</button>
          <button class="btn btn-ghost btn-sm" @click="reset">취소</button>
        </div>
        <p v-if="info.scope_available" class="muted small">이후 전부: 이 날짜부터 이 자리를 고른 프로그램에 넘깁니다 (개편).</p>
      </div>

      <!-- 특집 -->
      <div v-else-if="mode === 'special'" class="sub">
        <select v-if="specials.length" v-model="special.program_id" class="select select-sm">
          <option value="">새 특집 만들기</option>
          <option v-for="s in specials" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <template v-if="!special.program_id">
          <input v-model="special.name" class="input input-sm" placeholder="특집 이름" />
          <div class="row">
            <label class="check small"><input v-model="special.category" type="radio" value="교양" /> 교양</label>
            <label class="check small"><input v-model="special.category" type="radio" value="오락" /> 오락</label>
            <label class="check small"><input v-model="special.is_listener_participation" type="checkbox" /> 청취자 참여</label>
          </div>
        </template>
        <div class="row">
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="submitSpecial">특집 넣기</button>
          <button class="btn btn-ghost btn-sm" @click="reset">취소</button>
        </div>
      </div>

      <!-- 실제 변경 -->
      <div v-else-if="mode === 'actual'" class="sub">
        <textarea v-model="actualNote" class="textarea small" rows="2" placeholder="예: 송출 사고로 다른 음원으로 대체" />
        <div class="row">
          <button class="btn btn-primary btn-sm" :disabled="busy" @click="run(api.cellActual(date, hour, actualNote), true)">기록</button>
          <button class="btn btn-ghost btn-sm" @click="reset">취소</button>
        </div>
        <p class="muted small">편성(계획)은 그대로 두고 실제로 나간 내용만 적어 둡니다.</p>
      </div>

      <!-- 동작 목록 -->
      <ul v-else class="actions">
        <template v-if="cell">
          <li v-if="canStep" class="stepper">
            <span>회차</span>
            <div class="step">
              <button class="sq" aria-label="회차 내리기" :disabled="(cell.episode ?? 0) <= 1" @click="stepEpisode(-1)">
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M6 12h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
              </button>
              <b>{{ cell.episode != null ? `${cell.episode}화` : '—' }}</b>
              <button class="sq" aria-label="회차 올리기" @click="stepEpisode(1)">
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 6v12M6 12h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
              </button>
              <button v-if="cell.rerun_episode_override" class="btn btn-ghost btn-sm" :disabled="busy" @click="run(api.cellOverride(date, hour, ''), true)">자동</button>
            </div>
          </li>
          <li><button @click="openReplace">다른 프로그램으로 교체 <span>{{ info.scope_available ? '이번만 / 이후 전부' : '이번만' }}</span></button></li>
          <li><button @click="openSpecial">특집 넣기</button></li>
          <li><button @click="mode = 'cancel'; cancelReason = ''">결방 <span>재방 대체 / 비우기</span></button></li>
          <li><button @click="openActual">실제 변경 기록 <span>사고·긴급 결방</span></button></li>
          <li class="prep">
            <span>송출 파일</span>
            <div class="seg-sm">
              <button v-for="s in ['미입고', '입고', '송출완료']" :key="s" :aria-pressed="cell.prep_status === s" :disabled="busy"
                      @click="run(api.cellPrep(date, hour, s), true)">{{ s === '송출완료' ? '송출 완료' : s }}</button>
            </div>
          </li>
        </template>
        <template v-else>
          <li><button @click="openReplace">프로그램 넣기</button></li>
          <li><button @click="openSpecial">특집 넣기</button></li>
        </template>
        <li v-if="canRevert" class="danger"><button :disabled="busy" @click="run(api.cellRevert(date, hour))">원래대로 되돌리기</button></li>
      </ul>
    </template>

    <footer v-if="updatedText">{{ updatedText }}</footer>
  </div>
</template>

<style scoped>
.pop {
  position: fixed; z-index: 60; width: 312px; max-height: calc(100vh - 16px); overflow: auto;
  background: var(--color-background-overlay-100); border: 1px solid var(--color-border-normal);
  border-radius: var(--radius-300); box-shadow: var(--shadow-md);
}
header { padding: var(--space-150) var(--space-200); border-bottom: 1px solid var(--color-border-normal); display: grid; gap: var(--space-050); }
.pn { font-size: var(--text-100); line-height: var(--leading-100); font-weight: var(--font-weight-heavy); letter-spacing: var(--tracking-heading); }
.pm { font-size: var(--text-050); line-height: var(--leading-050); color: var(--color-foreground-normal-100); }
.tags { display: flex; gap: var(--space-050); flex-wrap: wrap; }
.orig, .actual { margin: 0; font-size: var(--text-050); line-height: var(--leading-050); color: var(--color-foreground-normal-100); }
.actual { color: var(--color-foreground-warning-200); }
.err { margin: var(--space-100) var(--space-150) 0; }
.locked { padding: var(--space-150) var(--space-200); margin: 0; }
.tog { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-075); padding: var(--space-150) var(--space-200) var(--space-050); }
.tog button, .seg-sm button {
  position: relative; height: var(--control-md); border: 0; border-radius: var(--radius-300); cursor: pointer;
  background: var(--color-background-canvas-100); box-shadow: inset 0 0 0 1px var(--color-border-secondary);
  font-weight: var(--font-weight-medium);
}
.tog button[aria-pressed="true"], .seg-sm button[aria-pressed="true"] {
  background: var(--color-background-primary-100); color: var(--color-foreground-primary-200);
  box-shadow: inset 0 0 0 1px var(--color-border-primary);
}
.sub { display: grid; gap: var(--space-100); padding: var(--space-150) var(--space-200); }
.sub p { margin: 0; }
.row { display: flex; gap: var(--space-075); align-items: center; flex-wrap: wrap; }
.choices { list-style: none; margin: 0; padding: var(--space-050); max-height: 200px; overflow: auto; border-radius: var(--radius-300); box-shadow: inset 0 0 0 1px var(--color-border-normal); }
.choices button {
  display: flex; justify-content: space-between; gap: var(--space-100); width: 100%; text-align: left;
  padding: var(--space-075) var(--space-100); border: 0; border-radius: var(--radius-200); background: transparent; cursor: pointer;
}
.choices button:hover { background: var(--color-background-secondary-100); }
.choices button[aria-pressed="true"] { background: var(--color-background-primary-100); color: var(--color-foreground-primary-200); }
.choices .empty { padding: var(--space-100); }
.actions { list-style: none; margin: 0; padding: var(--space-050) var(--space-100) var(--space-100); }
.actions li > button {
  position: relative; display: flex; justify-content: space-between; align-items: center; width: 100%;
  min-height: var(--control-md); padding: var(--space-050) var(--space-100); border: 0; border-radius: var(--radius-300);
  background: transparent; cursor: pointer; text-align: left;
}
.actions li > button::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.actions li > button:hover::before { opacity: var(--overlay-hover); }
.actions li > button span { font-size: var(--text-050); color: var(--color-foreground-hint-100); }
.actions li.danger > button { color: var(--color-foreground-danger-100); }
.stepper { display: flex; align-items: center; justify-content: space-between; gap: var(--space-100); padding: var(--space-050) var(--space-100); }
.step { display: flex; align-items: center; gap: var(--space-075); }
.step b { min-width: 48px; text-align: center; font-weight: var(--font-weight-bold); }
.sq {
  position: relative; display: grid; place-items: center; width: var(--control-sm); height: var(--control-sm); padding: 0;
  border: 0; border-radius: var(--radius-300); cursor: pointer; color: var(--color-foreground-normal-200);
  background: var(--color-background-canvas-100); box-shadow: inset 0 0 0 1px var(--color-border-secondary);
}
.sq::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.sq:hover::before { opacity: var(--overlay-hover); }
.sq:disabled { opacity: var(--disabled-opacity); cursor: default; }
.prep { display: flex; align-items: center; justify-content: space-between; gap: var(--space-100); padding: var(--space-050) var(--space-100); }
.seg-sm { display: flex; gap: var(--space-050); }
.seg-sm button { height: var(--control-sm); padding: 0 var(--space-075); font-size: var(--text-050); }
footer { border-top: 1px solid var(--color-border-normal); padding: var(--space-100) var(--space-200); font-size: var(--text-050); color: var(--color-foreground-hint-100); }
</style>
