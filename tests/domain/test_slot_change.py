"""'이후 전부' 변경 = 편성 자리 이력 갱신 (개편)."""
from app.domain.slot_change import plan_from_date

from .helpers import D, slot


def test_진행중인_자리는_전날까지로_닫고_새_자리():
    old = slot("s", "p", 1, 11, valid_from="2026-01-05")
    plan = plan_from_date(old, D("2026-11-10"), new_program_id="q", new_role="본방")
    assert plan.close_old_to == D("2026-11-09")
    assert not plan.delete_old
    assert (plan.new_program_id, plan.new_role, plan.new_valid_from, plan.new_valid_to) == (
        "q", "본방", D("2026-11-10"), None)


def test_자리_시작일과_같은_날이면_기존_자리는_지움():
    old = slot("s", "p", 1, 11, valid_from="2026-11-10")
    plan = plan_from_date(old, D("2026-11-10"), new_program_id="p", new_role="재방")
    assert plan.delete_old and plan.close_old_to is None


def test_끝나는_날이_있던_자리는_새_자리도_같은_날_끝남():
    old = slot("s", "p", 1, 11, valid_from="2026-01-05", valid_to="2026-12-31")
    plan = plan_from_date(old, D("2026-11-10"), new_program_id="p", new_role="재방")
    assert plan.new_valid_to == D("2026-12-31")


def test_자리_기간_밖의_날짜는_거부():
    old = slot("s", "p", 1, 11, valid_from="2026-01-05", valid_to="2026-10-31")
    assert plan_from_date(old, D("2026-11-10"), "p", "재방") is None
    assert plan_from_date(old, D("2025-12-29"), "p", "재방") is None
