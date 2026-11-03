"""P1 완료 조건: 매주·격주·부정기 프로그램을 등록·수정·종영 처리할 수 있다."""
import pytest

from app.config import migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations
from app.repository import change_log_repo
from app.repository._common import new_id, now_iso
from app.services import programs as svc

TODAY = "2026-11-03"


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "s.db")
    apply_migrations(c, migrations_dir())
    yield c
    c.close()


def _slot(weekday, hour, role="본방", valid_from="2026-01-05", valid_to=None, id=None):
    return {"id": id, "weekday": weekday, "hour": hour, "role": role,
            "valid_from": valid_from, "valid_to": valid_to}


def _weekly(**kw):
    p = {"name": "마을살이 정류장", "category": "교양", "cycle_type": "weekly",
         "start_episode": 41, "start_date": "2026-01-05", "aliases": ["마을살이"],
         "slots": [_slot(1, 11), _slot(4, 19, "재방")]}
    p.update(kw)
    return p


def test_매주_등록(conn):
    r = svc.save_program(conn, _weekly())
    assert r["ok"], r
    p = r["program"]
    assert p["start_episode"] == 41
    assert p["aliases"] == ["마을살이"]
    assert [(s["weekday"], s["hour"], s["role"]) for s in p["slots"]] == [(1, 11, "본방"), (4, 19, "재방")]
    assert len(change_log_repo.list_for(conn, "program", p["id"])) == 1


def test_격주_등록_기준일_없으면_실패(conn):
    r = svc.save_program(conn, _weekly(name="수원은 지금", aliases=[], cycle_type="biweekly"))
    assert not r["ok"]
    r = svc.save_program(conn, _weekly(name="수원은 지금", aliases=[], cycle_type="biweekly",
                                       cycle_anchor_date="2026-11-05"))
    assert r["ok"]
    assert r["program"]["cycle_anchor_date"] == "2026-11-05"


def test_부정기_등록(conn):
    r = svc.save_program(conn, _weekly(name="[10기] 그 삶이다", aliases=[], cycle_type="irregular"))
    assert r["ok"] and r["program"]["cycle_type"] == "irregular"


def test_수정_자리_추가_변경_삭제(conn):
    p = svc.save_program(conn, _weekly())["program"]
    s_main, s_rerun = p["slots"]
    payload = _weekly(id=p["id"], host="홍길동", aliases=["마을살이", "정류장"], slots=[
        {**s_main, "valid_to": "2026-10-31"},          # 개편: 기존 본방 자리 종료
        _slot(2, 13, valid_from="2026-11-01"),          # 새 본방 자리
        # s_rerun 은 목록에서 빠짐 → 삭제
    ])
    r = svc.save_program(conn, payload)
    assert r["ok"], r
    q = r["program"]
    assert q["host"] == "홍길동"
    assert q["aliases"] == ["마을살이", "정류장"]
    ids = {s["id"] for s in q["slots"]}
    assert s_main["id"] in ids and s_rerun["id"] not in ids
    assert len(q["slots"]) == 2
    assert [e["action"] for e in change_log_repo.list_for(conn, "program", p["id"])] == ["등록", "수정"]


def test_이름이_다른_프로그램_별칭과_겹치면_실패(conn):
    svc.save_program(conn, _weekly())
    r = svc.save_program(conn, _weekly(name="마을살이", aliases=[], slots=[]))
    assert not r["ok"] and "마을살이" in r["errors"][0]


def test_종영_처리와_목록_숨김(conn):
    p = svc.save_program(conn, _weekly())["program"]
    r = svc.end_program(conn, p["id"], "2026-10-31")
    assert r["ok"], r
    assert r["program"]["end_date"] == "2026-10-31"
    assert all(s["valid_to"] == "2026-10-31" for s in r["program"]["slots"])

    assert svc.list_programs(conn, include_ended=False, today=TODAY) == []
    listed = svc.list_programs(conn, include_ended=True, today=TODAY)
    assert listed[0]["is_ended"] and listed[0]["slot_count"] == 2

    assert svc.resume_program(conn, p["id"])["ok"]
    assert svc.list_programs(conn, include_ended=False, today=TODAY)[0]["end_date"] is None


def test_종영일_형식_오류(conn):
    p = svc.save_program(conn, _weekly())["program"]
    assert not svc.end_program(conn, p["id"], "")["ok"]
    assert not svc.end_program(conn, p["id"], "2025-01-01")["ok"]  # 시작일보다 빠름


def test_검색은_이름과_별칭(conn):
    svc.save_program(conn, _weekly())
    svc.save_program(conn, _weekly(name="오후의 플레이리스트", category="오락", aliases=["오플"], slots=[]))
    assert [p["name"] for p in svc.list_programs(conn, "오플", today=TODAY)] == ["오후의 플레이리스트"]
    assert [p["name"] for p in svc.list_programs(conn, "정류장", today=TODAY)] == ["마을살이 정류장"]


def test_특집_빠른_등록(conn):
    r = svc.create_special(conn, {"name": "가을 음악회 실황 특집", "category": "오락"})
    assert r["ok"], r
    assert r["program"]["is_special"] and r["program"]["cycle_type"] == "oneoff"
    assert r["program"]["slots"] == []


def test_편성에_쓰인_프로그램은_삭제_불가_자리도_삭제_불가(conn):
    p = svc.save_program(conn, _weekly())["program"]
    slot_id = p["slots"][0]["id"]
    ts = now_iso()
    conn.execute(
        "INSERT INTO schedule_cells (id, date, hour, program_id, kind, original_slot_id,"
        " created_at, updated_at) VALUES (?, '2026-11-03', 11, ?, '본방', ?, ?, ?)",
        (new_id(), p["id"], slot_id, ts, ts))
    assert not svc.delete_program(conn, p["id"])["ok"]

    r = svc.save_program(conn, _weekly(id=p["id"], slots=[p["slots"][1]]))
    assert not r["ok"] and "적용 종료일" in r["errors"][0]
    # 실패한 저장은 아무것도 바꾸지 않는다
    assert len(svc.get_program(conn, p["id"])["program"]["slots"]) == 2


def test_안쓰인_프로그램은_삭제(conn):
    p = svc.save_program(conn, _weekly())["program"]
    assert svc.delete_program(conn, p["id"])["ok"]
    assert not svc.get_program(conn, p["id"])["ok"]
