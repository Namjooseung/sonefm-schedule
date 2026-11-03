"""프로그램 주기 판정.

- 매주 / 주 n회: 매주 본방 (주 n회는 요일마다 본방 자리를 둔다)
- 격주: 기준일이 있는 주를 방송 주로 보고 2주 간격
- 매월 n째 주: 주의 소속(월요일 기준)으로 센 그 달의 n번째 주
- 비정기: 자동 본방 없음. 모든 자리가 재방으로 깔리고 사람이 "본방으로" 바꾼다
- 단발(특집): 편성 자리 없음
방송하지 않는 주의 본방 자리는 비방송 주 처리값(rerun=재방으로 채움, empty=비움)을 따른다.
"""
from __future__ import annotations

from datetime import date

from app.domain.models import ProgramRule, SlotRule
from app.domain.weeks import monday_of, week_index_in_month


def is_broadcast_week(program: ProgramRule, d: date) -> bool:
    """d가 속한 주가 이 프로그램의 본방 주인지."""
    monday = monday_of(d)
    ct = program.cycle_type
    if ct in ("weekly", "multi_weekly"):
        return True
    if ct == "biweekly":
        if program.cycle_anchor_date is None:
            return True   # 기준일 누락은 입력 검증에서 막는다. 여기서는 매주로 취급
        weeks = (monday - monday_of(program.cycle_anchor_date)).days // 7
        return weeks % 2 == 0
    if ct == "monthly_nth":
        return program.monthly_nth is not None and week_index_in_month(monday) == program.monthly_nth
    return False   # irregular, oneoff


def rule_kind(program: ProgramRule, slot: SlotRule, d: date, default_offweek: str) -> str | None:
    """이 자리가 이 날짜에 규칙상 어떤 칸이 되는지: '본방' / '재방' / None(비움)."""
    if slot.role == "재방" or program.cycle_type == "irregular":
        return "재방"
    if is_broadcast_week(program, d):
        return "본방"
    policy = program.offweek_policy or default_offweek
    return "재방" if policy == "rerun" else None
