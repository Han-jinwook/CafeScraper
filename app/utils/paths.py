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
    
    # 0. APPDATA 내부 자체 마이그레이션 (crawler_config.json -> user_settings.json)
    appdata_old_cfg = new_root / "crawler_config.json"
    appdata_new_cfg = new_root / "user_settings.json"
    if appdata_old_cfg.exists() and not appdata_new_cfg.exists():
        try:
            shutil.copy2(appdata_old_cfg, appdata_new_cfg)
        except Exception:
            pass

    if legacy_root.resolve() == new_root.resolve():
        return
        
    # 1. crawler_config.json (레거시 루트) -> user_settings.json (APPDATA)
    legacy_old_cfg = legacy_root / "crawler_config.json"
    if legacy_old_cfg.exists() and not appdata_new_cfg.exists():
        try:
            shutil.copy2(legacy_old_cfg, appdata_new_cfg)
        except Exception:
            pass

    # 2. user_settings.json (레거시 루트) -> user_settings.json (APPDATA)
    legacy_new_cfg = legacy_root / "user_settings.json"
    if legacy_new_cfg.exists() and not appdata_new_cfg.exists():
        try:
            shutil.copy2(legacy_new_cfg, appdata_new_cfg)
        except Exception:
            pass

    # 3. comment_templates.json 마이그레이션
    src_tpl = legacy_root / "comment_templates.json"
    dst_tpl = new_root / "comment_templates.json"
    if src_tpl.exists() and not dst_tpl.exists():
        try:
            shutil.copy2(src_tpl, dst_tpl)
        except Exception:
            pass
                
    # 4. 디렉토리 마이그레이션
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
    return get_user_data_dir() / "user_settings.json"


def get_comment_templates_path() -> Path:
    """자동댓글러 저장 템플릿 JSON (exe/프로젝트 루트와 동일 규칙 — crawler_config 옆)."""
    return get_user_data_dir() / "comment_templates.json"


def get_zero_maintenance_data_dir() -> Path:
    """Zero-maintenance Data Policy에 따른 최상위 고정 데이터 저장 경로."""
    p = Path(os.path.expanduser('~\\Documents\\MarketingMonster\\CafeScraper'))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_zero_maintenance_db_dir() -> Path:
    """Zero-maintenance Data Policy에 따른 DB 저장 경로 (DB 폴더 숨김)."""
    p = get_zero_maintenance_data_dir() / "DB"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_zero_maintenance_logs_dir() -> Path:
    """Zero-maintenance Data Policy에 따른 로그 저장 경로 (Logs 폴더 숨김)."""
    p = get_zero_maintenance_data_dir() / "Logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir() -> Path:
    """로그 폴더 경로 (Zero-maintenance Logs 디렉토리 반환)."""
    return get_zero_maintenance_logs_dir()


def get_latest_db_path(prefix: str) -> Path:
    """
    해당 prefix를 가진 가장 최근의 DB 경로를 반환합니다.
    존재하는 파일이 없을 경우 기본 경로를 반환합니다.
    """
    db_dir = get_zero_maintenance_db_dir()
    db_files = list(db_dir.glob(f"{prefix}_*.db"))
    if not db_files:
        return db_dir / f"{prefix}.db"
    db_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return db_files[0]


def generate_new_db_path(prefix: str) -> Path:
    """
    매 작업 실행 시 호출되어 의미있는 식별자(카페명_시작일~종료일) 및 타임스탬프가 포함된 새 DB 파일 경로를 생성합니다.
    """
    from datetime import datetime
    import json
    import re
    
    db_dir = get_zero_maintenance_db_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    # Load config to get meaningful identifiers
    config = {}
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    def sanitize_filename(name: str) -> str:
        name = re.sub(r'[\\/*?:"<>|]', "", name)
        return name.strip()

    suffix = ""
    if prefix == "cafe_data":
        cafe_name = str(config.get("cafe_name") or "").strip()
        start_date = str(config.get("start_date") or "").strip()
        end_date = str(config.get("end_date") or "").strip()
        if cafe_name and start_date and end_date:
            d1 = start_date.replace("-", "")
            d2 = end_date.replace("-", "")
            suffix = sanitize_filename(f"{cafe_name}_{d1}~{d2}")
    elif prefix == "event_analysis":
        event_cafe_name = str(config.get("event_cafe_name") or "").strip()
        event_start_date = str(config.get("event_start_date") or "").strip()
        event_end_date = str(config.get("event_end_date") or "").strip()
        if event_cafe_name and event_start_date and event_end_date:
            d1 = event_start_date.replace("-", "")
            d2 = event_end_date.replace("-", "")
            suffix = sanitize_filename(f"{event_cafe_name}_{d1}~{d2}")
    elif prefix == "auto_commenter":
        commenter_cafe_name = str(config.get("commenter_cafe_name") or "").strip()
        commenter_start_date = str(config.get("commenter_target_start_date") or "").strip()
        commenter_end_date = str(config.get("commenter_target_end_date") or "").strip()
        if commenter_cafe_name and commenter_start_date and commenter_end_date:
            d1 = commenter_start_date.replace("-", "")
            d2 = commenter_end_date.replace("-", "")
            suffix = sanitize_filename(f"{commenter_cafe_name}_{d1}~{d2}")

    if suffix:
        return db_dir / f"{prefix}_{suffix}_{timestamp}.db"
    else:
        return db_dir / f"{prefix}_{timestamp}.db"


def _resolve_dynamic_db_path(prefix: str, session_key: str) -> Path:
    # 1. Streamlit 세션 내 활성 경로 확인
    try:
        import streamlit as st
        if session_key in st.session_state and st.session_state[session_key]:
            active_path = Path(st.session_state[session_key]).resolve()
            active_path.parent.mkdir(parents=True, exist_ok=True)
            return active_path
    except Exception:
        pass

    # 2. 대기 시, 가장 최근 수정된 DB 경로 선택
    target_path = get_latest_db_path(prefix).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return target_path


def resolve_db_path(config_db_path: str | None = None) -> Path:
    """
    카페 메인 수집 SQLite DB 경로 동적 해결.
    Zero-maintenance Data Policy에 따라 무조건 고정 경로 및 최신 DB를 사용합니다.
    """
    return _resolve_dynamic_db_path("cafe_data", "active_db_path_main")


def resolve_event_db_path(config_event_db_path: str | None = None) -> Path:
    """
    이벤트 댓글 분석 SQLite DB 경로 동적 해결.
    """
    return _resolve_dynamic_db_path("event_analysis", "active_db_path_event")


def resolve_commenter_db_path(config_commenter_db_path: str | None = None) -> Path:
    """
    자동 댓글러 SQLite DB 경로 동적 해결.
    """
    return _resolve_dynamic_db_path("auto_commenter", "active_db_path_commenter")


def export_all_latest_dbs_to_csv() -> None:
    """
    가장 최근 누적된 DB 파일들을 읽어서 최상위 문서 폴더에 CSV 결과물을 즉시 생성(Export)합니다.
    """
    import sqlite3
    import pandas as pd
    from datetime import datetime
    import json

    data_dir = get_zero_maintenance_data_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Load config to get meaningful identifiers (cafe_name, start_date, end_date)
    config = {}
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    def sanitize_filename(name: str) -> str:
        import re
        name = re.sub(r'[\\/*?:"<>|]', "", name)
        return name.strip()

    # 1. 카페 메인 수집 DB
    latest_main = get_latest_db_path("cafe_data")
    if latest_main.exists():
        try:
            conn = sqlite3.connect(latest_main)
            df_posts = pd.read_sql_query("SELECT * FROM posts", conn)
            df_comments = pd.read_sql_query("SELECT * FROM comments", conn)
            conn.close()

            cafe_name = str(config.get("cafe_name") or "").strip()
            start_date = str(config.get("start_date") or "").strip()
            end_date = str(config.get("end_date") or "").strip()
            
            if cafe_name and start_date and end_date:
                d1 = start_date.replace("-", "")
                d2 = end_date.replace("-", "")
                main_suffix = sanitize_filename(f"{cafe_name}_{d1}~{d2}")
            else:
                main_suffix = timestamp

            if not df_posts.empty:
                df_posts.to_csv(data_dir / f"카페수집_게시글_{main_suffix}.csv", index=False, encoding="utf-8-sig")
            if not df_comments.empty:
                df_comments.to_csv(data_dir / f"카페수집_댓글_{main_suffix}.csv", index=False, encoding="utf-8-sig")
        except Exception:
            pass

    # 2. 이벤트 수집 DB
    latest_event = get_latest_db_path("event_analysis")
    if latest_event.exists():
        try:
            conn = sqlite3.connect(latest_event)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            event_cafe_name = str(config.get("event_cafe_name") or "").strip()
            event_start_date = str(config.get("event_start_date") or "").strip()
            event_end_date = str(config.get("event_end_date") or "").strip()

            if event_cafe_name and event_start_date and event_end_date:
                d1 = event_start_date.replace("-", "")
                d2 = event_end_date.replace("-", "")
                event_suffix = sanitize_filename(f"{event_cafe_name}_{d1}~{d2}")
            else:
                event_suffix = timestamp

            for table in tables:
                if table.startswith("sqlite_"):
                    continue
                df_table = pd.read_sql_query(f"SELECT * FROM [{table}]", conn)
                if not df_table.empty:
                    table_name_kr = table
                    if table == "event_comments":
                        table_name_kr = "이벤트수집_댓글"
                    elif table == "event_posts":
                        table_name_kr = "이벤트수집_게시글"
                    elif table == "event_post_analysis":
                        table_name_kr = "이벤트수집_게시글분석"
                    elif table == "event_mentor_visits":
                        table_name_kr = "이벤트수집_방문내역"
                    df_table.to_csv(data_dir / f"{table_name_kr}_{event_suffix}.csv", index=False, encoding="utf-8-sig")
            conn.close()
        except Exception:
            pass

    # 3. 자동 댓글러 DB
    latest_commenter = get_latest_db_path("auto_commenter")
    if latest_commenter.exists():
        try:
            conn = sqlite3.connect(latest_commenter)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            commenter_cafe_name = str(config.get("commenter_cafe_name") or "").strip()
            commenter_start_date = str(config.get("commenter_target_start_date") or "").strip()
            commenter_end_date = str(config.get("commenter_target_end_date") or "").strip()

            if commenter_cafe_name and commenter_start_date and commenter_end_date:
                d1 = commenter_start_date.replace("-", "")
                d2 = commenter_end_date.replace("-", "")
                commenter_suffix = sanitize_filename(f"{commenter_cafe_name}_{d1}~{d2}")
            else:
                commenter_suffix = timestamp

            for table in tables:
                if table.startswith("sqlite_"):
                    continue
                df_table = pd.read_sql_query(f"SELECT * FROM [{table}]", conn)
                if not df_table.empty:
                    table_name_kr = table
                    if table == "event_comments":
                        table_name_kr = "자동댓글_댓글"
                    elif table == "event_posts":
                        table_name_kr = "자동댓글_게시글"
                    elif table == "event_post_analysis":
                        table_name_kr = "자동댓글_게시글분석"
                    elif table == "event_mentor_visits":
                        table_name_kr = "자동댓글_방문내역"
                    elif table == "commenter_targets":
                        table_name_kr = "자동댓글_대상글"
                    df_table.to_csv(data_dir / f"{table_name_kr}_{commenter_suffix}.csv", index=False, encoding="utf-8-sig")
            conn.close()
        except Exception:
            pass


def open_zero_maintenance_data_dir() -> None:
    """윈도우 파일 탐색기를 열어 최상위 폴더를 화면에 띄워줍니다."""
    import os
    data_dir = get_zero_maintenance_data_dir()
    try:
        os.startfile(str(data_dir))
    except Exception:
        pass
