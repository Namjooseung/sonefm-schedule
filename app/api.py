"""화면(js_api)에 노출하는 함수들. 얇게 유지하고 실제 일은 services/domain/repository에 맡긴다.

모든 함수는 예외를 밖으로 던지지 않는다. 예상 못 한 오류는 로그에 남기고
{"ok": False, "errors": ["...한국어 안내..."]} 를 돌려준다.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from app import APP_VERSION
from app.config import AppConfig
from app.db.connection import open_db
from app.domain import programs as program_rules
from app.repository import meta_repo
from app.services import programs as program_service

log = logging.getLogger("sonefm.api")

_UNEXPECTED = "처리 중 문제가 생겼습니다. 다시 시도해 주세요. 계속되면 로그 파일을 개발자에게 보내 주세요."


class Api:
    def __init__(self, cfg: AppConfig) -> None:
        # pywebview는 밑줄로 시작하는 속성을 화면에 노출하지 않는다
        self._cfg = cfg

    def _run(self, name: str, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        """DB 연결 하나 = 트랜잭션 하나. 실패 결과({"ok": False})면 쓰기를 되돌린다."""
        try:
            with open_db(self._cfg.db_path) as conn:
                result = fn(conn)
                if isinstance(result, dict) and result.get("ok") is False:
                    conn.rollback()
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
