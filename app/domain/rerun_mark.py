"""재방 표시('재' / 엑셀 '(재)')를 붙일지.

본방 자리에 나가는 재방(격주 쉬는 주, 부정기 프로그램의 본방 자리 등)에는 표시를 붙이지 않는다.
회차·집계에서는 그대로 재방이다 — 표시만 다르다.

판정
1. 칸이 편성 자리에서 나왔으면(original_slot_id) 그 자리의 역할이 본방인지로.
2. 자리 정보가 없으면(엑셀에서 가져온 칸 등) 같은 프로그램의 직전 본방이 같은 요일·시각이었는지로
   (휴방 기간처럼 몇 주씩 재방이 이어져도 같은 자리면 본방 자리). 직전 본방이 없으면
   다음 3주 안에 같은 자리에서 본방이 나오는지로.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from app.domain.models import Cell

NEARBY_WEEKS = 3


def rerun_marks(cells: Iterable[Cell], slot_roles: dict[str, str]) -> dict[tuple[date, int], bool]:
    """재방 칸마다 표시를 붙일지(True) 말지(False). cells는 직전 본방을 찾을 만큼 앞쪽 이력을 포함해야 한다."""
    cells = sorted(cells, key=lambda c: c.key)
    ons: dict[str, list[Cell]] = {}
    for c in cells:
        if c.kind == "본방":
            ons.setdefault(c.program_id, []).append(c)
    out: dict[tuple[date, int], bool] = {}
    for c in cells:
        if c.kind != "재방":
            continue
        role = slot_roles.get(c.original_slot_id) if c.original_slot_id else None
        if role is not None:
            out[c.key] = role != "본방"
            continue
        same_pos = lambda o: o.date.weekday() == c.date.weekday() and o.hour == c.hour  # noqa: E731
        history = ons.get(c.program_id, [])
        prev = [o for o in history if o.key < c.key]
        if prev:
            main = same_pos(prev[-1])
        else:
            limit = c.date + timedelta(weeks=NEARBY_WEEKS)
            main = any(same_pos(o) for o in history if c.key < o.key and o.date <= limit)
        out[c.key] = not main
    return out
