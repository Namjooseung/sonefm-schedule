from app.domain.generate import build_rule_cells, plan_generation
from app.domain.weeks import generation_dates, week_dates, weeks_of_month

from .helpers import D, cell, prog, slot


def _gen(programs, slots, dates, default_offweek="rerun"):
    return build_rule_cells(dates, {p.id: p for p in programs}, slots, default_offweek)


NOV = generation_dates(2026, 11)
FIRST_WEEK = week_dates(weeks_of_month(2026, 11)[0])


def test_고정편성은_매일_채워짐():
    gm, gb = prog("gm"), prog("gb")
    slots = [slot(f"gm{i}", "gm", i, 6) for i in range(7)] + [slot(f"gb{i}", "gb", i, 22) for i in range(7)]
    cells, conflicts = _gen([gm, gb], slots, NOV)
    assert conflicts == []
    for d in NOV:
        assert cells[(d, 6)].program_id == "gm"
        assert cells[(d, 22)].program_id == "gb"


def test_첫주와_나머지주는_주기로_다시_판정():
    # 격주: 첫 주(11/2)는 본방, 둘째 주(11/9)는 재방. 첫 주를 복사하지 않는다
    p = prog("sj", "biweekly", anchor="2026-11-05")
    s = slot("s", "sj", 3, 15)
    first, _ = _gen([p], [s], FIRST_WEEK)
    assert first[(D("2026-11-05"), 15)].kind == "본방"
    rest, _ = _gen([p], [s], [d for d in NOV if d not in FIRST_WEEK])
    assert rest[(D("2026-11-12"), 15)].kind == "재방"
    assert rest[(D("2026-11-19"), 15)].kind == "본방"


def test_월_경계_주는_다음달_날짜까지_생성():
    p = prog("p")
    cells, _ = _gen([p], [slot("s", "p", 1, 11)], NOV)
    assert (D("2026-12-01"), 11) in cells           # 11월 소속 마지막 주의 화요일
    assert all(d >= D("2026-11-02") for d, _ in cells)   # 11/1은 10월 소속 주라 대상 아님


def test_자리_적용기간과_프로그램_기간을_지킴():
    p = prog("p", end="2026-11-20")
    slots = [slot("a", "p", 1, 11, valid_to="2026-11-15"), slot("b", "p", 2, 13, valid_from="2026-11-16")]
    cells, _ = _gen([p], slots, NOV)
    assert cells[(D("2026-11-10"), 11)].original_slot_id == "a"
    assert (D("2026-11-17"), 11) not in cells
    assert cells[(D("2026-11-18"), 13)].original_slot_id == "b"
    assert (D("2026-11-25"), 13) not in cells     # 종영 후


def test_같은_자리_격주_두_프로그램은_번갈아():
    a = prog("a", "biweekly", anchor="2026-11-02")
    b = prog("b", "biweekly", anchor="2026-11-09")
    slots = [slot("sa", "a", 0, 10), slot("sb", "b", 0, 10)]
    cells, conflicts = _gen([a, b], slots, NOV)
    assert conflicts == []
    assert cells[(D("2026-11-02"), 10)].program_id == "a"
    assert cells[(D("2026-11-09"), 10)].program_id == "b"


def test_같은_자리가_겹치면_가장_최근에_들어온_프로그램이_이어감():
    # 11기가 10월부터 같은 자리에 본방으로 들어오면 그 뒤로는 11기 자리
    old, new = prog("old"), prog("new")
    slots = [slot("so", "old", 0, 10), slot("sn", "new", 0, 10, valid_from="2026-11-09")]
    cells, conflicts = _gen([old, new], slots, NOV)
    assert conflicts == []
    assert cells[(D("2026-11-02"), 10)].program_id == "old"
    assert cells[(D("2026-11-09"), 10)].program_id == "new"
    assert cells[(D("2026-11-30"), 10)].program_id == "new"


def test_그_다음에_또_다른_본방이_들어오면_그쪽이_이어감():
    a, b, c = prog("a"), prog("b"), prog("c")
    slots = [slot("sa", "a", 0, 10), slot("sb", "b", 0, 10, valid_from="2026-11-09"),
             slot("sc", "c", 0, 10, valid_from="2026-11-16")]
    cells, conflicts = _gen([a, b, c], slots, NOV)
    assert conflicts == []
    assert [cells[(D(d), 10)].program_id for d in ("2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23")] == ["a", "b", "c", "c"]


def test_최근에_들어온_프로그램이_종영하면_이전_프로그램이_다시():
    old, new = prog("old"), prog("new", end="2026-11-15")
    slots = [slot("so", "old", 0, 10), slot("sn", "new", 0, 10, valid_from="2026-11-09")]
    cells, _ = _gen([old, new], slots, NOV)
    assert cells[(D("2026-11-09"), 10)].program_id == "new"
    assert cells[(D("2026-11-16"), 10)].program_id == "old"


def test_진짜_충돌은_보고():
    # 같은 날 시작한 같은 우선순위 자리끼리만 충돌
    a, b = prog("a"), prog("b")
    cells, conflicts = _gen([a, b], [slot("sa", "a", 0, 10), slot("sb", "b", 0, 10)], FIRST_WEEK)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert (c.date, c.hour) == (D("2026-11-02"), 10) and set(c.program_ids) == {"a", "b"}
    assert cells[(D("2026-11-02"), 10)].program_id in {"a", "b"}


def test_본방이_재방보다_우선():
    a = prog("a")
    b = prog("b")
    slots = [slot("sa", "a", 0, 10, "재방"), slot("sb", "b", 0, 10, "본방")]
    cells, conflicts = _gen([a, b], slots, FIRST_WEEK)
    assert cells[(D("2026-11-02"), 10)].program_id == "b"
    assert conflicts == []


# ── 기존 칸과 합치기 (다시 생성) ─────────────────────

def _plan(rule, existing, cancellations=(), overwrite=False):
    return plan_generation(rule, {c.key: c for c in existing}, set(cancellations), overwrite)


def test_사람이_손댄_칸은_기본_유지하고_확인목록에():
    p = prog("p")
    rule, _ = _gen([p], [slot("s", "p", 1, 11)], FIRST_WEEK)
    manual = cell("2026-11-03", 11, "special", source="manual")
    plan = _plan(rule, [manual])
    assert (D("2026-11-03"), 11) not in {c.key for c in plan.upserts}
    assert [c.key for c in plan.manual_conflicts] == [(D("2026-11-03"), 11)]

    plan = _plan(rule, [manual], overwrite=True)
    assert [c.program_id for c in plan.upserts if c.key == (D("2026-11-03"), 11)] == ["p"]


def test_같은_결과면_다시_쓰지_않고_규칙에서_빠진_칸은_지움():
    p = prog("p")
    rule, _ = _gen([p], [slot("s", "p", 1, 11)], FIRST_WEEK)
    same = cell("2026-11-03", 11, "p", slot_id="s")
    stale = cell("2026-11-04", 9, "old")           # 예전 규칙으로 만든 칸
    plan = _plan(rule, [same, stale])
    assert plan.upserts == []
    assert plan.deletes == [(D("2026-11-04"), 9)]


def test_결방_기록이_있으면_규칙칸을_만들지_않음():
    p = prog("p")
    rule, _ = _gen([p], [slot("s", "p", 1, 11)], FIRST_WEEK)
    plan = _plan(rule, [], cancellations=[("p", D("2026-11-03"), 11)])
    assert plan.upserts == []


def test_결방_자리를_채운_칸은_덮어쓰기에서도_보호():
    # 11/3 원래 p 본방 → 결방 기록 + 그 자리에 특집(manual). 덮어쓰기로 다시 생성해도 특집은 그대로
    p = prog("p")
    rule, _ = _gen([p], [slot("s", "p", 1, 11)], FIRST_WEEK)
    special = cell("2026-11-03", 11, "special", source="manual")
    plan = _plan(rule, [special], cancellations=[("p", D("2026-11-03"), 11)], overwrite=True)
    assert plan.manual_conflicts == [] and plan.upserts == [] and plan.deletes == []


def test_일회성_예외는_퍼지지_않음():
    # 11/3 칸을 특집으로 바꾼 상태에서 월단위 생성 → 다른 주는 원래 프로그램
    p = prog("p")
    rule, _ = _gen([p], [slot("s", "p", 1, 11)], NOV)
    manual = cell("2026-11-03", 11, "special", source="manual")
    plan = _plan(rule, [manual])
    by_key = {c.key: c.program_id for c in plan.upserts}
    assert by_key[(D("2026-11-10"), 11)] == "p"
    assert (D("2026-11-03"), 11) not in by_key


def test_엑셀에서_가져온_칸도_보호():
    p = prog("p")
    rule, _ = _gen([p], [slot("s", "p", 1, 11)], FIRST_WEEK)
    imported = cell("2026-11-03", 11, "other", source="import")
    plan = _plan(rule, [imported])
    assert plan.upserts == [] and [c.key for c in plan.manual_conflicts] == [(D("2026-11-03"), 11)]
    stale_import = cell("2026-11-04", 9, "old", source="import")
    assert _plan(rule, [stale_import]).deletes == []
