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


def _make_seed(path: Path) -> Path:
    prepare()  # 스키마가 있는 DB를 하나 만든 뒤 표식 행을 넣어 씨앗으로 쓴다
    src = Path(load_config().db_path)
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE seed_mark (x)")
    conn.commit()
    conn.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    src.replace(path)
    return path


def test_DB가_없으면_씨앗_DB를_복사해_시작(isolated_home, tmp_path):
    seed = _make_seed(tmp_path / "seed" / "schedule_seed.db")
    result = prepare(seed_db=seed)
    with sqlite3.connect(result.config.db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert "seed_mark" in tables
    assert seed.exists()  # 원본 씨앗은 그대로


def test_DB가_이미_있으면_씨앗을_무시(isolated_home, tmp_path):
    seed = _make_seed(tmp_path / "seed" / "schedule_seed.db")
    prepare()  # 기존 DB
    result = prepare(seed_db=seed)
    with sqlite3.connect(result.config.db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert "seed_mark" not in tables


def test_씨앗_파일이_없어도_빈_DB로_시작(isolated_home, tmp_path):
    result = prepare(seed_db=tmp_path / "없음.db")
    assert Path(result.config.db_path).exists()
