"""programs / program_aliases / program_slots 테이블 접근."""
from __future__ import annotations

import sqlite3
from typing import Any

from app.repository._common import new_id, now_iso

_PROGRAM_COLS = (
    "name", "category", "is_listener_participation", "producer_type", "cycle_type",
    "cycle_anchor_date", "monthly_nth", "offweek_policy", "start_episode", "start_date",
    "end_date", "host", "cohort", "is_special", "memo", "show_episode",
)
_SLOT_COLS = ("weekday", "hour", "role", "valid_from", "valid_to")


def _program_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["is_listener_participation"] = bool(d["is_listener_participation"])
    d["is_special"] = bool(d["is_special"])
    d["show_episode"] = bool(d["show_episode"])
    return d


# ── 조회 ──────────────────────────────────────────

def list_programs(conn: sqlite3.Connection, query: str = "", include_ended: bool = True,
                  today: str | None = None) -> list[dict[str, Any]]:
    """목록. query는 이름·별칭 부분 일치. include_ended=False면 today 이전에 종영한 프로그램 제외."""
    sql = ["SELECT p.* FROM programs p WHERE 1=1"]
    args: list[Any] = []
    q = query.strip()
    if q:
        sql.append("AND (p.name LIKE ? OR EXISTS (SELECT 1 FROM program_aliases a"
                   " WHERE a.program_id = p.id AND a.alias LIKE ?))")
        args += [f"%{q}%", f"%{q}%"]
    if not include_ended and today:
        sql.append("AND (p.end_date IS NULL OR p.end_date >= ?)")
        args.append(today)
    sql.append("ORDER BY p.is_special, p.name COLLATE NOCASE")
    return [_program_row(r) for r in conn.execute(" ".join(sql), args)]


def get_program(conn: sqlite3.Connection, program_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM programs WHERE id = ?", (program_id,)).fetchone()
    if row is None:
        return None
    p = _program_row(row)
    p["aliases"] = get_aliases(conn, program_id)
    p["slots"] = get_slots(conn, program_id)
    return p


def get_aliases(conn: sqlite3.Connection, program_id: str) -> list[str]:
    rows = conn.execute("SELECT alias FROM program_aliases WHERE program_id = ? ORDER BY rowid",
                        (program_id,))
    return [r[0] for r in rows]


def get_slots(conn: sqlite3.Connection, program_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, weekday, hour, role, valid_from, valid_to FROM program_slots"
        " WHERE program_id = ? ORDER BY valid_from, weekday, hour", (program_id,))
    return [dict(r) for r in rows]


def name_index(conn: sqlite3.Connection) -> list[tuple[str, str, list[str]]]:
    """(id, 이름, 별칭 목록) — 이름·별칭 중복 검사용."""
    aliases: dict[str, list[str]] = {}
    for pid, alias in conn.execute("SELECT program_id, alias FROM program_aliases"):
        aliases.setdefault(pid, []).append(alias)
    return [(pid, name, aliases.get(pid, []))
            for pid, name in conn.execute("SELECT id, name FROM programs")]


def slot_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """프로그램별 편성 자리 수 (목록 표시용)."""
    return {pid: n for pid, n in conn.execute(
        "SELECT program_id, COUNT(*) FROM program_slots GROUP BY program_id")}


# ── 쓰기 ──────────────────────────────────────────

def insert_program(conn: sqlite3.Connection, data: dict[str, Any]) -> str:
    pid = new_id()
    ts = now_iso()
    cols = ", ".join(_PROGRAM_COLS)
    marks = ", ".join("?" for _ in _PROGRAM_COLS)
    conn.execute(
        f"INSERT INTO programs (id, {cols}, created_at, updated_at) VALUES (?, {marks}, ?, ?)",
        (pid, *[data[c] for c in _PROGRAM_COLS], ts, ts))
    return pid


def update_program(conn: sqlite3.Connection, program_id: str, data: dict[str, Any]) -> None:
    sets = ", ".join(f"{c} = ?" for c in _PROGRAM_COLS)
    conn.execute(f"UPDATE programs SET {sets}, updated_at = ? WHERE id = ?",
                 (*[data[c] for c in _PROGRAM_COLS], now_iso(), program_id))


def set_end_date(conn: sqlite3.Connection, program_id: str, end_date: str | None) -> None:
    conn.execute("UPDATE programs SET end_date = ?, updated_at = ? WHERE id = ?",
                 (end_date, now_iso(), program_id))


def replace_aliases(conn: sqlite3.Connection, program_id: str, aliases: list[str]) -> None:
    current = get_aliases(conn, program_id)
    if current == aliases:
        return
    conn.execute("DELETE FROM program_aliases WHERE program_id = ?", (program_id,))
    ts = now_iso()
    conn.executemany(
        "INSERT INTO program_aliases (id, program_id, alias, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [(new_id(), program_id, a, ts, ts) for a in aliases])


def sync_slots(conn: sqlite3.Connection, program_id: str, slots: list[dict[str, Any]]) -> None:
    """화면의 편성 자리 목록과 DB를 맞춘다. id가 있으면 수정, 없으면 추가, 목록에서 빠진 것은 삭제.

    이미 편성 칸이 참조하는 자리를 삭제하면 외래 키 오류(sqlite3.IntegrityError)가 난다.
    """
    existing = {s["id"]: s for s in get_slots(conn, program_id)}
    keep: set[str] = set()
    ts = now_iso()
    for s in slots:
        sid = s.get("id")
        if sid and sid in existing:
            keep.add(sid)
            if any(existing[sid][c] != s[c] for c in _SLOT_COLS):
                conn.execute(
                    "UPDATE program_slots SET weekday = ?, hour = ?, role = ?, valid_from = ?,"
                    " valid_to = ?, updated_at = ? WHERE id = ? AND program_id = ?",
                    (*[s[c] for c in _SLOT_COLS], ts, sid, program_id))
        else:
            conn.execute(
                "INSERT INTO program_slots (id, program_id, weekday, hour, role, valid_from,"
                " valid_to, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (new_id(), program_id, *[s[c] for c in _SLOT_COLS], ts, ts))
    for sid in existing.keys() - keep:
        conn.execute("DELETE FROM program_slots WHERE id = ?", (sid,))


def delete_program(conn: sqlite3.Connection, program_id: str) -> None:
    """편성 칸·결방 기록이 참조하면 외래 키 오류가 난다 (그때는 종영 처리를 쓴다)."""
    conn.execute("DELETE FROM programs WHERE id = ?", (program_id,))


def is_referenced(conn: sqlite3.Connection, program_id: str) -> bool:
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM schedule_cells WHERE program_id = ? OR original_program_id = ?)"
        " OR EXISTS (SELECT 1 FROM cancellations WHERE program_id = ?)",
        (program_id, program_id, program_id)).fetchone()
    return bool(row[0])


# ── 편성 자리 단건 (칸 팝업의 '이후 전부') ────────

def insert_slot(conn: sqlite3.Connection, program_id: str, weekday: int, hour: int, role: str,
                valid_from: str, valid_to: str | None) -> str:
    sid = new_id()
    ts = now_iso()
    conn.execute(
        "INSERT INTO program_slots (id, program_id, weekday, hour, role, valid_from, valid_to,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, program_id, weekday, hour, role, valid_from, valid_to, ts, ts))
    return sid


def set_slot_valid_to(conn: sqlite3.Connection, slot_id: str, valid_to: str | None) -> None:
    conn.execute("UPDATE program_slots SET valid_to = ?, updated_at = ? WHERE id = ?", (valid_to, now_iso(), slot_id))


def delete_slot_force(conn: sqlite3.Connection, slot_id: str) -> None:
    """칸이 참조하고 있으면 참조를 끊고 지운다 (칸은 곧 다시 생성된다)."""
    conn.execute("UPDATE schedule_cells SET original_slot_id = NULL WHERE original_slot_id = ?", (slot_id,))
    conn.execute("DELETE FROM program_slots WHERE id = ?", (slot_id,))
