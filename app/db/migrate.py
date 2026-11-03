"""스키마 마이그레이션.

migrations/NNNN_이름.sql 파일을 번호 순서로 적용하고 PRAGMA user_version에 마지막 번호를 기록한다.
기존 파일은 절대 고치지 않고, 스키마를 바꿀 때는 새 번호 파일을 추가한다.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("sonefm.migrate")

_NAME = re.compile(r"^(\d{4})_[\w-]+\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int
    path: Path


def discover(folder: Path) -> list[Migration]:
    found: list[Migration] = []
    for p in folder.iterdir():
        m = _NAME.match(p.name)
        if m:
            found.append(Migration(int(m.group(1)), p))
    found.sort(key=lambda x: x.version)
    versions = [m.version for m in found]
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError(f"마이그레이션 번호가 1부터 연속되지 않습니다: {versions}")
    return found


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def pending(conn: sqlite3.Connection, folder: Path) -> list[Migration]:
    now = current_version(conn)
    return [m for m in discover(folder) if m.version > now]


def apply_migrations(
    conn: sqlite3.Connection,
    folder: Path,
    before_apply: Callable[[int, int], None] | None = None,
) -> int:
    """대기 중인 마이그레이션을 적용하고 최종 버전을 돌려준다.

    before_apply(현재버전, 목표버전)은 실제로 적용할 것이 있을 때만 한 번 불린다 (자동 백업용).
    각 파일은 하나의 트랜잭션으로 적용되어, 실패하면 그 파일 전체가 취소된다.
    """
    todo = pending(conn, folder)
    if not todo:
        return current_version(conn)
    if before_apply is not None:
        before_apply(current_version(conn), todo[-1].version)
    for mig in todo:
        sql = mig.path.read_text(encoding="utf-8")
        log.info("마이그레이션 적용: %s", mig.path.name)
        try:
            conn.executescript(f"BEGIN;\n{sql}\n;PRAGMA user_version = {mig.version};\nCOMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            log.exception("마이그레이션 실패: %s", mig.path.name)
            raise
    return current_version(conn)
