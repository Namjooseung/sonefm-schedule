from datetime import date

from app.domain.episodes import EpisodeInfo
from app.domain.validate import validate_month

from .helpers import D, cell

NOV = [date(2026, 11, d) for d in range(1, 31)]
HOURS = list(range(6, 23))


def full(except_keys=()):
    """11월 달력 날짜를 모두 채운 칸 (except_keys 제외)."""
    return {(d, h): cell(d.isoformat(), h, "p") for d in NOV for h in HOURS if (d, h) not in except_keys}


def run(cells, episodes=None, orphans=(), conflicts=()):
    return validate_month(NOV, HOURS, cells, episodes or {}, list(orphans), list(conflicts))


def test_다_채우면_문제없음():
    assert run(full()) == []


def test_빈칸은_날짜별로_묶고_총방송분도_알림():
    cells = full(except_keys={(D("2026-11-10"), 7), (D("2026-11-10"), 8), (D("2026-11-11"), 9)})
    issues = run(cells)
    kinds = [i.kind for i in issues]
    assert kinds.count("빈칸") == 2
    first = next(i for i in issues if i.kind == "빈칸")
    assert first.key == (D("2026-11-10"), 7) and "07시, 08시" in first.detail
    total = next(i for i in issues if i.kind == "총 방송분")
    assert "180분 부족" in total.detail
    assert first.level == "error"


def test_빈칸이_많으면_시각을_줄여서_표시():
    cells = full(except_keys={(D("2026-11-10"), h) for h in range(6, 13)})
    first = next(i for i in run(cells) if i.kind == "빈칸")
    assert "06시, 07시, 08시, 09시 외 3칸" in first.detail


def test_본방대기():
    cells = full()
    k1 = (D("2026-11-03"), 20)
    issues = run(cells, episodes={k1: EpisodeInfo(None, waiting=True)})
    assert [(i.kind, i.key) for i in issues] == [("본방 대기", k1)]


def test_고아예외와_자리충돌():
    issues = run(full(), orphans=[(D("2026-11-05"), 14, "오후의 플레이리스트")],
                 conflicts=[(D("2026-11-06"), 10, ("가", "나"))])
    assert {i.kind for i in issues} == {"고아 예외", "편성 자리 충돌"}
    assert all(i.level == "warn" for i in issues)


def test_날짜순_정렬():
    cells = full(except_keys={(D("2026-11-20"), 7), (D("2026-11-02"), 7)})
    issues = [i for i in run(cells) if i.key]
    assert [i.key for i in issues] == sorted(i.key for i in issues)
