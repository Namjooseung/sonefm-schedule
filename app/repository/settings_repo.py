"""settings 테이블 (운영 기준값). 값은 JSON으로 저장한다."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.repository._common import new_id, now_iso


def get_all(conn: sqlite3.Connection) -> dict[str, Any]:
    return {k: json.loads(v) for k, v in conn.execute("SELECT key, value_json FROM settings")}


def get(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
    return default if row is None else json.loads(row[0])


def set_value(conn: sqlite3.Connection, key: str, value: Any) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO settings (id, key, value_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at",
        (new_id(), key, json.dumps(value, ensure_ascii=False), ts, ts))
