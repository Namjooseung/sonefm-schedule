"""변경 기록 (언제, 무엇을, 어떻게 바꿨는지)."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.repository._common import new_id, now_iso


def add(conn: sqlite3.Connection, entity: str, entity_id: str | None, action: str,
        before: Any = None, after: Any = None, note: str | None = None) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO change_log (id, at, entity, entity_id, action, before_json, after_json, note,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (new_id(), ts, entity, entity_id, action,
         None if before is None else json.dumps(before, ensure_ascii=False),
         None if after is None else json.dumps(after, ensure_ascii=False),
         note, ts, ts),
    )


def list_for(conn: sqlite3.Connection, entity: str, entity_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT at, action, before_json, after_json, note FROM change_log"
        " WHERE entity = ? AND entity_id = ? ORDER BY at, rowid", (entity, entity_id)).fetchall()
    return [dict(r) for r in rows]
