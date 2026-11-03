import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteSingleFile } from 'vite-plugin-singlefile'

// 빌드 결과를 index.html 한 파일로 묶는다.
// 앱은 이 파일을 file:// 로 직접 열기 때문에 로컬 서버(포트)가 필요 없다.
export default defineConfig({
  plugins: [vue(), viteSingleFile()],
  base: './',
  server: { port: 5173, strictPort: true },
})
