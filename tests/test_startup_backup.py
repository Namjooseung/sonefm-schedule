import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.backup import backup_db, prune_backups
from app.config import data_root, load_config
from app.startup import prepare


def test_첫_실행이면_DB를_만들고_백업은_없음(isolated_home):
    result = prepare()
    assert Path(result.config.db_path) == data_root() / "data" / "schedule.db"
    assert Path(result.config.db_path).exists()
    assert result.schema_version >= 1
    backups = Path(result.config.backup_dir)
    assert not backups.exists() or not any(backups.iterdir())


def test_두번째_실행부터_시작_백업(isolated_home):
    prepare()
    result = prepare()
    files = list(Path(result.config.backup_dir).glob("schedule_*_startup*.db"))
    assert len(files) == 1
    with sqlite3.connect(files[0]) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == result.schema_version


def test_보관_개수만_남기고_정리(tmp_path):
    db = tmp_path / "s.db"
    sqlite3.connect(db).close()
    base = datetime(2026, 11, 1, 9, 0, 0)
    for i in range(5):
        backup_db(db, tmp_path / "b", now=base + timedelta(days=i))
    removed = prune_backups(tmp_path / "b", keep=3)
    left = sorted(p.name for p in (tmp_path / "b").iterdir())
    assert len(removed) == 2
    assert left[0].startswith("schedule_20261103")


def test_config_json_생성(isolated_home):
    cfg = load_config()
    assert (isolated_home / "config.json").exists()
    assert cfg.backup_keep > 0
