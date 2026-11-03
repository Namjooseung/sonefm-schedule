import re

from app.config import migrations_dir
from app.db.connection import connect
from app.db.migrate import apply_migrations
from app.repository import programs_repo, settings_repo

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _db(tmp_path):
    conn = connect(tmp_path / "s.db")
    apply_migrations(conn, migrations_dir())
    return conn


def test_기본_설정값(tmp_path):
    s = settings_repo.get_all(_db(tmp_path))
    assert s["offweek_policy_default"] == "rerun"
    assert s["irregular_missing_warn_count"] == 4
    assert len(s["fixed_program_ids"]) == 2


def test_고정편성_프로그램과_매일_자리(tmp_path):
    conn = _db(tmp_path)
    gm_id, gb_id = settings_repo.get(conn, "fixed_program_ids")
    gm, gb = programs_repo.get_program(conn, gm_id), programs_repo.get_program(conn, gb_id)
    assert gm["name"] == "굿모닝!" and gb["name"] == "굿바이!"
    assert sorted((s["weekday"], s["hour"]) for s in gm["slots"]) == [(d, 6) for d in range(7)]
    assert sorted((s["weekday"], s["hour"]) for s in gb["slots"]) == [(d, 22) for d in range(7)]
    ids = [gm_id, gb_id] + [s["id"] for s in gm["slots"] + gb["slots"]]
    assert all(UUID.match(i) for i in ids)
    assert len(set(ids)) == len(ids)


def test_설정값_쓰기(tmp_path):
    conn = _db(tmp_path)
    settings_repo.set_value(conn, "irregular_missing_warn_count", 5)
    settings_repo.set_value(conn, "새키", {"a": 1})
    assert settings_repo.get(conn, "irregular_missing_warn_count") == 5
    assert settings_repo.get(conn, "새키") == {"a": 1}
    assert settings_repo.get(conn, "없는키", "기본") == "기본"
