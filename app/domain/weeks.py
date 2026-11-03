"""주와 달의 관계.

규칙
- 주는 월~일.
- 주의 소속 = 그 주 월요일이 속한 달. 예: 10/26(월)~11/1(일)은 10월 소속.
- 집계(검증·비율·보고서)는 주가 아니라 달력 날짜 기준 → month_dates 사용.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_of_week(monday: date) -> tuple[int, int]:
    """주가 속한 (연, 월)."""
    m = monday_of(monday)
    return m.year, m.month


def weeks_of_month(year: int, month: int) -> list[date]:
    """그 달 소속 주들의 월요일 목록."""
    first = date(year, month, 1)
    monday = first + timedelta(days=(7 - first.weekday()) % 7)
    out: list[date] = []
    while monday.month == month:
        out.append(monday)
        monday += timedelta(days=7)
    return out


def reference_week(year: int, month: int) -> date:
    """직전 달 마지막 주의 월요일 (다음 달 화면 맨 위 흐린 참고 줄)."""
    return weeks_of_month(year, month)[0] - timedelta(days=7)


def week_index_in_month(monday: date) -> int:
    """소속 달에서 몇째 주인지 (1부터)."""
    y, m = month_of_week(monday)
    return weeks_of_month(y, m).index(monday_of(monday)) + 1


def week_dates(monday: date) -> list[date]:
    return [monday + timedelta(days=i) for i in range(7)]


def generation_dates(year: int, month: int) -> list[date]:
    """그 달 소속 주에 들어 있는 모든 날짜 (편성 생성·편집 대상)."""
    return [d for w in weeks_of_month(year, month) for d in week_dates(w)]


def month_dates(year: int, month: int) -> list[date]:
    """달력상 그 달의 날짜 (집계 대상)."""
    n = calendar.monthrange(year, month)[1]
    return [date(year, month, i) for i in range(1, n + 1)]


def iso_week(d: date) -> int:
    """연간 주차 (ISO 8601)."""
    return d.isocalendar()[1]
