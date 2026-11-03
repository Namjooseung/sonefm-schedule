<script setup>
// 설정 화면 — 지금은 데이터 파일 정보만 보여준다. 나머지 설정 항목은 P5·P7에서 추가.
import { onMounted, ref } from 'vue'
import { ping } from '../api.js'

const info = ref(null)
onMounted(async () => { info.value = await ping() })
</script>

<template>
  <section class="page">
    <h1>설정</h1>
    <div class="card body">
      <h2>데이터 파일</h2>
      <p v-if="!info" class="muted">불러오는 중입니다…</p>
      <p v-else-if="!info.ok" class="callout callout-danger">{{ info.errors?.[0] || info.message }}</p>
      <dl v-else>
        <dt>위치</dt><dd>{{ info.db_path }}</dd>
        <dt>앱 버전</dt><dd>{{ info.app_version }}</dd>
        <dt>데이터 구조 버전</dt><dd>{{ info.schema_version }}</dd>
      </dl>
    </div>
  </section>
</template>

<style scoped>
.page { padding: var(--space-300); display: grid; gap: var(--space-200); align-content: start; max-width: 880px; }
h1 { font-size: var(--text-400); line-height: var(--leading-400); font-weight: var(--font-weight-bold); }
h2 { font-size: var(--text-100); line-height: var(--leading-100); font-weight: var(--font-weight-medium); }
.body { padding: var(--space-300); display: grid; gap: var(--space-150); }
dl { display: grid; grid-template-columns: 140px 1fr; gap: var(--space-100) var(--space-200); margin: 0; }
dt { color: var(--color-foreground-hint-100); }
dd { margin: 0; word-break: break-all; }
</style>
