from app.domain.episodes import compute_episodes, rerun_streak_warnings
from app.domain.generate import build_rule_cells
from app.domain.weeks import generation_dates

from .helpers import D, cell, prog, slot


def _eps(cells, start_episode=1):
    return {(c.date.isoformat(), c.hour): e.episode
            for c, e in zip(sorted(cells, key=lambda c: c.key), compute_episodes(cells, start_episode))}


def test_본방은_순서대로_재방은_직전_본방():
    cells = [cell("2026-11-03", 11, "p"), cell("2026-11-07", 18, "p", "재방"),
             cell("2026-11-10", 11, "p"), cell("2026-11-14", 18, "p", "재방")]
    assert _eps(cells, 41) == {("2026-11-03", 11): 41, ("2026-11-07", 18): 41,
                               ("2026-11-10", 11): 42, ("2026-11-14", 18): 42}


def test_순서가_섞여_들어와도_시간순으로_계산():
    cells = [cell("2026-11-10", 11, "p"), cell("2026-11-03", 11, "p")]
    assert _eps(cells, 1) == {("2026-11-03", 11): 1, ("2026-11-10", 11): 2}


def test_결방_후_다음_본방이_회차를_이어받음():
    # 11/10 본방이 결방(칸이 다른 프로그램으로 교체) → 이 프로그램 칸 목록에 없음
    cells = [cell("2026-11-03", 11, "p"), cell("2026-11-14", 18, "p", "재방"), cell("2026-11-17", 11, "p")]
    assert _eps(cells, 41) == {("2026-11-03", 11): 41, ("2026-11-14", 18): 41, ("2026-11-17", 11): 42}


def test_재방_회차_수동지정이_우선():
    cells = [cell("2026-11-03", 11, "p"), cell("2026-11-07", 18, "p", "재방", override=12)]
    assert _eps(cells, 41)[("2026-11-07", 18)] == 12


def test_신규_프로그램_첫_본방_전_재방은_본방대기():
    cells = [cell("2026-11-03", 20, "p", "재방"), cell("2026-11-06", 15, "p")]
    infos = compute_episodes(cells, 1)
    assert infos[0].episode is None and infos[0].waiting
    assert infos[1].episode == 1 and not infos[1].waiting


def test_기존_프로그램_첫_본방_전_재방은_직전_회차():
    cells = [cell("2026-11-03", 20, "p", "재방")]
    info = compute_episodes(cells, 41)[0]
    assert info.episode == 40 and not info.waiting


def test_월_경계를_넘어도_회차_연속():
    p = prog("p", start_episode=41)
    s = slot("s", "p", 1, 11)
    rule_oct, _ = build_rule_cells(generation_dates(2026, 10), {"p": p}, [s], "rerun")
    rule_nov, _ = build_rule_cells(generation_dates(2026, 11), {"p": p}, [s], "rerun")
    cells = [c for c in [*rule_oct.values(), *rule_nov.values()] if c.date >= D("2026-10-06")]
    eps = _eps(cells, 41)
    assert eps[("2026-10-27", 11)] == 44     # 10/6, 13, 20, 27
    assert eps[("2026-11-03", 11)] == 45
    assert eps[("2026-12-01", 11)] == 49


def test_개편_전후_회차_연속():
    # 화 11시 → 11/16부터 수 13시로 이동. 프로그램은 그대로라 회차가 이어진다
    p = prog("p", start_episode=41, start="2026-11-01")
    slots = [slot("a", "p", 1, 11, valid_to="2026-11-15"), slot("b", "p", 2, 13, valid_from="2026-11-16")]
    rule, _ = build_rule_cells(generation_dates(2026, 11), {"p": p}, slots, "rerun")
    eps = _eps(list(rule.values()), 41)
    assert eps == {("2026-11-03", 11): 41, ("2026-11-10", 11): 42, ("2026-11-18", 13): 43,
                   ("2026-11-25", 13): 44, ("2026-12-02", 13): 45}


def test_격주_쉬는_주는_직전_회차_재방():
    # 엑셀 편성표와 같은 모습: 75화 → 75화(재) → 76화
    p = prog("sj", "biweekly", start_episode=75, anchor="2026-11-03")
    rule, _ = build_rule_cells(generation_dates(2026, 11), {"sj": p}, [slot("s", "sj", 1, 10)], "rerun")
    cells = sorted(rule.values(), key=lambda c: c.key)
    assert [(c.date.isoformat(), c.kind) for c in cells][:3] == [
        ("2026-11-03", "본방"), ("2026-11-10", "재방"), ("2026-11-17", "본방")]
    assert _eps(cells, 75)[("2026-11-10", 10)] == 75
    assert _eps(cells, 75)[("2026-11-17", 10)] == 76


def test_부정기_본방_전환_후_재방이_새_회차를_가리킴():
    p = prog("gs", "irregular", start_episode=5)
    rule, _ = build_rule_cells(generation_dates(2026, 11), {"gs": p}, [slot("s", "gs", 4, 15)], "rerun")
    cells = {c.key: c for c in rule.values()}
    assert all(c.kind == "재방" for c in cells.values())
    assert _eps(cells.values(), 5)[("2026-11-13", 15)] == 4      # 아직 본방 없음 → 직전(4화)
    # 사용자가 11/13 칸을 "본방으로" 바꿈
    k = (D("2026-11-13"), 15)
    cells[k] = cell("2026-11-13", 15, "gs", "본방", source="manual")
    eps = _eps(cells.values(), 5)
    assert eps[("2026-11-06", 15)] == 4
    assert eps[("2026-11-13", 15)] == 5
    assert eps[("2026-11-20", 15)] == 5
    assert eps[("2026-11-27", 15)] == 5


def test_부정기_같은_회차_재방이_이어지면_누락_의심():
    cells = [cell("2026-11-06", 15, "p")] + [cell(d, 15, "p", "재방") for d in
                                             ("2026-11-13", "2026-11-20", "2026-11-27", "2026-12-04", "2026-12-11")]
    infos = compute_episodes(cells, 7)
    flagged = rerun_streak_warnings(sorted(cells, key=lambda c: c.key), infos, threshold=4)
    assert flagged == [(D("2026-12-04"), 15), (D("2026-12-11"), 15)]


def test_수동지정_재방은_연속_계산에서_제외():
    cells = [cell("2026-11-06", 15, "p")] + [cell(d, 15, "p", "재방", override=3 if d == "2026-11-20" else None)
                                             for d in ("2026-11-13", "2026-11-20", "2026-11-27", "2026-12-04")]
    infos = compute_episodes(cells, 7)
    assert rerun_streak_warnings(sorted(cells, key=lambda c: c.key), infos, threshold=4) == []


def test_여러_프로그램이_섞여도_프로그램별로_계산():
    from app.domain.episodes import episodes_by_program
    cells = [cell("2026-11-03", 11, "a"), cell("2026-11-03", 12, "b"),
             cell("2026-11-10", 11, "a"), cell("2026-11-07", 18, "b", "재방")]
    out = episodes_by_program(cells, {"a": 41, "b": 1})
    assert out[(D("2026-11-10"), 11)].episode == 42
    assert out[(D("2026-11-07"), 18)].episode == 1
    assert out[(D("2026-11-03"), 12)].episode == 1
