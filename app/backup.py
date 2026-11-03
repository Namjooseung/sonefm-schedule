"""DB 자동 백업.

SQLite 백업 API로 복사하므로 쓰는 도중이어도 일관된 사본이 만들어진다.
파일 이름: schedule_YYYYMMDD_HHMMSS_<사유>.db
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger("sonefm.backup")

_PATTERN = re.compile(r"^schedule_\d{8}_\d{6}(_[\w-]+)?\.db$")


def backup_db(db_path: str | Path, backup_dir: str | Path, reason: str = "startup",
              now: datetime | None = None) -> Path | None:
    """DB 파일을 백업 폴더에 복사한다. DB 파일이 아직 없으면 아무것도 하지 않는다."""
    src = Path(db_path)
    if not src.exists():
        return None
    folder = Path(backup_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    dest = folder / f"schedule_{stamp}_{reason}.db"
    n = 1
    while dest.exists():
        dest = folder / f"schedule_{stamp}_{reason}-{n}.db"
        n += 1
    source = sqlite3.connect(src)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    log.info("백업 생성: %s", dest)
    return dest


def prune_backups(backup_dir: str | Path, keep: int) -> list[Path]:
    """오래된 백업부터 지워 최신 keep개만 남긴다. 지운 파일 목록을 돌려준다."""
    folder = Path(backup_dir)
    if keep < 1 or not folder.exists():
        return []
    files = sorted(p for p in folder.iterdir() if _PATTERN.match(p.name))
    removed = files[:-keep] if len(files) > keep else []
    for p in removed:
        p.unlink()
        log.info("오래된 백업 삭제: %s", p)
    return removed
