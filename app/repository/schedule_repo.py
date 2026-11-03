"""schedule_cells / cancellations / month_plans / holidays(수동) 테이블 접근."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from app.domain.models import Cell, ProgramRule, SlotRule
from app.repository._common import new_id, now_iso

_D = date.fromisoformat


def _cell(row: sqlite3.Row) -> Cell:
    return Cell(date=_D(row["date"]), hour=row["hour"], program_id=row["program_id"], kind=row["kind"],
                source=row["source"], original_slot_id=row["original_slot_id"],
                rerun_episode_override=row["rerun_episode_override"],
                exception_type=row["exception_type"], original_program_id=row["original_program_id"])


# ── 칸 ────────────────────────────────────────────

def cells_until(conn: sqlite3.Connection, last: date) -> list[Cell]:
    """last 날짜까지의 모든 칸 (회차 계산은 전체 이력이 필요하다)."""
    rows = conn.execute("SELECT * FROM schedule_cells WHERE date <= ? ORDER BY date, hour", (last.isoformat(),))
    return [_cell(r) for r in rows]


def cell_rows_between(conn: sqlite3.Connection, first: date, last: date) -> list[dict[str, Any]]:
    """화면 표시용 원본 행 (준비 상태·실제 변경 메모 포함)."""
    rows = conn.execute("SELECT * FROM schedule_cells WHERE date BETWEEN ? AND ? ORDER BY date, hour",
                        (first.isoformat(), last.isoformat()))
    return [dict(r) for r in rows]


def cells_between(conn: sqlite3.Connection, first: date, last: date) -> list[Cell]:
    rows = conn.execute("SELECT * FROM schedule_cells WHERE date BETWEEN ? AND ?",
                        (first.isoformat(), last.isoformat()))
    return [_cell(r) for r in rows]


def upsert_rule_cell(conn: sqlite3.Connection, c: Cell) -> None:
    """규칙으로 만든 칸 쓰기. 같은 자리에 칸이 있으면 내용을 바꾸고 규칙 칸으로 되돌린다."""
    ts = now_iso()
    conn.execute(
        "INSERT INTO schedule_cells (id, date, hour, program_id, kind, source, original_slot_id,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'rule', ?, ?, ?)"
        " ON CONFLICT(date, hour) DO UPDATE SET program_id = excluded.program_id, kind = excluded.kind,"
        " source = 'rule', original_slot_id = excluded.original_slot_id, exception_type = NULL,"
        " original_program_id = NULL, rerun_episode_override = NULL, updated_at = excluded.updated_at",
        (new_id(), c.date.isoformat(), c.hour, c.program_id, c.kind, c.original_slot_id, ts, ts))


def delete_cell(conn: sqlite3.Connection, d: date, hour: int) -> None:
    conn.execute("DELETE FROM schedule_cells WHERE date = ? AND hour = ?", (d.isoformat(), hour))


# ── 결방 ──────────────────────────────────────────

def cancellation_keys(conn: sqlite3.Connection, first: date, last: date) -> set[tuple[str, date, int]]:
    rows = conn.execute("SELECT program_id, original_date, original_hour FROM cancellations"
                        " WHERE original_date BETWEEN ? AND ?", (first.isoformat(), last.isoformat()))
    return {(r[0], _D(r[1]), r[2]) for r in rows}


# ── 규칙 입력 ─────────────────────────────────────

def program_rules(conn: sqlite3.Connection) -> dict[str, ProgramRule]:
    out: dict[str, ProgramRule] = {}
    for r in conn.execute("SELECT * FROM programs"):
        out[r["id"]] = ProgramRule(
            id=r["id"], cycle_type=r["cycle_type"], start_episode=r["start_episode"],
            cycle_anchor_date=_D(r["cycle_anchor_date"]) if r["cycle_anchor_date"] else None,
            monthly_nth=r["monthly_nth"], offweek_policy=r["offweek_policy"],
            start_date=_D(r["start_date"]) if r["start_date"] else None,
            end_date=_D(r["end_date"]) if r["end_date"] else None)
    return out


def slot_rules(conn: sqlite3.Connection) -> list[SlotRule]:
    return [SlotRule(id=r["id"], program_id=r["program_id"], weekday=r["weekday"], hour=r["hour"],
                     role=r["role"], valid_from=_D(r["valid_from"]),
                     valid_to=_D(r["valid_to"]) if r["valid_to"] else None)
            for r in conn.execute("SELECT * FROM program_slots")]


def program_display(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """화면 표시용 프로그램 정보 (이름·분야·특집 여부)."""
    return {r["id"]: {"name": r["name"], "category": r["category"], "is_special": bool(r["is_special"]),
                      "cycle_type": r["cycle_type"], "show_episode": bool(r["show_episode"])}
            for r in conn.execute("SELECT id, name, category, is_special, cycle_type, show_episode FROM programs")}


# ── 월 상태 ───────────────────────────────────────

def get_month_plan(conn: sqlite3.Connection, year_month: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM month_plans WHERE year_month = ?", (year_month,)).fetchone()
    return dict(row) if row else None


def month_statuses(conn: sqlite3.Connection, year: int) -> dict[str, str]:
    rows = conn.execute("SELECT year_month, status FROM month_plans WHERE year_month LIKE ?", (f"{year}-%",))
    return {r[0]: r[1] for r in rows}


def touch_month_generated(conn: sqlite3.Connection, year_month: str) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO month_plans (id, year_month, status, generated_at, created_at, updated_at)"
        " VALUES (?, ?, '작성중', ?, ?, ?)"
        " ON CONFLICT(year_month) DO UPDATE SET generated_at = excluded.generated_at,"
        " updated_at = excluded.updated_at",
        (new_id(), year_month, ts, ts, ts))


# ── 공휴일 (수동 추가분) ──────────────────────────

def manual_holidays(conn: sqlite3.Connection, first: date, last: date) -> dict[date, str]:
    rows = conn.execute("SELECT date, name FROM holidays WHERE source = 'manual' AND date BETWEEN ? AND ?",
                        (first.isoformat(), last.isoformat()))
    return {_D(r[0]): r[1] for r in rows}


# ── 칸 편집 (P4) ──────────────────────────────────

def get_cell_row(conn: sqlite3.Connection, d: date, hour: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM schedule_cells WHERE date = ? AND hour = ?", (d.isoformat(), hour)).fetchone()
    return dict(row) if row else None


_CELL_EDITABLE = ("program_id", "kind", "source", "exception_type", "original_program_id", "original_slot_id",
                  "rerun_episode_override", "prep_status", "actual_change_note")


def update_cell(conn: sqlite3.Connection, d: date, hour: int, **fields: Any) -> None:
    bad = set(fields) - set(_CELL_EDITABLE)
    if bad:
        raise ValueError(f"고칠 수 없는 칸 항목: {bad}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE schedule_cells SET {sets}, updated_at = ? WHERE date = ? AND hour = ?",
                 (*fields.values(), now_iso(), d.isoformat(), hour))


def put_manual_cell(conn: sqlite3.Connection, d: date, hour: int, program_id: str, kind: str,
                    exception_type: str | None, original_program_id: str | None,
                    original_slot_id: str | None) -> None:
    """사람이 넣은 칸 쓰기. 준비 상태·실제 변경 메모는 새 프로그램 기준으로 초기화한다."""
    ts = now_iso()
    conn.execute(
        "INSERT INTO schedule_cells (id, date, hour, program_id, kind, source, exception_type,"
        " original_program_id, original_slot_id, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'manual', ?, ?, ?, ?, ?)"
        " ON CONFLICT(date, hour) DO UPDATE SET program_id = excluded.program_id, kind = excluded.kind,"
        " source = 'manual', exception_type = excluded.exception_type,"
        " original_program_id = excluded.original_program_id, original_slot_id = excluded.original_slot_id,"
        " rerun_episode_override = NULL, prep_status = '미입고', actual_change_note = NULL,"
        " updated_at = excluded.updated_at",
        (new_id(), d.isoformat(), hour, program_id, kind, exception_type, original_program_id,
         original_slot_id, ts, ts))


def max_cell_date(conn: sqlite3.Connection) -> date | None:
    row = conn.execute("SELECT MAX(date) FROM schedule_cells").fetchone()
    return _D(row[0]) if row and row[0] else None


def add_cancellation(conn: sqlite3.Connection, program_id: str, d: date, hour: int, reason: str | None) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO cancellations (id, program_id, original_date, original_hour, reason, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(program_id, original_date, original_hour)"
        " DO UPDATE SET reason = excluded.reason, updated_at = excluded.updated_at",
        (new_id(), program_id, d.isoformat(), hour, reason, ts, ts))


def cancellations_at(conn: sqlite3.Connection, d: date, hour: int) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT program_id, reason FROM cancellations WHERE original_date = ? AND original_hour = ?",
                        (d.isoformat(), hour))
    return [dict(r) for r in rows]


def delete_cancellations_at(conn: sqlite3.Connection, d: date, hour: int) -> None:
    conn.execute("DELETE FROM cancellations WHERE original_date = ? AND original_hour = ?", (d.isoformat(), hour))


def month_status_of(conn: sqlite3.Connection, year_month: str) -> str | None:
    row = conn.execute("SELECT status FROM month_plans WHERE year_month = ?", (year_month,)).fetchone()
    return row[0] if row else None


def closed_months(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT year_month FROM month_plans WHERE status = '마감'")}


# ── 되돌리기용 스냅숏 ─────────────────────────────

def snapshot(conn: sqlite3.Connection, first: date, last: date, program_ids: list[str]) -> dict[str, Any]:
    """[first, last] 칸·결방 기록과 program_ids의 편성 자리 전체를 그대로 떠 둔다."""
    a, b = first.isoformat(), last.isoformat()
    marks = ",".join("?" for _ in program_ids)
    slots = [dict(r) for r in conn.execute(
        f"SELECT * FROM program_slots WHERE program_id IN ({marks})", program_ids)] if program_ids else []
    return {
        "first": a, "last": b, "program_ids": list(program_ids),
        "cells": [dict(r) for r in conn.execute("SELECT * FROM schedule_cells WHERE date BETWEEN ? AND ?", (a, b))],
        "cancellations": [dict(r) for r in conn.execute(
            "SELECT * FROM cancellations WHERE original_date BETWEEN ? AND ?", (a, b))],
        "slots": slots,
    }


def _insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        cols = ", ".join(r)
        marks = ", ".join("?" for _ in r)
        conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(r.values()))


def restore(conn: sqlite3.Connection, snap: dict[str, Any]) -> None:
    """snapshot()으로 떠 둔 상태로 되돌린다."""
    a, b = snap["first"], snap["last"]
    conn.execute("DELETE FROM schedule_cells WHERE date BETWEEN ? AND ?", (a, b))
    conn.execute("DELETE FROM cancellations WHERE original_date BETWEEN ? AND ?", (a, b))
    if snap["program_ids"]:
        keep = {s["id"] for s in snap["slots"]}
        marks = ",".join("?" for _ in snap["program_ids"])
        for (sid,) in conn.execute(f"SELECT id FROM program_slots WHERE program_id IN ({marks})",
                                   snap["program_ids"]).fetchall():
            if sid not in keep:
                conn.execute("UPDATE schedule_cells SET original_slot_id = NULL WHERE original_slot_id = ?", (sid,))
                conn.execute("DELETE FROM program_slots WHERE id = ?", (sid,))
        for s in snap["slots"]:
            cols = [c for c in s if c != "id"]
            conn.execute(
                f"INSERT INTO program_slots ({', '.join(s)}) VALUES ({', '.join('?' for _ in s)})"
                f" ON CONFLICT(id) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in cols)}",
                tuple(s.values()))
    _insert_rows(conn, "cancellations", snap["cancellations"])
    _insert_rows(conn, "schedule_cells", snap["cells"])


# ── 월 상태·검증 (P5) ─────────────────────────────

def set_month_status(conn: sqlite3.Connection, year_month: str, status: str,
                     stamp_field: str | None = None, unlock_reason: str | None = None) -> None:
    """월 상태 바꾸기. 행이 없으면 만든다. stamp_field: confirmed_at | closed_at."""
    if stamp_field not in (None, "confirmed_at", "closed_at"):
        raise ValueError(stamp_field)
    ts = now_iso()
    conn.execute(
        "INSERT INTO month_plans (id, year_month, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(year_month) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
        (new_id(), year_month, status, ts, ts))
    if stamp_field:
        conn.execute(f"UPDATE month_plans SET {stamp_field} = ? WHERE year_month = ?", (ts, year_month))
    if unlock_reason is not None:
        conn.execute("UPDATE month_plans SET unlock_reason = ? WHERE year_month = ?", (unlock_reason, year_month))


def cancellations_between(conn: sqlite3.Connection, first: date, last: date) -> list[tuple[str, date, int]]:
    rows = conn.execute("SELECT program_id, original_date, original_hour FROM cancellations"
                        " WHERE original_date BETWEEN ? AND ?", (first.isoformat(), last.isoformat()))
    return [(r[0], _D(r[1]), r[2]) for r in rows]


def months_using(conn: sqlite3.Connection, after: date, program_ids: list[str]) -> list[str]:
    """after 이후에 이 프로그램들의 칸이 있는 날짜(YYYY-MM-DD) 목록. 마감 달 영향 경고에 쓴다."""
    if not program_ids:
        return []
    marks = ",".join("?" for _ in program_ids)
    rows = conn.execute(
        f"SELECT DISTINCT date FROM schedule_cells WHERE date > ? AND program_id IN ({marks})",
        (after.isoformat(), *program_ids))
    return [r[0] for r in rows]


def list_manual_holidays(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT date, name FROM holidays WHERE source = 'manual' ORDER BY date")
    return [dict(r) for r in rows]


def add_manual_holiday(conn: sqlite3.Connection, d: date, name: str) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO holidays (id, date, name, source, created_at, updated_at) VALUES (?, ?, ?, 'manual', ?, ?)"
        " ON CONFLICT(date, source) DO UPDATE SET name = excluded.name, updated_at = excluded.updated_at",
        (new_id(), d.isoformat(), name, ts, ts))


def delete_manual_holiday(conn: sqlite3.Connection, d: date) -> None:
    conn.execute("DELETE FROM holidays WHERE source = 'manual' AND date = ?", (d.isoformat(),))
