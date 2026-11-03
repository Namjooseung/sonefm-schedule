<script setup>
// 한 주 = 월~일 7열 × 06~22시 17행.
// - 고정 편성(굿모닝!/굿바이!)이 7일 모두 그대로면 한 줄 띠로 크게 그린다.
// - 소속 달이 아닌 날짜는 흐리게, 참고 줄(직전 달 마지막 주)은 전체를 흐리게 + 읽기 전용.
import { computed } from 'vue'

const props = defineProps({
  week: { type: Object, required: true },
  cells: { type: Object, required: true },   // 'YYYY-MM-DD|시' → 칸 정보
  hours: { type: Array, required: true },
  today: { type: String, required: true },
  selected: { type: String, default: '' },
})
const emit = defineEmits(['goto-month', 'select'])

const cellAt = (date, hour) => props.cells[`${date}|${hour}`]

// 고정 편성 띠: 그 시각의 7칸이 모두 같은 고정 프로그램이고 사람이 손대지 않았을 때
const bands = computed(() => {
  const out = {}
  for (const h of props.hours) {
    const cs = props.week.days.map((d) => cellAt(d.date, h))
    if (cs.every((c) => c && c.is_fixed && !c.manual && c.program_id === cs[0].program_id)) {
      out[h] = cs[0].name
    }
  }
  return out
})

function cellClass(c, day) {
  if (!c) return ['empty', { out: !day.in_month && !props.week.is_reference }]
  return [
    c.is_special ? 'special' : c.is_fixed ? 'fixed' : c.category === '교양' ? 'edu' : 'ent',
    c.kind === '본방' ? 'on' : 're',
    { manual: c.manual, waiting: c.waiting, out: !day.in_month && !props.week.is_reference },
  ]
}

function episodeText(c) {
  if (c.waiting) return '본방 대기'
  if (c.is_fixed || c.is_special || c.episode == null) return ''
  return `${c.episode}화`
}

function titleText(c, day, h) {
  if (!c) return `${day.month}/${day.day}(${day.weekday}) ${h}시 · 빈칸`
  const parts = [`${day.month}/${day.day}(${day.weekday}) ${h}시`, c.name, c.kind]
  const ep = episodeText(c)
  if (ep) parts.push(ep)
  if (c.missing_warn) parts.push('본방 입력 누락?')
  if (c.manual) parts.push('직접 수정한 칸')
  return parts.join(' · ')
}

function onSelect(day, h) {
  if (props.week.is_reference) return
  emit('select', `${day.date}|${h}`)
}

const refMonth = computed(() => props.week.days[0].month)
const isEmpty = computed(() => props.week.days.every((d) => props.hours.every((h) => !cellAt(d.date, h))))
const collapsed = computed(() => props.week.is_reference && isEmpty.value)
</script>

<template>
  <section class="weekrow week card" :class="{ ref: week.is_reference }" :aria-label="`${week.label} ${week.iso_week}주차`">
    <div v-if="week.is_reference" class="ref-note">
      {{ refMonth }}월 마지막 주 (참고용, 읽기 전용){{ collapsed ? ' — 아직 비어 있습니다' : '' }} ·
      <button class="link" @click="emit('goto-month', refMonth)">{{ refMonth }}월에서 편집</button>
    </div>
    <div v-if="!collapsed" class="head">
      <div class="wk"><b>{{ week.label }}</b><span>{{ week.iso_week }}주차</span></div>
      <div
        v-for="(d, i) in week.days" :key="d.date" class="dh"
        :class="{ sat: i === 5, sun: i === 6 || d.holiday, out: !d.in_month && !week.is_reference, today: d.date === today }"
      >
        <b>{{ d.month }}.{{ d.day }}</b><span>{{ d.weekday }}</span>
        <em v-if="d.holiday" :title="d.holiday">{{ d.holiday }}</em>
      </div>
    </div>
    <div v-if="!collapsed" class="grid">
      <template v-for="h in hours" :key="h">
        <div class="hr">{{ String(h).padStart(2, '0') }}</div>
        <div v-if="bands[h]" class="band" :title="`매일 ${String(h).padStart(2, '0')}:00 고정 편성`">
          <b>{{ bands[h] }}</b><span>매일 {{ String(h).padStart(2, '0') }}:00 · 고정 편성</span>
        </div>
        <template v-else>
          <div
            v-for="d in week.days" :key="d.date" class="c"
            :class="[cellClass(cellAt(d.date, h), d), { sel: selected === `${d.date}|${h}` }]"
            :title="titleText(cellAt(d.date, h), d, h)"
            @click="onSelect(d, h)"
          >
            <template v-if="cellAt(d.date, h)">
              <span class="n">{{ cellAt(d.date, h).name }}</span>
              <span v-if="cellAt(d.date, h).missing_warn" class="warn">누락?</span>
              <span v-if="cellAt(d.date, h).kind === '재방' && !cellAt(d.date, h).waiting" class="r">재</span>
              <span v-if="episodeText(cellAt(d.date, h))" class="e">{{ episodeText(cellAt(d.date, h)) }}</span>
            </template>
          </div>
        </template>
      </template>
    </div>
  </section>
</template>

<style scoped>
.week { overflow: hidden; }
.week.ref .head, .week.ref .grid { opacity: var(--dim-reference); }
.week.ref .ref-note:last-child { border-bottom: 0; }
.ref-note {
  padding: var(--space-075) var(--space-150); font-size: var(--text-050); line-height: var(--leading-050);
  color: var(--color-foreground-normal-100); background: var(--color-background-secondary-100);
  border-bottom: 1px solid var(--color-border-normal);
}
.link {
  border: 0; background: none; padding: 0; cursor: pointer; font-weight: var(--font-weight-medium);
  color: var(--color-foreground-primary-100); text-decoration: underline; text-underline-offset: 2px;
}
.head, .grid { display: grid; grid-template-columns: 52px repeat(7, minmax(0, 1fr)); }
.head { background: var(--color-background-secondary-100); border-bottom: 1px solid var(--color-border-normal); }
.wk { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: var(--space-050) 0; }
.wk b { font-size: var(--text-050); line-height: var(--leading-050); font-weight: var(--font-weight-heavy); }
.wk span { font-size: var(--text-025); line-height: var(--leading-025); color: var(--color-foreground-hint-100); }
.dh {
  display: flex; align-items: baseline; gap: var(--space-075); min-width: 0;
  padding: var(--space-075) var(--space-100); border-left: 1px solid var(--cell-line);
}
.dh b { font-size: var(--text-075); font-weight: var(--font-weight-bold); }
.dh span { font-size: var(--text-050); color: var(--color-foreground-hint-100); }
.dh em {
  margin-left: auto; font-style: normal; font-size: var(--text-025); line-height: var(--leading-025);
  color: var(--color-weekday-sun); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;
}
.dh.sat span { color: var(--color-weekday-sat); }
.dh.sun span, .dh.sun b { color: var(--color-weekday-sun); }
.dh.out { opacity: var(--dim-out-of-month); }
.dh.today b { color: var(--color-foreground-primary-200); text-decoration: underline; text-underline-offset: 3px; }

.hr {
  display: flex; align-items: center; justify-content: flex-end; padding: 0 var(--space-100);
  font-size: var(--text-050); color: var(--color-foreground-hint-100); border-top: 1px solid var(--cell-line);
}
.c {
  position: relative; display: flex; align-items: center; gap: var(--space-050); min-width: 0;
  height: var(--row-height, var(--cell-height)); padding: 0 var(--space-100) 0 var(--space-150);
  border-left: 1px solid var(--cell-line); border-top: 1px solid var(--cell-line); cursor: pointer;
}
.c::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }
.c::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.c:hover::after { opacity: var(--overlay-hover-dense); }
.c .n { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: var(--font-weight-medium); }
.c .e { flex: none; font-size: var(--text-050); color: var(--color-foreground-normal-100); }
.c .r {
  flex: none; font-size: var(--text-025); line-height: 14px; padding: 0 3px; border-radius: var(--radius-100);
  box-shadow: inset 0 0 0 1px currentColor; font-weight: var(--font-weight-bold);
}
.c .warn {
  flex: none; font-size: var(--text-025); line-height: 14px; padding: 0 var(--space-050); border-radius: var(--radius-100);
  background: var(--color-background-warning-100); color: var(--color-foreground-warning-200); font-weight: var(--font-weight-bold);
}
.c.edu.on { background: var(--cell-edu-on); }
.c.edu.re { background: var(--cell-edu-re); }
.c.edu::before { background: var(--cell-edu-bar); }
.c.edu .r { color: var(--color-category-edu-fg); }
.c.ent.on { background: var(--cell-ent-on); }
.c.ent.re { background: var(--cell-ent-re); }
.c.ent::before { background: var(--cell-ent-bar); }
.c.ent .r { color: var(--color-category-ent-fg); }
.c.re .n { font-weight: var(--font-weight-regular); color: var(--color-foreground-normal-100); }
.c.special { background: var(--cell-special-bg); }
.c.special::before { background: var(--cell-special-bar); }
.c.special .n { color: var(--color-special-fg); }
.c.fixed { background: var(--cell-fixed-bg); }
.c.fixed::before { background: var(--cell-fixed-bar); }
.c.waiting { background: var(--cell-waiting-bg); }
.c.waiting::before { background: var(--cell-waiting-bar); }
.c.waiting .e { color: var(--color-foreground-danger-200); font-weight: var(--font-weight-bold); }
.c.manual { box-shadow: inset 0 0 0 1.5px var(--cell-manual-ring); }
.c.out { opacity: var(--dim-out-of-month); }
.c.sel { outline: 2px solid var(--color-foreground-normal-200); outline-offset: -2px; z-index: 1; }
.week.ref .c { cursor: default; }

.band {
  grid-column: 2 / -1; position: relative; display: flex; align-items: center; gap: var(--space-150);
  height: var(--row-height, var(--cell-height)); padding: 0 var(--space-200);
  background: var(--cell-fixed-bg); border-top: 1px solid var(--cell-line); border-left: 1px solid var(--cell-line);
}
.band::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--cell-fixed-bar); }
.band b { font-size: var(--text-100); font-weight: var(--font-weight-heavy); color: var(--color-foreground-normal-100); }
.band span { font-size: var(--text-050); color: var(--color-foreground-hint-100); }

</style>

<style>
/* 압축 보기 (ScheduleView 최상위의 .compact 클래스에 반응). scoped 밖에 둔다 */
.compact .weekrow .c .e, .compact .weekrow .c .r { font-size: var(--text-025); }
.compact .weekrow .c .n { font-size: var(--text-050); }
.compact .weekrow .band b { font-size: var(--text-075); }
.compact .weekrow .band span { display: none; }
.compact .weekrow .hr { font-size: var(--text-025); }
</style>
