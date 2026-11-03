"""편성표 월 화면과 월 생성 흐름."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from app.domain.episodes import compute_episodes, rerun_streak_warnings
from app.domain.generate import build_rule_cells, plan_generation
from app.domain.holidays_kr import holidays_between
from app.domain.models import HOURS, Cell
from app.domain.validate import validate_month
from app.domain.weeks import (
    iso_week,
    month_dates,
    month_of_week,
    reference_week,
    week_dates,
    week_index_in_month,
    weeks_of_month,
)
from app.repository import change_log_repo, schedule_repo, settings_repo

WEEKDAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")
MINUTES_PER_CELL = 60   # 보고서 검증식(일수 × 17 × 60)과 같은 단위
STATUS_NONE = "미작성"

Result = dict[str, Any]


def _ym(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _valid_month(year: Any, month: Any) -> tuple[int, int] | None:
    try:
        y, m = int(year), int(month)
    except (TypeError, ValueError):
        return None
    return (y, m) if 2000 <= y <= 2100 and 1 <= m <= 12 else None


# ── 회차·경고 계산 ────────────────────────────────

def _episode_map(conn: sqlite3.Connection, last: date) -> tuple[dict[tuple[date, int], Any], set[tuple[date, int]]]:
    """last까지 전체 이력으로 칸별 회차와 '본방 입력 누락?' 칸을 계산한다."""
    programs = schedule_repo.program_rules(conn)
    threshold = int(settings_repo.get(conn, "irregular_missing_warn_count", 4))
    groups: dict[str, list[Cell]] = {}
    for c in schedule_repo.cells_until(conn, last):
        groups.setdefault(c.program_id, []).append(c)
    episodes: dict[tuple[date, int], Any] = {}
    missing: set[tuple[date, int]] = set()
    for pid, cells in groups.items():
        p = programs.get(pid)
        start = p.start_episode if p else 1
        ordered = sorted(cells, key=lambda c: c.key)
        infos = compute_episodes(ordered, start)
        for c, info in zip(ordered, infos):
            episodes[c.key] = info
        if p and p.cycle_type == "irregular":
            missing.update(rerun_streak_warnings(ordered, infos, threshold))
    return episodes, missing


# ── 월 화면 ───────────────────────────────────────

def get_month(conn: sqlite3.Connection, year: int, month: int) -> Result:
    ym = _valid_month(year, month)
    if ym is None:
        return {"ok": False, "errors": ["연도와 월을 다시 골라 주세요."]}
    year, month = ym
    weeks = weeks_of_month(year, month)
    ref = reference_week(year, month)
    first, last = ref, weeks[-1] + timedelta(days=6)

    display = schedule_repo.program_display(conn)
    fixed_ids = set(settings_repo.get(conn, "fixed_program_ids", []))
    episodes, missing = _episode_map(conn, last)
    hol = holidays_between(first, last, schedule_repo.manual_holidays(conn, first, last))

    cells: dict[str, dict[str, Any]] = {}
    for r in schedule_repo.cell_rows_between(conn, first, last):
        d = date.fromisoformat(r["date"])
        info = episodes.get((d, r["hour"]))
        prog = display.get(r["program_id"], {"name": "(삭제된 프로그램)", "category": "교양",
                                              "is_special": False, "cycle_type": ""})
        cells[f"{r['date']}|{r['hour']}"] = {
            "program_id": r["program_id"], "name": prog["name"], "category": prog["category"],
            "is_special": prog["is_special"], "is_fixed": r["program_id"] in fixed_ids,
            "show_episode": prog.get("show_episode", True), "imported": r["source"] == "import",
            "kind": r["kind"], "episode": info.episode if info else None,
            "waiting": bool(info and info.waiting), "missing_warn": (d, r["hour"]) in missing,
            "manual": r["source"] == "manual", "exception_type": r["exception_type"],
            "prep_status": r["prep_status"], "actual_change_note": r["actual_change_note"],
        }

    def week_payload(monday: date, is_reference: bool) -> dict[str, Any]:
        return {
            "monday": monday.isoformat(),
            "is_reference": is_reference,
            "label": f"{(monday.month)}월" if is_reference else f"{week_index_in_month(monday)}주",
            "iso_week": iso_week(monday),
            "days": [{
                "date": d.isoformat(), "day": d.day, "month": d.month,
                "weekday": WEEKDAY_LABELS[d.weekday()],
                "in_month": (not is_reference) and d.month == month and d.year == year,
                "holiday": hol.get(d),
            } for d in week_dates(monday)],
        }

    cal_days = month_dates(year, month)
    filled = sum(1 for k in cells if date.fromisoformat(k.split("|")[0]).month == month
                 and date.fromisoformat(k.split("|")[0]).year == year)
    first_week_keys = {f"{d.isoformat()}|{h}" for d in week_dates(weeks[0]) for h in HOURS}
    plan = schedule_repo.get_month_plan(conn, _ym(year, month))
    issues = _validate(conn, cal_days, episodes, missing, display)

    return {
        "ok": True,
        "year": year, "month": month,
        "status": plan["status"] if plan else STATUS_NONE,
        "plan": {k: plan[k] for k in ("confirmed_at", "closed_at", "unlock_reason")} if plan else None,
        "issues": issues,
        "year_statuses": schedule_repo.month_statuses(conn, year),
        "reference_week": week_payload(ref, True),
        "weeks": [week_payload(w, False) for w in weeks],
        "hours": list(HOURS),
        "cells": cells,
        "fixed_program_ids": sorted(fixed_ids),
        "first_week_filled": any(k in cells for k in first_week_keys),
        "totals": {
            "minutes": filled * MINUTES_PER_CELL,
            "expected_minutes": len(cal_days) * len(HOURS) * MINUTES_PER_CELL,
            "days": len(cal_days),
        },
    }


def _validate(conn: sqlite3.Connection, cal_days: list[date], episodes: dict, missing: set,
              display: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """달력 날짜 기준 검증. 그 달 칸이 하나도 없으면(미작성) 목록을 비운다."""
    first, last = cal_days[0], cal_days[-1]
    cells = {c.key: c for c in schedule_repo.cells_between(conn, first, last)}
    if not cells:
        return []
    default = settings_repo.get(conn, "offweek_policy_default", "rerun")
    rule, conflicts = build_rule_cells(cal_days, schedule_repo.program_rules(conn),
                                       schedule_repo.slot_rules(conn), default)

    def name(pid: str) -> str:
        return display.get(pid, {}).get("name", "?")

    orphans = [(d, h, name(pid)) for pid, d, h in schedule_repo.cancellations_between(conn, first, last)
               if rule.get((d, h)) is None or rule[(d, h)].program_id != pid]
    found = validate_month(cal_days, list(HOURS), cells, episodes, missing, orphans,
                           [(c.date, c.hour, tuple(name(p) for p in c.program_ids)) for c in conflicts])
    month = cal_days[0].month

    def detail(i: Any) -> str:
        # 11/1처럼 다른 달 소속 주에 있는 날짜는 그 달 화면에서 고친다
        if i.key and month_of_week(i.key[0])[1] != month:
            return f"{i.detail} ({month_of_week(i.key[0])[1]}월 화면에서 고칩니다)"
        return i.detail

    return [{"kind": i.kind, "level": i.level, "detail": detail(i),
             "key": f"{i.key[0].isoformat()}|{i.key[1]}" if i.key else None} for i in found]


# ── 월 생성 ───────────────────────────────────────

SCOPES = {"first_week": "첫 주 불러오기", "rest": "월단위 생성", "all": "한 달 전체 생성"}


def generate(conn: sqlite3.Connection, year: int, month: int, scope: str,
             overwrite_manual: bool = False) -> Result:
    """규칙으로 칸을 채운다. 사람이 손댄 칸은 overwrite_manual=True일 때만 바꾼다."""
    ym = _valid_month(year, month)
    if ym is None or scope not in SCOPES:
        return {"ok": False, "errors": ["생성할 달 또는 범위가 올바르지 않습니다."]}
    year, month = ym
    plan_row = schedule_repo.get_month_plan(conn, _ym(year, month))
    if plan_row and plan_row["status"] == "마감":
        return {"ok": False, "errors": ["마감된 달은 다시 생성할 수 없습니다. 잠금을 먼저 풀어 주세요."]}

    weeks = weeks_of_month(year, month)
    chosen = weeks[:1] if scope == "first_week" else weeks[1:] if scope == "rest" else weeks
    dates = [d for w in chosen for d in week_dates(w)]
    if not dates:
        return {"ok": True, "changed": 0, "manual_conflicts": [], "slot_conflicts": []}

    default_offweek = settings_repo.get(conn, "offweek_policy_default", "rerun")
    rule, slot_conflicts = build_rule_cells(dates, schedule_repo.program_rules(conn),
                                            schedule_repo.slot_rules(conn), default_offweek)
    snap = schedule_repo.snapshot(conn, dates[0], dates[-1], [])   # Ctrl+Z용
    existing = {c.key: c for c in schedule_repo.cells_between(conn, dates[0], dates[-1])}
    cancels = schedule_repo.cancellation_keys(conn, dates[0], dates[-1])
    plan = plan_generation(rule, existing, cancels, overwrite_manual, dates)

    for key in plan.deletes:
        schedule_repo.delete_cell(conn, *key)
    for c in plan.upserts:
        schedule_repo.upsert_rule_cell(conn, c)
    schedule_repo.touch_month_generated(conn, _ym(year, month))

    names = {pid: p["name"] for pid, p in schedule_repo.program_display(conn).items()}
    changed = len(plan.upserts) + len(plan.deletes)
    change_log_repo.add(conn, "month", _ym(year, month), SCOPES[scope], None,
                        {"changed": changed, "overwrite_manual": overwrite_manual})

    def conflict_row(c: Cell) -> dict[str, Any]:
        r = rule.get(c.key)
        return {"date": c.date.isoformat(), "hour": c.hour, "current": names.get(c.program_id, "?"),
                "rule": names.get(r.program_id, "?") if r else "(빈칸)"}

    return {
        "ok": True,
        "changed": changed,
        # overwrite_manual=False면 아직 안 바뀐 칸, True면 방금 바꾼 칸
        "manual_conflicts": [conflict_row(c) for c in plan.manual_conflicts],
        "overwritten": overwrite_manual,
        "undo": {"label": f"{month}월 {SCOPES[scope]}", "snapshot": snap} if changed else None,
        "slot_conflicts": [{"date": s.date.isoformat(), "hour": s.hour,
                            "programs": [names.get(p, "?") for p in s.program_ids]} for s in slot_conflicts],
    }
