"""도메인 계산에 쓰는 값 객체. DB 행을 이 형태로 바꿔서 넘긴다."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

FIRST_HOUR, LAST_HOUR = 6, 22
HOURS: tuple[int, ...] = tuple(range(FIRST_HOUR, LAST_HOUR + 1))   # 하루 17칸


@dataclass(frozen=True)
class ProgramRule:
    """주기 판정·회차 계산에 필요한 프로그램 정보."""
    id: str
    cycle_type: str                       # weekly|biweekly|multi_weekly|monthly_nth|irregular|oneoff
    start_episode: int = 1
    cycle_anchor_date: date | None = None
    monthly_nth: int | None = None
    offweek_policy: str | None = None     # None이면 설정 기본값
    start_date: date | None = None
    end_date: date | None = None

    def active_on(self, d: date) -> bool:
        return (self.start_date is None or self.start_date <= d) and \
               (self.end_date is None or d <= self.end_date)


@dataclass(frozen=True)
class SlotRule:
    """편성 자리 (개편 이력 포함)."""
    id: str
    program_id: str
    weekday: int          # 0=월
    hour: int
    role: str             # 본방|재방
    valid_from: date
    valid_to: date | None = None

    def active_on(self, d: date) -> bool:
        return d.weekday() == self.weekday and self.valid_from <= d and \
               (self.valid_to is None or d <= self.valid_to)


@dataclass(frozen=True)
class Cell:
    """편성표의 한 칸 (날짜·시각당 하나)."""
    date: date
    hour: int
    program_id: str
    kind: str                             # 본방|재방
    source: str = "rule"                  # rule=규칙으로 생성, manual=사람이 손댐
    original_slot_id: str | None = None
    rerun_episode_override: int | None = None
    exception_type: str | None = None     # None|결방대체|교체|특집
    original_program_id: str | None = None

    @property
    def key(self) -> tuple[date, int]:
        return self.date, self.hour
