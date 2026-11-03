<script setup>
// 기존 엑셀 편성표 가져오기 (1회 이관): 파일 → 시트 고르기 → 이름 연결 → 가져오기 → 결과
import { computed, ref } from 'vue'
import * as api from '../api.js'

const emit = defineEmits(['done'])

const step = ref(1)
const path = ref('')
const analysis = ref(null)
const programs = ref([])
const selected = ref({})          // 시트 이름 → 체크
const mapping = ref({})           // 엑셀 이름 → { action, program_id, target, category, is_listener_participation }
const overwrite = ref(true)
const busy = ref(false)
const errors = ref([])
const result = ref(null)
const filter = ref('check')        // check(확인 필요) | auto(자동 연결) | all

async function pick() {
  errors.value = []
  const r = await api.excelPickFile()
  if (!r.ok) { errors.value = r.errors; return }
  if (!r.path) return
  path.value = r.path
  busy.value = true
  const a = await api.excelAnalyze(r.path)
  const p = await api.listPrograms('', true)
  busy.value = false
  if (!a.ok) { errors.value = a.errors; return }
  analysis.value = a
  programs.value = p.ok ? p.items : []
  selected.value = Object.fromEntries(a.sheets.filter((s) => s.importable).map((s) => [s.title, s.status !== '마감']))
  mapping.value = Object.fromEntries(a.names.map((n) => [n.name, {
    action: n.status === 'unmatched' ? 'new' : 'map',
    program_id: n.program_id || '',
    target: '',
    category: '교양',
    is_listener_participation: false,
  }]))
  step.value = 2
}

const chosenTitles = computed(() => Object.keys(selected.value).filter((t) => selected.value[t]))
const names = computed(() => {
  if (!analysis.value) return []
  const titles = new Set(chosenTitles.value)
  return analysis.value.names.filter((n) => n.sheets.some((t) => titles.has(t)))
})
const shownNames = computed(() => names.value.filter((n) =>
  filter.value === 'all' || (filter.value === 'auto' ? n.status === 'matched' : n.status !== 'matched')))
const counts = computed(() => ({
  check: names.value.filter((n) => n.status !== 'matched').length,
  auto: names.value.filter((n) => n.status === 'matched').length,
}))

// 선택 상자 값: 'new' | 'skip' | 'p:<id>' | 's:<엑셀 이름>'
function choiceOf(name) {
  const m = mapping.value[name]
  if (m.action === 'map') return `p:${m.program_id}`
  if (m.action === 'same') return `s:${m.target}`
  return m.action
}
function setChoice(name, v) {
  const m = mapping.value[name]
  if (v.startsWith('p:')) { m.action = 'map'; m.program_id = v.slice(2) } else if (v.startsWith('s:')) { m.action = 'same'; m.target = v.slice(2) } else m.action = v
}
function setAllNew(category) {
  for (const n of names.value) {
    if (n.status === 'unmatched') Object.assign(mapping.value[n.name], { action: 'new', category })
  }
}

async function run() {
  busy.value = true
  errors.value = []
  const payload = Object.fromEntries(names.value.map((n) => [n.name, { ...mapping.value[n.name] }]))
  const r = await api.excelImport(path.value, chosenTitles.value, payload, overwrite.value)
  busy.value = false
  if (!r.ok) { errors.value = r.errors; return }
  result.value = r
  step.value = 4
  emit('done')
}

function reset() { step.value = 1; path.value = ''; analysis.value = null; result.value = null; errors.value = [] }
const fileName = computed(() => path.value.split(/[\\/]/).pop())
</script>

<template>
  <div class="wizard">
    <ol class="steps">
      <li v-for="(t, i) in ['파일', '시트', '이름 연결', '결과']" :key="t" :aria-current="step === i + 1 ? 'step' : undefined">{{ i + 1 }}. {{ t }}</li>
    </ol>

    <div v-if="errors.length" class="callout callout-danger small"><ul><li v-for="e in errors" :key="e">{{ e }}</li></ul></div>

    <!-- 1. 파일 -->
    <section v-if="step === 1" class="body">
      <p>지금까지 쓰던 엑셀 편성표(xlsx)를 앱으로 옮깁니다. 처음 한 번만 하면 됩니다.</p>
      <ul class="small muted">
        <li>시트 이름이 <b>2611</b>처럼 연월(YYMM)인 시트만 가져옵니다.</li>
        <li>가져오기 전에 지금 데이터를 자동으로 백업합니다.</li>
      </ul>
      <div><button class="btn btn-primary" :disabled="busy" @click="pick">{{ busy ? '읽는 중…' : '엑셀 파일 고르기' }}</button></div>
    </section>

    <!-- 2. 시트 -->
    <section v-else-if="step === 2" class="body">
      <p class="small">파일: <b>{{ fileName }}</b></p>
      <table class="tbl">
        <thead><tr><th></th><th>시트</th><th>달</th><th>주</th><th>채워진 칸</th><th>앱의 그 달</th></tr></thead>
        <tbody>
          <tr v-for="s in analysis.sheets" :key="s.title" :class="{ off: !s.importable }">
            <td><input v-if="s.importable" v-model="selected[s.title]" type="checkbox" :disabled="s.status === '마감'" /></td>
            <td>{{ s.title }}</td>
            <td>{{ s.importable ? `${s.year}년 ${s.month}월` : '—' }}</td>
            <td>{{ s.importable ? s.weeks : '' }}</td>
            <td>{{ s.importable ? s.cells : s.reason }}</td>
            <td>{{ s.status || '' }}</td>
          </tr>
        </tbody>
      </table>
      <p class="muted small">한 주가 두 시트에 걸쳐 있으면 그 주의 월요일이 속한 달 시트에서 가져옵니다. (예: 10/26~11/1 주는 2610 시트)</p>
      <ul v-if="analysis.notes.length" class="small"><li v-for="n in analysis.notes" :key="n">{{ n }}</li></ul>
      <p v-if="analysis.error_count" class="callout callout-warning small">수식 오류(#REF! 등)로 가져올 수 없는 칸이 {{ analysis.error_count }}개 있습니다. 가져온 뒤 빈칸으로 남습니다.</p>
      <div class="row">
        <button class="btn" @click="reset">처음으로</button>
        <button class="btn btn-primary" :disabled="!chosenTitles.length" @click="step = 3">다음: 이름 연결</button>
      </div>
    </section>

    <!-- 3. 이름 연결 -->
    <section v-else-if="step === 3" class="body">
      <p class="small">엑셀에 적힌 프로그램 이름을 앱의 프로그램과 연결합니다. 표기만 다른 이름(띄어쓰기, 오타)은 <b>엑셀의 다른 이름과 같음</b>으로 묶으면 회차가 이어집니다.</p>
      <div class="row">
        <div class="seg" role="group" aria-label="보기">
          <button :aria-pressed="filter === 'check'" @click="filter = 'check'">확인 필요 {{ counts.check }}</button>
          <button :aria-pressed="filter === 'auto'" @click="filter = 'auto'">자동 연결 {{ counts.auto }}</button>
          <button :aria-pressed="filter === 'all'" @click="filter = 'all'">전체</button>
        </div>
        <span class="spacer" />
        <span class="small muted">연결 안 된 이름 모두 새로 등록:</span>
        <button class="btn btn-sm" @click="setAllNew('교양')">교양으로</button>
        <button class="btn btn-sm" @click="setAllNew('오락')">오락으로</button>
      </div>
      <div class="scroll-tbl">
        <table class="tbl">
          <thead><tr><th>엑셀 이름</th><th>칸</th><th>처음</th><th>연결</th><th>새로 등록할 때</th></tr></thead>
          <tbody>
            <tr v-for="n in shownNames" :key="n.name">
              <td class="nm">{{ n.name }}<span v-if="n.status === 'suggested'" class="badge">추천</span></td>
              <td>{{ n.count }}</td>
              <td class="nowrap">{{ n.first_date }}</td>
              <td>
                <select class="select select-sm" :value="choiceOf(n.name)" @change="setChoice(n.name, $event.target.value)">
                  <option value="new">새 프로그램으로 등록</option>
                  <option value="skip">가져오지 않음</option>
                  <optgroup label="기존 프로그램에 연결">
                    <option v-for="p in programs" :key="p.id" :value="`p:${p.id}`">{{ p.name }}</option>
                  </optgroup>
                  <optgroup label="엑셀의 다른 이름과 같음">
                    <option v-for="o in names.filter((x) => x.name !== n.name)" :key="o.name" :value="`s:${o.name}`">{{ o.name }}</option>
                  </optgroup>
                </select>
              </td>
              <td>
                <template v-if="mapping[n.name].action === 'new'">
                  <select v-model="mapping[n.name].category" class="select select-sm"><option>교양</option><option>오락</option></select>
                  <label class="check small"><input v-model="mapping[n.name].is_listener_participation" type="checkbox" /> 청취자 참여</label>
                </template>
              </td>
            </tr>
            <tr v-if="!shownNames.length"><td colspan="5" class="muted small">해당하는 이름이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
      <label class="check small"><input v-model="overwrite" type="checkbox" /> 앱에 이미 있는 칸도 엑셀 내용으로 덮어쓰기</label>
      <p class="muted small">새로 등록한 프로그램의 편성 자리와 주기는 마지막 4주를 보고 추정합니다. 그 4주에 나오지 않은 프로그램은 마지막 방송일로 종영 처리합니다. 가져온 뒤 프로그램 화면에서 확인해 주세요.</p>
      <div class="row">
        <button class="btn" :disabled="busy" @click="step = 2">이전</button>
        <button class="btn btn-primary" :disabled="busy" @click="run">{{ busy ? '가져오는 중…' : '가져오기' }}</button>
      </div>
    </section>

    <!-- 4. 결과 -->
    <section v-else-if="step === 4 && result" class="body">
      <div class="callout callout-success">{{ result.written.toLocaleString('ko-KR') }}칸을 가져왔습니다.</div>
      <ul class="small">
        <li>새로 등록한 프로그램 {{ result.created }}개 (편성 자리 추정 {{ result.inferred }}개, 종영 처리 {{ result.ended }}개), 별칭 추가 {{ result.aliases_added }}개</li>
        <li v-if="result.read_as_rerun">본방 자리에 같은 회차가 다시 나온 {{ result.read_as_rerun.toLocaleString('ko-KR') }}칸은 재방으로 읽었습니다. (엑셀에서 (재)를 생략한 칸)</li>
        <li v-if="result.kept">이미 있던 칸 {{ result.kept }}개는 그대로 두었습니다.</li>
        <li v-if="result.skipped">"가져오지 않음"으로 고른 이름의 칸 {{ result.skipped }}개는 비워 두었습니다.</li>
        <li v-if="result.backup">가져오기 전 백업: {{ result.backup }}</li>
        <li v-for="n in result.notes" :key="n">{{ n }}</li>
      </ul>
      <template v-if="result.episode_diff_count">
        <p class="small">엑셀과 회차가 다른 칸 <b>{{ result.episode_diff_count }}개</b> — 최근 회차에 맞췄기 때문에 주로 지난 달에서 엑셀 회차가 건너뛰었거나 이름 표기가 달랐던 곳입니다.</p>
        <div class="scroll-tbl small-tbl">
          <table class="tbl">
            <thead><tr><th>날짜</th><th>시</th><th>프로그램</th><th>엑셀</th><th>앱</th></tr></thead>
            <tbody>
              <tr v-for="d in result.episode_diffs" :key="`${d.date}|${d.hour}`">
                <td class="nowrap">{{ d.date }}</td><td>{{ d.hour }}</td><td>{{ d.name }}</td><td>{{ d.excel }}화</td><td>{{ d.app ?? '—' }}화</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <div class="row"><button class="btn" @click="reset">다른 파일 가져오기</button></div>
    </section>
  </div>
</template>

<style scoped>
.wizard { display: grid; gap: var(--space-200); }
.steps { display: flex; gap: var(--space-200); list-style: none; margin: 0; padding: 0; font-size: var(--text-050); color: var(--color-foreground-hint-100); }
.steps li[aria-current="step"] { color: var(--color-foreground-primary-200); font-weight: var(--font-weight-bold); }
.body { display: grid; gap: var(--space-150); }
.body p, .body ul { margin: 0; }
.row { display: flex; gap: var(--space-100); align-items: center; flex-wrap: wrap; }
.spacer { flex: 1; }
.tbl { border-collapse: collapse; width: 100%; font-size: var(--text-050); line-height: var(--leading-050); }
.tbl th { text-align: left; font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100); background: var(--color-background-overlay-100); position: sticky; top: 0; z-index: 1; }
.tbl th, .tbl td { padding: var(--space-075) var(--space-100); border-bottom: 1px solid var(--color-border-normal); vertical-align: middle; }
.tbl tr.off td { color: var(--color-foreground-hint-100); }
.tbl .nm { min-width: 220px; }
.tbl .nm .badge { margin-left: var(--space-075); }
.tbl td .check { margin-left: var(--space-100); }
.nowrap { white-space: nowrap; }
.scroll-tbl { max-height: 420px; overflow: auto; border: 1px solid var(--color-border-normal); border-radius: var(--radius-300); }
.small-tbl { max-height: 240px; }
.seg { display: inline-flex; padding: var(--space-025); gap: var(--space-025); border-radius: var(--radius-300); background: var(--color-background-secondary-200); }
.seg button { height: 26px; padding: 0 var(--space-100); border: 0; border-radius: var(--radius-200); cursor: pointer; background: transparent; font-size: var(--text-050); font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100); }
.seg button[aria-pressed="true"] { background: var(--color-background-canvas-100); color: var(--color-foreground-normal-200); box-shadow: var(--shadow-sm); }
</style>
