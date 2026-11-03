"""엑셀 편성표 쓰기 — 기존 양식과 같은 배치·서식, 수식 없이 글자만.

배치 (기존 엑셀과 같음)
- B1:D1 병합: 그 달 1일 (표시 형식 '2026년 11월')
- 주마다 머리글 1줄 + 06~22시 17줄. A열 = 'M-주차' / 'HH:00~HH:57', B~H = 월~일
- 고정 편성 줄(굿모닝!/굿바이!)은 B~H를 병합하고 비워 둔다
- 재방 칸은 연노랑 배경
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

_THIN = Side(style="thin")
BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
FILL_HEADER = PatternFill("solid", fgColor="FF9FC5E8")
FILL_RERUN = PatternFill("solid", fgColor="FFFFF2CC")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(vertical="center", wrap_text=True)

FONT_TITLE = Font(name="Arial", size=32)
FONT_WEEK = Font(name="Calibri", size=19, bold=True)
FONT_TIME = Font(name="Malgun Gothic", size=12, bold=True)
FONT_CELL = Font(name="Gulim", size=12, bold=True)

COL_WIDTHS = {"A": 16.4, "B": 35, "C": 35.5, "D": 35, "E": 37, "F": 37, "G": 34, "H": 39}
HEIGHT_TITLE, HEIGHT_WEEK, HEIGHT_BAND, HEIGHT_CELL = 64.5, 35.25, 34.5, 41.25


@dataclass
class WeekBlock:
    label: str                                    # '11-45'
    days: list[int]                               # 일(日) 7개
    rows: dict[int, list[tuple[str, bool]]] = field(default_factory=dict)   # 시 → [(글자, 재방 여부)] × 7
    bands: set[int] = field(default_factory=set)  # 병합해서 비울 시각 (고정 편성)


@dataclass
class MonthSheet:
    title: str            # '2611'
    first_day: date
    weeks: list[WeekBlock]


def _time_label(h: int) -> str:
    return f"{h:02d}:00~{h:02d}:57"


def write_months(sheets: list[MonthSheet], path: str | Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for sheet in sheets:
        ws = wb.create_sheet(sheet.title)
        for col, w in COL_WIDTHS.items():
            ws.column_dimensions[col].width = w
        ws.freeze_panes = "B1"
        ws.merge_cells("B1:D1")
        c = ws["B1"]
        c.value, c.number_format, c.font, c.alignment = sheet.first_day, 'yyyy"년" m"월"', FONT_TITLE, CENTER
        ws.row_dimensions[1].height = HEIGHT_TITLE

        r = 2
        for wk in sheet.weeks:
            ws.row_dimensions[r].height = HEIGHT_WEEK
            for col, v in enumerate([wk.label, *wk.days], start=1):
                cell = ws.cell(r, col, v)
                cell.font, cell.fill, cell.alignment, cell.border = FONT_WEEK, FILL_HEADER, CENTER, BORDER
            r += 1
            for h in range(6, 23):
                t = ws.cell(r, 1, _time_label(h))
                t.font, t.alignment, t.border = FONT_TIME, CENTER, BORDER
                if h in wk.bands:
                    ws.row_dimensions[r].height = HEIGHT_BAND
                    for col in range(2, 9):
                        ws.cell(r, col).border = BORDER
                    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=8)
                else:
                    ws.row_dimensions[r].height = HEIGHT_CELL
                    for col, (text, rerun) in enumerate(wk.rows.get(h, [("", False)] * 7), start=2):
                        cell = ws.cell(r, col, text or None)
                        cell.font, cell.alignment, cell.border = FONT_CELL, LEFT, BORDER
                        if rerun:
                            cell.fill = FILL_RERUN
                r += 1
    wb.save(path)
