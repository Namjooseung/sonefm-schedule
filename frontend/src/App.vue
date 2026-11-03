<script setup>
// P0 뼈대 화면: Python ↔ 화면 왕복 호출만 확인한다. 스타일은 P3에서 DESIGN.md 기준으로 입힌다.
import { onMounted, ref } from 'vue'
import { ping } from './api.js'

const info = ref(null)
const error = ref('')

onMounted(async () => {
  try {
    info.value = await ping()
  } catch (e) {
    error.value = '프로그램 내부와 연결하지 못했습니다. 프로그램을 다시 실행해 주세요.'
  }
})
</script>

<template>
  <main>
    <h1>SoneFM 편성표</h1>
    <p v-if="error">{{ error }}</p>
    <dl v-else-if="info">
      <dt>연결 상태</dt><dd>{{ info.message }}</dd>
      <dt>앱 버전</dt><dd>{{ info.app_version }}</dd>
      <dt>데이터 파일</dt><dd>{{ info.db_path }}</dd>
      <dt>스키마 버전</dt><dd>{{ info.schema_version }}</dd>
    </dl>
    <p v-else>연결 중입니다…</p>
  </main>
</template>
