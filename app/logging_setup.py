"""로그 파일 설정. 상세 오류는 Documents\\SoneFM\\logs\\app.log 에 남긴다."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import logs_dir


def setup_logging() -> logging.Logger:
    folder = logs_dir()
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        folder / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:  # 창 모드 exe에서는 stderr가 없을 수 있다
        root.addHandler(logging.StreamHandler())

    def _excepthook(exc_type, exc, tb):  # type: ignore[no-untyped-def]
        logging.getLogger("sonefm").critical("처리되지 않은 오류", exc_info=(exc_type, exc, tb))

    sys.excepthook = _excepthook
    return logging.getLogger("sonefm")
