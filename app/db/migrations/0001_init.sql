-- 0001: 초기 스키마 (PLAN.md 4장)
-- 이 파일은 적용 후 수정하지 않는다. 변경은 0002_*.sql 부터 새 파일로.
-- 모든 테이블: id(UUID 문자열), created_at, updated_at (ISO8601 UTC)

-- 프로그램
CREATE TABLE programs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('교양', '오락')),
  is_listener_participation INTEGER NOT NULL DEFAULT 0 CHECK (is_listener_participation IN (0, 1)),
  producer_type TEXT NOT NULL DEFAULT '자체' CHECK (producer_type IN ('자체', '타공동체라디오', '외부')),
  cycle_type TEXT NOT NULL CHECK (cycle_type IN ('weekly', 'biweekly', 'multi_weekly', 'monthly_nth', 'irregular', 'oneoff')),
  cycle_anchor_date TEXT,                 -- 격주·월 n회 판정 기준일 (YYYY-MM-DD)
  monthly_nth INTEGER CHECK (monthly_nth BETWEEN 1 AND 5),
  offweek_policy TEXT CHECK (offweek_policy IN ('rerun', 'empty')),  -- NULL이면 settings 기본값
  start_episode INTEGER NOT NULL DEFAULT 1,
  start_date TEXT,
  end_date TEXT,
  host TEXT,
  cohort TEXT,                            -- 기수(방송활동가)
  is_special INTEGER NOT NULL DEFAULT 0 CHECK (is_special IN (0, 1)),
  memo TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 별칭 (엑셀 가져오기 매칭용)
CREATE TABLE program_aliases (
  id TEXT PRIMARY KEY,
  program_id TEXT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  alias TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX idx_program_aliases_program ON program_aliases(program_id);

-- 편성 자리 (개편 이력 포함: 적용 시작일~종료일)
CREATE TABLE program_slots (
  id TEXT PRIMARY KEY,
  program_id TEXT NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),   -- 0=월 .. 6=일
  hour INTEGER NOT NULL CHECK (hour BETWEEN 6 AND 22),
  role TEXT NOT NULL CHECK (role IN ('본방', '재방')),
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX idx_program_slots_program ON program_slots(program_id);
CREATE INDEX idx_program_slots_when ON program_slots(weekday, hour);

-- 월 상태
CREATE TABLE month_plans (
  id TEXT PRIMARY KEY,
  year_month TEXT NOT NULL UNIQUE,        -- '2026-11'
  status TEXT NOT NULL DEFAULT '작성중' CHECK (status IN ('작성중', '확정', '마감')),
  generated_at TEXT,
  confirmed_at TEXT,
  closed_at TEXT,
  unlock_reason TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 편성 칸 (날짜·시각당 1행). 회차는 저장하지 않고 계산한다.
CREATE TABLE schedule_cells (
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL,                     -- YYYY-MM-DD
  hour INTEGER NOT NULL CHECK (hour BETWEEN 6 AND 22),
  program_id TEXT NOT NULL REFERENCES programs(id),
  kind TEXT NOT NULL CHECK (kind IN ('본방', '재방')),
  source TEXT NOT NULL DEFAULT 'rule' CHECK (source IN ('rule', 'manual')),
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
CREATE INDEX idx_schedule_cells_program ON schedule_cells(program_id, date, hour);

-- 결방 기록 (회차 계산에서 제외할 원래 칸)
CREATE TABLE cancellations (
  id TEXT PRIMARY KEY,
  program_id TEXT NOT NULL REFERENCES programs(id),
  original_date TEXT NOT NULL,
  original_hour INTEGER NOT NULL CHECK (original_hour BETWEEN 6 AND 22),
  reason TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (program_id, original_date, original_hour)
);

-- 공휴일 (라이브러리 + 수동 임시공휴일)
CREATE TABLE holidays (
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL,
  name TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('library', 'manual')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (date, source)
);

-- 변경 기록
CREATE TABLE change_log (
  id TEXT PRIMARY KEY,
  at TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX idx_change_log_at ON change_log(at);

-- 운영 설정 (비율 기준, 고정 편성, 경고 횟수 등)
CREATE TABLE settings (
  id TEXT PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  value_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
