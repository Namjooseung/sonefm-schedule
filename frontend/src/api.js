// window.pywebview.api 래퍼.
// 화면 코드는 이 파일의 함수만 호출하고 pywebview를 직접 만지지 않는다.

function ready() {
  return new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) {
      resolve(window.pywebview.api)
      return
    }
    window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true })
  })
}

async function call(name, ...args) {
  const api = await ready()
  return api[name](...args)
}

/** 연결 확인: 앱 버전, DB 경로, 스키마 버전을 돌려받는다. */
export const ping = () => call('ping')
