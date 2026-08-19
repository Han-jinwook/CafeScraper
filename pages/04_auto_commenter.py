import streamlit as st
import pandas as pd
import os
import time
import random
import json
import re
import traceback
import html
import uuid
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from selenium.webdriver.common.by import By

from app.products.commenter.bot import (
    NaverCafeCommenter,
    apply_comment_template_placeholders,
    sanitize_commenter_nickname,
)
from app.utils.paths import get_comment_templates_path, get_config_path, resolve_commenter_db_path
from app.utils.event_db import (
    clear_commenter_targets,
    get_commenter_targets_count,
    init_event_db,
    load_commenter_targets,
    replace_commenter_targets,
    update_commenter_target_comment_status,
)
from app.utils.streamlit_brand import render_logo_png
from app.utils.streamlit_input_history import inject_connect_history_suggestions
from app.utils.streamlit_top_nav import (
    inject_settings_three_cards_css,
    render_main_top_nav,
    render_settings_card_title,
)
from app.utils.naver_login import auto_login_naver_with_js

from app.utils.auth_helper import CafeMonsterAuthHelper
from app.utils.app_version import read_app_version
_APP_SEMVER = read_app_version()
st.set_page_config(
    page_title=f"카페 몬스터 [자동 댓글러] v{_APP_SEMVER}",
    layout="wide",
    initial_sidebar_state="collapsed",
)

@st.cache_resource
def get_commenter_collect_jobs():
    return {}

COMMENTER_COLLECT_JOBS = get_commenter_collect_jobs()

# Check background collection job status
if st.session_state.get("commenter_collecting", False):
    job_id = st.session_state.get("commenter_collect_job_id")
    if job_id and job_id in COMMENTER_COLLECT_JOBS:
        job = COMMENTER_COLLECT_JOBS[job_id]
        thread = job.get("thread")
        if thread and thread.is_alive():
            st.session_state.commenter_collect_progress = job.get("progress", 0.0)
            st.session_state.commenter_collect_status_text = job.get("status_text", "수집 시작 중…")
        else:
            # Thread finished
            df = job.get("result_df")
            if df is not None:
                st.session_state.target_df = df
                st.session_state.commenter_target_df_full = df.copy()
            
            # Transfer warnings/info/errors to streamlit
            if "info_msg" in job:
                st.session_state._commenter_collect_info_msg = job["info_msg"]
            if "warn_msg" in job:
                st.session_state._commenter_collect_warn_msg = job["warn_msg"]
            if "success_msg" in job:
                st.session_state._commenter_collect_success_msg = job["success_msg"]
            if "error_msg" in job:
                st.session_state._commenter_collect_error_msg = job["error_msg"]
                
            st.session_state.commenter_collecting = False
            st.session_state.commenter_collect_job_id = None
            st.rerun()

render_main_top_nav(active="commenter")

if st.session_state.pop("_commenter_finished_ok", False):
    st.success("댓글 일괄 작업이 끝났습니다. 아래 표·집계에 최종 결과가 반영되었습니다.")
    st.balloons()

# 메인 크롤링 구동 중에는 다른 메뉴 작업을 잠시 차단
if st.session_state.get("crawl_running", False):
    st.warning("메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

inject_settings_three_cards_css(key_basename="commenter_settings_card")

st.markdown(
    """
    <style>
    /* 자동댓글러: 본문 하단 여백 축소(스크롤 완화) */
    section.main > div.block-container {
        padding-bottom: 1.1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CONFIG_PATH = str(get_config_path())


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


def _sanitize_commenter_db_path_cfg(raw: str | None) -> str | None:
    """설정에 'D:\\...\\data\\file.db' 같은 예시 문자열이 들어 있으면 무시하고 기본 경로 규칙을 씀."""
    if raw is None:
        return None
    t = str(raw).strip().replace("…", ".").replace("`", "").strip()
    if not t:
        return None
    if "..." in t:
        return None
    return t


config = load_config()
_cfg_commenter_db = _sanitize_commenter_db_path_cfg(config.get("commenter_db_path"))
COMMENTER_DB_PATH = str(resolve_commenter_db_path(_cfg_commenter_db))
init_event_db(COMMENTER_DB_PATH)

# 댓글 간격: 30~120초 랜덤 (UI 입력 불필요, 고정 정책)
COMMENTER_GAP_MIN_SEC = 30
COMMENTER_GAP_MAX_SEC = 120
# 세션당 최대 댓글 수
COMMENTER_SESSION_LIMIT = 60
# 세션 간 휴식 시간(초) — 1시간
COMMENTER_SESSION_REST_SEC = 3600

# ----- 자동댓글러 전용 설정 키 (이벤트분석과 분리) -----
if "commenter" not in st.session_state:
    st.session_state.commenter = None
if "comment_logs" not in st.session_state:
    st.session_state.comment_logs = []
if "target_df" not in st.session_state:
    st.session_state.target_df = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "commenter_run_index" not in st.session_state:
    st.session_state.commenter_run_index = 0
if "commenter_stop_requested" not in st.session_state:
    st.session_state.commenter_stop_requested = False
if "commenter_collecting" not in st.session_state:
    st.session_state.commenter_collecting = False
if "commenter_target_df_full" not in st.session_state:
    st.session_state.commenter_target_df_full = None
if "commenter_collect_job_id" not in st.session_state:
    st.session_state.commenter_collect_job_id = None
if "commenter_collect_progress" not in st.session_state:
    st.session_state.commenter_collect_progress = 0.0
if "commenter_collect_status_text" not in st.session_state:
    st.session_state.commenter_collect_status_text = ""

if "commenter_cafe_name_input" not in st.session_state:
    st.session_state.commenter_cafe_name_input = str(config.get("commenter_cafe_name", "") or "")
if "commenter_cafe_url_input" not in st.session_state:
    st.session_state.commenter_cafe_url_input = str(config.get("commenter_cafe_url", "") or "")
if "commenter_extracted_boards" not in st.session_state or not st.session_state.commenter_extracted_boards:
    _cfg_boards = config.get("commenter_extracted_boards", [])
    if isinstance(_cfg_boards, list) and _cfg_boards:
        st.session_state.commenter_extracted_boards = _cfg_boards
    elif "commenter_extracted_boards" not in st.session_state:
        st.session_state.commenter_extracted_boards = []
if "commenter_selected_board_urls" not in st.session_state or not st.session_state.get(
    "commenter_selected_board_urls"
):
    _cfg_selected_urls = config.get("commenter_selected_board_urls", [])
    if isinstance(_cfg_selected_urls, list) and _cfg_selected_urls:
        st.session_state.commenter_selected_board_urls = [
            str(u).strip() for u in _cfg_selected_urls if str(u).strip()
        ]
    elif "commenter_selected_board_urls" not in st.session_state:
        st.session_state.commenter_selected_board_urls = [
            u.strip() for u in str(config.get("commenter_board_url", "") or "").splitlines() if u.strip()
        ]
if "commenter_selected_board_url" not in st.session_state or not st.session_state.get(
    "commenter_selected_board_url"
):
    _fallback_urls = st.session_state.get("commenter_selected_board_urls", []) or []
    st.session_state.commenter_selected_board_url = (
        _fallback_urls[0]
        if _fallback_urls
        else str(config.get("commenter_board_url", "") or "").strip()
    )
if "commenter_board_picker_version" not in st.session_state:
    st.session_state.commenter_board_picker_version = 0
if "commenter_board_picker_options_sig" not in st.session_state:
    st.session_state.commenter_board_picker_options_sig = ""
if "commenter_cafe_connect_side_mode" not in st.session_state:
    _cfg_cn = str(config.get("commenter_cafe_name", "") or "").strip()
    _cfg_cu = str(config.get("commenter_cafe_url", "") or "").strip()
    st.session_state.commenter_cafe_connect_side_mode = (
        "reset" if (_cfg_cn or _cfg_cu) else "save"
    )
if "commenter_auto_login_after_reset_save_mode" not in st.session_state:
    _saved_login_id = str(config.get("commenter_naver_id", "") or "").strip()
    st.session_state.commenter_auto_login_after_reset_save_mode = not _saved_login_id
if "commenter_db_reset_confirm" not in st.session_state:
    st.session_state.commenter_db_reset_confirm = False

if "commenter_auto_login_expanded" not in st.session_state:
    st.session_state.commenter_auto_login_expanded = False
if "commenter_naver_id_input" not in st.session_state:
    st.session_state.commenter_naver_id_input = str(config.get("commenter_naver_id", "") or "")
if "commenter_naver_pw_input" not in st.session_state:
    st.session_state.commenter_naver_pw_input = str(config.get("commenter_naver_pw", "") or "")
if "commenter_auto_login_enabled_input" not in st.session_state:
    st.session_state.commenter_auto_login_enabled_input = True

def on_commenter_auto_login_change():
    st.session_state.commenter_auto_login_expanded = True
    st.session_state.commenter_auto_login_after_reset_save_mode = True


def _parse_cfg_date(val, fallback):
    if not val:
        return fallback
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except Exception:
        return fallback


if "commenter_target_start_date" not in st.session_state:
    st.session_state.commenter_target_start_date = _parse_cfg_date(
        config.get("commenter_target_start_date"),
        (datetime.now() - timedelta(days=30)).date(),
    )
if "commenter_target_end_date" not in st.session_state:
    st.session_state.commenter_target_end_date = _parse_cfg_date(
        config.get("commenter_target_end_date"),
        datetime.now().date(),
    )
if "commenter_exclude_nicks" not in st.session_state:
    st.session_state.commenter_exclude_nicks = str(
        config.get("commenter_exclude_nicks", "운영자,매니저,스탭") or "운영자,매니저,스탭"
    )
if "commenter_allow_dup_nick" not in st.session_state:
    st.session_state.commenter_allow_dup_nick = bool(
        config.get("commenter_allow_dup_nick", False)
    )


def _safe_date_py(d):
    """date_input / 저장값 혼합을 날짜로."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    try:
        return _parse_cfg_date(d, datetime.now().date())
    except Exception:
        return None


def _commenter_ensure_comment_cols(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        return
    if "comment_status" not in df.columns:
        df["comment_status"] = ""
    if "comment_detail" not in df.columns:
        df["comment_detail"] = ""
    df["comment_status"] = df["comment_status"].fillna("").astype(str)
    df["comment_detail"] = df["comment_detail"].fillna("").astype(str)


def _commenter_filter_targets_by_post_date(
    base: pd.DataFrame,
    *,
    use_date: bool,
    d_start,
    d_end,
) -> pd.DataFrame:
    """전체 스냅샷에서 `date` 열 구간만 반영 (재수집 없음)."""
    if base is None or getattr(base, "empty", True):
        return pd.DataFrame()
    if not use_date:
        return base.copy()
    df = base.copy()
    _commenter_ensure_comment_cols(df)
    ds = _safe_date_py(d_start)
    de = _safe_date_py(d_end)
    if ds is None or de is None or "date" not in df.columns:
        return df
    if de < ds:
        ds, de = de, ds
    d_series = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    ds_pd = pd.Timestamp(ds).normalize()
    de_pd = pd.Timestamp(de).normalize()
    m = pd.notna(d_series) & (d_series >= ds_pd) & (d_series <= de_pd)
    df = df.loc[m].copy()
    _commenter_ensure_comment_cols(df)
    return df


if "commenter_dm_use_date_filter" not in st.session_state:
    st.session_state.commenter_dm_use_date_filter = False
if "commenter_dm_f_start" not in st.session_state:
    _d0 = st.session_state.get("commenter_target_start_date")
    st.session_state.commenter_dm_f_start = _safe_date_py(_d0) or (datetime.now() - timedelta(days=30)).date()
if "commenter_dm_f_end" not in st.session_state:
    _d1 = st.session_state.get("commenter_target_end_date")
    st.session_state.commenter_dm_f_end = _safe_date_py(_d1) or datetime.now().date()


def _commenter_apply_comment_result(url: str, status: str, detail: str) -> None:
    detail = (detail or "")[:500]
    status = str(status or "")
    u = str(url).strip()
    u_norm = u.rstrip("/")
    for _key in ("target_df", "commenter_target_df_full"):
        _df = st.session_state.get(_key)
        if _df is None or getattr(_df, "empty", True):
            continue
        _commenter_ensure_comment_cols(_df)
        if "url" not in _df.columns:
            continue
        _urls = _df["url"].astype(str).str.strip()
        _m = (_urls == u) | (_urls.str.rstrip("/") == u_norm)
        if _m.any():
            _df.loc[_m, "comment_status"] = status
            _df.loc[_m, "comment_detail"] = detail


def _commenter_full_dataframe() -> pd.DataFrame | None:
    full = st.session_state.get("commenter_target_df_full")
    if full is not None and not full.empty:
        _commenter_ensure_comment_cols(full)
        return full
    td = st.session_state.get("target_df")
    if td is not None and not td.empty:
        _commenter_ensure_comment_cols(td)
        return td
    return None


def _commenter_df_nonempty(df) -> bool:
    return df is not None and not getattr(df, "empty", True)


if not _commenter_df_nonempty(st.session_state.target_df) and not _commenter_df_nonempty(
    st.session_state.commenter_target_df_full
):
    try:
        _snap_rows = load_commenter_targets(COMMENTER_DB_PATH)
        if _snap_rows:
            _td = pd.DataFrame(_snap_rows)
            _commenter_ensure_comment_cols(_td)
            st.session_state.target_df = _td
            st.session_state.commenter_target_df_full = _td.copy()
    except Exception:
        pass
elif _commenter_df_nonempty(st.session_state.commenter_target_df_full):
    td0 = st.session_state.target_df
    if td0 is None or getattr(td0, "empty", True):
        st.session_state.target_df = st.session_state.commenter_target_df_full.copy()
elif _commenter_df_nonempty(st.session_state.target_df) and not _commenter_df_nonempty(
    st.session_state.commenter_target_df_full
):
    try:
        _snap_rows = load_commenter_targets(COMMENTER_DB_PATH)
        if _snap_rows:
            _td = pd.DataFrame(_snap_rows)
            _commenter_ensure_comment_cols(_td)
            st.session_state.commenter_target_df_full = _td.copy()
    except Exception:
        pass


def _inject_commenter_cafe_history_suggestions(cafe_names: list[str], cafe_urls: list[str]) -> None:
    inject_connect_history_suggestions(
        prefix="commenter",
        container_key_fragment="commenter_settings_card_1",
        cafe_names=cafe_names,
        cafe_urls=cafe_urls,
    )


def _commenter_overall_url_from_boards(boards: list) -> str:
    for b in boards or []:
        u = str((b or {}).get("url", "") or "")
        if "ArticleList.nhn" in u and "search.clubid=" in u:
            m_club = re.search(r"search\.clubid=(\d+)", u)
            if m_club:
                return (
                    f"https://cafe.naver.com/ArticleList.nhn?search.clubid={m_club.group(1)}"
                    f"&search.boardtype=L"
                )
        if "/f-e/cafes/" in u:
            m_fe = re.search(r"/cafes/(\d+)/menus/(\d+)", u)
            if m_fe:
                return f"https://cafe.naver.com/f-e/cafes/{m_fe.group(1)}/menus/0?viewType=L"
    return ""


_COMMENTER_TEMPLATE_BUILTIN = "{인사} {작성자}님! 좋은 글 잘 보고 갑니다 ^^"
_COMMENTER_TEMPLATE_DIRECT = "(직접 입력)"


def load_templates() -> list:
    """저장된 목록 + 기본 1문장 + (직접 입력). 저장 파일은 exe 옆(get_comment_templates_path)."""
    p = get_comment_templates_path()
    saved: list = []
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                saved = [str(x).strip() for x in raw if str(x).strip()]
        except Exception:
            saved = []

    seen: set[str] = set()
    out: list[str] = []
    for t in saved:
        if t not in seen and t != _COMMENTER_TEMPLATE_DIRECT:
            seen.add(t)
            out.append(t)
    if _COMMENTER_TEMPLATE_BUILTIN not in seen:
        out.append(_COMMENTER_TEMPLATE_BUILTIN)
        seen.add(_COMMENTER_TEMPLATE_BUILTIN)
    if _COMMENTER_TEMPLATE_DIRECT not in seen:
        out.append(_COMMENTER_TEMPLATE_DIRECT)
    return out


def save_new_template(content):
    if not content or content.strip() == "":
        return
    p = get_comment_templates_path()
    current: list = []
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                current = [str(x) for x in raw if str(x).strip()]
        except Exception:
            pass
    c = str(content).strip()
    if c == _COMMENTER_TEMPLATE_DIRECT or c == _COMMENTER_TEMPLATE_BUILTIN:
        return
    if c not in current:
        current.insert(0, c)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


if "template_list" not in st.session_state:
    st.session_state.template_list = load_templates()


def log_msg(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.comment_logs.append(f"[{timestamp}] {msg}")


def _commenter_reset_run_state() -> None:
    st.session_state.is_running = False
    st.session_state.pop("_commenter_run_template", None)
    st.session_state.commenter_run_index = 0
    st.session_state.commenter_stop_requested = False



def _commenter_browser_opened() -> bool:
    _c = st.session_state.get("commenter")
    return bool(_c is not None and getattr(_c, "driver", None) is not None)


def _commenter_ui_busy() -> bool:
    return bool(
        st.session_state.get("commenter_collecting", False)
        or st.session_state.get("is_running", False)
    )


def _render_commenter_db_section() -> None:
    """타겟 수집 설정 카드 하단 expander 안에서 호출."""
    _eff_commenter_db = str(COMMENTER_DB_PATH)

    st.metric("저장된 댓글 대상 글", f"{get_commenter_targets_count(_eff_commenter_db):,}건")
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # Zero-maintenance Data Policy: 단일 작업 폴더 열기 버튼
    if st.button("📁 작업 폴더 열기", type="primary", use_container_width=True, key="open_zero_maintenance_dir_btn"):
        from app.utils.paths import export_all_latest_dbs_to_csv, open_zero_maintenance_data_dir
        export_all_latest_dbs_to_csv()
        open_zero_maintenance_data_dir()
        st.toast("📂 작업 폴더를 열고 CSV 파일들을 변환했습니다.")

    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
    if st.button("🧹 통계 초기화 후 작업하기", use_container_width=True, key="reset_commenter_statistics_and_db_btn"):
        from app.utils.paths import generate_new_db_path
        from app.utils.event_db import init_event_db
        new_db_path = generate_new_db_path("auto_commenter")
        st.session_state["active_db_path_commenter"] = str(new_db_path)
        
        # Save to config as well so it persists
        config["commenter_db_path"] = str(new_db_path)
        save_config(config)
        
        # Initialize the new DB immediately
        init_event_db(str(new_db_path))
        
        # 세션 상태에 저장된 메모리 타겟 데이터 및 인덱스 초기화
        st.session_state.target_df = None
        st.session_state.commenter_target_df_full = None
        st.session_state.commenter_run_index = 0
        if st.session_state.get("commenter"):
            st.session_state.commenter.db_path = str(new_db_path)
            
        st.success("🧹 통계가 초기화되었습니다. 새 작업 환경에서 시작합니다.")
        st.rerun()


def _commenter_normalized_target_range():
    _start_d = st.session_state.get("commenter_target_start_date")
    _end_d = st.session_state.get("commenter_target_end_date")
    if isinstance(_start_d, datetime):
        _start_d = _start_d.date()
    if isinstance(_end_d, datetime):
        _end_d = _end_d.date()
    if _end_d is None or _start_d is None:
        return None, None
    if _end_d < _start_d:
        _start_d, _end_d = _end_d, _start_d
    return _start_d, _end_d


def _commenter_board_label_for_url(board_url: str) -> str:
    """왼쪽에서 가져온 게시판 목록 URL → 표시 이름 (목록 DOM에 board_name이 없을 때)."""
    boards = st.session_state.get("commenter_extracted_boards") or []
    needle = str(board_url).strip()
    for b in boards:
        if str((b or {}).get("url") or "").strip() == needle:
            return str((b or {}).get("name") or "").strip()
    return ""


def _commenter_board_label_for_url_static(board_url: str, boards: list) -> str:
    """왼쪽에서 가져온 게시판 목록 URL → 표시 이름 (목록 DOM에 board_name이 없을 때)."""
    needle = str(board_url).strip()
    for b in boards:
        if str((b or {}).get("url") or "").strip() == needle:
            return str((b or {}).get("name") or "").strip()
    return ""


def _commenter_collect_thread_func(
    job_id, crw, board_urls, start_dt, end_dt, exclude_keyword, allow_dup, db_path, extracted_boards
):
    job = COMMENTER_COLLECT_JOBS[job_id]
    try:
        by_url = {}
        for b_idx, board_url_each in enumerate(board_urls, start=1):
            job["status_text"] = f"게시판 {b_idx}/{len(board_urls)} 목록 수집 중…"
            job["progress"] = (b_idx - 1) / max(1, len(board_urls))
            
            articles = []
            _page_cursor = 1
            _board_batch = 50
            _board_page_cap = 8000
            _board_guard = 0
            _is_finished = False
            while _page_cursor <= _board_page_cap and _board_guard < 400:
                _board_guard += 1
                result = crw.scrape_board_list(
                    board_url_each,
                    start_dt,
                    end_dt,
                    exclude_boards=[],
                    start_page=_page_cursor,
                    max_pages=_board_batch,
                )
                if isinstance(result, tuple) and len(result) == 2:
                    _batch, _is_finished = result
                else:
                    _batch, _is_finished = (result or []), True
                _batch = _batch or []
                articles.extend(_batch)
                job["status_text"] = (
                    f"게시판 {b_idx}/{len(board_urls)} 목록 스캔 중… "
                    f"(이번 배치 {len(_batch)}건 · 누적 {len(articles)}건)"
                )
                if _is_finished:
                    break
                _eff_pg = int(
                    getattr(crw, "last_effective_start_page", _page_cursor) or _page_cursor
                )
                _page_cursor = _eff_pg + _board_batch
                
            for art in articles:
                u = str(art.get("url") or "").strip()
                if not u or u in by_url:
                    continue
                board_name = str(art.get("board_name") or "").strip()
                if crw._is_noise_board_label(board_name):
                    board_name = ""
                if not board_name:
                    board_name = _commenter_board_label_for_url_static(board_url_each, extracted_boards)
                if crw._is_noise_board_label(board_name):
                    board_name = _commenter_board_label_for_url_static(board_url_each, extracted_boards) or ""
                nickname = str(art.get("nickname") or "").strip() or "unknown"
                by_url[u] = {
                    "post_id": art.get("post_id", ""),
                    "nickname": nickname,
                    "title": art.get("title", ""),
                    "date": art.get("date", ""),
                    "url": u,
                    "board_name": board_name,
                }
                
        job["progress"] = 1.0
        job["status_text"] = "데이터 가공 중…"
        
        df = pd.DataFrame(list(by_url.values()))
        if not df.empty:
            df["_sort_d"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("_sort_d", ascending=False).drop(columns=["_sort_d"])
        excludes = [x.strip() for x in exclude_keyword.split(",") if x.strip()]
        if excludes and not df.empty:
            mask = df["nickname"].apply(lambda x: not any(exc in str(x) for exc in excludes))
            df = df[mask]
            
        if not allow_dup and not df.empty:
            _before = len(df)
            _nk = df["nickname"].astype(str).str.strip()
            _fallback = df["url"].astype(str).str.strip()
            _dedup_key = _nk.mask(_nk.str.lower().eq("unknown"), _fallback)
            _dedup_key = _dedup_key.mask(_dedup_key.eq("") | _dedup_key.isna(), _fallback)
            df = df.assign(_commenter_nick_dedup=_dedup_key).drop_duplicates(
                subset=["_commenter_nick_dedup"], keep="first"
            ).drop(columns=["_commenter_nick_dedup"])
            _removed = _before - len(df)
            if _removed > 0:
                job["info_msg"] = f"동일 닉네임 중복 {_removed}건 제거됨 (설정에서 허용 가능)"
                
        if "comment_status" not in df.columns:
            df["comment_status"] = ""
        if "comment_detail" not in df.columns:
            df["comment_detail"] = ""
        df["comment_status"] = df["comment_status"].fillna("").astype(str)
        df["comment_detail"] = df["comment_detail"].fillna("").astype(str)
        
        job["result_df"] = df
        try:
            replace_commenter_targets(
                db_path, df.to_dict("records") if not df.empty else []
            )
        except Exception as _db_exc:
            job["warn_msg"] = f"타겟 DB 저장에 실패했습니다(화면 표는 유지됨). 원인: {_db_exc}"
            
        if df.empty:
            job["warn_msg"] = "선택한 기간·게시판에서 수집된 글이 없습니다."
        else:
            job["success_msg"] = f"{len(df)}건 수집 완료"
            
        job["status"] = "completed"
    except Exception as e:
        job["status"] = "error"
        job["error_msg"] = f"수집 실패: {e}"


def _collect_commenter_targets_into_session() -> None:
    try:
        st.session_state._commenter_collect_warning = None
        crw = st.session_state.commenter
        if not crw or not getattr(crw, "driver", None):
            st.warning("먼저 **1단계: 브라우저 열기**를 해주세요.")
            return
        board_urls = list(
            dict.fromkeys(
                [
                    str(u).strip()
                    for u in (st.session_state.get("commenter_selected_board_urls") or [])
                    if str(u).strip()
                ]
            )
        )
        if not board_urls:
            st.session_state._commenter_collect_warning = "⚠️ 왼쪽에서 **게시판을 선택**한 뒤 저장하고 진행해주세요."
            return
        _start_d, _end_d = _commenter_normalized_target_range()
        if _start_d is None:
            st.session_state._commenter_collect_warning = "⚠️ 수집 기간을 확인해주세요."
            return
            
        # Start background job
        job_id = str(uuid.uuid4())
        exclude_keyword = str(st.session_state.get("commenter_exclude_nicks", "") or "")
        allow_dup = st.session_state.get("commenter_allow_dup_nick", False)
        extracted_boards = list(st.session_state.get("commenter_extracted_boards") or [])
        
        start_dt = datetime.combine(_start_d, datetime.min.time())
        end_dt = datetime.combine(_end_d, datetime.max.time())
        
        COMMENTER_COLLECT_JOBS[job_id] = {
            "status": "running",
            "progress": 0.0,
            "status_text": "수집 대기 중…",
            "thread": None
        }
        
        t = threading.Thread(
            target=_commenter_collect_thread_func,
            args=(
                job_id,
                crw,
                board_urls,
                start_dt,
                end_dt,
                exclude_keyword,
                allow_dup,
                COMMENTER_DB_PATH,
                extracted_boards
            ),
            daemon=True
        )
        COMMENTER_COLLECT_JOBS[job_id]["thread"] = t
        
        st.session_state.commenter_collecting = True
        st.session_state.commenter_collect_job_id = job_id
        st.session_state.commenter_collect_progress = 0.0
        st.session_state.commenter_collect_status_text = "수집 시작 중…"
        
        t.start()
    except Exception as e:
        st.error(f"수집 시작 실패: {e}")
        st.session_state.commenter_collecting = False


def _render_commenter_dashboard_header() -> None:
    _logo_path = Path(__file__).resolve().parent.parent / "assets" / "CafeMonster_logo.png"
    
    if "show_guide" not in st.session_state:
        st.session_state.show_guide = False

    with st.container(key="dashboard_header"):
        if st.session_state.show_guide:
            col_left, col_right = st.columns([1, 3], gap="medium")
            with col_left:
                _hdr_logo, _hdr_title = st.columns([1, 4], gap="small", vertical_alignment="center")
                with _hdr_logo:
                    render_logo_png(_logo_path, width_px=64)
                with _hdr_title:
                    st.markdown(
                        f'<h2 style="margin: 0px; padding:0; line-height:1.2; font-size:1.45rem; color: #1e3a8a !important; font-weight: 700 !important;">카페 몬스터 [자동 댓글러]</h2>'
                        f'{CafeMonsterAuthHelper.get_license_badge_html("AutoComment")}',
                        unsafe_allow_html=True,
                    )
            with col_right:
                with st.container(border=True):
                    c_hdr_title, c_hdr_btn = st.columns([4, 1.2], vertical_alignment="center")
                    with c_hdr_title:
                        st.markdown('<p style="margin: 0px; font-weight: 700; color: #1e3a8a; font-size: 1.0rem;">📖 사용 가이드 (필독)</p>', unsafe_allow_html=True)
                    with c_hdr_btn:
                        st.button(
                            "❌ 닫기",
                            key="guide_close_btn",
                            on_click=lambda: st.session_state.__setitem__("show_guide", False),
                            use_container_width=True
                        )
                    
                    st.markdown('<div style="height:0;margin:0.25rem 0 0.75rem 0;border:none;border-top:1px solid #cbd5e1;"></div>', unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns(3, gap="medium")
                    with col1:
                        st.markdown(
                            f"""
                            **1) 기본 실행 순서**
                            - 타겟 글은 브라우저로 게시판 목록을 직접 스크랩합니다.
                            - **카페 · 연결**: 카페 정보 입력 후 **저장**합니다.
                            - **타겟 수집 설정**: 수집 기간 및 제외 닉네임 설정 후 **💾 저장**합니다.
                            - **실행 제어**: 1단계(브라우저) → 2단계(목록 수집) → **댓글 작성 시작**을 순차 진행합니다.
                            """
                        )
                    with col2:
                        st.markdown(
                            """
                            **2) 데이터 및 타겟 관리**
                            - **재수집 시 기록 연동**: 목록 재수집 시 같은 글(URL)에 대한 `작성 완료` 등 기록은 DB에서 연동됩니다.
                            - **📋 타겟 목록 필터링**: 글 작성일 필터 체크 후 날짜를 적용하여 범위를 좁힐 수 있습니다 (재수집 불필요).
                            - 메인 카페 크롤링 실행 중에는 본 화면을 사용할 수 없습니다.
                            """
                        )
                    with col3:
                        st.markdown(
                            f"""
                            **3) 안전 사용 조건 (요약)**
                            - **자동 대기/휴식**: 글 간 **{COMMENTER_GAP_MIN_SEC}~{COMMENTER_GAP_MAX_SEC}초** 무작위 대기, **{COMMENTER_SESSION_LIMIT}건**마다 **{COMMENTER_SESSION_REST_SEC // 60}분** 휴식합니다.
                            - **하루 권장량**: **300건 이하** 작성을 권장하며 초과 시 추가 실행을 금지합니다.
                            - **제재 방지**: `{{인사}}` 랜덤 치환을 활용하되 스팸 신고 등 정책 위반 시 제재 가능성이 있습니다.
                            """
                        )
        else:
            col_left, col_right = st.columns([3, 1], gap="medium", vertical_alignment="center")
            with col_left:
                _hdr_logo, _hdr_title = st.columns([1, 10], gap="small", vertical_alignment="center")
                with _hdr_logo:
                    render_logo_png(_logo_path, width_px=80)
                with _hdr_title:
                    st.markdown(
                        f'<h2 style="margin: 0px; padding:0; line-height:1.2; font-size:1.45rem; color: #1e3a8a !important; font-weight: 700 !important;">카페 몬스터 [자동 댓글러]</h2>'
                        f'{CafeMonsterAuthHelper.get_license_badge_html("AutoComment")}',
                        unsafe_allow_html=True,
                    )
            with col_right:
                st.button(
                    "📖 사용 가이드 보기",
                    key="guide_btn_open",
                    on_click=lambda: st.session_state.__setitem__("show_guide", True),
                    use_container_width=True
                )


_render_commenter_dashboard_header()

st.markdown("#### ⚙️ 설정")
_col1, _col2, _col3 = st.columns([1, 1, 1], gap="medium")

with _col1:
    with st.container(border=True, key="commenter_settings_card_1"):
        render_settings_card_title("카페 · 연결", icon="🏪")
        if st.session_state.pop("_commenter_pending_clear_cafe_name_input", False):
            st.session_state.commenter_cafe_name_input = ""
        st.text_input(
            "카페명",
            key="commenter_cafe_name_input",
            on_change=lambda: None,
        )
        try:
            _ev_url_col, _ev_side_col = st.columns([5, 1], gap="small", vertical_alignment="center")
        except TypeError:
            _ev_url_col, _ev_side_col = st.columns([5, 1], gap="small")
        with _ev_url_col:
            if st.session_state.pop("_commenter_pending_clear_cafe_url_input", False):
                st.session_state.commenter_cafe_url_input = ""
            cafe_url = st.text_input(
                "카페 URL",
                key="commenter_cafe_url_input",
                on_change=lambda: None,  # 엔터 시 불필요한 전체 리렌더/에러 방지
            )
        _inject_commenter_cafe_history_suggestions(
            (config.get("commenter_cafe_name_history", []) or []) + [str(config.get("commenter_cafe_name", "") or "")],
            (config.get("commenter_cafe_url_history", []) or []) + [str(config.get("commenter_cafe_url", "") or "")],
        )
        _co_side = str(st.session_state.get("commenter_cafe_connect_side_mode") or "save")
        _co_lbl = "리셋" if _co_side == "reset" else "저장"
        _co_help = (
            "저장한 카페·게시판 연결 초기화 — 단추는 다시 `저장`으로 바뀝니다."
            if _co_side == "reset"
            else "카페명/카페 URL을 자동댓글러 설정 파일에 저장합니다."
        )
        with _ev_side_col:
            if st.button(
                _co_lbl,
                key="commenter_cafe_side_btn",
                use_container_width=True,
                help=_co_help,
                disabled=_commenter_ui_busy(),
            ):
                if _co_side == "save":
                    cfg_now = dict(load_config() or {})
                    saved_commenter_cafe_name = str(st.session_state.get("commenter_cafe_name_input", "") or "").strip()
                    saved_commenter_cafe_url = str(st.session_state.get("commenter_cafe_url_input", "") or "").strip()
                    cfg_now["commenter_cafe_name"] = saved_commenter_cafe_name
                    cfg_now["commenter_cafe_url"] = saved_commenter_cafe_url
                    if saved_commenter_cafe_name:
                        prev_commenter_name_hist = [
                            str(x).strip()
                            for x in (cfg_now.get("commenter_cafe_name_history", []) or [])
                            if str(x).strip()
                        ]
                        cfg_now["commenter_cafe_name_history"] = (
                            [saved_commenter_cafe_name]
                            + [x for x in prev_commenter_name_hist if x != saved_commenter_cafe_name]
                        )[:20]
                    if saved_commenter_cafe_url:
                        prev_commenter_url_hist = [
                            str(x).strip()
                            for x in (cfg_now.get("commenter_cafe_url_history", []) or [])
                            if str(x).strip()
                        ]
                        cfg_now["commenter_cafe_url_history"] = (
                            [saved_commenter_cafe_url]
                            + [x for x in prev_commenter_url_hist if x != saved_commenter_cafe_url]
                        )[:20]
                    save_config(cfg_now)
                    config.update(cfg_now)
                    st.session_state.commenter_cafe_connect_side_mode = "reset"
                    st.session_state._commenter_cafe_url_apply_ack = True
                    st.rerun()
                else:
                    cfg_clr = dict(load_config() or {})
                    cfg_clr["commenter_cafe_name"] = ""
                    cfg_clr["commenter_cafe_url"] = ""
                    cfg_clr["commenter_extracted_boards"] = []
                    cfg_clr["commenter_selected_board_urls"] = []
                    cfg_clr["commenter_board_url"] = ""
                    save_config(cfg_clr)
                    config.update(cfg_clr)
                    st.session_state.commenter_extracted_boards = []
                    st.session_state.commenter_selected_board_urls = []
                    st.session_state.commenter_selected_board_url = ""
                    st.session_state._commenter_pending_clear_cafe_name_input = True
                    st.session_state._commenter_pending_clear_cafe_url_input = True
                    st.session_state.commenter_cafe_connect_side_mode = "save"
                    st.session_state._commenter_cafe_reset_done = True
                    st.rerun()
        if st.session_state.get("_commenter_cafe_reset_done"):
            st.session_state._commenter_cafe_reset_done = False
            st.success(
                "카페 연결 상태를 초기화했습니다. 카페명·URL 설정을 비웠고 입력칸도 비워졌습니다 — 다시 **`저장`** 을 진행해 주세요."
            )
        if st.session_state.get("_commenter_cafe_url_apply_ack"):
            st.session_state._commenter_cafe_url_apply_ack = False
            st.success("카페 연결 정보를 저장했습니다.")

        _saved_login_id = str(config.get("commenter_naver_id", "") or "").strip()
        _saved_login_pw = str(config.get("commenter_naver_pw", "") or "")
        _auto_login_done = bool(_saved_login_id and _saved_login_pw)
        _auto_login_title = "🔐 자동로그인 설정 (완료)" if _auto_login_done else "🔐 자동로그인 설정"
        with st.expander(_auto_login_title, expanded=st.session_state.commenter_auto_login_expanded):
            if st.session_state.pop("_commenter_pending_clear_auto_login_inputs", False):
                st.session_state.commenter_auto_login_enabled_input = True
                st.session_state.commenter_naver_id_input = ""
                st.session_state.commenter_naver_pw_input = ""
            if "commenter_auto_login_enabled_input" not in st.session_state:
                st.session_state.commenter_auto_login_enabled_input = True
            st.checkbox(
                "브라우저 열 때 자동로그인 실행",
                key="commenter_auto_login_enabled_input",
                on_change=on_commenter_auto_login_change,
                help="브라우저 열기 직후 저장된 계정으로 로그인을 시도합니다.",
            )
            _ev_al_input_col, _ev_al_btn_col = st.columns([4, 1], gap="small")
            with _ev_al_input_col:
                if "commenter_naver_id_input" not in st.session_state:
                    st.session_state.commenter_naver_id_input = str(config.get("commenter_naver_id", "") or "")
                if "commenter_naver_pw_input" not in st.session_state:
                    st.session_state.commenter_naver_pw_input = str(config.get("commenter_naver_pw", "") or "")
                st.text_input(
                    "네이버 아이디",
                    key="commenter_naver_id_input",
                    placeholder="아이디 입력",
                )
                st.text_input(
                    "네이버 비밀번호",
                    key="commenter_naver_pw_input",
                    type="password",
                    placeholder="비밀번호 입력",
                )
            with _ev_al_btn_col:
                st.markdown("<div style='margin-top: 88px;'></div>", unsafe_allow_html=True)
                _ev_al_save_mode = (
                    bool(st.session_state.get("commenter_auto_login_after_reset_save_mode", False))
                    or str(st.session_state.get("commenter_naver_id_input", "") or "").strip() != str(config.get("commenter_naver_id", "") or "").strip()
                    or str(st.session_state.get("commenter_naver_pw_input", "") or "") != str(config.get("commenter_naver_pw", "") or "")
                    or bool(st.session_state.get("commenter_auto_login_enabled_input", True)) != bool(config.get("commenter_auto_login_enabled", True))
                )
                _ev_al_lbl = "저장" if _ev_al_save_mode else "리셋"
                if st.button(
                    _ev_al_lbl,
                    key="commenter_auto_login_side_btn",
                    use_container_width=True,
                    disabled=_commenter_ui_busy(),
                ):
                    if _ev_al_save_mode:
                        cfg_now = dict(load_config() or {})
                        cfg_now["commenter_auto_login_enabled"] = bool(
                            st.session_state.get("commenter_auto_login_enabled_input", False)
                        )
                        cfg_now["commenter_naver_id"] = str(
                            st.session_state.get("commenter_naver_id_input", "") or ""
                        ).strip()
                        cfg_now["commenter_naver_pw"] = str(
                            st.session_state.get("commenter_naver_pw_input", "") or ""
                        )
                        save_config(cfg_now)
                        config.update(cfg_now)
                        st.session_state.commenter_auto_login_after_reset_save_mode = False
                        st.session_state.commenter_auto_login_expanded = False
                        st.session_state._commenter_auto_login_save_ack = True
                        st.rerun()
                    else:
                        st.session_state._commenter_pending_clear_auto_login_inputs = True
                        st.session_state.commenter_auto_login_after_reset_save_mode = True
                        st.session_state.commenter_auto_login_expanded = True
                        st.session_state._commenter_auto_login_reset_ack = True
                        st.rerun()
            if st.session_state.get("_commenter_auto_login_reset_ack"):
                st.session_state._commenter_auto_login_reset_ack = False
                st.success("자동로그인 설정 값을 비웠습니다. 새 값을 입력한 뒤 오른쪽 저장을 눌러주세요.")
            if st.session_state.get("_commenter_auto_login_save_ack"):
                st.session_state._commenter_auto_login_save_ack = False
                st.success("자동로그인 설정을 저장했습니다.")

        if st.button(
            "🔍 게시판 목록 가져오기",
            key="commenter_scan_boards_btn",
            use_container_width=True,
            disabled=_commenter_ui_busy() or (not _commenter_browser_opened()),
        ):
            if not st.session_state.get("commenter") or not getattr(
                st.session_state.commenter, "driver", None
            ):
                st.error("먼저 **실행 제어 → 1단계: 브라우저 열기**를 실행해주세요.")
            else:
                try:
                    with st.spinner("게시판 목록 스캔 중..."):
                        crawler_obj = st.session_state.commenter
                        boards: list = []
                        if hasattr(crawler_obj, "get_all_board_urls"):
                            boards = crawler_obj.get_all_board_urls(cafe_url=cafe_url) or []
                        if not boards:
                            driver = crawler_obj.driver
                            seen: set[str] = set()
                            target_cafe_url = str(cafe_url or "").strip()
                            if target_cafe_url:
                                try:
                                    driver.switch_to.default_content()
                                except Exception:
                                    pass
                                try:
                                    if hasattr(crawler_obj, "_convert_to_legacy_board_url"):
                                        target_cafe_url = crawler_obj._convert_to_legacy_board_url(
                                            target_cafe_url
                                        )
                                    driver.get(target_cafe_url)
                                    time.sleep(1.2)
                                except Exception:
                                    pass

                            def _is_board_href(href: str) -> bool:
                                u = str(href or "").strip()
                                if not u:
                                    return False
                                return ("ArticleList.nhn" in u and "search.menuid" in u) or (
                                    "/menus/" in u and "/articles/" not in u
                                )

                            def _append_boards_from_current_dom():
                                for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                                    try:
                                        href = str(a.get_attribute("href") or "").strip()
                                        if not _is_board_href(href):
                                            continue
                                        name = str(
                                            (a.text or "").strip()
                                            or (a.get_attribute("title") or "").strip()
                                            or (a.get_attribute("aria-label") or "").strip()
                                            or ""
                                        )
                                        if not name:
                                            continue
                                        if href in seen:
                                            continue
                                        seen.add(href)
                                        boards.append({"name": name, "url": href})
                                    except Exception:
                                        continue
                                for a in driver.find_elements(By.CSS_SELECTOR, "a[onclick]"):
                                    try:
                                        onclick = str(a.get_attribute("onclick") or "")
                                        if "goMenu" not in onclick:
                                            continue
                                        m = re.search(r"goMenu\('(\d+)'\)", onclick) or re.search(
                                            r"goMenu\((\d+)\)", onclick
                                        )
                                        if not m:
                                            continue
                                        menuid = m.group(1)
                                        cur_url = str(getattr(driver, "current_url", "") or "")
                                        m_club = re.search(r"clubid=(\d+)", cur_url) or re.search(
                                            r"/cafes/(\d+)", cur_url
                                        )
                                        if not m_club:
                                            continue
                                        clubid = m_club.group(1)
                                        href = (
                                            f"https://cafe.naver.com/ArticleList.nhn?search.clubid={clubid}"
                                            f"&search.menuid={menuid}&search.boardtype=L"
                                        )
                                        name = (a.text or "").strip() or f"게시판_{menuid}"
                                        if href in seen:
                                            continue
                                        seen.add(href)
                                        boards.append({"name": name, "url": href})
                                    except Exception:
                                        continue

                            try:
                                driver.switch_to.default_content()
                            except Exception:
                                pass
                            _append_boards_from_current_dom()
                            try:
                                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                                for fr in iframes:
                                    try:
                                        driver.switch_to.default_content()
                                        driver.switch_to.frame(fr)
                                        _append_boards_from_current_dom()
                                    except Exception:
                                        continue
                                driver.switch_to.default_content()
                            except Exception:
                                pass
                    if boards:
                        st.session_state.commenter_extracted_boards = boards
                        st.session_state.commenter_selected_board_urls = []
                        st.session_state.commenter_selected_board_url = ""
                        st.session_state.commenter_board_picker_version = int(
                            st.session_state.get("commenter_board_picker_version", 0)
                        ) + 1
                        cfg_now = dict(load_config() or {})
                        cfg_now["commenter_extracted_boards"] = boards
                        cfg_now["commenter_selected_board_urls"] = []
                        cfg_now["commenter_board_url"] = ""
                        save_config(cfg_now)
                        config.update(cfg_now)
                        st.success(f"✅ 게시판 스캔 완료: {len(boards)}개")
                    else:
                        st.warning("게시판을 찾지 못했습니다. 카페 메인/메뉴가 보이는 화면에서 다시 시도해주세요.")
                except Exception as e:
                    st.error(f"게시판 목록 스캔 실패: {e}")

        if st.session_state.commenter_extracted_boards:
            total_board_count = len(st.session_state.commenter_extracted_boards)
            selected_count_header = st.empty()
            _selected_now = len(
                list(
                    dict.fromkeys(
                        [u for u in (st.session_state.get("commenter_selected_board_urls", []) or []) if u]
                    )
                )
            )
            selected_count_header.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;gap:12px;white-space:nowrap;"
                f"padding:4px 0 8px 0;margin:2px 0 6px 0;'>"
                f"<div style='font-size:1.32rem;font-weight:700;line-height:1.2;'>📋 게시판 선택 (총 {total_board_count}개)</div>"
                f"<div style='font-size:0.92rem;color:#475569;'>[{_selected_now}개 게시판 선택]</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            options = st.session_state.commenter_extracted_boards
            board_options: dict[str, str] = {}
            for i, b in enumerate(options, start=1):
                name = str((b or {}).get("name", "") or "").strip() or f"게시판_{i}"
                url = str((b or {}).get("url", "") or "").strip()
                board_options[f"{i:02d}. {name}"] = url

            overall_url = _commenter_overall_url_from_boards(options)

            options_list: list[str] = []
            if overall_url:
                options_list.append("00. 전체글보기")
            options_list.extend(list(board_options.keys()))

            options_sig = "||".join(options_list)
            if options_sig != str(st.session_state.get("commenter_board_picker_options_sig", "")):
                st.session_state.commenter_board_picker_options_sig = options_sig
                _new_version = int(st.session_state.get("commenter_board_picker_version", 0)) + 1
                st.session_state.commenter_board_picker_version = _new_version
                _available_urls = [str(u).strip() for u in board_options.values() if str(u).strip()]
                if overall_url:
                    _available_urls.insert(0, str(overall_url).strip())
                _available_set = set(_available_urls)
                _existing_selected = list(
                    dict.fromkeys(
                        [
                            str(u).strip()
                            for u in (st.session_state.get("commenter_selected_board_urls", []) or [])
                            if str(u).strip()
                        ]
                    )
                )
                _preserved = [u for u in _existing_selected if u in _available_set]
                st.session_state.commenter_selected_board_urls = _preserved
                st.session_state.commenter_selected_board_url = _preserved[0] if _preserved else ""
                _preserved_set = set(_preserved)
                for _lb in options_list:
                    _idx = options_list.index(_lb)
                    _u = overall_url if _lb == "00. 전체글보기" else board_options.get(_lb, "")
                    if _u:
                        st.session_state[f"commenter_board_chk_{_new_version}_{_idx}"] = bool(_u in _preserved_set)

            label_to_url: dict[str, str] = {}
            for label in options_list:
                if label == "00. 전체글보기":
                    label_to_url[label] = overall_url
                else:
                    label_to_url[label] = board_options.get(label, "")

            with st.expander("게시판 목록 열기/접기", expanded=False):
                v = int(st.session_state.get("commenter_board_picker_version", 0))
                label_to_idx = {label: i for i, label in enumerate(options_list)}
                overall_label = "00. 전체글보기" if "00. 전체글보기" in options_list else None
                combo_key = f"commenter_board_combo_select_all_{v}"
                combo_prev_key = f"_commenter_board_combo_select_all_prev_{v}"
                wanted_urls = set(st.session_state.get("commenter_selected_board_urls", []) or [])

                overall_key = ""
                if overall_label:
                    overall_idx = int(label_to_idx.get(overall_label, -1))
                    if overall_idx >= 0:
                        overall_key = f"commenter_board_chk_{v}_{overall_idx}"
                if overall_key and bool(st.session_state.get(overall_key, False)):
                    st.session_state[combo_key] = False
                    st.session_state[combo_prev_key] = False

                with st.container():
                    combo_checked_now = st.checkbox(
                        "✨ 전체 게시판 선택",
                        key=combo_key,
                        help="한 번에 전체 게시판을 체크합니다. 이후 제외할 게시판만 해제하세요.",
                    )

                combo_prev = bool(st.session_state.get(combo_prev_key, False))
                if combo_checked_now and (not combo_prev):
                    for label in options_list:
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        chk_key = f"commenter_board_chk_{v}_{i}"
                        if overall_label and label == overall_label:
                            st.session_state[chk_key] = False
                        else:
                            st.session_state[chk_key] = True
                elif (not combo_checked_now) and combo_prev:
                    for label in options_list:
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        st.session_state[f"commenter_board_chk_{v}_{i}"] = False
                st.session_state[combo_prev_key] = bool(combo_checked_now)

                if overall_key and bool(st.session_state.get(overall_key, False)):
                    combo_checked_now = False
                elif combo_checked_now and overall_key:
                    st.session_state[overall_key] = False

                for label in options_list:
                    i = int(label_to_idx.get(label, -1))
                    if i < 0:
                        continue
                    u = str(label_to_url.get(label, "") or "")
                    chk_key = f"commenter_board_chk_{v}_{i}"
                    if chk_key not in st.session_state:
                        st.session_state[chk_key] = bool(u and u in wanted_urls)

                if overall_label:
                    overall_idx = int(label_to_idx.get(overall_label, -1))
                    overall_key = f"commenter_board_chk_{v}_{overall_idx}" if overall_idx >= 0 else ""
                    overall_checked = bool(st.session_state.get(overall_key, False)) if overall_key else False
                    other_checked = False
                    for label in options_list:
                        if label == overall_label:
                            continue
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        if bool(st.session_state.get(f"commenter_board_chk_{v}_{i}", False)):
                            other_checked = True
                            break
                    if overall_checked:
                        for label in options_list:
                            if label == overall_label:
                                continue
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            st.session_state[f"commenter_board_chk_{v}_{i}"] = False
                    elif other_checked and overall_key:
                        st.session_state[overall_key] = False

                try:
                    with st.container(height=360):
                        for label in options_list:
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            chk_key = f"commenter_board_chk_{v}_{i}"
                            disable_this = False
                            if overall_label and label != overall_label:
                                oidx = int(label_to_idx.get(overall_label, -1))
                                if oidx >= 0 and bool(st.session_state.get(f"commenter_board_chk_{v}_{oidx}", False)):
                                    disable_this = True
                            st.checkbox(label, key=chk_key, disabled=disable_this)
                except TypeError:
                    for label in options_list:
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        chk_key = f"commenter_board_chk_{v}_{i}"
                        disable_this = False
                        if overall_label and label != overall_label:
                            oidx = int(label_to_idx.get(overall_label, -1))
                            if oidx >= 0 and bool(st.session_state.get(f"commenter_board_chk_{v}_{oidx}", False)):
                                disable_this = True
                        st.checkbox(label, key=chk_key, disabled=disable_this)

                selected_urls: list[str] = []
                for label in options_list:
                    i = int(label_to_idx.get(label, -1))
                    if i < 0:
                        continue
                    if bool(st.session_state.get(f"commenter_board_chk_{v}_{i}", False)):
                        u = str(label_to_url.get(label, "") or "")
                        if u:
                            selected_urls.append(u)
                selected_urls_dedup = list(dict.fromkeys(selected_urls))
                st.session_state.commenter_selected_board_urls = selected_urls_dedup
                st.session_state.commenter_selected_board_url = (
                    selected_urls_dedup[0] if selected_urls_dedup else ""
                )

                _selected_sig = "|".join(selected_urls_dedup)
                if st.session_state.get("_commenter_selected_board_urls_saved_sig", "") != _selected_sig:
                    st.session_state._commenter_selected_board_urls_saved_sig = _selected_sig
                    cfg_now = dict(load_config() or {})
                    cfg_now["commenter_selected_board_urls"] = selected_urls_dedup
                    cfg_now["commenter_board_url"] = "\n".join(selected_urls_dedup)
                    save_config(cfg_now)
                    config.update(cfg_now)

                selected_count_header.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center;gap:12px;white-space:nowrap;"
                    f"padding:4px 0 8px 0;margin:2px 0 6px 0;'>"
                    f"<div style='font-size:1.32rem;font-weight:700;line-height:1.2;'>📋 게시판 선택 (총 {total_board_count}개)</div>"
                    f"<div style='font-size:0.92rem;color:#475569;'>[{len(selected_urls_dedup)}개 게시판 선택]</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info(
                "먼저 **아래 실행 제어 → 1단계: 브라우저 열기** 후, 왼쪽 **게시판 목록 가져오기**로 목록을 채운 뒤 "
                "게시판을 선택합니다."
            )

with _col2:
    with st.container(border=True, key="commenter_settings_card_2"):
        render_settings_card_title("타겟 수집 설정", icon="🎯")
        st.caption(
            "왼쪽에서 고른 **게시판**과 아래 **수집 기간**·**제외 닉네임**을 지정한 뒤 **💾 저장**합니다. "
            "(브라우저·목록 수집은 저장 후 **아래 실행 제어**에서 진행합니다.)"
        )
        st.markdown("##### 📅 수집 기간")
        _period_a, _period_b = st.columns(2)
        with _period_a:
            st.date_input("시작일", key="commenter_target_start_date")
        with _period_b:
            st.date_input("종료일", key="commenter_target_end_date")
        st.text_input("제외 닉네임 (쉼표)", key="commenter_exclude_nicks")
        st.checkbox(
            "동일 별명 중복 허용",
            key="commenter_allow_dup_nick",
            help="여러 게시판에서 같은 닉네임이 있을 때, 체크하면 모두 포함합니다. 기본은 첫 번째만 유지.",
        )

        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
        if st.button(
            "💾 저장",
            use_container_width=True,
            key="commenter_save_target_settings_btn",
            disabled=_commenter_ui_busy(),
        ):
            _s = st.session_state.get("commenter_target_start_date")
            _e = st.session_state.get("commenter_target_end_date")
            if isinstance(_s, datetime):
                _s = _s.date()
            if isinstance(_e, datetime):
                _e = _e.date()
            if _s is not None and _e is not None and _e < _s:
                _s, _e = _e, _s
            cfg_now = dict(load_config() or {})
            if _s is not None:
                cfg_now["commenter_target_start_date"] = _s.strftime("%Y-%m-%d")
            if _e is not None:
                cfg_now["commenter_target_end_date"] = _e.strftime("%Y-%m-%d")
            cfg_now["commenter_exclude_nicks"] = str(
                st.session_state.get("commenter_exclude_nicks", "") or ""
            )
            cfg_now["commenter_allow_dup_nick"] = bool(
                st.session_state.get("commenter_allow_dup_nick", False)
            )
            save_config(cfg_now)
            config.update(cfg_now)
            st.success("✅ 타겟 수집 설정이 저장되었습니다.")
            time.sleep(1)
            st.rerun()

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        with st.expander("💾 DB 경로 · 댓글 대상 (접기/펼치기)", expanded=False):
            _render_commenter_db_section()

with _col3:
    with st.container(border=True, key="commenter_settings_card_3"):
        render_settings_card_title("댓글 · 실행", icon="💬")
        st.session_state.template_list = load_templates()
        selected_template = st.selectbox(
            "템플릿", st.session_state.template_list, label_visibility="collapsed"
        )
        with st.expander("⚙️ 댓글 설정 접기/펼치기", expanded=True):
            default_text = "" if selected_template == "(직접 입력)" else selected_template
            _tl, _tr = st.columns([1, 1], gap="small")
            with _tl:
                st.markdown(
                    '<p style="margin:0;padding:0.35rem 0 0 0;font-size:1rem;font-weight:600;">댓글 내용 입력</p>',
                    unsafe_allow_html=True,
                )
            with _tr:
                st.markdown(
                    '<p style="margin:0;padding:0.4rem 0 0 0;text-align:right;font-size:0.82rem;'
                    'line-height:1.35;color:#64748b;">{{작성자}} · {{인사}}(댓글마다 랜덤) 치환</p>',
                    unsafe_allow_html=True,
                )
            final_template = st.text_area(
                "댓글 내용 입력",
                value=default_text,
                height=170,
                label_visibility="collapsed",
            )

            if st.button(
                "💾 템플릿 저장",
                use_container_width=True,
                key="commenter_save_template_btn",
                disabled=_commenter_ui_busy(),
            ):
                if final_template.strip():
                    save_new_template(final_template)
                    st.success("저장됨")
                    time.sleep(0.5)
                    st.rerun()

            st.markdown("<div style='height:3px;'></div>", unsafe_allow_html=True)
            st.caption("브라우저·목록 수집은 **아래 실행 제어**에서 하세요.")
            st.caption(
                f"⏱ 댓글 간격: **{COMMENTER_GAP_MIN_SEC}~{COMMENTER_GAP_MAX_SEC}초** 랜덤 · "
                f"세션 **{COMMENTER_SESSION_LIMIT}건** 후 {COMMENTER_SESSION_REST_SEC//60}분 휴식"
            )
            if st.session_state.get("commenter_collecting"):
                st.caption("⏳ **타겟 수집 중**에는 댓글 작성을 시작할 수 없습니다.")

            if st.session_state.get("is_running"):
                if st.button(
                    "⏹ 댓글 작성 중지",
                    type="secondary",
                    use_container_width=True,
                    key="commenter_stop_btn",
                ):
                    st.session_state.commenter_stop_requested = True
                    st.rerun()
            else:
                _collecting = st.session_state.get("commenter_collecting", False)
                _can_start = (
                    (not _collecting)
                    and _commenter_browser_opened()
                    and (st.session_state.target_df is not None)
                    and (not st.session_state.target_df.empty)
                    and bool(final_template.strip())
                )
                if st.button(
                    "🚀 댓글 작성 시작",
                    type="primary",
                    use_container_width=True,
                    disabled=not _can_start,
                    key="commenter_start_btn",
                ):
                    if not st.session_state.commenter or not st.session_state.commenter.driver:
                        st.error("브라우저 미실행")
                    elif (
                        st.session_state.target_df is None
                        or st.session_state.target_df.empty
                    ):
                        st.error(
                            "타겟 없음 — **실행 제어 → 2단계: 타겟 목록 수집**을 먼저 실행해주세요."
                        )
                    elif not final_template.strip():
                        st.error("내용 없음")
                    else:
                        has_lic, lic_limit = CafeMonsterAuthHelper.check_product_license("AutoComment")
                        if not has_lic:
                            used_count = CafeMonsterAuthHelper.get_trial_used_count("AutoComment")
                            if used_count >= 50:
                                st.error("🚫 [체험판 한도 초과] 자동댓글러 무료체험판 한도(50건)를 모두 소진하셨습니다. 정식 라이선스를 등록해 주세요.")
                                st.stop()
                        elif lic_limit is not None and lic_limit > 0:
                            try:
                                conn_chk = sqlite3.connect(COMMENTER_DB_PATH)
                                c_chk = conn_chk.cursor()
                                c_chk.execute("SELECT COUNT(*) FROM commenter_targets WHERE comment_status = 'success'")
                                row = c_chk.fetchone()
                                conn_chk.close()
                                db_cnt = int(row[0]) if row and row[0] is not None else 0
                                if db_cnt >= lic_limit:
                                    st.error(f"🚫 [라이선스 한도 초과] 본 라이선스의 수집/작업 한도({lic_limit}건)를 모두 소진하셨습니다.")
                                    st.stop()
                            except:
                                pass
                        # Piling DB 생성 및 할당
                        from app.utils.paths import generate_new_db_path
                        new_db_path = generate_new_db_path("auto_commenter")
                        st.session_state.active_db_path_commenter = str(new_db_path)
                        init_event_db(str(new_db_path))

                        if st.session_state.get("commenter"):
                            st.session_state.commenter.db_path = str(new_db_path)

                        st.session_state.is_running = True
                        st.session_state.commenter_run_index = 0
                        st.session_state.commenter_stop_requested = False
                        st.session_state._commenter_run_template = final_template.strip()
                        st.toast("댓글 작업을 시작합니다…", icon="🚀")

            # Streamlit 1.39에서 expander + 빈번한 rerun 조합이 removeChild 에러를 유발하는 경우가 있어
            # 미리보기는 단순 토글(checkbox) 방식으로 안정화.
            if final_template.strip():
                _show_preview = st.checkbox("💬 댓글 미리보기", key="commenter_preview_open")
                if _show_preview and not st.session_state.get("is_running"):
                    sample_author = "홍길동"
                    if st.session_state.target_df is not None and not st.session_state.target_df.empty:
                        sample_author = st.session_state.target_df.iloc[0]["nickname"]

                    preview_text = apply_comment_template_placeholders(
                        final_template, sample_author, ""
                    )
                    _body_h = html.escape(str(preview_text))
                    st.markdown(
                        f'<div style="padding:0.65rem 0.85rem;background:#e8f4fc;border-radius:0.45rem;'
                        f'font-size:0.95rem;line-height:1.5;border-left:4px solid #2196f3;">'
                        f"{_body_h}</div>",
                        unsafe_allow_html=True,
                    )
                elif _show_preview:
                    st.caption("작업 진행 중에는 미리보기를 잠시 숨깁니다.")

            # 실시간 로그 콘솔 노출
            if st.session_state.get("comment_logs"):
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                log_content = "\n".join(st.session_state.comment_logs)
                log_html = f"""
                <p style="margin:0 0 4px 0;font-size:0.85rem;font-weight:600;color:#475569;">📋 실시간 작업 로그</p>
                <div style="
                    background-color: #0f172a;
                    color: #38bdf8;
                    font-family: 'Courier New', Courier, monospace;
                    font-size: 0.8rem;
                    padding: 8px;
                    border-radius: 6px;
                    height: 160px;
                    overflow-y: auto;
                    white-space: pre-wrap;
                    border: 1px solid #334155;
                ">{html.escape(log_content)}</div>
                """
                st.markdown(log_html, unsafe_allow_html=True)

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
# 실제 write_comment 루프는 파일 하단(표·메트릭 아래)에서 실행 →
# 여기서 먼저 표가 그려지므로 직전까지 댓글결과가 보입니다.
with st.container(key="commenter_running_progress_area"):
    if st.session_state.get("is_running") and not st.session_state.get("commenter_stop_requested"):
        _early_df = st.session_state.get("target_df")
        if _early_df is not None and not getattr(_early_df, "empty", True):
            _e_idx = int(st.session_state.get("commenter_run_index") or 0)
            _e_total = len(_early_df)
            st.warning(
                "⏳ **댓글 작업 실행 중**입니다. 글 한 편을 처리하는 동안 Streamlit이 **전체를 잠시 흐릿하게** 덮을 수 있습니다. "
                "**정지된 것이 아닙니다.** 중지는 위 **⏹ 댓글 작성 중지**."
            )
            st.progress(min(1.0, _e_idx / max(1, _e_total)))
            st.caption(
                f"**{_e_idx + 1}** / {_e_total} 번째 처리 중·대기. 아래 표 **`댓글결과`**는 **끝난 글만** 채워집니다. "
                "목록은 날짜순이라 **위 행이 빈칸**이어도 됩니다. **상단 성공/실패 숫자·열 검색**을 활용하세요."
            )

st.markdown(
    """
    <style>
    div.st-key-commenter_exec_btns button {
        padding-top: 0.4rem !important;
        padding-bottom: 0.4rem !important;
        min-height: 2.4rem !important;
    }
    div.st-key-commenter_dm_metrics div[data-testid="stMetricContainer"] {
        padding: 0.2rem 0 0.05rem 0 !important;
        min-height: unset !important;
    }
    div.st-key-commenter_dm_metrics [data-testid="stMetricValue"] {
        font-size: 1.45rem !important;
    }
    div.st-key-commenter_dm_metrics [data-testid="stMetricLabel"] {
        margin-bottom: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<hr class='commenter-tight-hr' style='border:none;border-top:1px solid #e2e8f0;margin:0.25rem 0 0.4rem 0;'/>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="margin:0;font-size:1.02rem;font-weight:600;line-height:1.25;">🚀 실행 제어</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="margin:0.15rem 0 0.4rem 0;font-size:0.8rem;color:#64748b;line-height:1.35;">'
    "1단계 브라우저 → 2단계 목록 수집. 왼쪽 게시판·가운데 <strong>💾 저장</strong> 후 진행."
    "</p>",
    unsafe_allow_html=True,
)
_commenter_crw = st.session_state.get("commenter")
commenter_browser_opened = bool(
    _commenter_crw is not None and getattr(_commenter_crw, "driver", None) is not None
)
_has_targets_now = bool(st.session_state.get("target_df") is not None and not st.session_state.target_df.empty)

if st.session_state.get("commenter_selected_board_urls"):
    st.session_state._commenter_collect_warning = None

if st.session_state.get("is_running", False):
    st.info("현재 단계: 댓글 작성 중 — 중지는 오른쪽 카드의 **⏹ 댓글 작성 중지** 버튼")
elif st.session_state.get("commenter_collecting", False):
    st.info("현재 단계: 타겟 수집 중 — 수집 완료 후 댓글 작성 시작이 자동으로 활성화됩니다.")
    _prog_val = st.session_state.get("commenter_collect_progress", 0.0)
    _status_txt = st.session_state.get("commenter_collect_status_text", "수집 중…")
    st.progress(_prog_val)
    st.caption(f"📊 {_status_txt}")
elif not commenter_browser_opened:
    st.info("현재 단계: 대기 — **1단계 브라우저 열기**부터 진행하세요.")
elif not _has_targets_now:
    st.info("현재 단계: 브라우저 준비 완료 — 다음은 **2단계: 타겟 목록 수집**입니다.")
else:
    st.success("현재 단계: 작성 준비 완료 — 템플릿 확인 후 **🚀 댓글 작성 시작**을 누르세요.")

_collect_warn = st.session_state.get("_commenter_collect_warning")
if _collect_warn:
    st.warning(_collect_warn)

if st.session_state.get("_commenter_collect_info_msg"):
    st.info(st.session_state.pop("_commenter_collect_info_msg"))
if st.session_state.get("_commenter_collect_warn_msg"):
    st.warning(st.session_state.pop("_commenter_collect_warn_msg"))
if st.session_state.get("_commenter_collect_success_msg"):
    st.success(st.session_state.pop("_commenter_collect_success_msg"))
if st.session_state.get("_commenter_collect_error_msg"):
    st.error(st.session_state.pop("_commenter_collect_error_msg"))
with st.container(key="commenter_exec_btns"):
    step_c1, step_c2 = st.columns(2, gap="small")
    with step_c1:
        if st.button(
            "1단계: 브라우저 열기",
            use_container_width=True,
            disabled=commenter_browser_opened or _commenter_ui_busy(),
            type="primary" if not commenter_browser_opened else "secondary",
            key="commenter_open_browser_btn",
        ):
            try:
                if not st.session_state.commenter:
                    st.session_state.commenter = NaverCafeCommenter(
                        db_path=COMMENTER_DB_PATH, debug_mode=True
                    )
                st.session_state.commenter.start_browser()
                st.success("브라우저 실행됨")
            except Exception as e:
                st.error(f"브라우저 열기 실패: {e}")
                st.stop()
            try:
                _ev_auto_on = bool(
                    st.session_state.get(
                        "commenter_auto_login_enabled_input", config.get("commenter_auto_login_enabled", True)
                    )
                )
                _ev_login_id = str(
                    st.session_state.get("commenter_naver_id_input", config.get("commenter_naver_id", "")) or ""
                ).strip()
                _ev_login_pw = str(
                    st.session_state.get("commenter_naver_pw_input", config.get("commenter_naver_pw", "")) or ""
                )
                if _ev_auto_on and _ev_login_id and _ev_login_pw:
                    login_ok, reason = auto_login_naver_with_js(
                        st.session_state.commenter, _ev_login_id, _ev_login_pw
                    )
                    if login_ok:
                        st.success(f"자동로그인 성공 ({reason})")
                    else:
                        st.warning(f"자동로그인 실패: {reason} — 수동 로그인해주세요.")
                elif _ev_auto_on:
                    st.warning("자동로그인을 쓰려면 아이디/비밀번호를 입력·저장해주세요.")
            except Exception as _login_err:
                st.warning(f"자동로그인 처리 중 오류: {_login_err}")
            st.rerun()
    with step_c2:
        _step2_blocked = (
            (not commenter_browser_opened)
            or st.session_state.get("commenter_collecting", False)
            or st.session_state.get("is_running", False)
        )
        _step2_help = (
            "1단계로 브라우저를 먼저 열고, 선택한 게시판·수집 기간 저장 후 진행합니다. "
            "(이전처럼 눌러도 반응 없으면 앱 새로고침 한 번 후 다시 시도해 주세요.)"
        )
        if st.button(
            "2단계: 타겟 목록 수집",
            use_container_width=True,
            disabled=_step2_blocked,
            type="primary" if commenter_browser_opened and not _step2_blocked else "secondary",
            key="commenter_target_collect_step2_btn",
            help=_step2_help,
        ):
            if st.session_state.get("is_running", False):
                st.warning("댓글 작업 진행 중에는 2단계 수집을 시작할 수 없습니다.")
            else:
                _collect_commenter_targets_into_session()
                st.rerun()


st.markdown(
    "<hr style='border:none;border-top:1px solid #e2e8f0;margin:0.35rem 0 0.35rem 0;'/>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="margin:0;font-size:1.02rem;font-weight:600;line-height:1.25;">📊 데이터 관리</p>',
    unsafe_allow_html=True,
)
_ds_rng, _de_rng = _commenter_normalized_target_range()
_period_line = "—"
if _ds_rng and _de_rng:
    _period_line = f"{_ds_rng.strftime('%Y-%m-%d')} ~ {_de_rng.strftime('%Y-%m-%d')}"
_n_boards_dm = len(st.session_state.get("commenter_selected_board_urls") or [])
st.markdown(
    f'<p style="margin:0.1rem 0 0.35rem 0;font-size:0.78rem;color:#64748b;line-height:1.35;">'
    f"🗓️ 표시 기간: {_period_line} &nbsp;·&nbsp; 📋 선택 게시판: {_n_boards_dm}개"
    f"</p>",
    unsafe_allow_html=True,
)
_tgt_n_dm = (
    0
    if st.session_state.target_df is None or st.session_state.target_df.empty
    else len(st.session_state.target_df)
)
_fd_stat = _commenter_full_dataframe()
_n_c_ok = _n_c_fail = _n_c_pending = 0
if _fd_stat is not None and not _fd_stat.empty:
    _commenter_ensure_comment_cols(_fd_stat)
    _cs_stat = _fd_stat["comment_status"].fillna("").astype(str).str.strip().str.lower()
    _n_c_ok = int((_cs_stat == "success").sum())
    _n_c_fail = int((_cs_stat == "fail").sum())
    _n_c_pending = int((_cs_stat == "").sum())
with st.container(key="commenter_dm_metrics"):
    _dm1, _dm2, _dm3 = st.columns(3, gap="small")
    with _dm1:
        st.metric("타겟 글", f"{_tgt_n_dm}건")
    with _dm2:
        st.metric("브라우저", "연결됨" if commenter_browser_opened else "미연결")
    with _dm3:
        st.metric("선택 게시판", f"{_n_boards_dm}개")
st.caption(
    f"댓글 시도 기록(전체 스냅샷): 성공 **{_n_c_ok}** · 실패 **{_n_c_fail}** · 미시도 **{_n_c_pending}**"
)

st.markdown(
    "<hr style='border:none;border-top:1px solid #e2e8f0;margin:0.35rem 0 0.4rem 0;'/>",
    unsafe_allow_html=True,
)
with st.container(border=True, key="commenter_target_table_box"):
    st.caption(f"DB: `{COMMENTER_DB_PATH}`")
    st.markdown(
        '<p style="margin:0 0 0.35rem 0;font-size:1.05rem;font-weight:600;">📋 타겟 목록</p>',
        unsafe_allow_html=True,
    )
    _full_snap = st.session_state.commenter_target_df_full
    _has_snap = _full_snap is not None and not getattr(_full_snap, "empty", True)
    _dm_row = st.columns([1.05, 1.15, 1.15, 0.52, 0.52], gap="small")
    with _dm_row[0]:
        _dm_ud = st.checkbox(
            "작성일 적용",
            key="commenter_dm_use_date_filter",
            disabled=not _has_snap,
        )
    with _dm_row[1]:
        st.date_input(
            "시작",
            key="commenter_dm_f_start",
            disabled=not _has_snap or not _dm_ud,
        )
    with _dm_row[2]:
        st.date_input(
            "끝",
            key="commenter_dm_f_end",
            disabled=not _has_snap or not _dm_ud,
        )
    with _dm_row[3]:
        if st.button(
            "적용",
            use_container_width=True,
            disabled=_commenter_ui_busy() or not _has_snap,
            key="commenter_dm_apply_btn",
        ):
            base = st.session_state.commenter_target_df_full
            if base is None or getattr(base, "empty", True):
                st.warning(
                    "목록 스냅샷이 비어 있습니다. **2단계 타겟 수집**을 다시 실행하거나 새로고침해 보세요 "
                    "(DB에 데이터가 있으면 다음 실행 때 자동 복구됩니다)."
                )
            else:
                _go_ud = bool(st.session_state.get("commenter_dm_use_date_filter"))
                out = _commenter_filter_targets_by_post_date(
                    base,
                    use_date=_go_ud,
                    d_start=st.session_state.get("commenter_dm_f_start"),
                    d_end=st.session_state.get("commenter_dm_f_end"),
                )
                if _go_ud and out.empty:
                    st.warning("해당 작성일 구간에 행이 없습니다.")
                else:
                    st.session_state.target_df = out
            st.rerun()
    with _dm_row[4]:
        if st.button(
            "전체",
            use_container_width=True,
            disabled=_commenter_ui_busy() or not _has_snap,
            key="commenter_dm_show_all_btn",
        ):
            if st.session_state.commenter_target_df_full is not None:
                st.session_state.target_df = st.session_state.commenter_target_df_full.copy()
            st.rerun()

    if st.session_state.target_df is not None and not st.session_state.target_df.empty:
        _commenter_ensure_comment_cols(st.session_state.target_df)
        _show_df = st.session_state.target_df.copy()
        if "nickname" in _show_df.columns:
            _show_df["nickname"] = _show_df["nickname"].map(
                lambda x: sanitize_commenter_nickname(str(x))
            )
        _pref_order = [
            "comment_status",
            "comment_detail",
            "date",
            "nickname",
            "title",
            "board_name",
            "url",
            "post_id",
        ]
        _cols_show = [c for c in _pref_order if c in _show_df.columns] + [
            c for c in _show_df.columns if c not in _pref_order
        ]
        _show_df = _show_df[_cols_show]
        st.dataframe(
            _show_df,
            use_container_width=True,
            height=420,
            key="commenter_target_dataframe",
            column_config={
                "url": st.column_config.LinkColumn("링크", display_text="🔗", width="small"),
                "date": "작성일",
                "nickname": "작성자",
                "title": "제목",
                "board_name": "게시판",
                "comment_status": st.column_config.TextColumn(
                    "댓글결과", width="small", help="success / fail / 빈칸=미시도"
                ),
                "comment_detail": st.column_config.TextColumn("결과 메시지", width="medium"),
            },
        )
    else:
        st.info(
            "위 **타겟 수집 설정**을 저장한 뒤 **실행 제어 → 2단계**를 실행하면 수집된 글이 여기 표에 나타납니다."
        )

def _check_and_increment_limits():
    has_lic, lic_limit = CafeMonsterAuthHelper.check_product_license("AutoComment")
    if not has_lic:
        used_count = CafeMonsterAuthHelper.get_trial_used_count("AutoComment")
        new_count = used_count + 1
        CafeMonsterAuthHelper.save_trial_used_count("AutoComment", new_count)
        if new_count >= 50:
            _commenter_reset_run_state()
            log_msg("🚫 무료체험판 작업 한도(50건)에 도달하여 댓글 작성을 안전하게 중단합니다.")
            st.rerun()
    elif lic_limit is not None and lic_limit > 0:
        try:
            active_db = st.session_state.get("active_db_path_commenter", COMMENTER_DB_PATH)
            conn_chk = sqlite3.connect(active_db)
            c_chk = conn_chk.cursor()
            c_chk.execute("SELECT COUNT(*) FROM commenter_targets WHERE comment_status = 'success'")
            row = c_chk.fetchone()
            conn_chk.close()
            db_cnt = int(row[0]) if row and row[0] is not None else 0
            if db_cnt >= lic_limit:
                _commenter_reset_run_state()
                log_msg(f"🚫 라이선스 수집/작업 한도({lic_limit}건)에 도달하여 작업을 안전하게 중단합니다.")
                st.rerun()
        except:
            pass

if st.session_state.get("is_running", False):
    if st.session_state.get("commenter_stop_requested"):
        st.warning(
            "⏹ 댓글 작업을 **중지**했습니다. (이미 처리한 글·실패한 건은 그대로이며, 타겟 목록은 DB에서 다시 불러올 수 있습니다.)"
        )
        _commenter_reset_run_state()
    else:
        _df_run = st.session_state.target_df
        if _df_run is None or _df_run.empty:
            st.error("타겟이 없습니다. 작업을 중단합니다.")
            _commenter_reset_run_state()
        elif not st.session_state.commenter or not st.session_state.commenter.driver:
            st.error("브라우저가 연결되어 있지 않습니다.")
            _commenter_reset_run_state()
        else:
            targets = _df_run.to_dict("records")
            total = len(targets)
            idx = int(st.session_state.get("commenter_run_index") or 0)
            _tpl = (st.session_state.get("_commenter_run_template") or "").strip()
            if not _tpl:
                st.error("댓글 템플릿이 비어 있습니다. 다시 시작해주세요.")
                _commenter_reset_run_state()
            elif idx >= total:
                _commenter_reset_run_state()
                st.session_state._commenter_finished_ok = True
                st.rerun()
            else:
                row = targets[idx]

                # 이미 성공한 건은 패스
                _prev_status = str(row.get("댓글결과") or row.get("comment_status") or "").strip().lower()
                if _prev_status == "success":
                    log_msg(f"[{idx + 1}/{total}] 이미 성공 → 건너뜀")
                    st.session_state.commenter_run_index = idx + 1
                    st.rerun()

                try:
                    if idx == 0:
                        print(
                            f"[commenter] 댓글 작업 시작: {total}건, DB={COMMENTER_DB_PATH}",
                            flush=True,
                        )
                        log_msg(f"총 {total}개 글에 작업을 시작합니다.")
                    log_msg(
                        f"[{idx + 1}/{total}] '{row['title']}' ({sanitize_commenter_nickname(str(row.get('nickname') or ''))}) 방문 중..."
                    )
                    _nick_run = sanitize_commenter_nickname(str(row.get("nickname") or ""))
                    res = st.session_state.commenter.write_comment(
                        article_url=row["url"],
                        template=_tpl,
                        nickname=_nick_run,
                        title=str(row.get("title") or ""),
                    )
                    _u_short = str(row.get("url") or "")[:110]
                    print(
                        f"[commenter] [{idx + 1}/{total}] {res['status']}: {res.get('message', '')} | {_u_short}",
                        flush=True,
                    )
                    try:
                        _n_up = update_commenter_target_comment_status(
                            COMMENTER_DB_PATH,
                            str(row.get("url") or ""),
                            res["status"],
                            str(res.get("message") or ""),
                        )
                        if _n_up == 0:
                            print(
                                f"[commenter] WARNING: DB에 해당 URL 없어 결과 미저장(rowcount=0). "
                                f"2단계 수집 직후인지 확인. url={_u_short}",
                                flush=True,
                            )
                            log_msg("⚠️ DB에 URL 없음 — 결과가 스냅샷에 반영되지 않았을 수 있음")
                    except Exception as _db_e:
                        print(
                            f"[commenter] DB 결과 저장 실패: {_db_e} url={_u_short}",
                            flush=True,
                        )
                        log_msg(f"⚠️ DB 저장 오류: {_db_e}")
                    _commenter_apply_comment_result(
                        str(row.get("url") or ""),
                        res["status"],
                        str(res.get("message") or ""),
                    )
                    if res["status"] == "success":
                        log_msg("✅ 작성 성공")
                        _check_and_increment_limits()
                    else:
                        log_msg(f"❌ 실패: {res['message']}")
                    st.session_state.commenter_run_index = idx + 1

                    # 세션 한도 체크
                    _done_count = idx + 1
                    if _done_count >= total:
                        _commenter_reset_run_state()
                        st.session_state._commenter_finished_ok = True
                        st.rerun()
                    elif _done_count % COMMENTER_SESSION_LIMIT == 0:
                        _rest_min = COMMENTER_SESSION_REST_SEC // 60
                        log_msg(f"⏸ 세션 {_done_count}건 완료. {_rest_min}분 휴식 시작...")
                        print(f"[commenter] 세션 한도 도달 ({COMMENTER_SESSION_LIMIT}건). {_rest_min}분 휴식.", flush=True)
                        time.sleep(COMMENTER_SESSION_REST_SEC)
                        log_msg(f"▶ 휴식 종료. 재개합니다.")
                        st.rerun()
                    else:
                        _gap = random.uniform(COMMENTER_GAP_MIN_SEC, COMMENTER_GAP_MAX_SEC)
                        time.sleep(_gap)
                        st.rerun()
                except Exception as e:
                    st.error(f"작업 중 오류: {e}")
                    st.code(traceback.format_exc())
                    print(f"[commenter] 오류: {e}\n{traceback.format_exc()}", flush=True)
                    _commenter_reset_run_state()

st.markdown(
    "<hr style='border:none;border-top:1px solid #e2e8f0;margin:0.3rem 0 0.4rem 0;'/>",
    unsafe_allow_html=True,
)

if st.session_state.get("commenter_collecting", False):
    time.sleep(1.0)
    st.rerun()
