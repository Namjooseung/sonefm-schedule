"""화면(js_api)에 노출하는 함수들. 얇게 유지하고 실제 일은 services/domain/repository에 맡긴다.

모든 함수는 예외를 밖으로 던지지 않는다. 예상 못 한 오류는 로그에 남기고
{"ok": False, "errors": ["...한국어 안내..."]} 를 돌려준다.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from collections.abc import Callable
from typing import Any

from app import APP_VERSION
from app.backup import backup_db
from app.config import AppConfig
from app.db.connection import open_db
from app.domain import programs as program_rules
from app.repository import meta_repo
from app.repository import change_log_repo
from app.services import cell_edit, month_status
from app.services import excel as excel_service
from app.services import programs as program_service
from app.services import schedule as schedule_service

log = logging.getLogger("sonefm.api")

UNDO_LIMIT = 50   # 세션 안에서 되돌릴 수 있는 작업 수

_UNEXPECTED = "처리 중 문제가 생겼습니다. 다시 시도해 주세요. 계속되면 로그 파일을 개발자에게 보내 주세요."


class Api:
    def __init__(self, cfg: AppConfig) -> None:
        # pywebview는 밑줄로 시작하는 속성을 화면에 노출하지 않는다
        self._cfg = cfg
        self._undo: list[dict[str, Any]] = []   # Ctrl+Z용 직전 상태 (이번 실행 동안만)

    def _run(self, name: str, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        """DB 연결 하나 = 트랜잭션 하나. 실패 결과({"ok": False})면 쓰기를 되돌린다."""
        try:
            with open_db(self._cfg.db_path) as conn:
                result = fn(conn)
                if isinstance(result, dict) and result.get("ok") is False:
                    conn.rollback()
                if isinstance(result, dict) and "undo" in result:
                    record = result.pop("undo")
                    if record:
                        self._undo.append(record)
                        del self._undo[:-UNDO_LIMIT]
                if isinstance(result, dict):
                    result["can_undo"] = bool(self._undo)
                return result
        except Exception:
            log.exception("%s 실패", name)
            return {"ok": False, "errors": [_UNEXPECTED]}

    # ── 공통 ──────────────────────────────────────
    def ping(self) -> dict[str, Any]:
        """연결 확인용 왕복 호출."""
        def fn(conn: sqlite3.Connection) -> dict[str, Any]:
            version = meta_repo.schema_version(conn)
            log.info("ping 응답: 스키마 v%d", version)
            return {"ok": True, "message": "정상 연결", "app_version": APP_VERSION,
                    "db_path": self._cfg.db_path, "schema_version": version}
        return self._run("ping", fn)

    # ── 프로그램 ──────────────────────────────────
    def program_choices(self) -> dict[str, Any]:
        return {"ok": True, **program_rules.choices()}

    def list_programs(self, query: str = "", include_ended: bool = False) -> dict[str, Any]:
        return self._run("list_programs", lambda c: {
            "ok": True, "items": program_service.list_programs(c, query or "", bool(include_ended))})

    def get_program(self, program_id: str) -> dict[str, Any]:
        return self._run("get_program", lambda c: program_service.get_program(c, program_id))

    def save_program(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._run("save_program", lambda c: program_service.save_program(c, payload))

    def end_program(self, program_id: str, end_date: str) -> dict[str, Any]:
        return self._run("end_program", lambda c: program_service.end_program(c, program_id, end_date))

    def resume_program(self, program_id: str) -> dict[str, Any]:
        return self._run("resume_program", lambda c: program_service.resume_program(c, program_id))

    def delete_program(self, program_id: str) -> dict[str, Any]:
        return self._run("delete_program", lambda c: program_service.delete_program(c, program_id))

    def create_special(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._run("create_special", lambda c: program_service.create_special(c, payload))

    # ── 편성표 ────────────────────────────────────
    def get_month(self, year: int, month: int) -> dict[str, Any]:
        return self._run("get_month", lambda c: schedule_service.get_month(c, year, month))

    def generate_month(self, year: int, month: int, scope: str,
                       overwrite_manual: bool = False) -> dict[str, Any]:
        """scope: first_week(첫 주 불러오기) | rest(월단위 생성) | all"""
        return self._run("generate_month", lambda c: schedule_service.generate(
            c, year, month, scope, bool(overwrite_manual)))

    # ── 칸 편집 ───────────────────────────────────
    def get_cell(self, date: str, hour: int) -> dict[str, Any]:
        return self._run("get_cell", lambda c: cell_edit.get_cell(c, date, hour))

    def cell_set_kind(self, date: str, hour: int, kind: str, scope: str = "once") -> dict[str, Any]:
        return self._run("cell_set_kind", lambda c: cell_edit.set_kind(c, date, hour, kind, scope))

    def cell_cancel(self, date: str, hour: int, mode: str, reason: str = "") -> dict[str, Any]:
        return self._run("cell_cancel", lambda c: cell_edit.cancel(c, date, hour, mode, reason))

    def cell_replace(self, date: str, hour: int, program_id: str, kind: str, scope: str = "once") -> dict[str, Any]:
        return self._run("cell_replace", lambda c: cell_edit.replace(c, date, hour, program_id, kind, scope))

    def cell_special(self, date: str, hour: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._run("cell_special", lambda c: cell_edit.put_special(c, date, hour, payload or {}))

    def cell_override(self, date: str, hour: int, episode: Any) -> dict[str, Any]:
        return self._run("cell_override", lambda c: cell_edit.set_override(c, date, hour, episode))

    def cell_actual(self, date: str, hour: int, note: str) -> dict[str, Any]:
        return self._run("cell_actual", lambda c: cell_edit.set_actual(c, date, hour, note))

    def cell_prep(self, date: str, hour: int, status: str) -> dict[str, Any]:
        return self._run("cell_prep", lambda c: cell_edit.set_prep(c, date, hour, status))

    def cell_revert(self, date: str, hour: int) -> dict[str, Any]:
        return self._run("cell_revert", lambda c: cell_edit.revert(c, date, hour))

    def undo(self) -> dict[str, Any]:
        """Ctrl+Z: 가장 최근 작업을 되돌린다 (이번 실행 동안 한 작업만)."""
        if not self._undo:
            return {"ok": False, "errors": ["되돌릴 작업이 없습니다."], "can_undo": False}
        record = self._undo.pop()
        result = self._run("undo", lambda c: cell_edit.undo(c, record))
        if not result.get("ok"):
            self._undo.append(record)
            result["can_undo"] = True
        return result

    def list_change_log(self, limit: int = 200) -> dict[str, Any]:
        return self._run("list_change_log", lambda c: {
            "ok": True, "items": change_log_repo.recent(c, max(1, min(int(limit), 1000)))})

    # ── 월 상태 ───────────────────────────────────
    def month_status(self, year: int, month: int, action: str, reason: str = "") -> dict[str, Any]:
        """action: confirm(확정) | reopen(확정 취소) | close(마감) | unlock(잠금 해제, 사유 필수)"""
        return self._run("month_status", lambda c: month_status.change(c, year, month, action, reason))

    # ── 엑셀 ──────────────────────────────────────
    def _window(self):  # type: ignore[no-untyped-def]
        import webview
        return webview.windows[0] if webview.windows else None

    def excel_pick_file(self) -> dict[str, Any]:
        """가져올 엑셀 파일 고르기 (열기 창)."""
        import webview
        win = self._window()
        if win is None:
            return {"ok": False, "errors": ["파일 선택 창을 열 수 없습니다."]}
        picked = win.create_file_dialog(webview.OPEN_DIALOG, file_types=("엑셀 파일 (*.xlsx;*.xlsm)",))
        return {"ok": True, "path": picked[0] if picked else None}

    def excel_analyze(self, path: str) -> dict[str, Any]:
        return self._run("excel_analyze", lambda c: excel_service.analyze(c, path))

    def excel_import(self, path: str, titles: list[str], mapping: dict[str, Any], overwrite: bool = True) -> dict[str, Any]:
        """가져오기 전에 DB를 백업한다 (되돌리기 대신 백업으로 복원)."""
        try:
            backup = backup_db(self._cfg.db_path, self._cfg.backup_dir, reason="before-import")
        except Exception:
            log.exception("가져오기 전 백업 실패")
            return {"ok": False, "errors": ["가져오기 전 백업을 만들지 못해 중단했습니다. 백업 폴더를 확인해 주세요."]}
        result = self._run("excel_import", lambda c: excel_service.run_import(c, path, titles or [], mapping or {}, bool(overwrite)))
        if result.get("ok") and backup:
            result["backup"] = str(backup)
        return result

    def excel_export(self, year: int, month: int) -> dict[str, Any]:
        """그 달 편성표를 엑셀로 저장 (저장 창). 수식 없이 글자만."""
        import webview
        win = self._window()
        if win is None:
            return {"ok": False, "errors": ["저장 창을 열 수 없습니다."]}
        name = f"SoneFM편성표_{int(year)}년{int(month):02d}월.xlsx"
        docs = Path(self._cfg.db_path).parent.parent
        picked = win.create_file_dialog(webview.SAVE_DIALOG, directory=str(docs), save_filename=name,
                                        file_types=("엑셀 파일 (*.xlsx)",))
        if not picked:
            return {"ok": True, "cancelled": True}
        path = picked if isinstance(picked, str) else picked[0]
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        return self._run("excel_export", lambda c: excel_service.export_months(c, [(int(year), int(month))], path))
