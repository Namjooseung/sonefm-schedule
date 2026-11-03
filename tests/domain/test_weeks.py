from datetime import date

from app.domain.weeks import (
    iso_week,
    month_dates,
    month_of_week,
    monday_of,
    reference_week,
    week_dates,
    week_index_in_month,
    weeks_of_month,
)

D = date.fromisoformat


def test_월요일_찾기():
    assert monday_of(D("2026-11-01")) == D("2026-10-26")   # 일요일
    assert monday_of(D("2026-11-02")) == D("2026-11-02")


def test_주의_소속은_월요일이_속한_달():
    assert month_of_week(D("2026-10-26")) == (2026, 10)     # 10/26~11/1 은 10월
    assert month_of_week(monday_of(D("2026-11-01"))) == (2026, 10)
    assert month_of_week(D("2026-11-30")) == (2026, 11)     # 11/30~12/6 은 11월


def test_11월의_주_목록():
    assert weeks_of_month(2026, 11) == [D("2026-11-02"), D("2026-11-09"), D("2026-11-16"),
                                        D("2026-11-23"), D("2026-11-30")]
    assert weeks_of_month(2026, 10)[-1] == D("2026-10-26")


def test_1일이_월요일인_달():
    assert weeks_of_month(2026, 6)[0] == D("2026-06-01")


def test_참고_주는_직전_달_마지막_주():
    assert reference_week(2026, 11) == D("2026-10-26")
    assert reference_week(2027, 1) == weeks_of_month(2026, 12)[-1]


def test_그_달_몇째_주():
    assert week_index_in_month(D("2026-11-02")) == 1
    assert week_index_in_month(D("2026-11-30")) == 5
    assert week_index_in_month(D("2026-10-26")) == 4   # 10월 4주 (10/5, 12, 19, 26)


def test_주의_7일():
    days = week_dates(D("2026-11-30"))
    assert days[0] == D("2026-11-30") and days[-1] == D("2026-12-06")


def test_집계용_달력_날짜는_주와_무관():
    days = month_dates(2026, 11)
    assert days[0] == D("2026-11-01") and days[-1] == D("2026-11-30") and len(days) == 30


def test_ISO_연간_주차():
    assert iso_week(D("2026-11-02")) == 45
    assert iso_week(D("2026-12-28")) == 53
