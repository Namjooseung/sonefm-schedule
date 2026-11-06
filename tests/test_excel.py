"""P6 완료 조건: 샘플 엑셀을 가져오고 다시 내보냈을 때 원본과 칸 내용이 일치 (엑셀 쪽 오류는 목록으로)."""
from pathlib import Path

import openpyxl
import pytest

from app.config import migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations
from app.io_excel.reader import read_workbook
from app.services import excel as svc
from app.services import programs as program_svc

SAMPLE = Path(__file__).resolve().parent.parent / "samples" / "samples.xlsx"
pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="samples/samples.xlsx 없음")


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "s.db")
    apply_migrations(c, migrations_dir())
    yield c
    c.close()


def _import_all_new(conn, titles):
    a = svc.analyze(conn, str(SAMPLE))
    mapping = {n["name"]: {"action": "new", "category": "교양"} for n in a["names"] if n["status"] != "matched"}
    return svc.run_import(conn, str(SAMPLE), titles, mapping)


def test_분석은_DB를_바꾸지_않음(conn):
    a = svc.analyze(conn, str(SAMPLE))
    assert a["ok"]
    titles = {s["title"]: s for s in a["sheets"]}
    assert titles["2611"]["importable"] and not titles["프로그램_정보"]["importable"]
    # #REF! 칸은 모두 다른 달 소속 주(가져오지 않는 주)에 있어 이 샘플에선 0건
    assert a["error_count"] == len(a["error_cells"]) == 0
    assert any(n["name"] == "마을살이정류장" and n["has_episode"] for n in a["names"])
    assert any(n["name"] == "963 음악쌀롱" and not n["has_episode"] for n in a["names"])
    assert conn.execute("SELECT COUNT(*) FROM schedule_cells").fetchone()[0] == 0


def test_기존_프로그램과_매칭_추천(conn):
    program_svc.save_program(conn, {"name": "마을살이 정류장", "category": "교양", "cycle_type": "weekly"})
    a = svc.analyze(conn, str(SAMPLE))
    row = next(n for n in a["names"] if n["name"] == "마을살이정류장")
    assert row["status"] == "suggested" and row["program_name"] == "마을살이 정류장"


def test_가져오고_다시_비교하면_엑셀과_같음(conn):
    titles = ["2609", "2610"]
    r = _import_all_new(conn, titles)
    assert r["ok"], r
    assert r["written"] > 900 and r["created"] > 20      # 9월 4주 + 10월 4주
    cmp = svc.compare(conn, str(SAMPLE), titles)
    # 프로그램은 모든 칸이 같고, 남는 차이는 엑셀 쪽 표기 불일치((재) 붙였다 말았다, 회차 오류)뿐
    assert set(cmp["by_kind"]) <= {"재방 표시만 다름", "회차만 다름"}, cmp["diffs"][:5]
    assert cmp["by_kind"].get("재방 표시만 다름", 0) < cmp["compared"] * 0.02
    assert r["episode_diff_count"] < cmp["compared"] * 0.05


def test_가져온_칸은_다시_생성해도_유지(conn):
    from app.services import schedule as sched
    _import_all_new(conn, ["2610"])
    before = conn.execute("SELECT COUNT(*) FROM schedule_cells WHERE source = 'import'").fetchone()[0]
    sched.generate(conn, 2026, 10, "all")
    after = conn.execute("SELECT COUNT(*) FROM schedule_cells WHERE source = 'import'").fetchone()[0]
    assert before == after > 0


def test_새_프로그램은_편성자리_추정(conn):
    _import_all_new(conn, ["2610"])
    p = next(x for x in program_svc.list_programs(conn, "마을살이정류장", True))
    detail = program_svc.get_program(conn, p["id"])["program"]
    assert detail["slots"] and detail["memo"].startswith("엑셀에서 가져와")
    music = program_svc.get_program(conn, next(x for x in program_svc.list_programs(conn, "963 음악쌀롱", True))["id"])["program"]
    assert music["show_episode"] is False


def test_내보내기는_수식없이_글자만(conn, tmp_path):
    _import_all_new(conn, ["2610", "2611"])
    out = tmp_path / "out.xlsx"
    r = svc.export_months(conn, [(2026, 11)], str(out))
    assert r["ok"]
    wb = openpyxl.load_workbook(out)
    ws = wb["2611"]
    assert ws["B1"].value.year == 2026
    assert ws["A2"].value == "10-44" and ws["B2"].value == 26        # ISO 주차
    formulas = [c.coordinate for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    assert formulas == []
    assert "B3:H3" in {str(m) for m in ws.merged_cells.ranges}         # 06시 고정 편성 띠
    # 내보낸 파일을 다시 읽으면 같은 칸 구조
    sheet = read_workbook(out)[0]
    assert [w.monday.isoformat() for w in sheet.weeks][:2] == ["2026-10-26", "2026-11-02"]
    texts = {k: v for w in sheet.weeks for k, (v, _) in w.cells.items() if v}
    assert any(isinstance(v, str) and v.endswith("(재)") for v in texts.values())


def test_잘못된_파일(conn, tmp_path):
    assert not svc.analyze(conn, str(tmp_path / "없음.xlsx"))["ok"]
    bad = tmp_path / "a.txt"
    bad.write_text("x")
    assert not svc.analyze(conn, str(bad))["ok"]


def test_마감_달은_가져오기_불가(conn):
    from app.repository import schedule_repo
    schedule_repo.set_month_status(conn, "2026-10", "마감")
    r = _import_all_new(conn, ["2610"])
    assert not r["ok"] and "마감" in r["errors"][0]


def test_표기만_다른_이름은_같은_프로그램으로_묶기(conn):
    a = svc.analyze(conn, str(SAMPLE))
    mapping = {n["name"]: {"action": "new", "category": "교양"} for n in a["names"]}
    mapping["[OBS7 오늘의 기후"] = {"action": "same", "target": "[OBS] 오늘의 기후"}
    mapping["[OBS] 오늘의 기후 119화"] = {"action": "same", "target": "[OBS7 오늘의 기후"}   # 연쇄
    sheets = sorted({t for n in a["names"] if n["name"].startswith("[OBS") for t in n["sheets"]})
    r = svc.run_import(conn, str(SAMPLE), sheets, mapping)
    assert r["ok"], r
    p = program_svc.list_programs(conn, "[OBS] 오늘의 기후", True)
    assert len(p) == 1
    detail = program_svc.get_program(conn, p[0]["id"])["program"]
    assert {"[OBS7 오늘의 기후", "[OBS] 오늘의 기후 119화"} <= set(detail["aliases"])


def test_괄호_재_생략된_격주는_격주로_추정(conn, tmp_path):
    """본방 자리에 같은 회차가 (재) 없이 다시 나오면 재방으로 읽고, 편성 자리 추정도 그 값으로 한다."""
    from datetime import date, timedelta
    from app.io_excel.writer import MonthSheet, WeekBlock, write_months
    mondays = [date(2026, 8, 3) + timedelta(weeks=i) for i in range(4)]
    blocks = []
    for i, mon in enumerate(mondays):
        wk = WeekBlock(label=f"8-{32 + i}", days=[(mon + timedelta(days=k)).day for k in range(7)])
        ep = 72 + i // 2                       # 72, 72, 73, 73 → 격주 본방, 쉬는 주는 (재) 없이 같은 회차
        wk.rows[10] = [(f"수원은 지금_{ep}화" if k == 1 else "", False) for k in range(7)]
        blocks.append(wk)
    path = tmp_path / "biweekly.xlsx"
    write_months([MonthSheet("2608", date(2026, 8, 1), blocks)], path)
    r = svc.run_import(conn, str(path), ["2608"], {"수원은 지금": {"action": "new"}})
    assert r["ok"] and r["read_as_rerun"] == 2
    p = program_svc.get_program(conn, program_svc.list_programs(conn, "수원은 지금", True)[0]["id"])["program"]
    assert p["cycle_type"] == "biweekly" and p["cycle_anchor_date"] == "2026-08-18"   # 마지막 본방 (8/4와 같은 격주 박자)


def _one_week_file(path, sheet, monday, label, text):
    from datetime import date, timedelta
    from app.io_excel.writer import MonthSheet, WeekBlock, write_months
    wk = WeekBlock(label=label, days=[(monday + timedelta(days=k)).day for k in range(7)])
    wk.rows[10] = [(text if k == 1 else "", False) for k in range(7)]
    write_months([MonthSheet(sheet, date(monday.year, monday.month, 1), [wk])], path)


def test_이어서_가져올_때_DB의_직전_회차까지_보고_재방으로_읽음(conn, tmp_path):
    from datetime import date
    a, b, c = tmp_path / "a.xlsx", tmp_path / "b.xlsx", tmp_path / "c.xlsx"
    _one_week_file(a, "2608", date(2026, 8, 24), "8-35", "수원은 지금_72화")
    _one_week_file(b, "2609", date(2026, 9, 7), "9-37", "수원은 지금_72화")     # (재) 없이 같은 회차
    _one_week_file(c, "2609", date(2026, 9, 14), "9-38", "수원은 지금_73화")
    assert svc.run_import(conn, str(a), ["2608"], {"수원은 지금": {"action": "new"}})["ok"]
    r = svc.run_import(conn, str(b), ["2609"], {})
    assert r["ok"] and r["read_as_rerun"] == 1
    kind = conn.execute("SELECT kind FROM schedule_cells WHERE date = '2026-09-08' AND hour = 10").fetchone()[0]
    assert kind == "재방"
    r = svc.run_import(conn, str(c), ["2609"], {}, overwrite=False)
    assert r["ok"] and r["read_as_rerun"] == 0
    assert conn.execute("SELECT kind FROM schedule_cells WHERE date = '2026-09-15' AND hour = 10").fetchone()[0] == "본방"
