// window.pywebview.api 래퍼.
// 화면 코드는 이 파일의 함수만 호출하고 pywebview를 직접 만지지 않는다.
// 모든 함수는 { ok: true, ... } 또는 { ok: false, errors: [한국어 문구] } 를 돌려준다.

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
  try {
    const api = await ready()
    return await api[name](...args)
  } catch (e) {
    console.error(name, e)
    return { ok: false, errors: ['프로그램 내부와 연결하지 못했습니다. 프로그램을 다시 실행해 주세요.'] }
  }
}

/** 연결 확인: 앱 버전, DB 경로, 스키마 버전 */
export const ping = () => call('ping')

// ── 프로그램 ──
export const programChoices = () => call('program_choices')
export const listPrograms = (query = '', includeEnded = false) => call('list_programs', query, includeEnded)
export const getProgram = (id) => call('get_program', id)
export const saveProgram = (payload) => call('save_program', payload)
export const endProgram = (id, endDate) => call('end_program', id, endDate)
export const resumeProgram = (id) => call('resume_program', id)
export const deleteProgram = (id) => call('delete_program', id)
export const createSpecial = (payload) => call('create_special', payload)
