<script setup>
// 앱 틀: 왼쪽 메뉴 + 본문. 화면 전환은 단순 상태값으로 한다 (라우터 불필요).
import { ref } from 'vue'
import ScheduleView from './views/ScheduleView.vue'
import ProgramsView from './views/ProgramsView.vue'
import SettingsView from './views/SettingsView.vue'

const MENUS = [
  { key: 'schedule', label: '편성표', view: ScheduleView },
  { key: 'programs', label: '프로그램', view: ProgramsView },
  { key: 'settings', label: '설정', view: SettingsView },
]
const LATER = ['방송일지', '보고서', '유튜브']

const current = ref('programs')
</script>

<template>
  <div class="app">
    <nav class="side" aria-label="메뉴">
      <div class="brand"><b>SoneFM</b><span>96.3</span></div>
      <button
        v-for="m in MENUS" :key="m.key" class="nav"
        :aria-current="current === m.key ? 'page' : undefined"
        @click="current = m.key"
      >{{ m.label }}</button>
      <div class="later" aria-label="준비 중인 메뉴">
        <div v-for="l in LATER" :key="l">{{ l }}</div>
      </div>
    </nav>
    <main class="main">
      <KeepAlive>
        <component :is="MENUS.find((m) => m.key === current).view" />
      </KeepAlive>
    </main>
  </div>
</template>

<style scoped>
.app { display: grid; grid-template-columns: 168px 1fr; height: 100vh; min-width: 1100px; }
.side {
  display: flex; flex-direction: column; gap: var(--space-050);
  padding: var(--space-200) var(--space-150);
  background: var(--color-background-canvas-100);
  border-right: 1px solid var(--color-border-normal);
}
.brand { display: flex; align-items: baseline; gap: var(--space-075); padding: 0 var(--space-100) var(--space-200); }
.brand b { font-size: var(--text-200); line-height: var(--leading-200); font-weight: var(--font-weight-heavy); }
.brand span { font-size: var(--text-050); color: var(--color-foreground-hint-100); }
.nav {
  position: relative; text-align: left; height: var(--control-md); padding: 0 var(--space-150);
  border: 0; border-radius: var(--radius-300); background: transparent; cursor: pointer;
  font-weight: var(--font-weight-medium); color: var(--color-foreground-normal-100);
}
.nav::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--color-overlay); opacity: 0; transition: opacity var(--motion-fast);
}
.nav:hover::before { opacity: var(--overlay-hover); }
.nav[aria-current="page"] { color: var(--color-foreground-primary-200); }
.later {
  margin-top: var(--space-200); padding: var(--space-100) var(--space-150) 0;
  border-top: 1px solid var(--color-border-normal);
  font-size: var(--text-050); line-height: var(--leading-050); color: var(--color-foreground-hint-100);
}
.later div { padding: var(--space-075) 0; opacity: var(--disabled-opacity); }
.main { min-width: 0; overflow: hidden; display: flex; flex-direction: column; }
</style>
