-- 0004: '본방 입력 누락?' 경고 기능 삭제 (2026-11-03 사용자 요청) — 쓰지 않는 설정값 지우기
DELETE FROM settings WHERE key = 'irregular_missing_warn_count';
