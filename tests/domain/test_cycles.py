from app.domain.cycles import is_broadcast_week, rule_kind

from .helpers import D, prog, slot


def test_매주는_항상_방송():
    p = prog("p")
    assert is_broadcast_week(p, D("2026-11-09"))


def test_격주_기준일_판정():
    # 기준일 11/5(목) → 11/2 주 방송, 11/9 주 쉼, 11/16 주 방송. 기준일 이전도 같은 박자
    p = prog("p", "biweekly", anchor="2026-11-05")
    assert is_broadcast_week(p, D("2026-11-02"))
    assert not is_broadcast_week(p, D("2026-11-09"))
    assert is_broadcast_week(p, D("2026-11-16"))
    assert not is_broadcast_week(p, D("2026-10-26"))
    assert is_broadcast_week(p, D("2026-10-19"))
    # 주 중간 날짜를 넣어도 그 주의 월요일로 판정
    assert is_broadcast_week(p, D("2026-11-22"))


def test_매월_n째_주는_주의_소속_기준():
    p = prog("p", "monthly_nth", nth=2)
    assert is_broadcast_week(p, D("2026-11-09"))
    assert not is_broadcast_week(p, D("2026-11-02"))
    # 11/1(일)은 10월 소속 주(10월 4주) → 11월 2째 주가 아님
    assert not is_broadcast_week(p, D("2026-11-01"))


def test_비정기와_단발은_자동_본방_없음():
    assert not is_broadcast_week(prog("p", "irregular"), D("2026-11-02"))
    assert not is_broadcast_week(prog("p", "oneoff"), D("2026-11-02"))


def test_칸_종류_판정():
    weekly = prog("p")
    s_main = slot("s1", "p", 1, 11)
    s_rerun = slot("s2", "p", 5, 18, "재방")
    assert rule_kind(weekly, s_main, D("2026-11-03"), "rerun") == "본방"
    assert rule_kind(weekly, s_rerun, D("2026-11-07"), "rerun") == "재방"


def test_격주_쉬는_주는_정책대로():
    bi = prog("p", "biweekly", anchor="2026-11-05")
    s = slot("s", "p", 3, 15)
    assert rule_kind(bi, s, D("2026-11-05"), "rerun") == "본방"
    assert rule_kind(bi, s, D("2026-11-12"), "rerun") == "재방"     # 설정 기본값: 재방으로 채움
    assert rule_kind(bi, s, D("2026-11-12"), "empty") is None       # 설정 기본값: 비움
    bi_empty = prog("p", "biweekly", anchor="2026-11-05", offweek="empty")
    assert rule_kind(bi_empty, s, D("2026-11-12"), "rerun") is None  # 프로그램 개별 값이 우선


def test_비정기는_본방_자리도_재방으로_깔림():
    irr = prog("p", "irregular")
    assert rule_kind(irr, slot("s", "p", 4, 15), D("2026-11-06"), "rerun") == "재방"
