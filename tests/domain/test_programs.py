from app.domain.programs import (
    check_name_conflicts,
    clean_aliases,
    clean_program,
    clean_slots,
    plan_end_program,
)


def _base(**kw):
    raw = {"name": " 수원은 지금 ", "category": "교양", "cycle_type": "weekly",
           "start_date": "2026-01-05"}
    raw.update(kw)
    return raw


# ── 프로그램 기본 정보 ─────────────────────────────

def test_매주_프로그램_정리():
    p, errors = clean_program(_base())
    assert errors == []
    assert p["name"] == "수원은 지금"
    assert p["start_episode"] == 1
    assert p["producer_type"] == "자체"
    assert p["is_special"] is False
    assert p["offweek_policy"] is None


def test_이름_분야_주기는_필수():
    _, errors = clean_program({"name": "  ", "category": "보도", "cycle_type": "daily"})
    assert len(errors) == 3


def test_격주는_기준일_필수():
    _, errors = clean_program(_base(cycle_type="biweekly"))
    assert any("기준일" in e for e in errors)
    p, errors = clean_program(_base(cycle_type="biweekly", cycle_anchor_date="2026-11-05",
                                    offweek_policy="empty"))
    assert errors == []
    assert p["offweek_policy"] == "empty"


def test_매월_n째_주는_n_필수():
    _, errors = clean_program(_base(cycle_type="monthly_nth"))
    assert any("몇째 주" in e for e in errors)
    p, errors = clean_program(_base(cycle_type="monthly_nth", monthly_nth=2))
    assert errors == [] and p["monthly_nth"] == 2


def test_매주는_비방송주_처리값을_버림():
    p, _ = clean_program(_base(offweek_policy="empty", monthly_nth=3))
    assert p["offweek_policy"] is None and p["monthly_nth"] is None


def test_단발은_특집으로_표시():
    p, errors = clean_program(_base(cycle_type="oneoff"))
    assert errors == [] and p["is_special"] is True


def test_종영일은_시작일_이후():
    _, errors = clean_program(_base(end_date="2025-12-31"))
    assert any("종영일" in e for e in errors)


def test_날짜_형식_오류():
    _, errors = clean_program(_base(start_date="2026/01/05"))
    assert any("시작일" in e for e in errors)


def test_시작_회차는_1_이상_정수():
    _, errors = clean_program(_base(start_episode="0"))
    assert errors
    p, errors = clean_program(_base(start_episode="23"))
    assert errors == [] and p["start_episode"] == 23


# ── 별칭 ──────────────────────────────────────────

def test_별칭은_공백정리_중복제거_이름과_같으면_제외():
    aliases = clean_aliases([" 수원지금 ", "수원지금", "", "수원은 지금", "수원  NOW"], "수원은 지금")
    assert aliases == ["수원지금", "수원 NOW"]


def test_다른_프로그램과_이름_별칭_충돌():
    others = [("p2", "마을살이 정류장", ["마을살이"])]
    assert check_name_conflicts("p1", "마을살이", [], others)
    assert check_name_conflicts("p1", "수원은 지금", ["마을살이 정류장"], others)
    assert check_name_conflicts("p1", "수원은 지금", ["수원지금"], others) == []
    # 자기 자신은 충돌이 아님
    assert check_name_conflicts("p2", "마을살이 정류장", ["마을살이"], others) == []


# ── 편성 자리 ─────────────────────────────────────

def _slot(**kw):
    s = {"weekday": 0, "hour": 10, "role": "본방", "valid_from": "2026-01-05", "valid_to": None}
    s.update(kw)
    return s


def test_편성자리_정상():
    slots, errors = clean_slots([_slot(), _slot(weekday=5, hour=18, role="재방")], "weekly")
    assert errors == []
    assert slots[1]["role"] == "재방"


def test_편성자리_범위_오류():
    _, errors = clean_slots([_slot(weekday=7), _slot(hour=23), _slot(role="생방")], "weekly")
    assert len(errors) == 3


def test_같은_요일_시각_기간이_겹치면_오류():
    _, errors = clean_slots([_slot(), _slot(valid_from="2026-03-02")], "weekly")
    assert any("겹칩니다" in e for e in errors)


def test_개편_이력은_기간이_이어지면_정상():
    # 1~2월 월10시 → 3월부터 월10시 다시 (종료 후 재개). 기간이 안 겹치면 허용
    _, errors = clean_slots([
        _slot(valid_to="2026-02-28"),
        _slot(valid_from="2026-03-01"),
    ], "weekly")
    assert errors == []


def test_적용_종료일은_시작일_이후():
    _, errors = clean_slots([_slot(valid_to="2026-01-01")], "weekly")
    assert errors


def test_단발은_편성자리_없음():
    _, errors = clean_slots([_slot()], "oneoff")
    assert errors


# ── 종영 ──────────────────────────────────────────

def test_종영하면_열린_자리를_종영일로_닫음():
    slots = [
        _slot(id="a"),                                   # 열린 자리 → 닫힘
        _slot(id="b", valid_to="2026-12-31"),            # 종영일 뒤에 끝남 → 당겨짐
        _slot(id="c", valid_to="2026-03-31"),            # 이미 끝남 → 그대로
    ]
    updated, errors = plan_end_program("2026-11-30", slots)
    assert errors == []
    assert {s["id"]: s["valid_to"] for s in updated} == {
        "a": "2026-11-30", "b": "2026-11-30", "c": "2026-03-31"}


def test_종영일_뒤에_시작하는_자리가_있으면_오류():
    _, errors = plan_end_program("2026-11-30", [_slot(valid_from="2026-12-07")])
    assert errors
