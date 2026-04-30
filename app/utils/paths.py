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
    카페 메인 수집 전용 SQLite DB (이벤트·논문·자동댓글러와 분리).
    우선순위:
    1) 환경변수 `CAFESCRAPER_DB_PATH`
    2) config_db_path
    3) 기본값: data/cafe_data.db
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
    이벤트 댓글 분석 전용 SQLite DB (카페 수집·논문·자동댓글러와 파일 분리).
    우선순위:
    1) 환경변수 `CAFESCRAPER_EVENT_DB_PATH`
    2) config_event_db_path
    3) 기본값: data/event_analysis.db
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

    p = (get_project_root() / "data" / "event_analysis.db").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def resolve_paper_db_path(config_paper_db_path: str | None = None) -> Path:
    """
    논문(위키 등) 수집 전용 SQLite DB.
    우선순위: `CAFESCRAPER_PAPER_DB_PATH` → config → data/paper_collection.db
    """
    env_path = (os.getenv("CAFESCRAPER_PAPER_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if config_paper_db_path and str(config_paper_db_path).strip():
        p = Path(str(config_paper_db_path)).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = (get_project_root() / "data" / "paper_collection.db").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def resolve_commenter_db_path(config_commenter_db_path: str | None = None) -> Path:
    """
    자동 댓글러 전용 SQLite DB.
    우선순위: `CAFESCRAPER_COMMENTER_DB_PATH` → config → data/auto_commenter.db
    """
    env_path = (os.getenv("CAFESCRAPER_COMMENTER_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if config_commenter_db_path and str(config_commenter_db_path).strip():
        p = Path(str(config_commenter_db_path)).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    p = (get_project_root() / "data" / "auto_commenter.db").resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

