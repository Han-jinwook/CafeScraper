from __future__ import annotations

import os
from pathlib import Path


def get_project_root() -> Path:
    """
    프로젝트 루트 디렉토리 반환.
    - 소스 실행: 이 파일 위치 <root>/app/utils/paths.py → parents[2]
    - PyInstaller: CWD (exe와 같은 폴더, run_app.py에서 os.chdir 설정)
    """
    import sys
    if getattr(sys, "frozen", False):
        return Path.cwd()
    return Path(__file__).resolve().parents[2]


def get_user_data_dir() -> Path:
    """
    사용자 데이터 저장 루트.
    우선순위: CAFESCRAPER_DATA_DIR(환경변수) → %APPDATA%/CafeScraper → ~/.CafeScraper
    """
    env_dir = (os.getenv("CAFESCRAPER_DATA_DIR") or "").strip()
    if env_dir:
        root = Path(env_dir).expanduser()
    else:
        appdata = os.getenv("APPDATA")
        if appdata:
            root = Path(appdata) / "CafeScraper"
        else:
            root = Path.home() / ".CafeScraper"
    root.mkdir(parents=True, exist_ok=True)
    
    # 레거시 데이터가 프로젝트 루트(CWD 등)에 있으면 새 APPDATA 위치로 자동 마이그레이션
    try:
        _migrate_legacy_data(get_project_root(), root)
    except Exception:
        pass
        
    return root


def _migrate_legacy_data(legacy_root: Path, new_root: Path) -> None:
    import shutil
    if legacy_root.resolve() == new_root.resolve():
        return
        
    # 파일 마이그레이션
    for filename in ["crawler_config.json", "comment_templates.json"]:
        src = legacy_root / filename
        dst = new_root / filename
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
                
    # 디렉토리 마이그레이션
    for dirname in ["logs", "data", "sessions", "snapshots", "outputs"]:
        src = legacy_root / dirname
        dst = new_root / dirname
        if src.exists() and src.is_dir() and not dst.exists():
            try:
                shutil.copytree(src, dst, dirs_exist_ok=True)
            except Exception:
                pass


def get_config_path() -> Path:
    """크롤러 설정 파일 경로."""
    return get_user_data_dir() / "crawler_config.json"


def get_comment_templates_path() -> Path:
    """자동댓글러 저장 템플릿 JSON (exe/프로젝트 루트와 동일 규칙 — crawler_config 옆)."""
    return get_user_data_dir() / "comment_templates.json"


def get_logs_dir() -> Path:
    """로그 폴더 경로."""
    return get_user_data_dir() / "logs"


def _safe_mkdir(p: Path) -> Path:
    """디렉토리 생성 시도. 실패하면 CWD/data 폴백."""
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    except (PermissionError, OSError):
        fallback = get_user_data_dir() / "data" / p.name
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def resolve_db_path(config_db_path: str | None = None) -> Path:
    """
    카페 메인 수집 전용 SQLite DB (이벤트·논문·자동댓글러와 분리).
    우선순위:
    1) 환경변수 `CAFESCRAPER_DB_PATH`
    2) config_db_path (존재 가능한 경로만)
    3) 기본값: data/cafe_data.db
    """
    env_path = (os.getenv("CAFESCRAPER_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        return _safe_mkdir(p)

    if config_db_path and str(config_db_path).strip():
        p = Path(str(config_db_path)).expanduser().resolve()
        return _safe_mkdir(p)

    p = (get_user_data_dir() / "data" / "cafe_data.db").resolve()
    return _safe_mkdir(p)


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
        return _safe_mkdir(p)

    if config_event_db_path and str(config_event_db_path).strip():
        p = Path(str(config_event_db_path)).expanduser().resolve()
        return _safe_mkdir(p)

    p = (get_user_data_dir() / "data" / "event_analysis.db").resolve()
    return _safe_mkdir(p)


def resolve_commenter_db_path(config_commenter_db_path: str | None = None) -> Path:
    """
    자동 댓글러 전용 SQLite DB.
    우선순위: `CAFESCRAPER_COMMENTER_DB_PATH` → config → data/auto_commenter.db
    """
    env_path = (os.getenv("CAFESCRAPER_COMMENTER_DB_PATH") or "").strip()
    if env_path:
        p = Path(env_path).expanduser().resolve()
        return _safe_mkdir(p)

    if config_commenter_db_path and str(config_commenter_db_path).strip():
        p = Path(str(config_commenter_db_path)).expanduser().resolve()
        return _safe_mkdir(p)

    p = (get_user_data_dir() / "data" / "auto_commenter.db").resolve()
    return _safe_mkdir(p)
