"""P4 완료 조건: 결방·교체·특집·본방 전환·재방 회차 지정이 되고 회차가 즉시 재계산된다. + 원래대로, 되돌리기."""
import pytest

from app.api import Api
from app.repository import change_log_repo, programs_repo
from app.repository._common import new_id, now_iso
from app.startup import prepare


@pytest.fixture
def api():
    a = Api(prepare().config)
    S = lambda wd, h, role="본방": {"weekday": wd, "hour": h, "role": role, "valid_from": "2026-01-05"}  # noqa: E731
    a.ids = {}
    for name, cyc, ep, slots in [
        ("마을살이 정류장", "weekly", 41, [S(1, 11), S(5, 18, "재방")]),
        ("오후의 플레이리스트", "weekly", 9, [S(2, 14)]),
        ("그 삶이다", "irregular", 5, [S(4, 15)]),
    ]:
        r = a.save_program({"name": name, "category": "교양", "cycle_type": cyc, "start_episode": ep, "slots": slots})
        assert r["ok"], r
        a.ids[name] = r["program"]["id"]
    assert a.generate_month(2026, 11, "all")["ok"]
    return a


def cell(api, d, h):
    return api.get_month(2026, 11)["cells"].get(f"{d}|{h}")


def ep(api, d, h):
    return cell(api, d, h)["episode"]


def test_결방_재방대체_후_다음_본방이_회차를_이어받음(api):
    r = api.cell_cancel("2026-11-10", 11, "rerun", "행사 중계")
    assert r["ok"] and r["can_undo"]
    c = cell(api, "2026-11-10", 11)
    assert c["kind"] == "재방" and c["exception_type"] == "결방대체" and c["manual"]
    assert c["episode"] == 41                        # 재방 = 직전 본방
    assert ep(api, "2026-11-17", 11) == 42           # 결방 회차를 이어받음
    # 다시 생성해도(덮어쓰기여도) 결방이 유지된다
    api.generate_month(2026, 11, "all", True)
    assert cell(api, "2026-11-10", 11)["exception_type"] == "결방대체"


def test_결방_비워두기(api):
    assert api.cell_cancel("2026-11-10", 11, "empty")["ok"]
    assert cell(api, "2026-11-10", 11) is None
    assert ep(api, "2026-11-17", 11) == 42
    assert api.generate_month(2026, 11, "all")["changed"] == 0   # 다시 채우지 않음


def test_교체_이번만(api):
    r = api.cell_replace("2026-11-10", 11, api.ids["오후의 플레이리스트"], "재방", "once")
    assert r["ok"], r
    c = cell(api, "2026-11-10", 11)
    assert c["name"] == "오후의 플레이리스트" and c["exception_type"] == "교체" and c["episode"] == 9
    assert ep(api, "2026-11-17", 11) == 42           # 원래 프로그램은 자동 결방
    detail = api.get_cell("2026-11-10", 11)
    assert detail["cell"]["original_name"] == "마을살이 정류장"
    assert detail["cancellations"][0]["name"] == "마을살이 정류장"


def test_교체_이후_전부는_편성자리_이력을_갱신(api):
    r = api.cell_replace("2026-11-17", 11, api.ids["오후의 플레이리스트"], "본방", "after")
    assert r["ok"], r
    assert cell(api, "2026-11-10", 11)["name"] == "마을살이 정류장"        # 이전은 그대로
    for d in ("2026-11-17", "2026-11-24", "2026-12-01"):
        c = cell(api, d, 11)
        assert c["name"] == "오후의 플레이리스트" and not c["manual"]
    assert ep(api, "2026-11-17", 11) == 11            # 수 14시 11/4(9), 11/11(10) 다음
    assert ep(api, "2026-11-18", 14) == 12
    slots = api.get_program(api.ids["마을살이 정류장"])["program"]["slots"]
    tue = [s for s in slots if s["weekday"] == 1]
    assert tue[0]["valid_to"] == "2026-11-16"
    new = [s for s in api.get_program(api.ids["오후의 플레이리스트"])["program"]["slots"] if s["weekday"] == 1]
    assert new[0]["valid_from"] == "2026-11-17" and new[0]["hour"] == 11


def test_특집_넣기와_재사용(api):
    r = api.cell_special("2026-11-18", 14, {"name": "가을 음악회 실황 특집", "category": "오락"})
    assert r["ok"], r
    c = cell(api, "2026-11-18", 14)
    assert c["is_special"] and c["exception_type"] == "특집"
    assert ep(api, "2026-11-25", 14) == 11           # 9(11/4), 10(11/11), 결방, 11(11/25)
    sp = next(p for p in api.list_programs("가을", True)["items"])
    assert api.cell_special("2026-11-21", 18, {"program_id": sp["id"]})["ok"]


def test_비정기_본방으로_전환하면_이후_재방이_새_회차(api):
    assert ep(api, "2026-11-13", 15) == 4
    r = api.cell_set_kind("2026-11-13", 15, "본방")
    assert r["ok"]
    assert ep(api, "2026-11-06", 15) == 4
    assert ep(api, "2026-11-13", 15) == 5
    assert ep(api, "2026-11-20", 15) == 5


def test_정규_재방으로_이후_전부(api):
    r = api.cell_set_kind("2026-11-17", 11, "재방", "after")
    assert r["ok"], r
    assert [cell(api, d, 11)["kind"] for d in ("2026-11-10", "2026-11-17", "2026-11-24")] == ["본방", "재방", "재방"]
    assert not cell(api, "2026-11-24", 11)["manual"]


def test_재방_회차_지정과_해제(api):
    assert api.cell_override("2026-11-07", 18, 30)["ok"]
    assert ep(api, "2026-11-07", 18) == 30
    assert not api.cell_override("2026-11-07", 18, "abc")["ok"]
    assert api.cell_override("2026-11-07", 18, "")["ok"]
    assert ep(api, "2026-11-07", 18) == 41


def test_원래대로(api):
    api.cell_replace("2026-11-10", 11, api.ids["오후의 플레이리스트"], "재방", "once")
    assert api.cell_revert("2026-11-10", 11)["ok"]
    c = cell(api, "2026-11-10", 11)
    assert c["name"] == "마을살이 정류장" and not c["manual"] and c["exception_type"] is None
    assert ep(api, "2026-11-17", 11) == 43
    assert api.get_cell("2026-11-10", 11)["cancellations"] == []


def test_되돌리기는_한_단계씩(api):
    api.cell_replace("2026-11-10", 11, api.ids["오후의 플레이리스트"], "재방", "once")
    api.cell_override("2026-11-14", 18, 3)
    assert api.undo()["ok"]
    assert ep(api, "2026-11-14", 18) != 3
    assert cell(api, "2026-11-10", 11)["name"] == "오후의 플레이리스트"
    assert api.undo()["ok"]
    assert cell(api, "2026-11-10", 11)["name"] == "마을살이 정류장"
    assert api.get_cell("2026-11-10", 11)["cancellations"] == []


def test_이후_전부도_되돌리기(api):
    api.cell_replace("2026-11-17", 11, api.ids["오후의 플레이리스트"], "본방", "after")
    assert api.undo()["ok"]
    assert cell(api, "2026-11-24", 11)["name"] == "마을살이 정류장"
    assert all(s["valid_to"] is None for s in api.get_program(api.ids["마을살이 정류장"])["program"]["slots"])
    assert [s for s in api.get_program(api.ids["오후의 플레이리스트"])["program"]["slots"] if s["weekday"] == 1] == []


def test_월_생성도_되돌리기(api):
    api.cell_cancel("2026-11-10", 11, "empty")
    api2 = api
    r = api2.generate_month(2026, 12, "first_week")
    assert r["ok"] and r["changed"] > 0
    assert api2.undo()["ok"]
    assert api2.get_month(2026, 12)["first_week_filled"] is False


def test_준비상태와_실제변경(api):
    assert api.cell_prep("2026-11-03", 11, "입고")["ok"]
    assert api.cell_actual("2026-11-03", 11, "송출 사고로 8분 지연")["ok"]
    c = cell(api, "2026-11-03", 11)
    assert c["prep_status"] == "입고" and c["actual_change_note"] == "송출 사고로 8분 지연"
    assert not c["manual"]                            # 계획은 그대로
    assert not api.cell_prep("2026-11-03", 11, "엉뚱")["ok"]


def test_변경기록(api):
    api.cell_cancel("2026-11-10", 11, "rerun", "행사")
    items = api.list_change_log(10)["items"]
    assert items[0]["action"] == "결방" and "마을살이 정류장" in items[0]["note"]


def test_마감된_달은_편집_불가(api):
    from app.db.connection import open_db
    with open_db(api._cfg.db_path) as conn:
        ts = now_iso()
        conn.execute("UPDATE month_plans SET status = '마감', updated_at = ? WHERE year_month = '2026-11'", (ts,))
    r = api.cell_cancel("2026-11-10", 11, "empty")
    assert not r["ok"] and "마감" in r["errors"][0]


def test_빈칸_채우기(api):
    r = api.cell_replace("2026-11-02", 9, api.ids["그 삶이다"], "재방", "once")
    assert r["ok"]
    c = cell(api, "2026-11-02", 9)
    assert c["name"] == "그 삶이다" and c["exception_type"] is None and c["manual"]


def test_본방_회차_올리고_내리기(api):
    assert ep(api, "2026-11-10", 11) == 42
    r = api.cell_override("2026-11-10", 11, 45)
    assert r["ok"], r
    assert ep(api, "2026-11-03", 11) == 41                 # 이전은 그대로
    assert ep(api, "2026-11-10", 11) == 45
    assert ep(api, "2026-11-14", 18) == 45                 # 재방은 직전 본방을 따라감
    assert ep(api, "2026-11-17", 11) == 46                 # 다음 본방이 이어짐
    assert api.get_cell("2026-11-10", 11)["cell"]["rerun_episode_override"] == 45
    assert api.undo()["ok"]
    assert ep(api, "2026-11-17", 11) == 43
    api.cell_override("2026-11-10", 11, 45)
    assert api.cell_override("2026-11-10", 11, "")["ok"]    # 자동으로
    assert ep(api, "2026-11-17", 11) == 43


def test_회차는_1보다_작게_못함(api):
    assert not api.cell_override("2026-11-10", 11, 0)["ok"]


def test_빈칸은_회차_지정_불가(api):
    assert not api.cell_override("2026-11-02", 9, 3)["ok"]


def test_칸_정보에_회차표시_여부(api):
    assert api.get_cell("2026-11-10", 11)["cell"]["show_episode"] is True


def test_회차를_내려_직전과_같아지면_새_회차가_아님(api):
    assert cell(api, "2026-11-10", 11)["kind"] == "본방"
    assert api.cell_override("2026-11-10", 11, 41)["ok"]     # 42 → 41 (직전 회차)
    c = cell(api, "2026-11-10", 11)
    assert c["kind"] == "재방" and c["episode"] == 41
    assert ep(api, "2026-11-17", 11) == 42                   # 다음 본방이 이어받음
    assert api.cell_override("2026-11-10", 11, 42)["ok"]     # 다시 올리면 새 회차
    c = cell(api, "2026-11-10", 11)
    assert c["kind"] == "본방" and c["episode"] == 42
    assert ep(api, "2026-11-17", 11) == 43


def test_비정기도_회차를_올리면_새_회차(api):
    assert cell(api, "2026-11-13", 15)["kind"] == "재방"
    assert api.cell_override("2026-11-13", 15, 5)["ok"]      # 4 → 5
    assert cell(api, "2026-11-13", 15)["kind"] == "본방"
    assert ep(api, "2026-11-20", 15) == 5                    # 뒤 재방이 새 회차를 따라감
    assert api.cell_override("2026-11-13", 15, 4)["ok"]      # 그날 안 하면 내림
    assert cell(api, "2026-11-13", 15)["kind"] == "재방"
    assert ep(api, "2026-11-20", 15) == 4


def test_직전보다_낮추면_그_칸만_재방(api):
    assert api.cell_override("2026-11-10", 11, 30)["ok"]
    c = cell(api, "2026-11-10", 11)
    assert c["kind"] == "재방" and c["episode"] == 30
    assert ep(api, "2026-11-17", 11) == 42


def test_재방_자리는_올려도_본방이_안됨(api):
    assert api.cell_override("2026-11-07", 18, 50)["ok"]
    c = cell(api, "2026-11-07", 18)
    assert c["kind"] == "재방" and c["episode"] == 50
    assert ep(api, "2026-11-10", 11) == 42


def test_본방_자리가_둘인_프로그램도_내렸다_올릴_수_있음():
    a = Api(prepare().config)
    r = a.save_program({"name": "그 사이 음악", "category": "오락", "cycle_type": "weekly", "start_episode": 80, "slots": []})
    pid = r["program"]["id"]
    # 엑셀에서 가져온 칸처럼 자리 정보가 없는 본방: 화·목
    from app.db.connection import open_db
    from app.repository._common import new_id, now_iso
    with open_db(a._cfg.db_path) as conn:
        ts = now_iso()
        for d in ("2026-11-03", "2026-11-05", "2026-11-10", "2026-11-12"):
            conn.execute("INSERT INTO schedule_cells (id, date, hour, program_id, kind, source, created_at, updated_at)"
                         " VALUES (?, ?, 13, ?, '본방', 'import', ?, ?)", (new_id(), d, pid, ts, ts))
        conn.execute("INSERT INTO month_plans (id, year_month, status, created_at, updated_at)"
                     " VALUES (?, '2026-11', '작성중', ?, ?)", (new_id(), ts, ts))
    assert a.cell_override("2026-11-12", 13, 82)["ok"]       # 83 → 82 (직전과 같음)
    c = a.get_month(2026, 11)["cells"]["2026-11-12|13"]
    assert c["kind"] == "재방" and c["rerun_mark"] is False   # 본방 자리 그대로
    assert a.cell_override("2026-11-12", 13, 83)["ok"]       # 다시 올리면 새 회차
    assert a.get_month(2026, 11)["cells"]["2026-11-12|13"]["kind"] == "본방"
