from __future__ import annotations

import os
from pathlib import Path


def get_project_root() -> Path:
    """
    프로젝트 루트 디렉토리 반환.
    - 이 파일 위치: <root>/app/utils/paths.py
    """
    return Path(__file__).resolve().parents[2]


def get_config_path() -> Path:
    """크롤러 설정 파일 경로."""
    return get_project_root() / "crawler_config.json"


def get_logs_dir() -> Path:
    """로그 폴더 경로."""
    return get_project_root() / "logs"


def resolve_db_path(config_db_path: str | None = None) -> Path:
    """
    SQLite DB 경로 결정 규칙 (우선순위):
    1) 환경변수 `CAFESCRAPER_DB_PATH` (절대경로 권장)
    2) config_db_path (UI/로컬 설정에 저장된 값)
    3) 기본값: <project_root>/cafe_data.db
    """
    env_path = (os.getenv("CAFESCRAPER_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if config_db_path and str(config_db_path).strip():
        p = Path(str(config_db_path)).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = (get_project_root() / "data" / "cafe_data.db").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def resolve_event_db_path(config_event_db_path: str | None = None) -> Path:
    """
    이벤트/단기 작업용 SQLite DB 경로 결정 규칙 (우선순위):
    1) 환경변수 `CAFESCRAPER_EVENT_DB_PATH`
    2) config_event_db_path (설정에 저장된 값)
    3) 기본값: <project_root>/event_comments.db
    """
    env_path = (os.getenv("CAFESCRAPER_EVENT_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if config_event_db_path and str(config_event_db_path).strip():
        p = Path(str(config_event_db_path)).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = (get_project_root() / "data" / "event_comments.db").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

