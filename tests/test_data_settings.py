"""P7 완료 조건: 다른 폴더로 DB 이동 후 재실행해도 데이터 유지, 백업에서 복원 가능. + 설정 저장."""
import sqlite3
from pathlib import Path

from app.api import Api
from app.config import load_config
from app.startup import prepare


def _api():
    return Api(prepare().config)


def _add(api, name):
    r = api.save_program({"name": name, "category": "교양", "cycle_type": "weekly",
                          "slots": [{"weekday": 1, "hour": 11, "role": "본방", "valid_from": "2026-01-05"}]})
    assert r["ok"], r
    return r["program"]["id"]


def _names(api):
    return {p["name"] for p in api.list_programs("", True)["items"]}


def test_DB_위치_이동_후_재실행해도_데이터_유지(tmp_path):
    api = _api()
    _add(api, "마을살이 정류장")
    api.generate_month(2026, 11, "all")
    target = tmp_path / "공유폴더"
    target.mkdir()
    r = api.db_move(str(target), "copy")
    assert r["ok"], r
    assert Path(r["db_path"]) == target / "schedule.db"
    api2 = Api(prepare(load_config()).config)          # 다시 실행 (config.json을 새로 읽음)
    assert api2.ping()["db_path"] == str(target / "schedule.db")
    assert "마을살이 정류장" in _names(api2)
    assert api2.get_month(2026, 11)["cells"]["2026-11-03|11"]["name"] == "마을살이 정류장"


def test_이미_파일이_있으면_복사_대신_그_파일_쓰기(tmp_path):
    api = _api()
    _add(api, "A")
    target = tmp_path / "t"
    target.mkdir()
    assert api.db_move(str(target), "copy")["ok"]
    _add(api, "B")
    other = tmp_path / "home2"
    other.mkdir()
    assert api.db_move(str(other), "copy")["ok"]
    r = api.db_move(str(target), "copy")
    assert not r["ok"] and "이미" in r["errors"][0]
    assert api.db_move(str(target), "use_existing")["ok"]
    assert {"A", "B"} <= _names(api)


def test_데이터_파일_아닌_곳은_거부(tmp_path):
    api = _api()
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "schedule.db").write_bytes(b"not sqlite at all")
    assert not api.db_move(str(bad), "use_existing")["ok"]
    assert not api.db_move(str(tmp_path / "없는폴더"), "copy")["ok"]


def test_백업에서_복원(tmp_path):
    api = _api()
    _add(api, "복원 전 프로그램")
    made = api.backup_now()
    assert made["ok"]
    _add(api, "백업 뒤에 추가")
    r = api.backup_restore(made["path"])
    assert r["ok"] and r["safety_backup"]
    names = _names(api)
    assert "복원 전 프로그램" in names and "백업 뒤에 추가" not in names
    assert api.backup_restore(r["safety_backup"])["ok"]       # 복원 직전 상태로 다시
    assert "백업 뒤에 추가" in _names(api)
    assert any(b["name"].endswith("_manual.db") for b in api.data_info()["backups"])


def test_데이터_내보내기_파일로_복원(tmp_path):
    from app.services import data as data_service
    api = _api()
    _add(api, "옮길 프로그램")
    out = tmp_path / "옮기기.db"
    assert data_service.export_data(api._cfg, str(out))["ok"]
    _add(api, "나중 프로그램")
    assert api.backup_restore(str(out))["ok"]
    assert "나중 프로그램" not in _names(api)


def test_엉뚱한_파일로_복원_거부(tmp_path):
    api = _api()
    other = tmp_path / "other.db"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE x (a)")
    conn.close()
    r = api.backup_restore(str(other))
    assert not r["ok"] and "아닙니다" in r["errors"][0]


def test_백업_설정(tmp_path):
    api = _api()
    assert not api.backup_options(None, 1)["ok"]
    r = api.backup_options(str(tmp_path / "드라이브" / "백업"), 10)
    assert r["ok"] and r["backup_keep"] == 10
    assert api.backup_now()["ok"]
    assert load_config().backup_dir == str(tmp_path / "드라이브" / "백업")


def test_운영_설정_저장(tmp_path):
    api = _api()
    s = api.settings_get()
    assert s["offweek_policy_default"] == "rerun" and len(s["fixed_programs"]) == 2
    pid = _add(api, "새벽 고정")
    r = api.settings_save({"offweek_policy_default": "empty",
                           "fixed_program_ids": [p["id"] for p in s["fixed_programs"]] + [pid]})
    assert r["ok"] and r["offweek_policy_default"] == "empty" and len(r["fixed_programs"]) == 3
    assert not api.settings_save({"offweek_policy_default": "x",
                                  "fixed_program_ids": ["없음"]})["ok"]


def test_임시공휴일(tmp_path):
    api = _api()
    assert not api.holiday_add("2026-11-16", " ")["ok"]
    assert api.holiday_add("2026-11-16", "임시공휴일")["ok"]
    days = {d["date"]: d for w in api.get_month(2026, 11)["weeks"] for d in w["days"]}
    assert days["2026-11-16"]["holiday"] == "임시공휴일"
    assert api.holiday_delete("2026-11-16")["ok"]
    days = {d["date"]: d for w in api.get_month(2026, 11)["weeks"] for d in w["days"]}
    assert days["2026-11-16"]["holiday"] is None
