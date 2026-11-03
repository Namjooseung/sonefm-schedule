"""화면(js_api)에 노출하는 함수들. 얇게 유지하고 실제 일은 repository/domain에 맡긴다."""
from __future__ import annotations

import logging
from typing import Any

from app import APP_VERSION
from app.config import AppConfig
from app.db.connection import open_db
from app.repository import meta_repo

log = logging.getLogger("sonefm.api")


class Api:
    def __init__(self, cfg: AppConfig) -> None:
        # pywebview는 밑줄로 시작하는 속성을 화면에 노출하지 않는다
        self._cfg = cfg

    def ping(self) -> dict[str, Any]:
        """연결 확인용 왕복 호출."""
        try:
            with open_db(self._cfg.db_path) as conn:
                version = meta_repo.schema_version(conn)
            log.info("ping 응답: 스키마 v%d", version)
            return {
                "ok": True,
                "message": "정상 연결",
                "app_version": APP_VERSION,
                "db_path": self._cfg.db_path,
                "schema_version": version,
            }
        except Exception:
            log.exception("ping 실패")
            return {"ok": False, "message": "데이터 파일을 열지 못했습니다. 로그를 확인해 주세요."}
