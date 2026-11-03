"""프로그램·별칭·편성 자리의 입력 정리와 검증 (순수 함수).

용어
- 편성 자리: 프로그램이 정기적으로 나가는 (요일, 시각, 본방/재방) 묶음. 적용 시작일~종료일이 있어
  개편 이력을 남긴다. 개편은 기존 자리를 종료하고 새 자리를 추가한다 (회차가 끊기지 않게).
- 단발(특집): 편성 자리 없이 특정 칸에만 들어가는 프로그램.
- 비방송 주 처리: 격주·매월 n째 주 프로그램이 방송하지 않는 주에 본방 자리를 어떻게 채울지.
  None이면 설정 화면의 기본값을 따른다.
"""
from __future__ import annotations

from datetime import date
from typing import Any

CATEGORIES: tuple[str, ...] = ("교양", "오락")
PRODUCER_TYPES: tuple[str, ...] = ("자체", "타공동체라디오", "외부")
CYCLE_TYPES: dict[str, str] = {
    "weekly": "매주",
    "biweekly": "격주",
    "multi_weekly": "주 n회",
    "monthly_nth": "매월 n째 주",
    "irregular": "부정기",
    "oneoff": "단발(특집)",
}
OFFWEEK_POLICIES: dict[str, str] = {"rerun": "재방으로 채움", "empty": "비움"}
ROLES: tuple[str, ...] = ("본방", "재방")
WEEKDAYS: tuple[str, ...] = ("월", "화", "수", "목", "금", "토", "일")
FIRST_HOUR, LAST_HOUR = 6, 22  # 06시~22시 시작 칸 (23시 종료)

# 비방송 주가 있는 주기
_CYCLES_WITH_OFFWEEK = ("biweekly", "monthly_nth")


def choices() -> dict[str, Any]:
    """화면의 선택 목록에 쓰는 값과 표시 이름."""
    return {
        "categories": list(CATEGORIES),
        "producer_types": list(PRODUCER_TYPES),
        "cycle_types": [{"value": k, "label": v} for k, v in CYCLE_TYPES.items()],
        "offweek_policies": [{"value": k, "label": v} for k, v in OFFWEEK_POLICIES.items()],
        "roles": list(ROLES),
        "weekdays": list(WEEKDAYS),
        "hours": list(range(FIRST_HOUR, LAST_HOUR + 1)),
    }


# ── 작은 도우미 ───────────────────────────────────

def _text(value: Any) -> str | None:
    if value is None:
        return None
    s = " ".join(str(value).split())
    return s or None


def parse_date(value: Any, label: str, errors: list[str], required: bool = False) -> str | None:
    s = _text(value)
    if s is None:
        if required:
            errors.append(f"{label}을(를) 입력해 주세요.")
        return None
    try:
        return date.fromisoformat(s).isoformat() if len(s) == 10 else _bad_date(label, errors)
    except ValueError:
        return _bad_date(label, errors)


def _bad_date(label: str, errors: list[str]) -> None:
    errors.append(f"{label} 형식이 올바르지 않습니다. (예: 2026-11-03)")
    return None


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else None


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "예")
    return bool(value)


def periods_overlap(a_from: str, a_to: str | None, b_from: str, b_to: str | None) -> bool:
    """두 적용 기간이 하루라도 겹치는지. 종료일 None은 '계속'."""
    a_end = a_to or "9999-12-31"
    b_end = b_to or "9999-12-31"
    return a_from <= b_end and b_from <= a_end


# ── 프로그램 ──────────────────────────────────────

def clean_program(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """화면 입력을 저장 가능한 형태로 정리한다. (정리된 값, 오류 문구 목록)"""
    errors: list[str] = []

    name = _text(raw.get("name"))
    if not name:
        errors.append("프로그램 이름을 입력해 주세요.")

    category = raw.get("category")
    if category not in CATEGORIES:
        errors.append("분야(교양/오락)를 선택해 주세요.")

    producer_type = raw.get("producer_type") or "자체"
    if producer_type not in PRODUCER_TYPES:
        errors.append("제작 주체를 선택해 주세요.")

    cycle_type = raw.get("cycle_type")
    if cycle_type not in CYCLE_TYPES:
        errors.append("방송 주기를 선택해 주세요.")

    anchor = parse_date(raw.get("cycle_anchor_date"), "기준일", errors)
    if cycle_type == "biweekly" and anchor is None and raw.get("cycle_anchor_date") in (None, ""):
        errors.append("격주 프로그램은 기준일(본방이 나가는 주의 날짜)을 입력해 주세요.")

    monthly_nth = _int(raw.get("monthly_nth"))
    if cycle_type == "monthly_nth":
        if monthly_nth is None or not 1 <= monthly_nth <= 5:
            errors.append("매월 몇째 주에 방송하는지(1~5) 입력해 주세요.")
    else:
        monthly_nth = None

    offweek = raw.get("offweek_policy") or None
    if cycle_type not in _CYCLES_WITH_OFFWEEK:
        offweek = None
    elif offweek not in (None, *OFFWEEK_POLICIES):
        errors.append("비방송 주 처리 방법을 다시 선택해 주세요.")

    start_episode = _int(raw.get("start_episode", 1))
    if start_episode is None or start_episode < 1:
        errors.append("시작 회차는 1 이상의 정수로 입력해 주세요.")

    start_date = parse_date(raw.get("start_date"), "시작일", errors)
    end_date = parse_date(raw.get("end_date"), "종영일", errors)
    if start_date and end_date and end_date < start_date:
        errors.append("종영일이 시작일보다 빠릅니다.")

    program = {
        "name": name,
        "category": category,
        "is_listener_participation": _bool(raw.get("is_listener_participation")),
        "producer_type": producer_type,
        "cycle_type": cycle_type,
        "cycle_anchor_date": anchor,
        "monthly_nth": monthly_nth,
        "offweek_policy": offweek,
        "start_episode": start_episode if start_episode and start_episode >= 1 else 1,
        "start_date": start_date,
        "end_date": end_date,
        "host": _text(raw.get("host")),
        "cohort": _text(raw.get("cohort")),
        "is_special": cycle_type == "oneoff",
        "memo": (str(raw.get("memo")).strip() or None) if raw.get("memo") else None,
    }
    return program, errors


# ── 별칭 ──────────────────────────────────────────

def clean_aliases(raw: list[Any] | None, name: str | None) -> list[str]:
    """공백 정리, 빈 값·중복·프로그램 이름과 같은 값 제거. 입력 순서 유지."""
    out: list[str] = []
    for item in raw or []:
        a = _text(item)
        if a and a != name and a not in out:
            out.append(a)
    return out


def check_name_conflicts(
    program_id: str | None,
    name: str | None,
    aliases: list[str],
    others: list[tuple[str, str, list[str]]],
) -> list[str]:
    """이름·별칭이 다른 프로그램의 이름·별칭과 겹치는지. 엑셀 가져오기 매칭이 모호해지는 것을 막는다.

    others: (프로그램 id, 이름, 별칭 목록)
    """
    errors: list[str] = []
    mine = [n for n in [name, *aliases] if n]
    for other_id, other_name, other_aliases in others:
        if other_id == program_id:
            continue
        taken = {other_name, *other_aliases}
        for n in mine:
            if n in taken:
                errors.append(f"'{n}'은(는) 이미 '{other_name}'의 이름이나 별칭으로 쓰이고 있습니다.")
    return errors


# ── 편성 자리 ─────────────────────────────────────

def _slot_label(s: dict[str, Any]) -> str:
    wd = s.get("weekday")
    day = WEEKDAYS[wd] if isinstance(wd, int) and 0 <= wd <= 6 else "?"
    return f"{day} {s.get('hour')}시"


def clean_slots(raw: list[dict[str, Any]] | None, cycle_type: str | None
                ) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    slots: list[dict[str, Any]] = []
    raw = raw or []

    if cycle_type == "oneoff" and raw:
        errors.append("단발(특집) 프로그램은 편성 자리를 두지 않습니다. 주기를 바꾸거나 자리를 지워 주세요.")
        return [], errors

    for i, r in enumerate(raw, start=1):
        row_errors: list[str] = []
        weekday = _int(r.get("weekday"))
        hour = _int(r.get("hour"))
        role = r.get("role")
        if weekday is None or not 0 <= weekday <= 6:
            row_errors.append(f"편성 자리 {i}번째 줄: 요일을 선택해 주세요.")
        if hour is None or not FIRST_HOUR <= hour <= LAST_HOUR:
            row_errors.append(f"편성 자리 {i}번째 줄: 시각은 {FIRST_HOUR}~{LAST_HOUR}시 중에서 골라 주세요.")
        if role not in ROLES:
            row_errors.append(f"편성 자리 {i}번째 줄: 본방/재방을 선택해 주세요.")
        valid_from = parse_date(r.get("valid_from"), f"편성 자리 {i}번째 줄 적용 시작일", row_errors,
                           required=True)
        valid_to = parse_date(r.get("valid_to"), f"편성 자리 {i}번째 줄 적용 종료일", row_errors)
        if valid_from and valid_to and valid_to < valid_from:
            row_errors.append(f"편성 자리 {i}번째 줄: 적용 종료일이 시작일보다 빠릅니다.")
        errors.extend(row_errors)
        slots.append({
            "id": r.get("id") or None,
            "weekday": weekday, "hour": hour, "role": role,
            "valid_from": valid_from, "valid_to": valid_to,
        })

    if errors:
        return slots, errors

    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            if (a["weekday"], a["hour"]) == (b["weekday"], b["hour"]) and periods_overlap(
                    a["valid_from"], a["valid_to"], b["valid_from"], b["valid_to"]):
                errors.append(f"{_slot_label(a)} 자리가 적용 기간이 겹칩니다. 한쪽의 기간을 조정해 주세요.")
    return slots, errors


# ── 종영 ──────────────────────────────────────────

def plan_end_program(end_date: str, slots: list[dict[str, Any]]
                     ) -> tuple[list[dict[str, Any]], list[str]]:
    """종영일에 맞춰 편성 자리를 닫는다. 이미 그 전에 끝난 자리는 그대로 둔다."""
    errors: list[str] = []
    updated: list[dict[str, Any]] = []
    for s in slots:
        if s["valid_from"] > end_date:
            errors.append(f"{_slot_label(s)} 자리가 종영일 이후({s['valid_from']})에 시작합니다. "
                          "그 자리를 지우거나 종영일을 바꿔 주세요.")
        new = dict(s)
        if new.get("valid_to") is None or new["valid_to"] > end_date:
            new["valid_to"] = end_date
        updated.append(new)
    return updated, errors
