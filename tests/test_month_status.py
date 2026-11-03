"""P5 완료 조건: 빈칸·본방 대기 시나리오에서 경고가 뜨고, 마감 달은 편집 불가."""
import pytest

from app.api import Api
from app.startup import prepare


@pytest.fixture
def api():
    a = Api(prepare().config)
    S = lambda wd, h, role="본방": {"weekday": wd, "hour": h, "role": role, "valid_from": "2026-01-05"}  # noqa: E731
    a.ids = {}
    for name, ep, slots in [("마을살이 정류장", 41, [S(1, 11)]),
                            ("[10기] 생존신고", 1, [S(4, 10), S(1, 21, "재방")])]:
        r = a.save_program({"name": name, "category": "교양", "cycle_type": "weekly", "start_episode": ep, "slots": slots})
        a.ids[name] = r["program"]["id"]
    return a


def kinds(m):
    return [i["kind"] for i in m["issues"]]


def test_미작성_달은_검증목록_없음(api):
    assert api.get_month(2026, 11)["issues"] == []


def test_빈칸과_본방대기_경고(api):
    api.generate_month(2026, 11, "all")
    m = api.get_month(2026, 11)
    k = kinds(m)
    assert "빈칸" in k and "총 방송분" in k
    waiting = [i for i in m["issues"] if i["kind"] == "본방 대기"]
    assert waiting and waiting[0]["key"] == "2026-11-03|21"    # 첫 본방(11/6) 전 재방
    assert m["issues"][-1]["kind"] == "총 방송분"
    # 11/1(10월 소속 주)도 11월 달력 날짜라 검증 대상
    assert any(i["key"] == "2026-11-01|6" for i in m["issues"] if i["kind"] == "빈칸")


def test_고아_예외(api):
    api.generate_month(2026, 11, "all")
    api.cell_cancel("2026-11-17", 11, "empty")
    # 개편: 마을살이 자리를 11/16에 종료 → 11/17 결방 기록의 원래 칸이 사라짐
    p = api.get_program(api.ids["마을살이 정류장"])["program"]
    p["slots"][0]["valid_to"] = "2026-11-16"
    assert api.save_program(p)["ok"]
    assert "고아 예외" in kinds(api.get_month(2026, 11))


def test_상태_전환_흐름(api):
    assert not api.month_status(2026, 11, "confirm")["ok"]            # 생성 전
    api.generate_month(2026, 11, "all")
    assert not api.month_status(2026, 11, "close")["ok"]              # 확정 전 마감 불가
    assert api.month_status(2026, 11, "confirm")["status"] == "확정"
    assert api.get_month(2026, 11)["plan"]["confirmed_at"]
    assert api.month_status(2026, 11, "reopen")["status"] == "작성중"
    api.month_status(2026, 11, "confirm")
    assert api.month_status(2026, 11, "close")["status"] == "마감"
    assert not api.month_status(2026, 11, "unlock", "  ")["ok"]       # 사유 필수
    r = api.month_status(2026, 11, "unlock", "보고서 수정 제출")
    assert r["status"] == "확정"
    assert api.get_month(2026, 11)["plan"]["unlock_reason"] == "보고서 수정 제출"
    assert "잠금 해제" in [i["action"] for i in api.list_change_log(5)["items"]]


def test_마감_달은_편집_생성_불가(api):
    api.generate_month(2026, 11, "all")
    api.month_status(2026, 11, "confirm")
    api.month_status(2026, 11, "close")
    assert not api.cell_cancel("2026-11-10", 11, "empty")["ok"]
    assert not api.cell_replace("2026-11-10", 11, api.ids["[10기] 생존신고"], "재방")["ok"]
    assert not api.generate_month(2026, 11, "all")["ok"]
    assert api.get_cell("2026-11-10", 11)["locked"]


def test_확정_후_변경은_기록에_표시(api):
    api.generate_month(2026, 11, "all")
    api.month_status(2026, 11, "confirm")
    assert api.cell_cancel("2026-11-10", 11, "rerun")["ok"]
    assert "[확정 후 변경]" in api.list_change_log(1)["items"][0]["note"]


def test_마감_달보다_앞선_칸을_바꾸면_경고(api):
    api.generate_month(2026, 11, "all")
    api.generate_month(2026, 12, "all")
    api.month_status(2026, 12, "confirm")
    api.month_status(2026, 12, "close")
    r = api.cell_cancel("2026-11-10", 11, "empty")
    assert r["ok"] and r["warnings"] and "12월" in r["warnings"][0]
    r = api.cell_prep("2026-11-03", 11, "입고")   # 준비 상태는 회차와 무관 → 경고 없음
    assert r["ok"] and r["warnings"] == []
