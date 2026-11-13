"""경로와 부트스트랩 설정.

DB 위치처럼 DB를 열기 *전에* 알아야 하는 값만 여기(config.json)에 둔다.
운영 기준값(비율, 고정 편성, 경고 횟수 등)은 DB의 settings 테이블에 둔다.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# 테스트 등에서 데이터 루트를 바꾸고 싶을 때 쓰는 환경변수
HOME_ENV = "SONEFM_HOME"
DEFAULT_BACKUP_KEEP = 30


def data_root() -> Path:
    """앱 데이터 루트. 기본 %USERPROFILE%\\Documents\\SoneFM."""
    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override)
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Documents" / "SoneFM"


def config_path() -> Path:
    return data_root() / "config.json"


def logs_dir() -> Path:
    return data_root() / "logs"


@dataclass
class AppConfig:
    db_path: str
    backup_dir: str
    backup_keep: int = DEFAULT_BACKUP_KEEP


def default_config() -> AppConfig:
    root = data_root()
    return AppConfig(
        db_path=str(root / "data" / "schedule.db"),
        backup_dir=str(root / "backups"),
    )


def load_config() -> AppConfig:
    """config.json을 읽는다. 없으면 기본값으로 만들어 저장한다."""
    path = config_path()
    cfg = default_config()
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in raw.items() if k in asdict(cfg)}
        cfg = AppConfig(**{**asdict(cfg), **known})
    save_config(cfg)
    return cfg


def save_config(cfg: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")


def resource_dir() -> Path:
    """앱에 함께 묶여 배포되는 파일(마이그레이션, 화면)의 기준 폴더.

    PyInstaller로 묶였으면 압축 해제 폴더, 아니면 저장소 루트.
    """
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parent.parent


def frontend_index() -> Path:
    return resource_dir() / "frontend" / "dist" / "index.html"


def migrations_dir() -> Path:
    return resource_dir() / "app" / "db" / "migrations"


def seed_db_path() -> Path:
    """저장소에 함께 들어 있는 기본 데이터(씨앗 DB). 새 PC에서 DB가 없을 때 이것으로 시작한다."""
    return resource_dir() / "seed" / "schedule_seed.db"
