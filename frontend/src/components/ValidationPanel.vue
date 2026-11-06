<script setup>
// 오른쪽 패널: 월 총 방송분, 확인할 것 목록, 범례.
// P3: 생성 때 발견한 편성 자리 충돌만 보여준다. 전체 검증(빈칸·본방 대기·비율 등)은 P5에서 채운다.
const props = defineProps({
  month: { type: Number, required: true },
  totals: { type: Object, required: true },
  issues: { type: Array, default: () => [] },   // [{ kind, level: error|warn, detail, key? }]
})
const emit = defineEmits(['jump'])

const fmt = (n) => n.toLocaleString('ko-KR')
</script>

<template>
  <aside class="panel">
    <div class="total">
      <span>{{ month }}월 총 방송</span>
      <b>{{ fmt(totals.minutes) }}분</b>
      <span class="muted">/ 기준 {{ fmt(totals.expected_minutes) }}분</span>
    </div>

    <div class="sep" />
    <h2>확인할 것 {{ issues.length }}건</h2>
    <ul v-if="issues.length" class="issues">
      <li v-for="(it, i) in issues" :key="i">
        <button class="issue" :class="it.level" :disabled="!it.key" @click="it.key && emit('jump', it.key)">
          <span class="it">{{ it.kind }}</span>
          <span class="id">{{ it.detail }}</span>
        </button>
      </li>
    </ul>
    <p v-else class="muted small">지금 확인할 것이 없습니다.</p>

    <div class="sep" />
    <h2>범례</h2>
    <div class="legend">
      <div><span class="sw edu on" />교양 본방 자리</div>
      <div><span class="sw edu re" />교양 재방 자리</div>
      <div><span class="sw ent on" />오락 본방 자리</div>
      <div><span class="sw ent re" />오락 재방 자리</div>
      <div><span class="newname">빨간 이름</span>회차가 올라간 칸</div>
      <div><span class="sw special" />특집</div>
      <div><span class="sw fixed" />고정 편성</div>
      <div><span class="sw waiting" />본방 대기</div>
      <div><span class="sw manual" />직접 수정한 칸</div>
      <div><span class="dotx in" />송출 파일 입고</div>
      <div><span class="dotx done" />송출 완료</div>
    </div>
  </aside>
</template>

<style scoped>
.panel {
  overflow: auto; padding: var(--space-200); background: var(--color-background-canvas-100);
  border-left: 1px solid var(--color-border-normal);
}
.total { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-050); font-size: var(--text-050); }
.total b { font-size: var(--text-100); font-weight: var(--font-weight-bold); }
.sep { height: 1px; background: var(--color-border-normal); margin: var(--space-200) 0; }
h2 { font-size: var(--text-075); font-weight: var(--font-weight-bold); margin-bottom: var(--space-100); color: var(--color-foreground-normal-100); }
.issues { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-100); }
.issue {
  position: relative; display: grid; gap: var(--space-025); width: 100%; text-align: left; cursor: pointer;
  padding: var(--space-100) var(--space-150); border-radius: var(--radius-300);
  border: 1px solid var(--color-border-warning); background: var(--color-background-warning-100);
}
.issue.error { border-color: var(--color-border-danger); background: var(--color-background-danger-100); }
.issue.error .it { color: var(--color-foreground-danger-200); }
.issue:disabled { cursor: default; }
.issue::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.issue:not(:disabled):hover::before { opacity: var(--overlay-hover-dense); }
.it { font-weight: var(--font-weight-bold); font-size: var(--text-050); color: var(--color-foreground-warning-200); }
.id { font-size: var(--text-050); line-height: var(--leading-050); color: var(--color-foreground-normal-100); }
.legend { display: grid; gap: var(--space-075); font-size: var(--text-050); color: var(--color-foreground-normal-100); }
.legend div { display: flex; align-items: center; gap: var(--space-100); }
.sw { position: relative; width: 22px; height: 14px; border-radius: var(--radius-100); overflow: hidden; background: var(--color-background-canvas-100); }
.sw::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }
.sw.edu.on { background: var(--cell-edu-on); } .sw.edu.re { background: var(--cell-edu-re); } .sw.edu::before { background: var(--cell-edu-bar); }
.sw.ent.on { background: var(--cell-ent-on); } .sw.ent.re { background: var(--cell-ent-re); } .sw.ent::before { background: var(--cell-ent-bar); }
.sw.special { background: var(--cell-special-bg); } .sw.special::before { background: var(--cell-special-bar); }
.sw.fixed { background: var(--cell-fixed-bg); } .sw.fixed::before { background: var(--cell-fixed-bar); }
.sw.waiting { background: var(--cell-waiting-bg); } .sw.waiting::before { background: var(--cell-waiting-bar); }
.dotx { width: 6px; height: 6px; margin: 0 8px; border-radius: var(--radius-pill); }
.dotx.in { background: var(--color-background-success-200); }
.dotx.done { background: var(--color-foreground-hint-100); }
.newname { color: var(--cell-new-episode); font-weight: var(--font-weight-bold); }
.sw.manual { box-shadow: inset 0 0 0 1.5px var(--cell-manual-ring); }
</style>
