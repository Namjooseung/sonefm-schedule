"""칸 팝업 동작: 본방/재방 전환, 결방, 교체, 특집, 재방 회차 지정, 실제 변경, 준비 상태, 원래대로.

- '이번만': 그 칸만 사람이 고친 칸(manual)으로 바꾸고, 원래 나갈 프로그램은 결방 기록을 남긴다.
- '이후 전부': 편성 자리 이력을 갱신(domain.slot_change)하고 그 날짜부터 이미 만든 칸을 다시 생성한다.
  사람이 고친 다른 칸과 마감된 달은 건드리지 않는다.
- 모든 동작은 변경 기록을 남기고, Ctrl+Z용 직전 상태(undo)를 결과에 담아 돌려준다.
  api.py가 undo를 세션 메모리에 쌓고 화면에는 보내지 않는다.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date
from typing import Any

from app.domain import programs as program_rules
from app.domain.episodes import plan_episode_change, previous_episode
from app.domain.generate import build_rule_cells, plan_generation
from app.domain.models import HOURS, Cell
from app.domain.slot_change import plan_from_date
from app.domain.weeks import month_of_week
from app.repository import change_log_repo, programs_repo, schedule_repo, settings_repo
from app.services import programs as program_service
from app.services.schedule import _episode_map, rerun_mark_map

Result = dict[str, Any]
KINDS = ("본방", "재방")
PREP = ("미입고", "입고", "송출완료")
SCOPES = {"once": "이번만", "after": "이후 전부"}


def _fail(*msgs: str) -> Result:
    return {"ok": False, "errors": list(msgs)}


def _parse(d: Any, hour: Any) -> tuple[date, int] | None:
    try:
        dd, hh = date.fromisoformat(str(d)), int(hour)
    except (TypeError, ValueError):
        return None
    return (dd, hh) if hh in HOURS else None


def _ym_of(d: date) -> str:
    y, m = month_of_week(d)
    return f"{y:04d}-{m:02d}"


def _locked(conn: sqlite3.Connection, d: date) -> bool:
    return schedule_repo.month_status_of(conn, _ym_of(d)) == "마감"


def _label(d: date, hour: int) -> str:
    return f"{d.month}/{d.day} {hour}시"


def _names(conn: sqlite3.Connection) -> dict[str, str]:
    return {pid: p["name"] for pid, p in schedule_repo.program_display(conn).items()}


def _rule_at(conn: sqlite3.Connection, d: date, hour: int) -> Cell | None:
    """결방 기록과 무관하게, 규칙상 이 칸에 들어갈 칸."""
    default = settings_repo.get(conn, "offweek_policy_default", "rerun")
    rule, _ = build_rule_cells([d], schedule_repo.program_rules(conn), schedule_repo.slot_rules(conn), default)
    return rule.get((d, hour))


def _slot(conn: sqlite3.Connection, slot_id: str | None):
    if not slot_id:
        return None
    return next((s for s in schedule_repo.slot_rules(conn) if s.id == slot_id), None)


# ── 공통 실행 틀 ──────────────────────────────────

def _run_edit(conn: sqlite3.Connection, d: date, hour: int, action: str,
              fn: Callable[[], str | Result], last: date | None = None,
              program_ids: tuple[str, ...] = (), affects_episodes: bool = True) -> Result:
    """마감 확인 → 스냅숏 → 실행 → 변경 기록. fn은 변경 기록 메모(str)나 실패 결과를 돌려준다."""
    if _locked(conn, d):
        return _fail("마감된 달의 칸은 고칠 수 없습니다. 잠금을 먼저 풀어 주세요.")
    before_cell = schedule_repo.get_cell_row(conn, d, hour)
    snap = schedule_repo.snapshot(conn, d, max(d, last or d), [p for p in program_ids if p])
    out = fn()
    if isinstance(out, dict):
        return out
    after_cell = schedule_repo.get_cell_row(conn, d, hour)
    note = out
    if schedule_repo.month_status_of(conn, _ym_of(d)) == "확정":
        note += " [확정 후 변경]"
    change_log_repo.add(conn, "cell", f"{d.isoformat()}|{hour}", action, before_cell, after_cell, note)
    return {"ok": True, "message": out, "warnings": _closed_after_warning(conn, d, program_ids, before_cell, after_cell)
            if affects_episodes else [],
            "undo": {"label": out, "snapshot": snap}}


def _closed_after_warning(conn: sqlite3.Connection, d: date, program_ids: tuple[str, ...],
                          before: dict | None, after: dict | None) -> list[str]:
    """이 칸보다 뒤의 마감 달에 같은 프로그램 칸이 있으면 그 달 회차가 바뀔 수 있다고 경고."""
    touched = sorted({p for p in (*program_ids, before and before["program_id"], after and after["program_id"]) if p})
    closed = schedule_repo.closed_months(conn)
    here = _ym_of(d)
    months = sorted({_ym_of(date.fromisoformat(x)) for x in schedule_repo.months_using(conn, d, touched)})
    later = [ym for ym in months if ym > here and ym in closed]
    if not later:
        return []
    names = ", ".join(f"{int(ym[5:])}월" for ym in later)
    return [f"마감된 {names}의 회차가 바뀔 수 있습니다. 제출한 보고서와 다르지 않은지 확인해 주세요."]


def _regenerate_from(conn: sqlite3.Connection, d: date) -> int:
    """d부터 이미 만든 마지막 칸까지 규칙 칸을 다시 맞춘다 (사람 칸·마감 달 제외)."""
    last = schedule_repo.max_cell_date(conn)
    if last is None or last < d:
        last = d
    closed = schedule_repo.closed_months(conn)
    dates = [date.fromordinal(o) for o in range(d.toordinal(), last.toordinal() + 1)]
    dates = [x for x in dates if _ym_of(x) not in closed]
    if not dates:
        return 0
    default = settings_repo.get(conn, "offweek_policy_default", "rerun")
    rule, _ = build_rule_cells(dates, schedule_repo.program_rules(conn), schedule_repo.slot_rules(conn), default)
    existing = {c.key: c for c in schedule_repo.cells_between(conn, dates[0], dates[-1])}
    cancels = schedule_repo.cancellation_keys(conn, dates[0], dates[-1])
    plan = plan_generation(rule, existing, cancels, False, dates)
    for key in plan.deletes:
        schedule_repo.delete_cell(conn, *key)
    for c in plan.upserts:
        schedule_repo.upsert_rule_cell(conn, c)
    return len(plan.deletes) + len(plan.upserts)


def _apply_slot_change(conn: sqlite3.Connection, slot_id: str, d: date, program_id: str, role: str) -> str | None:
    """편성 자리 이력 갱신. 실패하면 사용자용 오류 문구."""
    old = _slot(conn, slot_id)
    if old is None:
        return "이 칸의 편성 자리를 찾지 못했습니다."
    plan = plan_from_date(old, d, program_id, role)
    if plan is None:
        return "이 날짜는 편성 자리의 적용 기간 밖입니다."
    # 새 프로그램의 자리와 겹치는지 확인
    target = programs_repo.get_program(conn, program_id)
    if target is None:
        return "바꿀 프로그램을 찾지 못했습니다."
    others = [s for s in target["slots"] if s["id"] != old.id]
    new_slot = {"weekday": old.weekday, "hour": old.hour, "role": role,
                "valid_from": plan.new_valid_from.isoformat(),
                "valid_to": plan.new_valid_to.isoformat() if plan.new_valid_to else None}
    _, errors = program_rules.clean_slots([*others, new_slot], target["cycle_type"])
    if errors:
        return errors[0]
    if plan.delete_old:
        programs_repo.delete_slot_force(conn, old.id)
    else:
        programs_repo.set_slot_valid_to(conn, old.id, plan.close_old_to.isoformat())
    programs_repo.insert_slot(conn, program_id, old.weekday, old.hour, role,
                              new_slot["valid_from"], new_slot["valid_to"])
    return None


# ── 조회 ──────────────────────────────────────────

def get_cell(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any) -> Result:
    parsed = _parse(d_raw, hour_raw)
    if parsed is None:
        return _fail("칸 위치가 올바르지 않습니다.")
    d, hour = parsed
    row = schedule_repo.get_cell_row(conn, d, hour)
    display = schedule_repo.program_display(conn)
    rule = _rule_at(conn, d, hour)
    episodes = _episode_map(conn, d)
    info = episodes.get((d, hour))
    cancels = schedule_repo.cancellations_at(conn, d, hour)
    rule_slot = _slot(conn, rule.original_slot_id) if rule else None
    fixed = set(settings_repo.get(conn, "fixed_program_ids", []))

    cell = None
    if row:
        p = display.get(row["program_id"], {})
        cell = {
            **{k: row[k] for k in ("program_id", "kind", "source", "exception_type", "original_program_id",
                                   "rerun_episode_override", "prep_status", "actual_change_note", "updated_at")},
            "name": p.get("name", "?"), "category": p.get("category"), "is_special": p.get("is_special", False),
            "cycle_type": p.get("cycle_type"), "is_fixed": row["program_id"] in fixed,
            "show_episode": p.get("show_episode", True),
            "episode": info.episode if info else None, "waiting": bool(info and info.waiting),
            "original_name": display.get(row["original_program_id"], {}).get("name") if row["original_program_id"] else None,
        }
    return {
        "ok": True, "date": d.isoformat(), "hour": hour, "cell": cell,
        "rule": {"program_id": rule.program_id, "name": display.get(rule.program_id, {}).get("name"),
                 "kind": rule.kind} if rule else None,
        "matches_rule": bool(row and rule and row["source"] == "rule"),
        "cancellations": [{"name": display.get(c["program_id"], {}).get("name", "?"), "reason": c["reason"]}
                          for c in cancels],
        # '이후 전부'는 규칙 자리가 있을 때만 (비정기·단발은 본방/재방 전환을 이번만으로)
        "scope_available": rule_slot is not None,
        "kind_scope_available": bool(rule_slot and row and row["program_id"] == rule_slot.program_id
                                     and display.get(row["program_id"], {}).get("cycle_type") != "irregular"),
        "locked": _locked(conn, d),
        "month": _ym_of(d),
    }


# ── 동작 ──────────────────────────────────────────

def set_kind(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, kind: str, scope: str = "once") -> Result:
    parsed = _parse(d_raw, hour_raw)
    if parsed is None or kind not in KINDS or scope not in SCOPES:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    row = schedule_repo.get_cell_row(conn, d, hour)
    if row is None:
        return _fail("빈칸은 본방/재방을 바꿀 수 없습니다. 먼저 프로그램을 넣어 주세요.")
    if row["kind"] == kind and scope == "once":
        return {"ok": True, "message": "바뀐 것이 없습니다."}
    name = _names(conn).get(row["program_id"], "?")
    rule = _rule_at(conn, d, hour)

    if scope == "once":
        def fn() -> str:
            schedule_repo.update_cell(conn, d, hour, kind=kind, source="manual",
                                      rerun_episode_override=None if kind == "본방" else row["rerun_episode_override"])
            return f"{_label(d, hour)} {name} → {kind}으로 (이번만)"
        return _run_edit(conn, d, hour, f"{kind}으로", fn)

    if rule is None or rule.program_id != row["program_id"]:
        return _fail("이 칸은 편성 자리로 정해진 칸이 아니라 '이후 전부'를 쓸 수 없습니다.")

    def fn_after() -> str | Result:
        err = _apply_slot_change(conn, rule.original_slot_id, d, row["program_id"], kind)
        if err:
            return _fail(err)
        schedule_repo.delete_cell(conn, d, hour)
        n = _regenerate_from(conn, d)
        return f"{_label(d, hour)}부터 {name} 자리를 {kind}으로 (이후 전부, {n}칸 다시 생성)"
    return _run_edit(conn, d, hour, f"{kind}으로", fn_after, last=schedule_repo.max_cell_date(conn),
                     program_ids=(row["program_id"],))


def cancel(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, mode: str, reason: str | None = None) -> Result:
    """결방. mode: rerun(같은 프로그램 재방으로 대체) | empty(비워두기)."""
    parsed = _parse(d_raw, hour_raw)
    if parsed is None or mode not in ("rerun", "empty"):
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    row = schedule_repo.get_cell_row(conn, d, hour)
    if row is None:
        return _fail("이미 빈칸입니다.")
    pid = row["program_id"]
    name = _names(conn).get(pid, "?")
    reason = (reason or "").strip() or None

    def fn() -> str:
        schedule_repo.add_cancellation(conn, pid, d, hour, reason)
        if mode == "rerun":
            schedule_repo.update_cell(conn, d, hour, kind="재방", source="manual", exception_type="결방대체",
                                      original_program_id=pid, rerun_episode_override=None)
            return f"{_label(d, hour)} {name} 결방 → 재방으로 대체" + (f" ({reason})" if reason else "")
        schedule_repo.delete_cell(conn, d, hour)
        return f"{_label(d, hour)} {name} 결방 → 빈칸" + (f" ({reason})" if reason else "")
    return _run_edit(conn, d, hour, "결방", fn)


def replace(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, program_id: str, kind: str,
            scope: str = "once") -> Result:
    """다른 프로그램으로 교체 (빈칸 채우기 포함). 원래 프로그램은 그날 자동 결방."""
    parsed = _parse(d_raw, hour_raw)
    if parsed is None or kind not in KINDS or scope not in SCOPES:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    names = _names(conn)
    if program_id not in names:
        return _fail("넣을 프로그램을 골라 주세요.")
    row = schedule_repo.get_cell_row(conn, d, hour)
    rule = _rule_at(conn, d, hour)
    new_name = names[program_id]

    if scope == "after":
        if rule is None:
            return _fail("이 칸은 편성 자리로 정해진 칸이 아니라 '이후 전부'를 쓸 수 없습니다. 프로그램 화면에서 자리를 추가해 주세요.")

        def fn_after() -> str | Result:
            err = _apply_slot_change(conn, rule.original_slot_id, d, program_id, kind)
            if err:
                return _fail(err)
            schedule_repo.delete_cancellations_at(conn, d, hour)
            schedule_repo.delete_cell(conn, d, hour)
            n = _regenerate_from(conn, d)
            return (f"{_label(d, hour)}부터 {names.get(rule.program_id, '?')} 자리를 {new_name}({kind})으로"
                    f" (이후 전부, {n}칸 다시 생성)")
        return _run_edit(conn, d, hour, "교체", fn_after, last=schedule_repo.max_cell_date(conn),
                         program_ids=(rule.program_id, program_id))

    original = rule.program_id if rule else (row["original_program_id"] if row else None)
    if original is None:
        cancelled = schedule_repo.cancellations_at(conn, d, hour)
        original = cancelled[0]["program_id"] if cancelled else None

    def fn() -> str:
        if rule and rule.program_id == program_id and rule.kind == kind:
            # 원래 프로그램으로 다시 넣는 것 = 원래대로
            schedule_repo.delete_cancellations_at(conn, d, hour)
            schedule_repo.upsert_rule_cell(conn, rule)
            return f"{_label(d, hour)} {new_name} 원래대로"
        if original and original != program_id:
            schedule_repo.add_cancellation(conn, original, d, hour, f"{new_name}(으)로 교체")
        schedule_repo.put_manual_cell(conn, d, hour, program_id, kind,
                                      "교체" if original and original != program_id else None,
                                      original if original != program_id else None,
                                      rule.original_slot_id if rule else None)
        before = names.get(row["program_id"], "빈칸") if row else "빈칸"
        return f"{_label(d, hour)} {before} → {new_name}({kind}) (이번만)"
    return _run_edit(conn, d, hour, "교체", fn)


def put_special(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, payload: dict[str, Any]) -> Result:
    """특집 넣기. payload: {program_id} (기존 특집 재사용) 또는 {name, category, is_listener_participation}."""
    parsed = _parse(d_raw, hour_raw)
    if parsed is None:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    if _locked(conn, d):
        return _fail("마감된 달의 칸은 고칠 수 없습니다. 잠금을 먼저 풀어 주세요.")
    pid = payload.get("program_id")
    if not pid:
        made = program_service.create_special(conn, payload)
        if not made["ok"]:
            return made
        pid = made["program"]["id"]
    elif pid not in _names(conn):
        return _fail("특집을 찾지 못했습니다.")
    name = _names(conn)[pid]
    rule = _rule_at(conn, d, hour)
    row = schedule_repo.get_cell_row(conn, d, hour)
    original = rule.program_id if rule else (row["program_id"] if row else None)

    def fn() -> str:
        if original:
            schedule_repo.add_cancellation(conn, original, d, hour, f"특집 {name}")
        schedule_repo.put_manual_cell(conn, d, hour, pid, "본방", "특집", original,
                                      rule.original_slot_id if rule else None)
        return f"{_label(d, hour)} 특집 {name}" + (f" (원래 {_names(conn).get(original, '?')} 결방)" if original else "")
    return _run_edit(conn, d, hour, "특집", fn)


def set_override(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, episode: Any) -> Result:
    """회차 지정 (− / + 버튼). episode가 비면 지정 해제(자동 계산으로).

    본방 자리 칸은 직전 회차와 비교해 본방/재방까지 정한다 (domain.episodes.plan_episode_change).
    재방 자리 칸은 그 칸만 바뀐다.
    """
    parsed = _parse(d_raw, hour_raw)
    if parsed is None:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    row = schedule_repo.get_cell_row(conn, d, hour)
    if row is None:
        return _fail("빈칸에는 회차를 지정할 수 없습니다.")
    ep: int | None = None
    if episode not in (None, ""):
        try:
            ep = int(episode)
        except (TypeError, ValueError):
            return _fail("회차는 1 이상의 정수로 입력해 주세요.")
        if ep < 1:
            return _fail("회차는 1 이상의 정수로 입력해 주세요.")
    name = _names(conn).get(row["program_id"], "?")

    kind, override = row["kind"], None
    if ep is not None:
        in_main = row["kind"] == "본방" or not rerun_mark_map(conn, d, d).get((d, hour), True)
        rule = schedule_repo.program_rules(conn).get(row["program_id"])
        mine = [c for c in schedule_repo.cells_until(conn, d) if c.program_id == row["program_id"]]
        previous = previous_episode(mine, rule.start_episode if rule else 1, (d, hour))
        kind, override = plan_episode_change(ep, previous, in_main)

    def fn() -> str:
        schedule_repo.update_cell(conn, d, hour, kind=kind, rerun_episode_override=override, source="manual")
        if ep is None:
            return f"{_label(d, hour)} {name} 회차 자동 계산으로"
        return f"{_label(d, hour)} {name} {ep}화 ({'새 회차' if kind == '본방' else '재방'})"
    return _run_edit(conn, d, hour, "회차 지정", fn, affects_episodes="본방" in (kind, row["kind"]))


def set_actual(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, note: str | None) -> Result:
    """실제 변경 기록 (당일 사고·긴급 결방 등). 편성(계획)은 그대로 둔다."""
    parsed = _parse(d_raw, hour_raw)
    if parsed is None:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    if schedule_repo.get_cell_row(conn, d, hour) is None:
        return _fail("빈칸에는 실제 변경을 기록할 수 없습니다.")
    text = (note or "").strip() or None

    def fn() -> str:
        schedule_repo.update_cell(conn, d, hour, actual_change_note=text)
        return f"{_label(d, hour)} 실제 변경 " + (f"기록: {text}" if text else "기록 지움")
    return _run_edit(conn, d, hour, "실제 변경", fn, affects_episodes=False)


def set_prep(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any, status: str) -> Result:
    parsed = _parse(d_raw, hour_raw)
    if parsed is None or status not in PREP:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    if schedule_repo.get_cell_row(conn, d, hour) is None:
        return _fail("빈칸입니다.")

    def fn() -> str:
        schedule_repo.update_cell(conn, d, hour, prep_status=status)
        return f"{_label(d, hour)} 송출 파일 {status}"
    return _run_edit(conn, d, hour, "준비 상태", fn, affects_episodes=False)


def revert(conn: sqlite3.Connection, d_raw: Any, hour_raw: Any) -> Result:
    """원래대로: 이 칸의 결방 기록과 사람이 고친 내용을 지우고 규칙대로 되돌린다."""
    parsed = _parse(d_raw, hour_raw)
    if parsed is None:
        return _fail("요청이 올바르지 않습니다.")
    d, hour = parsed
    rule = _rule_at(conn, d, hour)

    def fn() -> str:
        schedule_repo.delete_cancellations_at(conn, d, hour)
        if rule is None:
            schedule_repo.delete_cell(conn, d, hour)
            return f"{_label(d, hour)} 원래대로 (규칙상 빈칸)"
        schedule_repo.upsert_rule_cell(conn, rule)
        return f"{_label(d, hour)} 원래대로 ({_names(conn).get(rule.program_id, '?')} {rule.kind})"
    return _run_edit(conn, d, hour, "원래대로", fn)


def undo(conn: sqlite3.Connection, record: dict[str, Any]) -> Result:
    schedule_repo.restore(conn, record["snapshot"])
    change_log_repo.add(conn, "undo", None, "되돌리기", None, None, f"되돌림: {record['label']}")
    return {"ok": True, "message": f"되돌렸습니다: {record['label']}"}
