-- 0003: 엑셀 연동
-- 1) programs.show_episode: 편성표·엑셀에 회차(_N화)를 붙일지. 예: 963 음악쌀롱은 회차 없이 표시
-- 2) schedule_cells.source에 'import'(엑셀에서 가져온 칸) 추가.
--    가져온 칸은 사람이 고친 칸처럼 다시 생성해도 지우지 않지만, 화면에서는 따로 표시한다.
--    SQLite는 CHECK 제약을 바꿀 수 없어 표를 새로 만들어 옮긴다.

ALTER TABLE programs ADD COLUMN show_episode INTEGER NOT NULL DEFAULT 1 CHECK (show_episode IN (0, 1));

-- 고정 편성(굿모닝!/굿바이!)은 회차를 표시하지 않는다
UPDATE programs SET show_episode = 0
WHERE id IN (SELECT value FROM settings, json_each(settings.value_json) WHERE settings.key = 'fixed_program_ids');

CREATE TABLE schedule_cells_new (
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL,
  hour INTEGER NOT NULL CHECK (hour BETWEEN 6 AND 22),
  program_id TEXT NOT NULL REFERENCES programs(id),
  kind TEXT NOT NULL CHECK (kind IN ('본방', '재방')),
  source TEXT NOT NULL DEFAULT 'rule' CHECK (source IN ('rule', 'manual', 'import')),
  exception_type TEXT CHECK (exception_type IN ('결방대체', '교체', '특집')),
  original_program_id TEXT REFERENCES programs(id),
  original_slot_id TEXT REFERENCES program_slots(id),
  rerun_episode_override INTEGER,
  prep_status TEXT NOT NULL DEFAULT '미입고' CHECK (prep_status IN ('미입고', '입고', '송출완료')),
  actual_change_note TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (date, hour)
);
INSERT INTO schedule_cells_new SELECT id, date, hour, program_id, kind, source, exception_type,
  original_program_id, original_slot_id, rerun_episode_override, prep_status, actual_change_note,
  created_at, updated_at FROM schedule_cells;
DROP TABLE schedule_cells;
ALTER TABLE schedule_cells_new RENAME TO schedule_cells;
CREATE INDEX idx_schedule_cells_program ON schedule_cells(program_id, date, hour);
