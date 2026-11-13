"""앱 시작 준비: 설정 읽기 → (DB가 없으면 씨앗 DB 복사) → 시작 백업 → 마이그레이션(필요 시 직전 백업 포함)."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.backup import backup_db, prune_backups
from app.config import AppConfig, load_config, migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations

log = logging.getLogger("sonefm.startup")


@dataclass
class StartupResult:
    config: AppConfig
    schema_version: int


def _copy_seed(seed_db: Path, db_path: Path) -> None:
    """씨앗 DB를 새 DB 위치로 복사한다 (SQLite 백업 API 사용)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{seed_db}?mode=ro", uri=True)
    dest = sqlite3.connect(db_path)
    try:
        src.backup(dest)
    finally:
        dest.close()
        src.close()
    log.info("기본 데이터로 시작: %s → %s", seed_db, db_path)


def prepare(cfg: AppConfig | None = None, seed_db: str | Path | None = None) -> StartupResult:
    """seed_db를 주면, DB 파일이 아직 없을 때 그 파일을 복사해 시작한다."""
    cfg = cfg or load_config()
    if seed_db and not Path(cfg.db_path).exists() and Path(seed_db).is_file():
        _copy_seed(Path(seed_db), Path(cfg.db_path))
    backup_db(cfg.db_path, cfg.backup_dir, reason="startup")

    def _before_migrate(old: int, new: int) -> None:
        # 기존 데이터가 있는 DB를 업그레이드할 때만 별도 백업
        if old > 0:
            backup_db(cfg.db_path, cfg.backup_dir, reason=f"before-v{new}")

    conn = connect(cfg.db_path)
    try:
        version = apply_migrations(conn, migrations_dir(), before_apply=_before_migrate)
    finally:
        conn.close()
    prune_backups(cfg.backup_dir, cfg.backup_keep)
    log.info("시작 준비 완료: DB=%s, 스키마 v%d", cfg.db_path, version)
    return StartupResult(cfg, version)
