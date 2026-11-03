<script setup>
// 설정 화면: 편성 규칙 · 임시공휴일 · 데이터 파일(위치·백업·복원·내보내기) · 엑셀 가져오기
import { computed, onActivated, onMounted, ref } from 'vue'
import * as api from '../api.js'
import BaseDialog from '../components/BaseDialog.vue'
import ImportWizard from '../components/ImportWizard.vue'

const info = ref(null)          // 앱 버전·스키마
const data = ref(null)          // DB 경로·백업
const rules = ref(null)
const programs = ref([])
const notice = ref('')
const noticeError = ref(false)
const confirm = ref(null)       // { title, text, button, danger, run }
const busy = ref(false)

let timer = 0
function flash(msg, error = false) {
  clearTimeout(timer)
  notice.value = msg
  noticeError.value = error
  timer = setTimeout(() => { notice.value = '' }, error ? 8000 : 4000)
}

async function loadAll() {
  const [p, d, r, l] = await Promise.all([api.ping(), api.dataInfo(), api.settingsGet(), api.listPrograms('', true)])
  info.value = p
  if (d.ok) data.value = d
  if (r.ok) rules.value = { ...r, fixed_program_ids: r.fixed_programs.map((x) => x.id) }
  if (l.ok) programs.value = l.items
}

async function act(promise, after = loadAll) {
  busy.value = true
  const r = await promise
  busy.value = false
  if (!r.ok) { flash(r.errors[0], true); return null }
  if (r.cancelled) return null
  if (r.message) flash(r.message)
  await after()
  return r
}

// ── 편성 규칙 ──
const fixedNames = computed(() => (rules.value?.fixed_program_ids || []).map((id) => programs.value.find((p) => p.id === id)?.name || '(삭제된 프로그램)'))
const addFixed = ref('')
function pushFixed() {
  if (addFixed.value && !rules.value.fixed_program_ids.includes(addFixed.value)) rules.value.fixed_program_ids.push(addFixed.value)
  addFixed.value = ''
}
function saveRules() {
  const r = rules.value
  act(api.settingsSave({ offweek_policy_default: r.offweek_policy_default,
    irregular_missing_warn_count: r.irregular_missing_warn_count, fixed_program_ids: r.fixed_program_ids }))
}

// ── 임시공휴일 ──
const hol = ref({ date: '', name: '임시공휴일' })
async function addHoliday() {
  const r = await act(api.holidayAdd(hol.value.date, hol.value.name))
  if (r) hol.value = { date: '', name: '임시공휴일' }
}

// ── 데이터 파일 ──
async function moveDb() {
  const f = await api.pickFolder()
  if (!f.path) return
  confirm.value = {
    title: '데이터 위치 바꾸기',
    text: `새 위치: ${f.path}\n지금 데이터를 그 폴더로 복사해서 쓸까요? 그 폴더에 이미 다른 PC에서 쓰던 schedule.db가 있다면 "그 폴더의 데이터 쓰기"를 고르세요.`,
    choices: [
      { label: '그 폴더의 데이터 쓰기', run: () => act(api.dbMove(f.path, 'use_existing')) },
      { label: '복사해서 옮기기', primary: true, run: () => act(api.dbMove(f.path, 'copy')) },
    ],
  }
}
function askRestore(b) {
  confirm.value = {
    title: '백업으로 되돌리기',
    text: `${b.modified}에 만든 백업(${b.name})으로 지금 데이터를 바꿉니다. 바꾸기 직전 상태도 자동으로 백업해 두므로 다시 돌아올 수 있습니다.`,
    choices: [{ label: '되돌리기', danger: true, run: () => act(api.backupRestore(b.path)) }],
  }
}
async function importDataFile() {
  const f = await api.dataImportPick()
  if (!f.path) return
  confirm.value = {
    title: '데이터 가져오기',
    text: `${f.path}\n이 파일의 데이터로 지금 데이터를 바꿉니다. 지금 데이터는 자동으로 백업해 둡니다.`,
    choices: [{ label: '가져오기', danger: true, run: () => act(api.backupRestore(f.path)) }],
  }
}
async function changeBackupDir() {
  const f = await api.pickFolder()
  if (f.path) act(api.backupOptions(f.path, data.value.backup_keep))
}
function runChoice(c) { confirm.value = null; c.run() }

onMounted(loadAll)
onActivated(loadAll)
</script>

<template>
  <section class="page">
    <h1>설정</h1>

    <!-- 편성 규칙 -->
    <div v-if="rules" class="card body">
      <h2>편성 규칙</h2>
      <div class="grid">
        <label class="field">
          <span>격주·매월 n째 주 프로그램이 방송 없는 주의 본방 자리</span>
          <select v-model="rules.offweek_policy_default" class="select">
            <option value="rerun">재방으로 채움 (직전 회차)</option>
            <option value="empty">비움</option>
          </select>
        </label>
        <label class="field">
          <span>부정기 프로그램 "본방 입력 누락?" 경고 — 같은 회차 재방 연속 횟수</span>
          <input v-model.number="rules.irregular_missing_warn_count" type="number" min="2" max="20" class="input num" />
        </label>
      </div>
      <div class="field">
        <span>고정 편성 (편성표에서 가로 띠로 보이고 회차를 숨기는 프로그램)</span>
        <div class="chips">
          <span v-for="(n, i) in fixedNames" :key="rules.fixed_program_ids[i]" class="chip">
            {{ n }}
            <button class="chip-x" :aria-label="`${n} 빼기`" @click="rules.fixed_program_ids.splice(i, 1)">
              <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" /></svg>
            </button>
          </span>
          <select v-model="addFixed" class="select select-sm" @change="pushFixed">
            <option value="">프로그램 추가…</option>
            <option v-for="p in programs.filter((x) => !rules.fixed_program_ids.includes(x.id))" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
      </div>
      <p class="muted small">법정 편성비율 기준값은 허가 조건 확인 후 추가합니다.</p>
      <div><button class="btn btn-primary" :disabled="busy" @click="saveRules">저장</button></div>
    </div>

    <!-- 임시공휴일 -->
    <div v-if="rules" class="card body">
      <h2>임시공휴일</h2>
      <p class="muted small">법정 공휴일은 자동으로 표시됩니다. 대체공휴일·임시공휴일처럼 빠진 날만 여기에 추가합니다.</p>
      <div class="row">
        <input v-model="hol.date" type="date" class="input" />
        <input v-model="hol.name" class="input" placeholder="이름" />
        <button class="btn" :disabled="busy || !hol.date" @click="addHoliday">추가</button>
      </div>
      <ul v-if="rules.holidays.length" class="list">
        <li v-for="h in rules.holidays" :key="h.date">
          <span>{{ h.date }} {{ h.name }}</span>
          <button class="btn btn-ghost-danger btn-sm" @click="act(api.holidayDelete(h.date))">삭제</button>
        </li>
      </ul>
    </div>

    <!-- 데이터 파일 -->
    <div class="card body">
      <h2>데이터 파일</h2>
      <dl v-if="data">
        <dt>위치</dt><dd>{{ data.db_path }} <button class="btn btn-sm" :disabled="busy" @click="moveDb">위치 바꾸기</button></dd>
        <dt>앱 버전</dt><dd>{{ info?.app_version }} (데이터 구조 {{ info?.schema_version }})</dd>
      </dl>
      <div class="row">
        <button class="btn" :disabled="busy" @click="act(api.dataExport())">데이터 내보내기 (파일 하나)</button>
        <button class="btn" :disabled="busy" @click="importDataFile">데이터 가져오기</button>
      </div>
      <p class="muted small">다른 PC로 옮길 때: 이 PC에서 "데이터 내보내기" → 새 PC에서 "데이터 가져오기".</p>
    </div>

    <!-- 백업 -->
    <div v-if="data" class="card body">
      <h2>백업</h2>
      <dl>
        <dt>백업 폴더</dt><dd>{{ data.backup_dir }} <button class="btn btn-sm" :disabled="busy" @click="changeBackupDir">폴더 바꾸기</button></dd>
        <dt>보관 개수</dt>
        <dd class="row">
          <input v-model.number="data.backup_keep" type="number" min="3" max="365" class="input num" />
          <button class="btn btn-sm" :disabled="busy" @click="act(api.backupOptions(null, data.backup_keep))">저장</button>
          <span class="muted small">오래된 백업부터 지웁니다.</span>
        </dd>
      </dl>
      <p class="muted small">프로그램을 켤 때마다 자동으로 백업합니다. 백업 폴더를 구글드라이브 같은 동기화 폴더로 바꾸면 PC가 고장 나도 안전합니다.</p>
      <div><button class="btn btn-primary" :disabled="busy" @click="act(api.backupNow())">지금 백업</button></div>
      <table v-if="data.backups.length" class="tbl">
        <thead><tr><th>만든 때</th><th>파일</th><th>크기</th><th></th></tr></thead>
        <tbody>
          <tr v-for="b in data.backups.slice(0, 15)" :key="b.path">
            <td class="nowrap">{{ b.modified }}</td><td>{{ b.name }}</td><td class="nowrap">{{ b.size_kb }}KB</td>
            <td><button class="btn btn-ghost btn-sm" :disabled="busy" @click="askRestore(b)">이 백업으로 되돌리기</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 엑셀 가져오기 -->
    <div class="card body">
      <h2>기존 엑셀 편성표 가져오기</h2>
      <ImportWizard @done="loadAll" />
    </div>

    <div v-if="notice" class="toast" :class="{ err: noticeError }" role="status">{{ notice }}</div>

    <BaseDialog v-if="confirm" :title="confirm.title" @close="confirm = null">
      <p class="pre">{{ confirm.text }}</p>
      <template #footer>
        <button class="btn" @click="confirm = null">취소</button>
        <button v-for="c in confirm.choices" :key="c.label" class="btn"
                :class="c.danger ? 'btn-danger' : c.primary ? 'btn-primary' : ''" @click="runChoice(c)">{{ c.label }}</button>
      </template>
    </BaseDialog>
  </section>
</template>

<style scoped>
.page { padding: var(--space-300); display: grid; gap: var(--space-200); align-content: start; max-width: 1100px; overflow: auto; height: 100%; }
h1 { font-size: var(--text-400); line-height: var(--leading-400); font-weight: var(--font-weight-bold); }
h2 { font-size: var(--text-100); line-height: var(--leading-100); font-weight: var(--font-weight-bold); }
.body { padding: var(--space-300); display: grid; gap: var(--space-150); }
.body p { margin: 0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-150) var(--space-300); }
.field { display: grid; gap: var(--space-050); align-content: start; }
.field > span { font-size: var(--text-050); line-height: var(--leading-050); font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100); }
.num { width: 100px; }
.row { display: flex; gap: var(--space-100); align-items: center; flex-wrap: wrap; }
.chips { display: flex; gap: var(--space-075); flex-wrap: wrap; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: var(--space-025); height: var(--control-sm); padding: 0 var(--space-050) 0 var(--space-100); border-radius: var(--radius-300); background: var(--color-background-secondary-200); font-size: var(--text-050); }
.chip-x { display: inline-grid; place-items: center; width: 20px; height: 20px; padding: 0; border: 0; border-radius: var(--radius-100); background: transparent; cursor: pointer; color: var(--color-foreground-hint-200); }
.chip-x:hover { color: var(--color-foreground-danger-100); }
.list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-050); }
.list li { display: flex; justify-content: space-between; align-items: center; padding: var(--space-050) var(--space-100); border-radius: var(--radius-300); background: var(--color-background-secondary-100); }
dl { display: grid; grid-template-columns: 120px 1fr; gap: var(--space-100) var(--space-200); margin: 0; align-items: center; }
dt { color: var(--color-foreground-hint-100); }
dd { margin: 0; word-break: break-all; display: flex; gap: var(--space-100); align-items: center; flex-wrap: wrap; }
.tbl { border-collapse: collapse; width: 100%; font-size: var(--text-050); }
.tbl th { text-align: left; font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100); }
.tbl th, .tbl td { padding: var(--space-050) var(--space-100); border-bottom: 1px solid var(--color-border-normal); }
.nowrap { white-space: nowrap; }
.pre { white-space: pre-line; }
.toast {
  position: fixed; left: 50%; bottom: var(--space-300); transform: translateX(-50%); z-index: 50; max-width: 560px;
  padding: var(--space-150) var(--space-200); border-radius: var(--radius-300); box-shadow: var(--shadow-md);
  background: var(--color-background-contrast-200); color: var(--color-foreground-inverse); font-weight: var(--font-weight-medium);
}
.toast.err { background: var(--color-background-danger-200); }
</style>
