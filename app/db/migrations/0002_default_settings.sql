-- 0002: 운영 기본값과 고정 편성 프로그램
-- - 굿모닝!(06시), 굿바이!(22시): 매일 본방 편성 자리를 가진 일반 프로그램
-- - settings: 방송 없는 주 처리 기본값, 부정기 누락 경고 횟수, 고정 편성 목록
-- 이미 같은 이름의 프로그램·같은 키의 설정이 있으면 건드리지 않는다.

-- UUID v4 문자열은 행마다 새로 계산되도록 식을 그대로 쓴다.

INSERT INTO programs (id, name, category, is_listener_participation, producer_type, cycle_type,
                      start_episode, is_special, memo)
SELECT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-' || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))), '굿모닝!', '오락', 0, '자체', 'weekly', 1, 0, '매일 06시 고정 편성'
WHERE NOT EXISTS (SELECT 1 FROM programs WHERE name = '굿모닝!');

INSERT INTO programs (id, name, category, is_listener_participation, producer_type, cycle_type,
                      start_episode, is_special, memo)
SELECT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-' || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))), '굿바이!', '오락', 0, '자체', 'weekly', 1, 0, '매일 22시 고정 편성'
WHERE NOT EXISTS (SELECT 1 FROM programs WHERE name = '굿바이!');

-- 편성 자리: 월~일 매일 (자리가 하나도 없을 때만)
INSERT INTO program_slots (id, program_id, weekday, hour, role, valid_from)
WITH RECURSIVE wd(n) AS (SELECT 0 UNION ALL SELECT n + 1 FROM wd WHERE n < 6),
     fixed(name, hour) AS (VALUES ('굿모닝!', 6), ('굿바이!', 22))
SELECT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-' || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))), p.id, wd.n, fixed.hour, '본방', '2000-01-01'
FROM fixed JOIN programs p ON p.name = fixed.name CROSS JOIN wd
WHERE NOT EXISTS (SELECT 1 FROM program_slots s WHERE s.program_id = p.id);

INSERT OR IGNORE INTO settings (id, key, value_json) VALUES
  ((lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-' || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))), 'offweek_policy_default', '"rerun"'),
  ((lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-' || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))), 'irregular_missing_warn_count', '4'),
  ((lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))), 2) || '-' || substr('89ab', 1 + (abs(random()) % 4), 1) || substr(lower(hex(randomblob(2))), 2) || '-' || lower(hex(randomblob(6)))), 'fixed_program_ids',
   (SELECT json_group_array(id) FROM (SELECT id FROM programs WHERE name IN ('굿모닝!', '굿바이!')
                                      ORDER BY name = '굿바이!')));
