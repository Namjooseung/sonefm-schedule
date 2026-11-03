from pathlib import Path

import pytest

from app.config import migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations, discover
from app.repository import meta_repo

TABLES = {
    "programs", "program_aliases", "program_slots", "month_plans", "schedule_cells",
    "cancellations", "holidays", "change_log", "settings",
}


def _tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def test_빈_DB에_0001_적용(tmp_path):
    conn = connect(tmp_path / "s.db")
    version = apply_migrations(conn, migrations_dir())
    assert version == len(discover(migrations_dir())) >= 1
    assert TABLES <= _tables(conn)


def test_모든_테이블에_id_created_at_updated_at(tmp_path):
    conn = connect(tmp_path / "s.db")
    apply_migrations(conn, migrations_dir())
    for table in TABLES:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        assert {"id", "created_at", "updated_at"} <= cols, table


def test_두번_적용해도_그대로(tmp_path):
    conn = connect(tmp_path / "s.db")
    v1 = apply_migrations(conn, migrations_dir())
    called = []
    v2 = apply_migrations(conn, migrations_dir(), before_apply=lambda a, b: called.append((a, b)))
    assert v1 == v2
    assert called == []  # 적용할 것이 없으면 백업 콜백도 안 불림


def test_저널모드는_DELETE(tmp_path):
    conn = connect(tmp_path / "s.db")
    apply_migrations(conn, migrations_dir())
    assert meta_repo.journal_mode(conn) == "delete"


def test_실패한_마이그레이션은_통째로_취소(tmp_path):
    folder = tmp_path / "migs"
    folder.mkdir()
    (folder / "0001_ok.sql").write_text("CREATE TABLE a (id TEXT PRIMARY KEY);", encoding="utf-8")
    (folder / "0002_bad.sql").write_text(
        "CREATE TABLE b (id TEXT PRIMARY KEY);\nTHIS IS NOT SQL;", encoding="utf-8")
    conn = connect(tmp_path / "s.db")
    with pytest.raises(Exception):
        apply_migrations(conn, folder)
    assert meta_repo.schema_version(conn) == 1
    assert "a" in _tables(conn) and "b" not in _tables(conn)


def test_번호가_비면_거부(tmp_path):
    folder = Path(tmp_path)
    (folder / "0001_a.sql").write_text("", encoding="utf-8")
    (folder / "0003_c.sql").write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError):
        discover(folder)
