"""설정 화면의 운영 기준값 (settings 테이블) + 임시공휴일.

비율 기준값은 보류 (PLAN P5).
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from app.repository import change_log_repo, programs_repo, schedule_repo, settings_repo

Result = dict[str, Any]


def _fail(*msgs: str) -> Result:
    return {"ok": False, "errors": list(msgs)}


def get_rules(conn: sqlite3.Connection) -> Result:
    fixed_ids = settings_repo.get(conn, "fixed_program_ids", [])
    names = {pid: n for pid, n, _ in programs_repo.name_index(conn)}
    return {
        "ok": True,
        "offweek_policy_default": settings_repo.get(conn, "offweek_policy_default", "rerun"),
        "fixed_programs": [{"id": pid, "name": names.get(pid, "(삭제된 프로그램)")} for pid in fixed_ids],
        "holidays": schedule_repo.list_manual_holidays(conn),
    }


def save_rules(conn: sqlite3.Connection, payload: dict[str, Any]) -> Result:
    errors: list[str] = []
    offweek = payload.get("offweek_policy_default")
    if offweek not in ("rerun", "empty"):
        errors.append("방송 없는 주 처리를 골라 주세요.")
    fixed = [str(x) for x in (payload.get("fixed_program_ids") or [])]
    names = {pid for pid, _n, _a in programs_repo.name_index(conn)}
    if any(pid not in names for pid in fixed):
        errors.append("고정 편성 목록에 없는 프로그램이 있습니다. 다시 골라 주세요.")
    if len(set(fixed)) != len(fixed):
        errors.append("고정 편성 목록에 같은 프로그램이 두 번 있습니다.")
    if errors:
        return _fail(*errors)
    before = get_rules(conn)
    settings_repo.set_value(conn, "offweek_policy_default", offweek)
    settings_repo.set_value(conn, "fixed_program_ids", fixed)
    change_log_repo.add(conn, "settings", None, "운영 설정 변경",
                        {"offweek_policy_default": before["offweek_policy_default"]},
                        {"offweek_policy_default": offweek,
                         "fixed_program_ids": fixed}, "운영 설정 변경")
    return {**get_rules(conn), "message": "설정을 저장했습니다."}


def add_holiday(conn: sqlite3.Connection, d_raw: Any, name: Any) -> Result:
    try:
        d = date.fromisoformat(str(d_raw))
    except ValueError:
        return _fail("날짜를 골라 주세요.")
    name = " ".join(str(name or "").split())
    if not name:
        return _fail("공휴일 이름을 입력해 주세요. (예: 임시공휴일)")
    schedule_repo.add_manual_holiday(conn, d, name)
    change_log_repo.add(conn, "holiday", d.isoformat(), "임시공휴일 추가", None, {"name": name}, f"{d} {name} 추가")
    return {**get_rules(conn), "message": f"{d.month}/{d.day} {name}을(를) 추가했습니다."}


def delete_holiday(conn: sqlite3.Connection, d_raw: Any) -> Result:
    try:
        d = date.fromisoformat(str(d_raw))
    except ValueError:
        return _fail("날짜가 올바르지 않습니다.")
    schedule_repo.delete_manual_holiday(conn, d)
    change_log_repo.add(conn, "holiday", d.isoformat(), "임시공휴일 삭제", None, None, f"{d} 공휴일 삭제")
    return {**get_rules(conn), "message": "삭제했습니다."}
