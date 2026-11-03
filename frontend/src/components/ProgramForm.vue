<script setup>
// 프로그램 상세 편집. draft 객체를 직접 수정하고, 저장·종영·삭제는 부모에게 알린다.
import { computed, ref, watch } from 'vue'
import SlotEditor from './SlotEditor.vue'

const props = defineProps({
  draft: { type: Object, required: true },
  choices: { type: Object, required: true },
  today: { type: String, required: true },
  dirty: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['save', 'revert', 'end', 'resume', 'delete'])

const isNew = computed(() => !props.draft.id)
const cycle = computed(() => props.draft.cycle_type)
const hasOffweek = computed(() => ['biweekly', 'monthly_nth'].includes(cycle.value))
const isEnded = computed(() => props.draft.end_date && props.draft.end_date < props.today)

// 별칭 입력
const aliasInput = ref('')
function addAlias() {
  const a = aliasInput.value.trim().replace(/\s+/g, ' ')
  if (a && !props.draft.aliases.includes(a)) props.draft.aliases.push(a)
  aliasInput.value = ''
}

// 종영·삭제 확인 줄
const confirming = ref('')   // '' | 'end' | 'delete'
const endDate = ref('')
watch(() => props.draft.id, () => { confirming.value = '' })
function askEnd() { confirming.value = 'end'; endDate.value = props.today }
</script>

<template>
  <form class="form" @submit.prevent="emit('save')">
    <header class="head">
      <div class="title">
        <h2>{{ isNew ? '새 프로그램' : draft.name || '이름 없음' }}</h2>
        <span v-if="draft.is_special" class="badge badge-special">특집</span>
        <span v-if="draft.end_date" class="badge badge-danger">종영 {{ draft.end_date }}</span>
      </div>
      <div class="head-actions">
        <button type="button" class="btn" :disabled="busy || (!dirty && !isNew)" @click="emit('revert')">
          {{ isNew ? '취소' : '되돌리기' }}
        </button>
        <button type="submit" class="btn btn-primary" :disabled="busy || (!dirty && !isNew)">저장</button>
      </div>
    </header>

    <div class="scroll">
      <slot name="messages" />

      <section>
        <h3>기본 정보</h3>
        <div class="grid">
          <label class="field wide">
            <span>프로그램 이름</span>
            <input v-model="draft.name" class="input" placeholder="예: [10기] 그 삶이다" />
          </label>
          <div class="field">
            <span>분야</span>
            <div class="seg" role="radiogroup" aria-label="분야">
              <label v-for="c in choices.categories" :key="c" class="check">
                <input v-model="draft.category" type="radio" :value="c" /> {{ c }}
              </label>
            </div>
          </div>
          <div class="field">
            <span>청취자 참여</span>
            <label class="check">
              <input v-model="draft.is_listener_participation" type="checkbox" /> 청취자 참여 프로그램
            </label>
          </div>
          <label class="field">
            <span>제작 주체</span>
            <select v-model="draft.producer_type" class="select">
              <option v-for="p in choices.producer_types" :key="p" :value="p">{{ p === '타공동체라디오' ? '타 공동체라디오' : p }}</option>
            </select>
          </label>
          <label class="field">
            <span>진행자</span>
            <input v-model="draft.host" class="input" />
          </label>
          <label class="field">
            <span>기수 (방송활동가)</span>
            <input v-model="draft.cohort" class="input" placeholder="예: 10기" />
          </label>
        </div>
      </section>

      <section>
        <h3>방송 주기</h3>
        <div class="grid">
          <label class="field">
            <span>주기</span>
            <select v-model="draft.cycle_type" class="select">
              <option v-for="c in choices.cycle_types" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </label>
          <label v-if="cycle === 'biweekly'" class="field">
            <span>기준일 <em class="muted small">본방이 나가는 주의 아무 날짜</em></span>
            <input v-model="draft.cycle_anchor_date" type="date" class="input" />
          </label>
          <label v-if="cycle === 'monthly_nth'" class="field">
            <span>매월 몇째 주</span>
            <select v-model.number="draft.monthly_nth" class="select">
              <option :value="null" disabled>선택</option>
              <option v-for="n in 5" :key="n" :value="n">{{ n }}째 주</option>
            </select>
          </label>
          <label v-if="hasOffweek" class="field">
            <span>방송 없는 주의 본방 자리</span>
            <select v-model="draft.offweek_policy" class="select">
              <option value="">설정 기본값 따름</option>
              <option v-for="o in choices.offweek_policies" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
        </div>
        <p v-if="cycle === 'irregular'" class="hint small">
          부정기 프로그램은 편성 자리가 모두 재방으로 깔립니다. 편성표에서 본방이 나가는 날 칸을 "본방으로" 바꿔 주세요.
        </p>
        <p v-if="cycle === 'oneoff'" class="hint small">
          단발(특집) 프로그램은 편성 자리 없이 편성표의 칸에 직접 넣습니다.
        </p>
      </section>

      <section>
        <h3>회차·기간</h3>
        <div class="grid">
          <label class="field">
            <span>시작 회차</span>
            <input v-model.number="draft.start_episode" type="number" min="1" class="input" />
          </label>
          <label class="field">
            <span>시작일</span>
            <input v-model="draft.start_date" type="date" class="input" />
          </label>
          <div class="field">
            <span>회차 표시</span>
            <label class="check"><input v-model="draft.show_episode" type="checkbox" /> 편성표·엑셀에 회차(_23화) 붙이기</label>
          </div>
          <div class="field">
            <span>종영일</span>
            <input :value="draft.end_date || '방송 중'" class="input" readonly />
          </div>
        </div>
      </section>

      <section v-if="cycle !== 'oneoff'">
        <h3>편성 자리</h3>
        <SlotEditor :slots="draft.slots" :choices="choices" :today="today" :default-from="draft.start_date" />
      </section>

      <section>
        <h3>별칭 <em class="muted small">엑셀 편성표에 다르게 적힌 이름 (가져오기 때 같은 프로그램으로 인식)</em></h3>
        <div class="aliases">
          <span v-for="(a, i) in draft.aliases" :key="a" class="chip">
            {{ a }}
            <button type="button" class="chip-x" :aria-label="`${a} 지우기`" @click="draft.aliases.splice(i, 1)">
              <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" /></svg>
            </button>
          </span>
          <input v-model="aliasInput" class="input input-sm alias-input" placeholder="별칭 입력 후 Enter"
                 @keydown.enter.prevent="addAlias" @blur="addAlias" />
        </div>
      </section>

      <section>
        <h3>메모</h3>
        <textarea v-model="draft.memo" class="textarea" rows="3" />
      </section>

      <section v-if="!isNew" class="danger-zone">
        <h3>종영·삭제</h3>
        <div v-if="confirming === 'end'" class="confirm">
          <span>종영일</span>
          <input v-model="endDate" type="date" class="input input-sm" />
          <button type="button" class="btn btn-danger btn-sm" :disabled="busy" @click="emit('end', endDate)">종영 처리</button>
          <button type="button" class="btn btn-sm" @click="confirming = ''">취소</button>
          <span class="muted small">방송 중인 편성 자리도 종영일에 함께 닫힙니다.</span>
        </div>
        <div v-else-if="confirming === 'delete'" class="confirm">
          <span>잘못 등록한 프로그램일 때만 삭제합니다. 삭제할까요?</span>
          <button type="button" class="btn btn-danger btn-sm" :disabled="busy" @click="emit('delete')">삭제</button>
          <button type="button" class="btn btn-sm" @click="confirming = ''">취소</button>
        </div>
        <div v-else class="confirm">
          <button v-if="!draft.end_date" type="button" class="btn btn-danger-outline btn-sm" :disabled="dirty" @click="askEnd">종영 처리</button>
          <button v-else type="button" class="btn btn-sm" :disabled="busy || dirty" @click="emit('resume')">종영 취소</button>
          <button type="button" class="btn btn-ghost-danger btn-sm" :disabled="dirty" @click="confirming = 'delete'">삭제</button>
          <span v-if="dirty" class="muted small">저장하지 않은 변경이 있으면 먼저 저장해 주세요.</span>
          <span v-else-if="isEnded" class="muted small">종영한 프로그램입니다. 목록에서는 "종영 포함"을 켜야 보입니다.</span>
        </div>
      </section>
    </div>
  </form>
</template>

<style scoped>
.form { display: flex; flex-direction: column; min-height: 0; height: 100%; }
.head {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-200);
  padding: var(--space-200) var(--space-300); border-bottom: 1px solid var(--color-border-normal);
}
.title { display: flex; align-items: center; gap: var(--space-100); min-width: 0; }
.title h2 {
  font-size: var(--text-300); line-height: var(--leading-300); font-weight: var(--font-weight-bold);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.head-actions { display: flex; gap: var(--space-100); }
.scroll { overflow: auto; padding: var(--space-200) var(--space-300) var(--space-500); display: grid; gap: var(--space-300); align-content: start; }
section { display: grid; gap: var(--space-150); }
h3 { font-size: var(--text-075); line-height: var(--leading-075); font-weight: var(--font-weight-bold); letter-spacing: var(--tracking-tight); }
h3 em, .field em { font-style: normal; font-weight: var(--font-weight-regular); margin-left: var(--space-075); }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-150) var(--space-200); }
.field { display: grid; gap: var(--space-050); align-content: start; }
.field > span { font-size: var(--text-050); line-height: var(--leading-050); color: var(--color-foreground-normal-100); font-weight: var(--font-weight-medium); }
.field.wide { grid-column: span 3; }
.seg { display: flex; gap: var(--space-200); height: var(--control-md); align-items: center; }
.field .check { height: var(--control-md); }
.hint { margin: 0; color: var(--color-foreground-hint-100); }
.aliases { display: flex; flex-wrap: wrap; gap: var(--space-075); align-items: center; }
.chip {
  display: inline-flex; align-items: center; gap: var(--space-025); height: var(--control-sm);
  padding: 0 var(--space-050) 0 var(--space-100); border-radius: var(--radius-300);
  background: var(--color-background-secondary-200); font-size: var(--text-050);
}
.chip-x {
  display: inline-grid; place-items: center; width: 20px; height: 20px; padding: 0;
  border: 0; border-radius: var(--radius-100); background: transparent; cursor: pointer;
  color: var(--color-foreground-hint-200);
}
.chip-x:hover { color: var(--color-foreground-danger-100); }
.alias-input { width: 200px; }
.danger-zone { padding-top: var(--space-200); border-top: 1px solid var(--color-border-normal); }
.confirm { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-100); }
</style>
