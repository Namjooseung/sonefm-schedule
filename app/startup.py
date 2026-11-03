"""앱 시작 준비: 설정 읽기 → 시작 백업 → 마이그레이션(필요 시 직전 백업 포함)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.backup import backup_db, prune_backups
from app.config import AppConfig, load_config, migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations

log = logging.getLogger("sonefm.startup")


@dataclass
class StartupResult:
    config: AppConfig
    schema_version: int


def prepare(cfg: AppConfig | None = None) -> StartupResult:
    cfg = cfg or load_config()
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
