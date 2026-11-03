"""엑셀 연동: 기존 편성표 가져오기(1회 이관) + 같은 양식으로 내보내기(수식 없이 글자만).

가져오기
1. analyze(): 시트·이름 목록과 매칭 상태를 보여준다 (DB를 바꾸지 않음).
2. run_import(): 사용자가 정한 매핑대로 칸을 넣는다.
   - 칸은 주의 소속(월요일이 속한 달) 시트에서만 가져온다. 같은 주가 두 시트에 있으면 소속 달 시트가 기준.
   - 한 시트에 같은 주가 두 번 있으면 아래쪽 블록을 쓰고 알린다.
   - 06·22시 줄이 비어 있으면 고정 편성(굿모닝!/굿바이!)으로 채운다.
   - 새로 등록한 프로그램은 마지막 달 기준으로 편성 자리·주기를 추정한다.
   - 엑셀 회차에 맞게 시작 회차를 정하고, 계산과 다른 재방은 재방 회차 지정으로 맞춘다.
   - 그래도 엑셀과 다른 칸(엑셀 쪽 회차 오류 등)은 목록으로 돌려준다.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.domain.episodes import compute_episodes
from app.domain.excel_text import format_cell_text, infer_slots, match_names, normalize_name, parse_cell_text
from app.domain.weeks import iso_week, month_of_week, week_dates
from app.io_excel.reader import Sheet, read_workbook
from app.io_excel.writer import MonthSheet, WeekBlock, write_months
from app.repository import change_log_repo, programs_repo, schedule_repo, settings_repo
from app.repository._common import new_id, now_iso
from app.services import programs as program_service

Result = dict[str, Any]
Key = tuple[date, int]
FIXED_HOURS = (6, 22)


def _fail(*msgs: str) -> Result:
    return {"ok": False, "errors": list(msgs)}


def _read(path: str) -> list[Sheet] | Result:
    p = Path(path or "")
    if not p.is_file():
        return _fail("엑셀 파일을 찾지 못했습니다.")
    if p.suffix.lower() not in (".xlsx", ".xlsm"):
        return _fail("xlsx 형식의 엑셀 파일만 가져올 수 있습니다. (예전 xls 파일은 엑셀에서 xlsx로 다시 저장해 주세요.)")
    try:
        return read_workbook(p)
    except PermissionError:
        return _fail("파일을 열 수 없습니다. 엑셀에서 그 파일을 닫고 다시 시도해 주세요.")
    except Exception:  # 손상된 파일 등
        return _fail("엑셀 파일을 읽지 못했습니다. 파일이 손상되지 않았는지 확인해 주세요.")


def _own_weeks(sheet: Sheet) -> tuple[dict[date, Any], list[str]]:
    """시트에서 그 달 소속 주만 (같은 주가 두 번이면 아래쪽)."""
    weeks: dict[date, Any] = {}
    notes: list[str] = []
    for w in sheet.weeks:
        if month_of_week(w.monday) != (sheet.year, sheet.month):
            continue
        if w.monday in weeks:
            notes.append(f"{sheet.title} 시트에 {w.monday.month}/{w.monday.day} 주가 두 번 있어 아래쪽({w.header_row}행)을 썼습니다.")
        weeks[w.monday] = w
    return weeks, notes


def _fixed_by_hour(conn: sqlite3.Connection) -> dict[int, str]:
    """고정 편성 프로그램 → 시각 (편성 자리 기준)."""
    out: dict[int, str] = {}
    for pid in settings_repo.get(conn, "fixed_program_ids", []):
        p = programs_repo.get_program(conn, pid)
        if p:
            for s in p["slots"]:
                out.setdefault(s["hour"], pid)
    return out


def _collect(sheets: list[Sheet], titles: set[str] | None):
    """선택한 시트의 소속 주 칸 → {(날짜, 시): (해석 결과 | None, 시트, 셀)} + 알림 + 오류 칸."""
    cells: dict[Key, tuple[Any, str, str]] = {}
    notes: list[str] = []
    errors: list[str] = []
    months: list[tuple[int, int]] = []
    for sh in sheets:
        if sh.year is None or (titles is not None and sh.title not in titles):
            continue
        weeks, n = _own_weeks(sh)
        notes += n
        if weeks:
            months.append((sh.year, sh.month))
        for w in weeks.values():
            for key, (val, coord) in w.cells.items():
                parsed = parse_cell_text(val)
                if parsed and parsed.error:
                    errors.append(f"{sh.title}!{coord} ({parsed.error})")
                    parsed = None
                cells[key] = (parsed, sh.title, coord)
    return cells, notes, errors, sorted(set(months))


# ── 1. 분석 ───────────────────────────────────────

def analyze(conn: sqlite3.Connection, path: str) -> Result:
    sheets = _read(path)
    if isinstance(sheets, dict):
        return sheets
    cells, notes, errors, _ = _collect(sheets, None)
    statuses = {}
    sheet_rows = []
    for sh in sheets:
        if sh.year is None:
            sheet_rows.append({"title": sh.title, "importable": False, "reason": "편성표 시트가 아님 (이름이 YYMM 형식이 아님)"})
            continue
        weeks, _ = _own_weeks(sh)
        ym = f"{sh.year:04d}-{sh.month:02d}"
        statuses[ym] = schedule_repo.month_status_of(conn, ym)
        filled = sum(1 for w in weeks.values() for v, _ in w.cells.values() if parse_cell_text(v))
        sheet_rows.append({"title": sh.title, "importable": bool(weeks), "year": sh.year, "month": sh.month,
                           "weeks": len(weeks), "cells": filled, "status": statuses[ym] or "미작성",
                           "reason": "" if weeks else "이 달 소속 주가 없음"})

    counts: dict[str, int] = defaultdict(int)
    has_ep: dict[str, bool] = defaultdict(bool)
    first_seen: dict[str, str] = {}
    sheet_of: dict[str, set[str]] = defaultdict(set)
    for (d, _h), (p, title, _c) in sorted(cells.items()):
        if p is None:
            continue
        counts[p.name] += 1
        has_ep[p.name] |= p.episode is not None
        first_seen.setdefault(p.name, d.isoformat())
        sheet_of[p.name].add(title)
    matched = match_names(counts.keys(), programs_repo.name_index(conn))
    names_by_id = {pid: n for pid, n, _ in programs_repo.name_index(conn)}
    names = [{
        "name": n, "count": counts[n], "has_episode": has_ep[n], "first_date": first_seen[n],
        "sheets": sorted(sheet_of[n]), "status": matched[n][0], "program_id": matched[n][1],
        "program_name": names_by_id.get(matched[n][1]),
    } for n in sorted(counts, key=lambda x: (matched[x][0] == "matched", x))]
    return {"ok": True, "sheets": sheet_rows, "names": names, "notes": notes,
            "error_cells": errors[:50], "error_count": len(errors)}


# ── 2. 가져오기 ───────────────────────────────────

def _put_import_cell(conn: sqlite3.Connection, d: date, hour: int, pid: str, kind: str) -> None:
    ts = now_iso()
    conn.execute(
        "INSERT INTO schedule_cells (id, date, hour, program_id, kind, source, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'import', ?, ?) ON CONFLICT(date, hour) DO UPDATE SET"
        " program_id = excluded.program_id, kind = excluded.kind, source = 'import', exception_type = NULL,"
        " original_program_id = NULL, original_slot_id = NULL, rerun_episode_override = NULL,"
        " updated_at = excluded.updated_at",
        (new_id(), d.isoformat(), hour, pid, kind, ts, ts))


def run_import(conn: sqlite3.Connection, path: str, titles: list[str], mapping: dict[str, dict[str, Any]],
               overwrite: bool = True) -> Result:
    """mapping: 엑셀 이름 → {action, ...}
    - map: 기존 프로그램(program_id)에 연결 (이름이 다르면 별칭 추가)
    - new: 새 프로그램으로 등록 (category, is_listener_participation)
    - same: 엑셀의 다른 이름(target)과 같은 프로그램 (표기만 다른 이름 묶기, 별칭 추가)
    - skip: 가져오지 않음
    mapping에 없는 이름은 이름·별칭이 정확히 같은 프로그램이 있으면 그 프로그램, 아니면 건너뛴다."""
    sheets = _read(path)
    if isinstance(sheets, dict):
        return sheets
    cells, notes, errors, months = _collect(sheets, set(titles or []))
    if not months:
        return _fail("가져올 시트를 하나 이상 골라 주세요.")
    closed = [f"{m}월" for y, m in months if schedule_repo.month_status_of(conn, f"{y:04d}-{m:02d}") == "마감"]
    if closed:
        return _fail(f"마감된 달({', '.join(closed)})은 가져올 수 없습니다. 잠금을 풀거나 그 시트를 빼 주세요.")

    # 이름 → 프로그램
    index = programs_repo.name_index(conn)
    auto = match_names({p.name for p, _, _ in cells.values() if p}, index)
    first_seen: dict[str, date] = {}
    has_ep: dict[str, bool] = defaultdict(bool)
    for (d, _h), (p, _t, _c) in sorted(cells.items()):
        if p:
            first_seen.setdefault(p.name, d)
            has_ep[p.name] |= p.episode is not None
    resolved: dict[str, str] = {}
    created: list[str] = []
    aliases_added = 0
    same_as: dict[str, str] = {}
    for name in sorted(first_seen):
        m = mapping.get(name) or {}
        action = m.get("action") or ("map" if auto[name][0] == "matched" else "skip")
        if action == "skip":
            continue
        if action == "same":
            same_as[name] = m.get("target") or ""
            continue
        if action == "new":
            r = program_service.save_program(conn, {
                "name": name, "category": m.get("category") or "교양",
                "is_listener_participation": bool(m.get("is_listener_participation")),
                "cycle_type": "weekly", "start_date": first_seen[name].isoformat(),
                "show_episode": has_ep[name], "memo": "엑셀에서 가져와 등록",
            })
            if not r["ok"]:
                return _fail(f"'{name}' 등록 실패: {r['errors'][0]}")
            resolved[name] = r["program"]["id"]
            created.append(r["program"]["id"])
            continue
        pid = m.get("program_id") or auto[name][1]
        prog = programs_repo.get_program(conn, pid) if pid else None
        if prog is None:
            return _fail(f"'{name}'을(를) 연결할 프로그램을 골라 주세요.")
        resolved[name] = pid
        if normalize_name(name) != prog["name"] and name not in prog["aliases"]:
            programs_repo.replace_aliases(conn, pid, [*prog["aliases"], name])
            aliases_added += 1

    # 표기만 다른 이름 → 대상 이름의 프로그램 (대상도 'same'이면 따라간다)
    for name, target in same_as.items():
        seen, t = {name}, target
        while t in same_as and t not in seen:
            seen.add(t)
            t = same_as[t]
        pid = resolved.get(t)
        if pid is None:
            return _fail(f"'{name}'을(를) 묶을 대상 '{target}'이 가져오지 않음으로 되어 있습니다. 대상을 먼저 정해 주세요.")
        resolved[name] = pid
        prog = programs_repo.get_program(conn, pid)
        if normalize_name(name) != prog["name"] and name not in prog["aliases"]:
            programs_repo.replace_aliases(conn, pid, [*prog["aliases"], name])
            aliases_added += 1

    # 기존 엑셀은 본방 자리에 같은 회차를 다시 낼 때 (재)를 안 붙였다 (예: 75화 → 75화 → 76화).
    # 프로그램별 날짜순으로 보아 이미 나간 회차가 다시 나오면 재방으로 읽는다.
    kinds: dict[Key, str] = {}
    last_on: dict[str, int] = {}
    as_rerun = 0
    for key, (p, _t, _c) in sorted(cells.items()):
        if p is None or p.name not in resolved:
            continue
        pid, kind = resolved[p.name], p.kind
        if kind == "본방" and p.episode is not None:
            if pid in last_on and p.episode <= last_on[pid]:
                kind = "재방"
                as_rerun += 1
            else:
                last_on[pid] = p.episode
        kinds[key] = kind

    # 칸 쓰기
    fixed = _fixed_by_hour(conn)
    written = kept = cleared = skipped = 0
    excel_ep: dict[Key, tuple[str, int | None]] = {}
    for (d, h), (p, _t, _c) in sorted(cells.items()):
        existing = schedule_repo.get_cell_row(conn, d, h)
        if existing and not overwrite:
            kept += 1
            continue
        if p is None:
            if h in FIXED_HOURS and h in fixed:
                _put_import_cell(conn, d, h, fixed[h], "본방")
                written += 1
            elif existing:
                schedule_repo.delete_cell(conn, d, h)
                cleared += 1
            continue
        pid = resolved.get(p.name)
        if pid is None:
            skipped += 1
            if existing:
                schedule_repo.delete_cell(conn, d, h)
            continue
        _put_import_cell(conn, d, h, pid, kinds.get((d, h), p.kind))
        excel_ep[(d, h)] = (pid, p.episode)
        written += 1
    for y, m in months:
        schedule_repo.touch_month_generated(conn, f"{y:04d}-{m:02d}")

    # 새 프로그램: 마지막 달 기준 편성 자리 추정
    inferred, ended = _infer_new(conn, created, resolved, cells, kinds)
    # 회차 맞추기
    _align_episodes(conn, excel_ep)
    diffs = _diff_episodes(conn, excel_ep)

    change_log_repo.add(conn, "import", None, "엑셀 가져오기", None,
                        {"sheets": titles, "written": written, "created": len(created)},
                        f"엑셀 가져오기: {', '.join(titles)} — {written}칸")
    return {"ok": True, "written": written, "kept": kept, "cleared": cleared, "skipped": skipped,
            "read_as_rerun": as_rerun,
            "created": len(created), "aliases_added": aliases_added, "inferred": inferred, "ended": ended,
            "notes": notes, "error_cells": errors[:50], "error_count": len(errors),
            "episode_diffs": diffs[:50], "episode_diff_count": len(diffs),
            "months": [f"{y:04d}-{m:02d}" for y, m in months]}


INFER_WEEKS = 4   # 편성 자리 추정에 쓰는 마지막 주 수


def _infer_new(conn, created: list[str], resolved: dict[str, str], cells, kinds: dict[Key, str]) -> tuple[int, int]:
    """새로 등록한 프로그램의 편성 자리(마지막 4주)와 주기(가져온 전체 기간의 본방 간격) 추정.
    그 4주에 한 번도 안 나온 프로그램은 마지막 방송일로 종영 처리한다."""
    if not created:
        return 0, 0
    filled_weeks = sorted({d - timedelta(days=d.weekday()) for (d, _h), (p, _t, _c) in cells.items() if p})
    mondays = filled_weeks[-INFER_WEEKS:]
    rows = [(d, h, resolved[p.name], kinds.get((d, h), p.kind)) for (d, h), (p, _t, _c) in cells.items()
            if p and resolved.get(p.name) in created]
    last_seen: dict[str, date] = {}
    for d, _h, pid, _k in rows:
        last_seen[pid] = max(last_seen.get(pid, d), d)
    guess = infer_slots(rows, mondays, history=rows)   # 자리는 마지막 4주, 주기·본방 자리는 가져온 전체 기간
    inferred = ended = 0
    for pid in created:
        prog = programs_repo.get_program(conn, pid)
        data = {k: prog[k] for k in programs_repo._PROGRAM_COLS}  # noqa: SLF001
        g = guess.get(pid)
        if pid in last_seen and mondays and last_seen[pid] < mondays[0]:
            data["end_date"] = last_seen[pid].isoformat()
            data["memo"] = "엑셀에서 가져와 등록 — 마지막 4주에 나오지 않아 마지막 방송일로 종영 처리했습니다."
            programs_repo.update_program(conn, pid, data)
            ended += 1
            continue
        if not g:
            continue
        data["cycle_type"] = g.cycle_type
        data["cycle_anchor_date"] = g.anchor.isoformat() if g.anchor else None
        data["memo"] = "엑셀에서 가져와 등록 — 편성 자리·주기는 추정값이니 확인해 주세요."
        programs_repo.update_program(conn, pid, data)
        programs_repo.sync_slots(conn, pid, [{"id": None, "weekday": s_.weekday, "hour": s_.hour, "role": s_.role,
                                               "valid_from": mondays[0].isoformat(), "valid_to": None} for s_ in g.slots])
        inferred += 1
    return inferred, ended


def _cells_by_program(conn: sqlite3.Connection) -> dict[str, list]:
    groups: dict[str, list] = defaultdict(list)
    for c in schedule_repo.cells_until(conn, date.max):
        groups[c.program_id].append(c)
    return {pid: sorted(cs, key=lambda c: c.key) for pid, cs in groups.items()}


def _align_episodes(conn: sqlite3.Connection, excel_ep: dict[Key, tuple[str, int | None]]) -> None:
    """엑셀 회차에 맞게 시작 회차를 정하고, 계산과 다른 재방은 회차 지정으로 맞춘다."""
    by_prog: dict[str, list[Key]] = defaultdict(list)
    for key, (pid, ep) in excel_ep.items():
        if ep is not None:
            by_prog[pid].append(key)
    all_cells = _cells_by_program(conn)
    for pid, keys in by_prog.items():
        cells = all_cells.get(pid, [])
        # 가장 최근 본방 회차에 맞춘다 → 앞으로 이어질 회차가 엑셀과 같다 (차이는 지난 달로 몰림)
        last_on = next((c for c in reversed(cells) if c.kind == "본방" and excel_ep.get(c.key, (None, None))[1] is not None), None)
        prog = programs_repo.get_program(conn, pid)
        start = prog["start_episode"]
        if last_on is not None:
            before = sum(1 for c in cells if c.kind == "본방" and c.key < last_on.key)
            start = max(1, excel_ep[last_on.key][1] - before)
        else:
            first_re = next((c for c in cells if excel_ep.get(c.key, (None, None))[1] is not None), None)
            if first_re is not None and not any(c.kind == "본방" and c.key < first_re.key for c in cells):
                start = excel_ep[first_re.key][1] + 1
        if start != prog["start_episode"]:
            conn.execute("UPDATE programs SET start_episode = ?, updated_at = ? WHERE id = ?", (start, now_iso(), pid))
        infos = compute_episodes(cells, start)
        for c, info in zip(cells, infos):
            want = excel_ep.get(c.key, (None, None))[1]
            if c.kind == "재방" and want is not None and want != info.episode:
                schedule_repo.update_cell(conn, c.date, c.hour, rerun_episode_override=want)


def _diff_episodes(conn: sqlite3.Connection, excel_ep: dict[Key, tuple[str, int | None]]) -> list[dict[str, Any]]:
    """가져온 뒤 계산 회차가 엑셀과 다른 칸 (대부분 엑셀 쪽 회차 입력 오류)."""
    names = {pid: n for pid, n, _ in programs_repo.name_index(conn)}
    show = {pid: p["show_episode"] for pid, p in schedule_repo.program_display(conn).items()}
    by_prog: dict[str, list[Key]] = defaultdict(list)
    for key, (pid, ep) in excel_ep.items():
        if ep is not None and show.get(pid, True):
            by_prog[pid].append(key)
    out = []
    all_cells = _cells_by_program(conn)
    for pid in by_prog:
        cells = all_cells.get(pid, [])
        prog = programs_repo.get_program(conn, pid)
        for c, info in zip(cells, compute_episodes(cells, prog["start_episode"])):
            want = excel_ep.get(c.key, (None, None))[1]
            if want is not None and want != info.episode:
                out.append({"date": c.date.isoformat(), "hour": c.hour, "name": names.get(pid, "?"),
                            "excel": want, "app": info.episode})
    return sorted(out, key=lambda x: (x["date"], x["hour"]))


# ── 3. 내보내기 ───────────────────────────────────

def _cell_texts(conn: sqlite3.Connection, first: date, last: date) -> dict[Key, tuple[str, bool, bool]]:
    """(날짜, 시) → (엑셀 글자, 재방 표시 여부, 고정 편성 그대로인지, 프로그램 id)."""
    from app.services.schedule import _episode_map, rerun_mark_map
    episodes = _episode_map(conn, last)
    marks = rerun_mark_map(conn, first, last)
    display = schedule_repo.program_display(conn)
    fixed = set(settings_repo.get(conn, "fixed_program_ids", []))
    out = {}
    for r in schedule_repo.cell_rows_between(conn, first, last):
        d = date.fromisoformat(r["date"])
        p = display.get(r["program_id"], {"name": "?", "show_episode": True, "is_special": False})
        info = episodes.get((d, r["hour"]))
        show = p["show_episode"] and not p["is_special"] and r["program_id"] not in fixed
        # 본방 자리에 나가는 재방은 (재)를 붙이지 않는다 (기존 엑셀과 같은 방식)
        marked = r["kind"] == "재방" and marks.get((d, r["hour"]), True)
        text = format_cell_text(p["name"], "재방" if marked else "본방", info.episode if info else None, show)
        is_band = r["program_id"] in fixed and r["source"] != "manual"
        out[(d, r["hour"])] = (text, marked, is_band, r["program_id"])
    return out


def build_month_sheet(conn: sqlite3.Connection, year: int, month: int) -> MonthSheet:
    first = date(year, month, 1)
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
    monday = first - timedelta(days=first.weekday())
    mondays = []
    while monday <= last:
        mondays.append(monday)
        monday += timedelta(days=7)
    texts = _cell_texts(conn, mondays[0], mondays[-1] + timedelta(days=6))
    blocks = []
    for mon in mondays:
        days = week_dates(mon)
        wk = WeekBlock(label=f"{month_of_week(mon)[1]}-{iso_week(mon)}", days=[d.day for d in days])
        for h in range(6, 23):
            row = [texts.get((d, h)) for d in days]
            if all(c and c[2] and c[3] == row[0][3] for c in row):
                wk.bands.add(h)
            else:
                wk.rows[h] = [(c[0], c[1]) if c else ("", False) for c in row]
        blocks.append(wk)
    return MonthSheet(title=f"{year % 100:02d}{month:02d}", first_day=first, weeks=blocks)


def export_months(conn: sqlite3.Connection, months: list[tuple[int, int]], path: str) -> Result:
    try:
        write_months([build_month_sheet(conn, y, m) for y, m in months], path)
    except PermissionError:
        return _fail("파일을 저장할 수 없습니다. 같은 이름의 파일이 엑셀에 열려 있으면 닫고 다시 시도해 주세요.")
    return {"ok": True, "path": str(path), "message": f"엑셀로 내보냈습니다: {Path(path).name}"}


# ── 확인: 엑셀 원본과 앱 칸 비교 ──────────────────

def compare(conn: sqlite3.Connection, path: str, titles: list[str], limit: int = 100) -> Result:
    """선택 시트의 소속 주에서 엑셀 글자와 앱 글자가 다른 칸. 06·22시 빈 줄 = 고정 편성으로 본다."""
    sheets = _read(path)
    if isinstance(sheets, dict):
        return sheets
    cells, _n, _e, months = _collect(sheets, set(titles))
    if not cells:
        return {"ok": True, "diffs": [], "count": 0, "compared": 0}
    first, last = min(k[0] for k in cells), max(k[0] for k in cells)
    texts = _cell_texts(conn, first, last)
    diffs = []
    for key, (p, title, coord) in sorted(cells.items()):
        app = texts.get(key)
        excel_text = format_cell_text(p.name, p.kind, p.episode, p.episode is not None) if p else ""
        app_text = "" if app is None or (p is None and app[2]) else app[0]
        if excel_text != app_text:
            diffs.append({"cell": f"{title}!{coord}", "date": key[0].isoformat(), "hour": key[1],
                          "excel": excel_text, "app": app_text, "kind": _diff_kind(excel_text, app_text)})
    by_kind: dict[str, int] = defaultdict(int)
    for d in diffs:
        by_kind[d["kind"]] += 1
    return {"ok": True, "diffs": diffs[:limit], "count": len(diffs), "compared": len(cells), "by_kind": dict(by_kind)}


def _diff_kind(excel_text: str, app_text: str) -> str:
    """차이 분류: 재방 표시만 다름((재)가 한쪽에만) / 회차만 다름 / 그 밖."""
    if app_text == excel_text + "(재)" or excel_text == app_text + "(재)":
        return "재방 표시만 다름"
    a, b = parse_cell_text(excel_text), parse_cell_text(app_text)
    if a and b and a.name == b.name:
        return "회차만 다름"
    return "그 밖"
