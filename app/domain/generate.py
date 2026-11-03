"""월 생성: 편성 자리 + 주기 규칙으로 칸을 만들고, 기존 칸과 합친다.

흐름
1. build_rule_cells(날짜들, ...) — 규칙만으로 만든 칸. "첫 주 불러오기"는 첫 주 날짜만,
   "월단위 생성"은 나머지 주 날짜를 넘긴다. 날짜마다 주기를 다시 판정하므로 첫 주를 복사하지 않는다.
2. plan_generation(규칙 칸, 기존 칸, 결방 기록, 덮어쓰기 여부) — 실제로 바꿀 목록.
   - 사람이 손댄 칸(source=manual)은 기본 유지. 규칙과 다르면 manual_conflicts로 돌려줘 화면이 확인창을 띄운다.
   - 결방 기록이 있는 원래 칸은 규칙 칸을 만들지 않는다.
   - 특집·교체 같은 일회성 예외는 manual 칸이라 다른 날짜로 퍼지지 않는다.

같은 칸에 여러 자리가 걸리면 우선순위: 본방 > 재방 자리 > 방송 없는 주 재방 채움.
같은 우선순위끼리 겹치면 충돌로 보고하고 프로그램 id 순으로 하나를 고른다.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from app.domain.cycles import rule_kind
from app.domain.models import HOURS, Cell, ProgramRule, SlotRule

Key = tuple[date, int]


@dataclass(frozen=True)
class SlotConflict:
    date: date
    hour: int
    program_ids: tuple[str, ...]


@dataclass
class GenerationPlan:
    upserts: list[Cell] = field(default_factory=list)          # 새로 쓰거나 바꿀 칸
    deletes: list[Key] = field(default_factory=list)           # 규칙에서 빠져 지울 칸
    manual_conflicts: list[Cell] = field(default_factory=list) # 사람이 손댄 칸 중 규칙과 다른 것 (기존 칸)


def _priority(slot: SlotRule, kind: str) -> int:
    if kind == "본방":
        return 0
    return 1 if slot.role == "재방" else 2


def build_rule_cells(
    dates: Iterable[date],
    programs: dict[str, ProgramRule],
    slots: Iterable[SlotRule],
    default_offweek: str,
) -> tuple[dict[Key, Cell], list[SlotConflict]]:
    slots = list(slots)
    by_weekday: dict[int, list[SlotRule]] = {}
    for s in slots:
        by_weekday.setdefault(s.weekday, []).append(s)

    cells: dict[Key, Cell] = {}
    conflicts: list[SlotConflict] = []
    for d in dates:
        candidates: dict[int, list[tuple[int, str, SlotRule, str]]] = {}
        for s in by_weekday.get(d.weekday(), []):
            p = programs.get(s.program_id)
            if p is None or p.cycle_type == "oneoff" or not s.active_on(d) or not p.active_on(d):
                continue
            kind = rule_kind(p, s, d, default_offweek)
            if kind is None:
                continue
            candidates.setdefault(s.hour, []).append((_priority(s, kind), p.id, s, kind))
        for hour, cands in candidates.items():
            cands.sort(key=lambda c: (c[0], c[1]))
            best = cands[0]
            tied = sorted({c[1] for c in cands if c[0] == best[0]})
            if len(tied) > 1:
                conflicts.append(SlotConflict(d, hour, tuple(tied)))
            _, pid, s, kind = best
            cells[(d, hour)] = Cell(date=d, hour=hour, program_id=pid, kind=kind,
                                    source="rule", original_slot_id=s.id)
    return cells, conflicts


def _same(a: Cell, b: Cell) -> bool:
    return (a.program_id, a.kind, a.original_slot_id) == (b.program_id, b.kind, b.original_slot_id)


def plan_generation(
    rule_cells: dict[Key, Cell],
    existing: dict[Key, Cell],
    cancellations: set[tuple[str, date, int]],
    overwrite_manual: bool = False,
    dates: Iterable[date] | None = None,
) -> GenerationPlan:
    """규칙 칸과 기존 칸을 합친 변경 계획. dates를 주면 그 날짜들만 대상으로 한다."""
    if dates is None:
        keys = set(rule_cells) | set(existing)
    else:
        keys = {(d, h) for d in dates for h in HOURS}
    plan = GenerationPlan()
    for key in sorted(keys):
        rule = rule_cells.get(key)
        if rule is not None and (rule.program_id, key[0], key[1]) in cancellations:
            rule = None
        cur = existing.get(key)

        if cur is not None and cur.source == "manual":
            differs = rule is None or not _same(rule, cur)
            if not differs:
                continue
            plan.manual_conflicts.append(cur)
            if overwrite_manual:
                if rule is None:
                    plan.deletes.append(key)
                else:
                    plan.upserts.append(rule)
            continue

        if rule is None:
            if cur is not None:
                plan.deletes.append(key)
        elif cur is None or not _same(rule, cur):
            plan.upserts.append(rule)
    return plan
