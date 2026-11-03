"""기존 엑셀 편성표 읽기.

양식이 달마다 조금씩 달라서(주 머리글이 '11-44' / 날짜 / 숫자 등) 머리글 글자에 기대지 않는다.
- 'HH:00~HH:57' 시각 줄이 17줄 이어지는 덩어리를 한 주로 본다. 바로 위 줄이 주 머리글.
- 머리글 B~H의 날짜 숫자와 시트 이름(YYMM)으로 그 주 월요일을 계산한다.
- 수식 칸은 엑셀이 저장해 둔 계산 결과를 읽는다 (data_only).
- 가로로 병합된 칸은 병합 범위 전체에 같은 글자가 있는 것으로 본다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import openpyxl

_TITLE = re.compile(r"^\s*(\d{2})(\d{2})\s*$")
_TIME = re.compile(r"^\s*(\d{1,2})\s*:\s*00\s*~")
HOURS = list(range(6, 23))


@dataclass
class Week:
    monday: date
    header_row: int
    cells: dict[tuple[date, int], tuple[Any, str]] = field(default_factory=dict)   # (날짜, 시) → (값, 셀 주소)


@dataclass
class Sheet:
    title: str
    year: int | None
    month: int | None
    weeks: list[Week] = field(default_factory=list)


def _sheet_month(title: str) -> tuple[int, int] | None:
    m = _TITLE.match(title)
    if not m:
        return None
    y, mo = 2000 + int(m.group(1)), int(m.group(2))
    return (y, mo) if 1 <= mo <= 12 else None


def _day_number(v: Any) -> int | None:
    if isinstance(v, (int, float)) and float(v).is_integer() and 1 <= int(v) <= 31:
        return int(v)
    if hasattr(v, "day") and hasattr(v, "month"):    # 날짜로 적힌 머리글
        return int(v.day)
    return None


def _monday_from_header(year: int, month: int, days: list[int | None]) -> date | None:
    """머리글 날짜 숫자 → 그 주 월요일. 앞뒤 달까지 보고 요일이 맞는 날짜를 고른다."""
    first = date(year, month, 1)
    for col, day in enumerate(days):
        if day is None:
            continue
        candidates = []
        for dm in (-1, 0, 1):
            y, m = year, month + dm
            if m == 0:
                y, m = y - 1, 12
            elif m == 13:
                y, m = y + 1, 1
            try:
                d = date(y, m, day)
            except ValueError:
                continue
            if d.weekday() == col:
                candidates.append(d)
        if candidates:
            best = min(candidates, key=lambda d: abs((d - first).days - 14))
            return best - timedelta(days=col)
    return None


def _merged_values(ws) -> dict[tuple[int, int], tuple[int, int]]:
    """병합 범위 안의 칸 → 왼쪽 위 칸 좌표."""
    out = {}
    for rng in ws.merged_cells.ranges:
        for r in range(rng.min_row, rng.max_row + 1):
            for c in range(rng.min_col, rng.max_col + 1):
                out[(r, c)] = (rng.min_row, rng.min_col)
    return out


def read_workbook(path: str | Path) -> list[Sheet]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
    sheets: list[Sheet] = []
    for ws in wb.worksheets:
        ym = _sheet_month(ws.title)
        sheet = Sheet(ws.title, *(ym or (None, None)))
        sheets.append(sheet)
        if ym is None:
            continue
        merged = _merged_values(ws)

        def value(r: int, c: int) -> Any:
            r0, c0 = merged.get((r, c), (r, c))
            return ws.cell(r0, c0).value

        r = 1
        while r <= ws.max_row:
            a = ws.cell(r, 1).value
            m = _TIME.match(str(a)) if isinstance(a, str) else None
            if not (m and int(m.group(1)) == 6):
                r += 1
                continue
            header = r - 1
            days = [_day_number(ws.cell(header, c).value) for c in range(2, 9)]
            monday = _monday_from_header(ym[0], ym[1], days)
            if monday is None:
                r += 1
                continue
            week = Week(monday, header)
            for k in range(17):
                row = r + k
                label = ws.cell(row, 1).value
                tm = _TIME.match(str(label)) if isinstance(label, str) else None
                if not tm:
                    break
                hour = int(tm.group(1))
                for col in range(2, 9):
                    d = monday + timedelta(days=col - 2)
                    week.cells[(d, hour)] = (value(row, col), ws.cell(row, col).coordinate)
            sheet.weeks.append(week)
            r += 17
    wb.close()
    return sheets
