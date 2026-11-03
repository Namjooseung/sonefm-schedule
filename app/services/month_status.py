"""월 상태: 작성중 → 확정 → 마감.

- 확정: 편집은 되지만 변경 기록에 '확정 후 변경'으로 남는다. 확정 취소로 작성중으로 돌릴 수 있다.
- 마감: 보고서를 낸 달. 편집 잠금. 풀려면 사유를 입력해야 하고, 풀면 확정 상태가 된다.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.repository import change_log_repo, schedule_repo

Result = dict[str, Any]

# 동작: (허용되는 현재 상태, 바뀔 상태, 시각 기록 칸, 변경 기록 이름)
_TRANSITIONS = {
    "confirm": (("작성중",), "확정", "confirmed_at", "확정"),
    "reopen": (("확정",), "작성중", None, "확정 취소"),
    "close": (("확정",), "마감", "closed_at", "마감"),
    "unlock": (("마감",), "확정", None, "잠금 해제"),
}
_HINT = {
    "confirm": "작성 중인 달만 확정할 수 있습니다. 먼저 편성을 생성해 주세요.",
    "reopen": "확정된 달만 확정을 취소할 수 있습니다.",
    "close": "확정한 달만 마감할 수 있습니다. 먼저 확정해 주세요.",
    "unlock": "마감된 달만 잠금을 풀 수 있습니다.",
}


def change(conn: sqlite3.Connection, year: Any, month: Any, action: str, reason: str | None = None) -> Result:
    try:
        y, m = int(year), int(month)
    except (TypeError, ValueError):
        return {"ok": False, "errors": ["연도와 월을 다시 골라 주세요."]}
    if action not in _TRANSITIONS or not (1 <= m <= 12):
        return {"ok": False, "errors": ["요청이 올바르지 않습니다."]}
    ym = f"{y:04d}-{m:02d}"
    allowed, new_status, stamp, label = _TRANSITIONS[action]
    current = schedule_repo.month_status_of(conn, ym)
    if current not in allowed:
        return {"ok": False, "errors": [_HINT[action]]}
    reason = (reason or "").strip()
    if action == "unlock" and not reason:
        return {"ok": False, "errors": ["잠금을 푸는 사유를 입력해 주세요."]}
    schedule_repo.set_month_status(conn, ym, new_status, stamp, reason if action == "unlock" else None)
    note = f"{m}월 {label}" + (f" — 사유: {reason}" if reason else "")
    change_log_repo.add(conn, "month", ym, label, {"status": current}, {"status": new_status}, note)
    return {"ok": True, "status": new_status, "message": note}
