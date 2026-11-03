"""repository 공통 도우미."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    """UTC ISO8601 (예: 2026-11-03T06:19:08Z). 스키마 DEFAULT와 같은 형식."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
