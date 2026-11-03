"""프로그램 관리 흐름."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from app.db.connection import savepoint
from app.domain import programs as rules
from app.repository import change_log_repo, programs_repo

Result = dict[str, Any]


def _fail(errors: list[str]) -> Result:
    return {"ok": False, "errors": errors}


def list_programs(conn: sqlite3.Connection, query: str = "", include_ended: bool = False,
                  today: str | None = None) -> list[dict[str, Any]]:
    today = today or date.today().isoformat()
    counts = programs_repo.slot_counts(conn)
    items = programs_repo.list_programs(conn, query, include_ended, today)
    for p in items:
        p["slot_count"] = counts.get(p["id"], 0)
        p["is_ended"] = bool(p["end_date"] and p["end_date"] < today)
        p["cycle_label"] = rules.CYCLE_TYPES.get(p["cycle_type"], p["cycle_type"])
    return items


def get_program(conn: sqlite3.Connection, program_id: str) -> Result:
    p = programs_repo.get_program(conn, program_id)
    if p is None:
        return _fail(["프로그램을 찾지 못했습니다. 목록을 새로 고쳐 주세요."])
    return {"ok": True, "program": p}


def save_program(conn: sqlite3.Connection, payload: dict[str, Any]) -> Result:
    """새로 등록(id 없음) 또는 수정(id 있음). 기본 정보·별칭·편성 자리를 한 번에 저장한다."""
    program_id = payload.get("id") or None
    before = programs_repo.get_program(conn, program_id) if program_id else None
    if program_id and before is None:
        return _fail(["수정하려는 프로그램이 없습니다. 목록을 새로 고쳐 주세요."])

    program, errors = rules.clean_program(payload)
    aliases = rules.clean_aliases(payload.get("aliases"), program["name"])
    slots, slot_errors = rules.clean_slots(payload.get("slots"), program["cycle_type"])
    errors += slot_errors
    errors += rules.check_name_conflicts(program_id, program["name"], aliases,
                                         programs_repo.name_index(conn))
    if errors:
        return _fail(errors)

    try:
        with savepoint(conn, "save_program"):
            if program_id:
                programs_repo.update_program(conn, program_id, program)
                action = "수정"
            else:
                program_id = programs_repo.insert_program(conn, program)
                action = "등록"
            programs_repo.replace_aliases(conn, program_id, aliases)
            programs_repo.sync_slots(conn, program_id, slots)
            after = programs_repo.get_program(conn, program_id)
            change_log_repo.add(conn, "program", program_id, action, before, after)
    except sqlite3.IntegrityError:
        return _fail(["이미 편성표에 쓰인 편성 자리는 지울 수 없습니다. "
                      "지우는 대신 적용 종료일을 넣어 주세요."])
    return {"ok": True, "program": after}


def end_program(conn: sqlite3.Connection, program_id: str, end_date: str) -> Result:
    """종영 처리: 종영일을 넣고, 열려 있는 편성 자리를 종영일에 닫는다."""
    before = programs_repo.get_program(conn, program_id)
    if before is None:
        return _fail(["프로그램을 찾지 못했습니다."])
    errors: list[str] = []
    end = rules.parse_date(end_date, "종영일", errors, required=True)
    if errors or end is None:
        return _fail(errors)
    if before["start_date"] and end < before["start_date"]:
        return _fail(["종영일이 시작일보다 빠릅니다."])
    slots, errors = rules.plan_end_program(end, before["slots"])
    if errors:
        return _fail(errors)
    programs_repo.set_end_date(conn, program_id, end)
    programs_repo.sync_slots(conn, program_id, slots)
    after = programs_repo.get_program(conn, program_id)
    change_log_repo.add(conn, "program", program_id, "종영", before, after)
    return {"ok": True, "program": after}


def resume_program(conn: sqlite3.Connection, program_id: str) -> Result:
    """종영 취소: 종영일만 지운다. 닫힌 편성 자리는 필요하면 새로 추가한다."""
    before = programs_repo.get_program(conn, program_id)
    if before is None:
        return _fail(["프로그램을 찾지 못했습니다."])
    programs_repo.set_end_date(conn, program_id, None)
    after = programs_repo.get_program(conn, program_id)
    change_log_repo.add(conn, "program", program_id, "종영 취소", before, after)
    return {"ok": True, "program": after}


def delete_program(conn: sqlite3.Connection, program_id: str) -> Result:
    """잘못 등록한 프로그램 삭제. 편성표에 한 번이라도 쓰였으면 삭제 대신 종영하도록 안내한다."""
    before = programs_repo.get_program(conn, program_id)
    if before is None:
        return _fail(["프로그램을 찾지 못했습니다."])
    if programs_repo.is_referenced(conn, program_id):
        return _fail(["편성표에 이미 쓰인 프로그램은 지울 수 없습니다. 대신 종영 처리해 주세요."])
    programs_repo.delete_program(conn, program_id)
    change_log_repo.add(conn, "program", program_id, "삭제", before, None)
    return {"ok": True}


def create_special(conn: sqlite3.Connection, payload: dict[str, Any]) -> Result:
    """특집 빠른 등록: 이름·분야·청취자참여만 받아 단발 프로그램을 만든다."""
    return save_program(conn, {
        "name": payload.get("name"),
        "category": payload.get("category"),
        "is_listener_participation": payload.get("is_listener_participation", False),
        "cycle_type": "oneoff",
        "start_episode": 1,
    })
