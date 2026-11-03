"""칸 팝업의 '이후 전부' = 편성 자리 이력 갱신.

기존 자리는 그 날짜 전날까지로 닫고, 같은 요일·시각에 새 자리를 그 날짜부터 연다.
- 자리 시작일과 같은 날부터 바꾸면 기존 자리는 기간이 남지 않으므로 지운다.
- 기존 자리에 끝나는 날이 있었으면 새 자리도 같은 날 끝난다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.models import SlotRule


@dataclass(frozen=True)
class SlotChangePlan:
    close_old_to: date | None     # 기존 자리의 새 적용 종료일 (delete_old면 None)
    delete_old: bool
    new_program_id: str
    new_role: str
    new_valid_from: date
    new_valid_to: date | None


def plan_from_date(old: SlotRule, d: date, new_program_id: str, new_role: str) -> SlotChangePlan | None:
    """d가 기존 자리의 적용 기간 밖이면 None."""
    if d < old.valid_from or (old.valid_to is not None and d > old.valid_to):
        return None
    delete_old = d == old.valid_from
    return SlotChangePlan(
        close_old_to=None if delete_old else d - timedelta(days=1),
        delete_old=delete_old,
        new_program_id=new_program_id,
        new_role=new_role,
        new_valid_from=d,
        new_valid_to=old.valid_to,
    )
