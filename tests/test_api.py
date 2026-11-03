"""화면이 부르는 Api 객체를 그대로 호출해 본다 (트랜잭션·오류 처리 확인)."""
from app.api import Api
from app.startup import prepare

FIXED = {"굿모닝!", "굿바이!"}  # 0002 마이그레이션이 넣는 고정 편성 프로그램


def _api():
    return Api(prepare().config)


def test_ping():
    r = _api().ping()
    assert r["ok"] and r["schema_version"] >= 1


def test_등록_후_목록에_보임():
    api = _api()
    r = api.save_program({"name": "수원은 지금", "category": "교양", "cycle_type": "biweekly",
                          "cycle_anchor_date": "2026-11-05", "slots": [
                              {"weekday": 3, "hour": 15, "role": "본방", "valid_from": "2026-11-02"}]})
    assert r["ok"], r
    items = [p for p in api.list_programs("", False)["items"] if p["name"] not in FIXED]
    assert [p["name"] for p in items] == ["수원은 지금"]
    assert items[0]["cycle_label"] == "격주"


def test_검증_실패는_아무것도_저장하지_않음():
    api = _api()
    r = api.save_program({"name": "", "category": "교양", "cycle_type": "weekly"})
    assert not r["ok"] and r["errors"]
    assert {p["name"] for p in api.list_programs("", True)["items"]} == FIXED


def test_예상못한_오류는_한국어_안내로():
    api = _api()
    r = api.save_program(None)  # type: ignore[arg-type]
    assert r["ok"] is False and "문제가 생겼습니다" in r["errors"][0]


def test_선택목록():
    c = _api().program_choices()
    assert c["categories"] == ["교양", "오락"]
    assert c["hours"][0] == 6 and c["hours"][-1] == 22
