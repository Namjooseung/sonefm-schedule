"""도메인 테스트용 짧은 생성 함수."""
from datetime import date

from app.domain.models import Cell, ProgramRule, SlotRule

D = date.fromisoformat


def prog(pid, cycle="weekly", start_episode=1, anchor=None, nth=None, offweek=None,
         start="2026-01-01", end=None):
    return ProgramRule(id=pid, cycle_type=cycle, start_episode=start_episode,
                       cycle_anchor_date=D(anchor) if anchor else None, monthly_nth=nth,
                       offweek_policy=offweek, start_date=D(start) if start else None,
                       end_date=D(end) if end else None)


def slot(sid, pid, weekday, hour, role="본방", valid_from="2026-01-01", valid_to=None):
    return SlotRule(id=sid, program_id=pid, weekday=weekday, hour=hour, role=role,
                    valid_from=D(valid_from), valid_to=D(valid_to) if valid_to else None)


def cell(d, hour, pid, kind="본방", source="rule", override=None, slot_id=None):
    return Cell(date=D(d), hour=hour, program_id=pid, kind=kind, source=source,
                rerun_episode_override=override, original_slot_id=slot_id)
