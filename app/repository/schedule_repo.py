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
                      "cycle_type": r["cycle_type"]}
            for r in conn.execute("SELECT id, name, category, is_special, cycle_type FROM programs")}


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
