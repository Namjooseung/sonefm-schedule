"""P3 완료 조건(백엔드): 11월을 빈 상태에서 열고 버튼 두 번(첫 주 불러오기, 월단위 생성)으로 한 달 편성."""
from datetime import date

import pytest

from app.config import migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations
from app.repository._common import new_id, now_iso
from app.services import programs as program_svc
from app.services import schedule as svc


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "s.db")
    apply_migrations(c, migrations_dir())
    yield c
    c.close()


def _slot(weekday, hour, role="본방", valid_from="2026-01-05"):
    return {"weekday": weekday, "hour": hour, "role": role, "valid_from": valid_from}


def _register(conn):
    a = program_svc.save_program(conn, {"name": "마을살이 정류장", "category": "교양", "cycle_type": "weekly",
                                        "start_episode": 41, "slots": [_slot(1, 11), _slot(5, 18, "재방")]})
    b = program_svc.save_program(conn, {"name": "수원은 지금", "category": "교양", "cycle_type": "biweekly",
                                        "start_episode": 75, "cycle_anchor_date": "2026-11-03",
                                        "slots": [_slot(1, 10)]})
    assert a["ok"] and b["ok"]
    return a["program"]["id"], b["program"]["id"]


def test_빈_11월은_칸이_없고_참고줄은_10월_마지막_주(conn):
    m = svc.get_month(conn, 2026, 11)
    assert m["ok"] and m["cells"] == {} and m["status"] == "미작성"
    assert m["reference_week"]["monday"] == "2026-10-26"
    assert [w["label"] for w in m["weeks"]] == ["1주", "2주", "3주", "4주", "5주"]
    assert m["weeks"][0]["iso_week"] == 45
    last_week_days = m["weeks"][-1]["days"]
    assert [d["in_month"] for d in last_week_days] == [True] + [False] * 6   # 12/1~6 흐리게
    assert m["totals"]["expected_minutes"] == 30 * 17 * 60


def test_버튼_두번으로_한달_편성(conn):
    a, b = _register(conn)
    r1 = svc.generate(conn, 2026, 11, "first_week")
    assert r1["ok"] and r1["changed"] > 0
    m = svc.get_month(conn, 2026, 11)
    assert m["first_week_filled"] and m["status"] == "작성중"
    assert "2026-11-10|11" not in m["cells"]          # 아직 첫 주만

    r2 = svc.generate(conn, 2026, 11, "rest")
    assert r2["ok"]
    m = svc.get_month(conn, 2026, 11)
    c = m["cells"]
    assert c["2026-11-03|11"]["name"] == "마을살이 정류장" and c["2026-11-03|11"]["episode"] == 41
    assert c["2026-11-10|11"]["episode"] == 42
    assert c["2026-11-07|18"]["kind"] == "재방" and c["2026-11-07|18"]["episode"] == 41
    assert [c[f"2026-11-{d}|10"]["kind"] for d in ("03", "10", "17")] == ["본방", "재방", "본방"]
    assert c["2026-11-10|10"]["episode"] == 75 and c["2026-11-17|10"]["episode"] == 76
    # 고정 편성은 매일, 화면에서 띠로 그릴 수 있게 표시
    assert c["2026-11-08|6"]["name"] == "굿모닝!" and c["2026-11-08|6"]["is_fixed"]
    assert c["2026-12-06|22"]["name"] == "굿바이!"
    # 11월 달력 날짜만 집계 (11/1은 10월 소속 주라 아직 비어 있음)
    assert m["totals"]["minutes"] > 0


def test_다시_생성하면_바뀐게_없음(conn):
    _register(conn)
    svc.generate(conn, 2026, 11, "all")
    again = svc.generate(conn, 2026, 11, "all")
    assert again["changed"] == 0


def test_손댄_칸은_유지하고_확인목록_덮어쓰기(conn):
    a, _ = _register(conn)
    svc.generate(conn, 2026, 11, "all")
    sp = program_svc.create_special(conn, {"name": "가을 음악회 특집", "category": "오락"})["program"]["id"]
    ts = now_iso()
    conn.execute("UPDATE schedule_cells SET program_id = ?, source = 'manual', exception_type = '특집',"
                 " updated_at = ? WHERE date = '2026-11-10' AND hour = 11", (sp, ts))

    r = svc.generate(conn, 2026, 11, "rest")
    assert r["manual_conflicts"] == [{"date": "2026-11-10", "hour": 11,
                                      "current": "가을 음악회 특집", "rule": "마을살이 정류장"}]
    m = svc.get_month(conn, 2026, 11)
    assert m["cells"]["2026-11-10|11"]["name"] == "가을 음악회 특집"
    assert m["cells"]["2026-11-10|11"]["manual"]
    # 특집 때문에 11/10 본방이 없으니 11/17이 42화를 이어받음 (결방 이어받기)
    assert m["cells"]["2026-11-17|11"]["episode"] == 42

    r = svc.generate(conn, 2026, 11, "rest", overwrite_manual=True)
    assert r["overwritten"]
    m = svc.get_month(conn, 2026, 11)
    assert m["cells"]["2026-11-10|11"]["name"] == "마을살이 정류장"
    assert not m["cells"]["2026-11-10|11"]["manual"]


def test_마감된_달은_생성_불가(conn):
    ts = now_iso()
    conn.execute("INSERT INTO month_plans (id, year_month, status, created_at, updated_at)"
                 " VALUES (?, '2026-11', '마감', ?, ?)", (new_id(), ts, ts))
    assert not svc.generate(conn, 2026, 11, "all")["ok"]


def test_자리_충돌_보고(conn):
    program_svc.save_program(conn, {"name": "새벽 특강", "category": "교양", "cycle_type": "weekly",
                                    "slots": [_slot(0, 6)]})
    r = svc.generate(conn, 2026, 11, "first_week")
    assert r["slot_conflicts"] and set(r["slot_conflicts"][0]["programs"]) == {"굿모닝!", "새벽 특강"}


def test_공휴일_표시(conn):
    m = svc.get_month(conn, 2026, 10)
    days = {d["date"]: d for w in m["weeks"] for d in w["days"]}
    assert days["2026-10-09"]["holiday"] == "한글날"


def test_잘못된_달(conn):
    assert not svc.get_month(conn, 2026, 13)["ok"]
    assert not svc.generate(conn, 2026, 11, "엉뚱")["ok"]


def test_월_경계_참고줄에_10월_칸이_보임(conn):
    _register(conn)
    svc.generate(conn, 2026, 10, "all")
    m = svc.get_month(conn, 2026, 11)
    assert m["cells"]["2026-10-27|11"]["name"] == "마을살이 정류장"
    assert m["cells"]["2026-11-01|6"]["name"] == "굿모닝!"   # 11/1은 10월에서 생성됨
    assert date.fromisoformat("2026-11-01").weekday() == 6
