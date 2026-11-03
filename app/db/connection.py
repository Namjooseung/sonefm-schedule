"""SQLite 연결.

- 저널 모드는 DELETE(기본값). 이후 공유 폴더 이전을 대비해 WAL은 쓰지 않는다.
- 외래 키 검사를 켠다.
- pywebview의 js_api 호출은 여러 스레드에서 오므로, 호출마다 연결을 새로 연다.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = DELETE")
    return conn


@contextmanager
def savepoint(conn: sqlite3.Connection, name: str = "sp") -> Iterator[None]:
    """블록 안의 쓰기만 묶는다. 오류가 나면 블록 안의 변경만 되돌리고 오류를 다시 던진다."""
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        conn.execute(f"ROLLBACK TO {name}")
        conn.execute(f"RELEASE {name}")
        raise
    conn.execute(f"RELEASE {name}")


@contextmanager
def open_db(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """with 블록이 정상 종료되면 커밋, 오류면 롤백하고 항상 닫는다."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
