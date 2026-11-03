"""월 검증 (달력 날짜 기준). 결과는 검증 패널 목록이 되고, key로 그 칸에 이동한다.

- 빈칸: 매일 06~22시 17칸이 모두 채워졌는지 (날짜별로 묶음). 같은 칸 중복은 DB가 막는다(UNIQUE).
- 총 방송분: 채워진 칸 × 60분 = 일수 × 17 × 60분 인지
- 본방 대기: 첫 본방 전 재방
- 고아 예외: 결방 기록의 원래 칸이 개편으로 사라짐
- 편성 자리 충돌: 같은 칸에 같은 우선순위 자리가 둘 이상
비율 미달 경고는 기준값 확정 전까지 보류 (PLAN P5).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.domain.episodes import EpisodeInfo
from app.domain.models import Cell

Key = tuple[date, int]
MINUTES_PER_CELL = 60
_WD = ("월", "화", "수", "목", "금", "토", "일")


@dataclass(frozen=True)
class Issue:
    kind: str
    level: str                 # error | warn
    detail: str
    key: Key | None = None


def _day(d: date) -> str:
    return f"{d.month}/{d.day}({_WD[d.weekday()]})"


def validate_month(
    dates: list[date],
    hours: list[int],
    cells: dict[Key, Cell],
    episodes: dict[Key, EpisodeInfo],
    orphans: Iterable[tuple[date, int, str]],
    conflicts: Iterable[tuple[date, int, tuple[str, ...]]],
) -> list[Issue]:
    issues: list[Issue] = []
    in_month = set(dates)

    empty_count = 0
    for d in dates:
        empty = [h for h in hours if (d, h) not in cells]
        if empty:
            empty_count += len(empty)
            hrs = ", ".join(f"{h:02d}시" for h in empty[:4])
            if len(empty) > 4:
                hrs += f" 외 {len(empty) - 4}칸"
            issues.append(Issue("빈칸", "error", f"{_day(d)} {hrs} 비어 있습니다.", (d, empty[0])))

    for key in sorted(k for k in cells if k[0] in in_month):
        info = episodes.get(key)
        if info and info.waiting:
            issues.append(Issue("본방 대기", "error", f"{_day(key[0])} {key[1]:02d}시 — 재방할 본방이 아직 없습니다.", key))

    for d, h, name in orphans:
        if d in in_month:
            issues.append(Issue("고아 예외", "warn",
                                f"{_day(d)} {h:02d}시 — {name} 결방 기록이 있지만 개편으로 원래 자리가 없어졌습니다. 칸을 열어 '원래대로'로 정리해 주세요.",
                                (d, h)))
    for d, h, names in conflicts:
        if d in in_month:
            issues.append(Issue("편성 자리 충돌", "warn",
                                f"{_day(d)} {h:02d}시 — {', '.join(names)} 중 하나만 들어갔습니다. 프로그램 화면에서 자리를 조정해 주세요.",
                                (d, h)))

    issues.sort(key=lambda i: (i.key or (date.max, 0)))
    if empty_count:
        expected = len(dates) * len(hours) * MINUTES_PER_CELL
        issues.append(Issue("총 방송분", "error",
                            f"{expected - empty_count * MINUTES_PER_CELL:,}분 / 기준 {expected:,}분 — "
                            f"{empty_count * MINUTES_PER_CELL:,}분 부족"))
    return issues
