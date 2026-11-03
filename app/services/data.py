"""데이터 파일 관리: 백업·복원, 데이터 내보내기/가져오기(파일 하나), DB 위치 바꾸기, 백업 설정.

DB 연결은 호출마다 열고 닫으므로(앱 전체에 열린 연결이 없음) 파일 교체가 안전하다.
복사·복원은 SQLite 백업 API로 해서 쓰는 도중이어도 일관된 사본이 된다.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.backup import _PATTERN, backup_db, prune_backups
from app.config import AppConfig, migrations_dir, save_config
from app.db.connection import connect
from app.db.migrate import apply_migrations, discover

log = logging.getLogger("sonefm.data")
Result = dict[str, Any]
DB_NAME = "schedule.db"
KEEP_MIN, KEEP_MAX = 3, 365


def _fail(*msgs: str) -> Result:
    return {"ok": False, "errors": list(msgs)}


def _copy_db(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    s = sqlite3.connect(src)
    d = sqlite3.connect(dest)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()


def check_db_file(path: str | Path) -> str | None:
    """이 앱의 데이터 파일인지 확인. 문제가 있으면 사용자용 문구."""
    p = Path(path)
    if not p.is_file():
        return "파일을 찾지 못했습니다."
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return "SoneFM 편성표 데이터 파일이 아니거나 손상된 파일입니다."
    if not {"programs", "schedule_cells", "settings"} <= tables:
        return "SoneFM 편성표 데이터 파일이 아닙니다."
    if version > len(discover(migrations_dir())):
        return "더 새 버전의 프로그램에서 만든 데이터 파일입니다. 프로그램을 먼저 업데이트해 주세요."
    return None


def _migrate(path: str | Path) -> None:
    conn = connect(path)
    try:
        apply_migrations(conn, migrations_dir())
    finally:
        conn.close()


# ── 백업 ──────────────────────────────────────────

def list_backups(cfg: AppConfig, limit: int = 50) -> list[dict[str, Any]]:
    folder = Path(cfg.backup_dir)
    if not folder.exists():
        return []
    files = sorted((p for p in folder.iterdir() if _PATTERN.match(p.name)), reverse=True)[:limit]
    out = []
    for p in files:
        st = p.stat()
        out.append({"name": p.name, "path": str(p), "size_kb": round(st.st_size / 1024),
                    "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")})
    return out


def backup_now(cfg: AppConfig) -> Result:
    made = backup_db(cfg.db_path, cfg.backup_dir, reason="manual")
    prune_backups(cfg.backup_dir, cfg.backup_keep)
    if made is None:
        return _fail("백업할 데이터 파일이 없습니다.")
    return {"ok": True, "path": str(made), "message": f"백업했습니다: {made.name}"}


def restore(cfg: AppConfig, source: str) -> Result:
    """백업(또는 다른 데이터 파일)으로 지금 데이터를 바꾼다. 바꾸기 전 상태도 백업한다."""
    problem = check_db_file(source)
    if problem:
        return _fail(problem)
    src = Path(source)
    if src.resolve() == Path(cfg.db_path).resolve():
        return _fail("지금 쓰고 있는 데이터 파일입니다. 다른 파일을 골라 주세요.")
    safety = backup_db(cfg.db_path, cfg.backup_dir, reason="before-restore")
    _copy_db(src, Path(cfg.db_path))
    _migrate(cfg.db_path)
    log.info("복원: %s → %s (복원 전 백업 %s)", src, cfg.db_path, safety)
    return {"ok": True, "message": f"{src.name}의 데이터로 바꿨습니다.",
            "safety_backup": str(safety) if safety else None}


def export_data(cfg: AppConfig, dest: str) -> Result:
    """데이터 내보내기: 지금 데이터를 파일 하나로 (다른 PC로 옮길 때)."""
    d = Path(dest)
    if d.suffix.lower() != ".db":
        d = d.with_suffix(".db")
    if d.resolve() == Path(cfg.db_path).resolve():
        return _fail("지금 쓰고 있는 데이터 파일과 같은 위치입니다. 다른 이름이나 폴더를 골라 주세요.")
    try:
        _copy_db(Path(cfg.db_path), d)
    except (PermissionError, sqlite3.OperationalError):
        return _fail("그 위치에 저장할 수 없습니다. 다른 폴더를 골라 주세요.")
    return {"ok": True, "path": str(d), "message": f"데이터를 내보냈습니다: {d.name}"}


# ── DB 위치 ───────────────────────────────────────

def change_db_location(cfg: AppConfig, folder: str, mode: str = "copy") -> Result:
    """mode: copy(지금 데이터를 새 폴더로 복사해서 쓰기) | use_existing(새 폴더에 있는 데이터 파일 쓰기)."""
    if mode not in ("copy", "use_existing"):
        return _fail("요청이 올바르지 않습니다.")
    target_dir = Path(folder or "")
    if not str(folder or "").strip() or not target_dir.exists() or not target_dir.is_dir():
        return _fail("폴더를 골라 주세요.")
    new_path = target_dir / DB_NAME
    old_path = Path(cfg.db_path)
    if new_path.resolve() == old_path.resolve():
        return _fail("지금과 같은 위치입니다.")
    if mode == "copy":
        if new_path.exists():
            return _fail(f"그 폴더에 이미 {DB_NAME}이(가) 있습니다. 그 파일을 쓰려면 '그 폴더의 데이터 쓰기'를 고르세요.")
        try:
            _copy_db(old_path, new_path)
        except (PermissionError, sqlite3.OperationalError):
            return _fail("그 폴더에 쓸 수 없습니다. 다른 폴더를 골라 주세요.")
    else:
        problem = check_db_file(new_path)
        if problem:
            return _fail(f"그 폴더의 {DB_NAME}: {problem}")
        backup_db(old_path, cfg.backup_dir, reason="before-move")
    _migrate(new_path)
    cfg.db_path = str(new_path)
    save_config(cfg)
    log.info("DB 위치 변경: %s → %s (%s)", old_path, new_path, mode)
    return {"ok": True, "db_path": cfg.db_path,
            "message": f"데이터 위치를 바꿨습니다: {new_path}"
                       + (" (예전 파일은 그대로 남아 있습니다)" if mode == "copy" else "")}


def set_backup_options(cfg: AppConfig, folder: str | None, keep: Any) -> Result:
    try:
        k = int(keep)
        if not KEEP_MIN <= k <= KEEP_MAX:
            raise ValueError
    except (TypeError, ValueError):
        return _fail(f"보관 개수는 {KEEP_MIN}~{KEEP_MAX} 사이 숫자로 입력해 주세요.")
    new_dir = Path(folder) if folder else Path(cfg.backup_dir)
    try:
        new_dir.mkdir(parents=True, exist_ok=True)
        probe = new_dir / ".sonefm_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return _fail("그 폴더에 백업을 저장할 수 없습니다. 다른 폴더를 골라 주세요.")
    cfg.backup_dir, cfg.backup_keep = str(new_dir), k
    save_config(cfg)
    prune_backups(cfg.backup_dir, cfg.backup_keep)
    return {"ok": True, "backup_dir": cfg.backup_dir, "backup_keep": cfg.backup_keep,
            "message": "백업 설정을 저장했습니다."}
