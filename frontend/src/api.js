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

// ── 편성표 ──
export const getMonth = (year, month) => call('get_month', year, month)
/** scope: 'first_week' | 'rest' | 'all' */
export const generateMonth = (year, month, scope, overwriteManual = false) =>
  call('generate_month', year, month, scope, overwriteManual)

// ── 칸 편집 ── (scope: 'once' 이번만 | 'after' 이후 전부)
export const getCell = (date, hour) => call('get_cell', date, hour)
export const cellSetKind = (date, hour, kind, scope = 'once') => call('cell_set_kind', date, hour, kind, scope)
/** mode: 'rerun' 재방으로 대체 | 'empty' 비워두기 */
export const cellCancel = (date, hour, mode, reason = '') => call('cell_cancel', date, hour, mode, reason)
export const cellReplace = (date, hour, programId, kind, scope = 'once') => call('cell_replace', date, hour, programId, kind, scope)
export const cellSpecial = (date, hour, payload) => call('cell_special', date, hour, payload)
export const cellOverride = (date, hour, episode) => call('cell_override', date, hour, episode)
export const cellActual = (date, hour, note) => call('cell_actual', date, hour, note)
export const cellPrep = (date, hour, status) => call('cell_prep', date, hour, status)
export const cellRevert = (date, hour) => call('cell_revert', date, hour)
export const undo = () => call('undo')
export const listChangeLog = (limit = 200) => call('list_change_log', limit)

// ── 월 상태 ── action: 'confirm' 확정 | 'reopen' 확정 취소 | 'close' 마감 | 'unlock' 잠금 해제(사유 필수)
export const monthStatus = (year, month, action, reason = '') => call('month_status', year, month, action, reason)
