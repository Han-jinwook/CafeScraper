import html
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import os
import sys
import time
import random
import json
import re
from pathlib import Path
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, get_logs_dir, get_project_root, resolve_db_path
from app.utils.streamlit_input_history import inject_connect_history_suggestions
from app.utils.streamlit_brand import render_logo_png
from app.utils.streamlit_top_nav import render_main_top_nav, render_settings_card_title
from app.utils.naver_login import (
    _has_naver_login_cookie,
    _is_captcha_like_page,
    auto_login_naver_with_js as _auto_login_naver_with_js,
)
from selenium.webdriver.common.by import By
import shutil

# 페이지 설정
st.set_page_config(
    page_title="[카페 몬스터] 카페 추출기 Pro V1.0",
    page_icon="☕",
    layout="wide",
)

# 커스텀 CSS: 판매용 UI 톤 정리(기능 영향 없음)
st.markdown("""
<style>
    /* 사이드바 완전 숨김 */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* 본문 가로폭·패딩: render_main_top_nav()가 `.block-container`로 전 페이지 통일 */

    /* 제목/소제목 간격 정리 */
    h1, h2, h3 {
        letter-spacing: -0.01em;
    }
    h2 {
        margin-top: 0.2rem !important;
        margin-bottom: 0.35rem !important;
    }
    h3 {
        margin-top: 0.8rem !important;
        margin-bottom: 0.35rem !important;
    }

    /* 구분선 톤 다운 */
    hr {
        margin: 0.45rem 0 0.55rem 0 !important;
        border-color: #e7e9ef !important;
    }

    /* metric 카드 안정감 */
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #f8fbff 0%, #f3f7fc 100%);
        border: 1px solid #dbe5f2;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        min-height: 110px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    /* 항목(라벨)과 데이터(값) 시각 분리 */
    div[data-testid="stMetricLabel"] p {
        font-size: 0.86rem !important;
        color: #64748b !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        line-height: 1.2 !important;
        color: #0f172a !important;
        font-weight: 800 !important;
    }
    /* 긴 시간 텍스트도 말줄임(...) 없이 보이게 */
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        word-break: keep-all !important;
    }

    /* 버튼 통일 */
    div.stButton > button {
        min-height: 42px;
        border-radius: 9px;
        font-weight: 600;
    }

    /* 탭 헤더 균형 */
    button[data-baseweb="tab"] {
        font-weight: 600;
    }

    /* 에디터/테이블 외곽 정리 */
    div[data-testid="stDataFrame"],
    div[data-testid="stDataEditor"] {
        border: 1px solid #e5e8ee;
        border-radius: 10px;
        overflow: hidden;
    }

    /* 게시글/댓글 테이블 스크롤바: 두껍게 + 상시 노출 */
    div[data-testid="stDataFrame"] [style*="overflow"],
    div[data-testid="stDataEditor"] [style*="overflow"] {
        overflow: scroll !important;
        scrollbar-gutter: stable both-edges;
        scrollbar-width: auto;
        scrollbar-color: #9aa4b2 #eef2f7;
    }
    div[data-testid="stDataFrame"] *::-webkit-scrollbar,
    div[data-testid="stDataEditor"] *::-webkit-scrollbar {
        width: 14px;
        height: 14px;
    }
    div[data-testid="stDataFrame"] *::-webkit-scrollbar-thumb,
    div[data-testid="stDataEditor"] *::-webkit-scrollbar-thumb {
        background: #9aa4b2;
        border-radius: 999px;
        border: 3px solid #eef2f7;
    }
    div[data-testid="stDataFrame"] *::-webkit-scrollbar-track,
    div[data-testid="stDataEditor"] *::-webkit-scrollbar-track {
        background: #eef2f7;
        border-radius: 999px;
    }
    div[data-testid="stDataFrame"] *::-webkit-scrollbar-corner,
    div[data-testid="stDataEditor"] *::-webkit-scrollbar-corner {
        background: #eef2f7;
    }

    /* 게시글 선택 행 하이라이트 (지원 브라우저에서 :has 동작) */
    div[data-testid="stDataEditor"] [role="row"]:has(input[type="checkbox"]:checked) {
        background-color: #fff6cf !important;
    }
    div[data-testid="stDataEditor"] [role="row"]:has(input[type="checkbox"]:checked) [role="gridcell"] {
        background-color: #fff6cf !important;
    }
    /* data_editor DOM 변형 대응: 체크된 셀 + 같은 행의 뒤쪽 셀 하이라이트 */
    div[data-testid="stDataEditor"] [role="gridcell"]:has(input[type="checkbox"]:checked),
    div[data-testid="stDataEditor"] [role="gridcell"]:has(input[type="checkbox"]:checked) ~ [role="gridcell"] {
        background-color: #fff2b3 !important;
    }
    /* streamlit 1.39 계열 체크박스(aria-checked) 대응 */
    div[data-testid="stDataEditor"] [role="row"]:has([aria-checked="true"]) {
        background-color: #fff2b3 !important;
    }
    div[data-testid="stDataEditor"] [role="row"]:has([aria-checked="true"]) [role="gridcell"] {
        background-color: #fff2b3 !important;
    }
    div[data-testid="stDataEditor"] [role="gridcell"]:has([aria-checked="true"]),
    div[data-testid="stDataEditor"] [role="gridcell"]:has([aria-checked="true"]) ~ [role="gridcell"] {
        background-color: #fff2b3 !important;
    }

    /* 선택 컬럼(첫 번째 헤더) 아이콘/텍스트 완전 숨김 */
    div[data-testid="stDataEditor"] [role="columnheader"]:first-child * {
        display: none !important;
    }
    /* 선택 컬럼(첫 번째 열) 폭 최소화 */
    div[data-testid="stDataEditor"] [role="columnheader"]:first-child,
    div[data-testid="stDataEditor"] [role="row"] [role="gridcell"]:first-child {
        min-width: 28px !important;
        width: 28px !important;
        max-width: 28px !important;
        padding-left: 2px !important;
        padding-right: 2px !important;
    }
    /* aria-colindex 기반으로도 동일 강제 (렌더러 차이 대응) */
    div[data-testid="stDataEditor"] [role="columnheader"][aria-colindex="1"],
    div[data-testid="stDataEditor"] [role="row"] [role="gridcell"][aria-colindex="1"] {
        min-width: 28px !important;
        width: 28px !important;
        max-width: 28px !important;
        padding-left: 2px !important;
        padding-right: 2px !important;
    }
    div[data-testid="stDataEditor"] input[type="checkbox"] {
        margin: 0 auto !important;
    }
    /* 체크 시 생기는 셀 포커스 사각 테두리 제거 */
    div[data-testid="stDataEditor"] [role="gridcell"][aria-selected="true"],
    div[data-testid="stDataEditor"] [role="gridcell"]:focus,
    div[data-testid="stDataEditor"] [role="gridcell"]:focus-within,
    div[data-testid="stDataEditor"] [role="columnheader"][aria-selected="true"],
    div[data-testid="stDataEditor"] [role="columnheader"]:focus,
    div[data-testid="stDataEditor"] [role="columnheader"]:focus-within {
        outline: none !important;
        box-shadow: none !important;
        border-color: transparent !important;
    }

    /* expander/사이드바 카드 톤 */
    div[data-testid="stExpander"] {
        border: 1px solid #e6e8ef;
        border-radius: 10px;
    }

    /* selectbox 전체에 포인터 커서 */
    div[data-baseweb="select"] > div {
        cursor: pointer !important;
    }

    /* 드롭다운 화살표 아이콘에 포인터 커서 */
    div[data-baseweb="select"] svg {
        cursor: pointer !important;
    }

    /* hover 시 배경색 변경 */
    div[data-baseweb="select"]:hover > div {
        background-color: #f0f2f6 !important;
        transition: background-color 0.2s ease;
    }

    /* 실행 중 중단 버튼(빨간색 강조) */
    .st-key-stop_crawl_btn button {
        background-color: #dc2626 !important;
        color: #ffffff !important;
        border-color: #dc2626 !important;
    }
    .st-key-stop_crawl_btn button:hover {
        background-color: #b91c1c !important;
        border-color: #b91c1c !important;
    }
</style>
""", unsafe_allow_html=True)

# 프로젝트 루트 기준 경로 고정 (실행 위치가 달라도 DB/설정이 안 갈라지게)
PROJECT_ROOT = get_project_root()
CONFIG_PATH = str(get_config_path())

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()
# 상단 표시에 사용할 카페명 (없으면 기본값)
DISPLAY_CAFE_NAME = str(config.get("cafe_name", "카페 몬스터") or "").strip() or "카페 몬스터"
# DB 경로는 설정/환경변수로 변경 가능
DB_PATH = str(resolve_db_path(config.get("db_path")))
CRAWL_CHECKPOINT_PATH = os.path.join(str(get_logs_dir()), "crawl_checkpoint.json")
CRAWL_CHECKPOINT_VERSION = 1
CRAWL_CHECKPOINT_SAVE_EVERY_ITEMS = 5

# 기존 DB가 있어도 CREATE TABLE IF NOT EXISTS는 안전하므로 항상 보장
init_db(DB_PATH)

def save_to_sqlite(post_data: dict, comments: list, replace_comments: bool = True):
    """SQLite에 게시글 및 댓글 저장 (timeout 및 재시도 추가)"""
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            # timeout 30초로 증가 (잠금 해제 대기)
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()
            # 안전장치: 등급이 비어 있으면 기본값을 '탈퇴'로 저장
            member_level_value = str(post_data.get("member_level", "") or "").strip() or "탈퇴"
            
            # 1. 게시글 저장 (Upsert)
            cursor.execute('''
                INSERT OR REPLACE INTO posts (
                    post_id, member_id, nickname, title, content, date, board_name, category, view_count, like_count, url, member_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_data['post_id'],
                post_data.get('member_id', 'unknown'),
                post_data['nickname'],
                post_data['title'],
                post_data['content'],
                post_data['date'],
                post_data.get('board_name', ''),
                post_data.get('category', ''),
                int(post_data.get('view_count', 0) or 0),
                int(post_data.get('like_count', 0) or 0),
                post_data['url'],
                member_level_value,
            ))
            
            # 2. 댓글 저장 (재실행/업데이트 시 중복 방지 옵션)
            if replace_comments:
                cursor.execute("DELETE FROM comments WHERE post_id = ?", (post_data["post_id"],))
            for comment in comments:
                cursor.execute('''
                    INSERT INTO comments (post_id, writer_id, nickname, content, is_target)
                    VALUES (?, ?, ?, ?, ?)
                ''', (post_data['post_id'], comment.get('writer_id', 'unknown'), 
                      comment['nickname'], comment['content'], comment.get('is_target', 0)))
                
            conn.commit()
            conn.close()
            return  # 성공하면 종료
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # 지수 백오프
                continue
            else:
                raise  # 마지막 시도 실패 시 예외 발생
        finally:
            try:
                conn.close()
            except:
                pass

# 세션 상태 초기화
if "crawler" not in st.session_state:
    st.session_state.crawler = None
if "status_messages" not in st.session_state:
    st.session_state.status_messages = []
if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False  # 기본은 프로덕션 모드
if "crawl_running" not in st.session_state:
    st.session_state.crawl_running = False
if "crawl_stop_requested" not in st.session_state:
    st.session_state.crawl_stop_requested = False
if "crawl_state" not in st.session_state:
    st.session_state.crawl_state = {}
if "crawl_checkpoint_available" not in st.session_state:
    st.session_state.crawl_checkpoint_available = False
if "crawl_checkpoint_bootstrapped" not in st.session_state:
    st.session_state.crawl_checkpoint_bootstrapped = False
if "crawl_checkpoint_last_index" not in st.session_state:
    st.session_state.crawl_checkpoint_last_index = -1
if "crawl_last_status_message" not in st.session_state:
    st.session_state.crawl_last_status_message = ""
if "crawl_last_status_type" not in st.session_state:
    st.session_state.crawl_last_status_type = "info"
if "login_confirmed" not in st.session_state:
    st.session_state.login_confirmed = False


st.markdown("""
<style>
    /* 로그 영역 스타일 개선 - 박스 제거 및 폰트 조정 */
    textarea[disabled] {
        background-color: transparent !important;
        border: none !important;
        color: #5a5f6a !important;
        font-family: Consolas, monospace;
        font-size: 0.88em;
        padding: 0 !important;
        resize: none;
    }
</style>
""", unsafe_allow_html=True)

# 실시간 로그 출력을 위한 placeholder (사이드바 아래 또는 메인에 배치)
# log_placeholder = st.empty()

def update_logs(msg=None):
    if msg:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {msg}"
        st.session_state.status_messages.append(log_entry)
        
        # 로그를 파일로도 저장 (영구 보관)
        log_dir = str(get_logs_dir())
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"crawler_{datetime.now().strftime('%Y%m%d')}.log")
        
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except:
            pass
    
    # 안정적인 로그 업데이트 (에러 방지)
    # try:
    #     # 최근 20개 로그만 표시 - 제목 없이 깔끔하게 텍스트만
    #     recent_logs = "\n".join(reversed(st.session_state.status_messages[-20:]))
    #     log_placeholder.text_area("", recent_logs, height=300, label_visibility="collapsed", disabled=True)
    # except:
    #     pass  # UI 에러 무시


def _serialize_crawl_state(state: dict) -> dict:
    out = dict(state or {})
    if isinstance(out.get("existing_ids"), set):
        out["existing_ids"] = list(out["existing_ids"])
    # existing_map은 크기가 클 수 있으므로 체크포인트 파일에는 저장하지 않고(재시작 시 DB에서 다시 로드)
    # 메모리에서만 유지하거나, 필요시 최소한으로 저장. 
    # 여기서는 파일 용량 문제로 제외하고, 재개 시 prepare 단계가 아니면 DB에서 다시 읽도록 유도하는 게 안전하지만,
    # 구조상 'run' 단계에서 재개하므로 DB 로드 로직을 복구 단계에 추가해야 함.
    # 일단은 호환성을 위해 existing_map은 제거하고 저장.
    if "existing_map" in out:
        del out["existing_map"]
    
    if isinstance(out.get("start_dt"), datetime):
        out["start_dt"] = out["start_dt"].isoformat()
    if isinstance(out.get("end_dt"), datetime):
        out["end_dt"] = out["end_dt"].isoformat()
    return out


def _deserialize_crawl_state(state: dict) -> dict:
    out = dict(state or {})
    if isinstance(out.get("existing_ids"), list):
        out["existing_ids"] = set(out["existing_ids"])
    # 재개 시 existing_map이 없으면 DB에서 복구
    if out.get("phase") == "run" and "existing_map" not in out:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            df_exist = pd.read_sql_query("SELECT post_id, member_level FROM posts", conn)
            out["existing_map"] = df_exist.set_index('post_id')['member_level'].to_dict()
            conn.close()
        except:
            out["existing_map"] = {}
            
    if isinstance(out.get("start_dt"), str):
        try:
            out["start_dt"] = datetime.fromisoformat(out["start_dt"])
        except:
            pass
    if isinstance(out.get("end_dt"), str):
        try:
            out["end_dt"] = datetime.fromisoformat(out["end_dt"])
        except:
            pass
    return out


def _save_crawl_checkpoint(force: bool = False):
    try:
        state = st.session_state.get("crawl_state", {}) or {}
        phase = str(state.get("phase", ""))
        idx = int(state.get("index", -1)) if isinstance(state.get("index", -1), (int, float)) else -1
        last_idx = int(st.session_state.get("crawl_checkpoint_last_index", -1))

        # 지나치게 잦은 디스크 쓰기를 피하기 위해 N건마다 저장 (중단/시작 등은 force=True)
        if (not force) and phase == "run" and idx >= 0 and (idx - last_idx) < CRAWL_CHECKPOINT_SAVE_EVERY_ITEMS:
            return

        os.makedirs(os.path.dirname(CRAWL_CHECKPOINT_PATH), exist_ok=True)
        payload = {
            "version": CRAWL_CHECKPOINT_VERSION,
            "saved_at": datetime.now().isoformat(),
            "crawl_state": _serialize_crawl_state(state),
        }
        with open(CRAWL_CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        st.session_state.crawl_checkpoint_available = True
        st.session_state.crawl_checkpoint_last_index = idx
    except Exception as e:
        update_logs(f"⚠️ 체크포인트 저장 실패: {e}")


def _load_crawl_checkpoint() -> dict:
    try:
        if not os.path.exists(CRAWL_CHECKPOINT_PATH):
            return {}
        with open(CRAWL_CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        file_ver = int(payload.get("version", 0) or 0)
        # 버전이 없거나 높아도(미래 버전) 안전하게 로드 시도
        if file_ver > CRAWL_CHECKPOINT_VERSION:
            return {}
        return _deserialize_crawl_state(payload.get("crawl_state", {}))
    except Exception:
        # 손상된 체크포인트는 백업 후 무시
        try:
            if os.path.exists(CRAWL_CHECKPOINT_PATH):
                broken_path = CRAWL_CHECKPOINT_PATH + f".broken_{int(time.time())}"
                os.replace(CRAWL_CHECKPOINT_PATH, broken_path)
        except:
            pass
        return {}


def _clear_crawl_checkpoint():
    try:
        if os.path.exists(CRAWL_CHECKPOINT_PATH):
            os.remove(CRAWL_CHECKPOINT_PATH)
    except:
        pass
    st.session_state.crawl_checkpoint_available = False
    st.session_state.crawl_checkpoint_last_index = -1


def _build_run_signature(
    board_url: str,
    start_date_value,
    end_date_value,
    exclude_boards_raw: str,
    level_backfill_mode: bool,
    quick_recovery_mode: bool,
    delay_min_sec: int,
    delay_max_sec: int,
    speed_profile: str,
    start_page_manual: int,
    auto_start_page: bool = True,
) -> dict:
    excludes = sorted(
        set(
            x.strip()
            for x in (exclude_boards_raw or "").splitlines()
            if x.strip()
        )
    )
    return {
        "board_url": (board_url or "").strip(),
        "start_date": str(start_date_value),
        "end_date": str(end_date_value),
        "exclude_boards": "|".join(excludes),
        "level_backfill_mode": bool(level_backfill_mode),
        "quick_recovery_mode": bool(quick_recovery_mode),
        "delay_min_sec": int(delay_min_sec),
        "delay_max_sec": int(delay_max_sec),
        "speed_profile": str(speed_profile or "stable"),
        "start_page_manual": int(start_page_manual),
        "auto_start_page": bool(auto_start_page),
    }


def _diff_run_signature(saved_sig: dict, current_sig: dict) -> list:
    if not saved_sig:
        return ["체크포인트에 기준 설정 정보가 없습니다(구버전)."]

    labels = {
        "board_url": "게시판 URL",
        "start_date": "시작일",
        "end_date": "종료일",
        "exclude_boards": "제외 게시판 목록",
        "level_backfill_mode": "등급 보강 모드",
        "quick_recovery_mode": "빠른 복구 모드",
        "delay_min_sec": "최소 대기(초)",
        "delay_max_sec": "최대 대기(초)",
        "speed_profile": "속도 프로파일",
        "start_page_manual": "탐색 시작 페이지",
        "auto_start_page": "자동 시작페이지",
    }
    mismatches = []
    for k, label in labels.items():
        if saved_sig.get(k) != current_sig.get(k):
            mismatches.append(label)
    return mismatches


def _format_seconds_to_hhmmss(total_seconds: float) -> str:
    try:
        s = max(0, int(total_seconds))
    except:
        s = 0
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}시간 {m}분 {sec}초"
    return f"{m}분 {sec}초"


def _format_seconds_to_hhmm(total_seconds: float) -> str:
    """카드 표시용 축약 시간 포맷(초 단위 생략)."""
    try:
        s = max(0, int(total_seconds))
    except:
        s = 0
    h = s // 3600
    m = (s % 3600) // 60
    if h > 0:
        return f"{h}시간 {m}분"
    return f"{m}분"


def _estimate_overall_progress(ctx: dict) -> tuple[float | None, int | None, float | None]:
    """
    전체 진행률/총 예상 건수/전체 ETA(초)를 추정한다.
    기준:
    - 기간 진행률: end_dt -> last_scan_oldest_date 로 얼마나 내려왔는지
    - 총 예상 건수: 누적 수집건수 / 진행률
    - ETA: 경과시간 * (남은비율 / 진행비율)
    """
    scan_date_txt = str(ctx.get("last_scan_oldest_date", "") or "").strip()
    run_started_raw = str(ctx.get("run_started_at", "") or "").strip()
    start_dt = ctx.get("start_dt")
    end_dt = ctx.get("end_dt")
    total_collected = int(ctx.get("total_collected", 0) or 0)

    if not (
        isinstance(start_dt, datetime)
        and isinstance(end_dt, datetime)
        and end_dt > start_dt
        and scan_date_txt
    ):
        return None, None, None

    try:
        scan_dt = datetime.fromisoformat(scan_date_txt)
    except:
        return None, None, None

    total_span_sec = (end_dt - start_dt).total_seconds()
    covered_sec = (end_dt - scan_dt).total_seconds()
    covered_sec = min(max(covered_sec, 0.0), total_span_sec)
    progress_ratio = covered_sec / total_span_sec if total_span_sec > 0 else 0.0

    est_total = None
    if progress_ratio >= 0.02 and total_collected > 0:
        est_total = max(total_collected, int(round(total_collected / progress_ratio)))

    eta_total_sec = None
    if run_started_raw and progress_ratio >= 0.02:
        try:
            started_dt = datetime.fromisoformat(run_started_raw)
            elapsed_sec = max(1.0, (datetime.now() - started_dt).total_seconds())
            eta_total_sec = elapsed_sec * ((1.0 - progress_ratio) / progress_ratio)
        except:
            eta_total_sec = None

    return progress_ratio, est_total, eta_total_sec


def _estimate_avg_process_seconds(ctx: dict) -> float | None:
    run_started_raw = str(ctx.get("run_started_at", "") or "").strip()
    processed = int(ctx.get("global_processed_count", 0) or 0)
    if not run_started_raw or processed <= 0:
        return None
    try:
        started_dt = datetime.fromisoformat(run_started_raw)
        elapsed_sec = max(1.0, (datetime.now() - started_dt).total_seconds())
        return elapsed_sec / float(processed)
    except:
        return None


def _build_completion_metrics(ctx: dict) -> dict:
    _, est_total, eta_total_sec = _estimate_overall_progress(ctx)
    processed = int(ctx.get("global_processed_count", 0) or 0)
    skip_count = int(ctx.get("skip_count", 0) or 0)
    error_count = int(ctx.get("error_count", 0) or 0)
    # 완료율/현재 수집 개수는 "실제 저장 성공건" 기준(스킵 제외)
    completed = max(0, processed - skip_count - error_count)

    completion_ratio = None
    if est_total and est_total > 0:
        completion_ratio = min(1.0, completed / float(est_total))

    run_started_raw = str(ctx.get("run_started_at", "") or "").strip()
    elapsed_sec = None
    total_sec = None
    if run_started_raw:
        try:
            started_dt = datetime.fromisoformat(run_started_raw)
            elapsed_sec = max(1.0, (datetime.now() - started_dt).total_seconds())
            if eta_total_sec is not None:
                total_sec = elapsed_sec + eta_total_sec
        except:
            elapsed_sec = None
            total_sec = None

    return {
        "est_total": est_total,
        "completed": completed,
        "completion_ratio": completion_ratio,
        "eta_total_sec": eta_total_sec,
        "elapsed_sec": elapsed_sec,
        "total_sec": total_sec,
        "avg_sec": _estimate_avg_process_seconds(ctx),
        "last_scanned_page": int(ctx.get("last_scanned_page", 0) or 0),
        "scan_date_txt": str(ctx.get("last_scan_oldest_date", "") or "").strip(),
    }


def _render_crawl_summary(ctx: dict, title: str = "진행 요약"):
    # 빠른 복구 모드인지 확인 (한 번에 로드하는 방식)
    is_quick_mode = bool(ctx.get("quick_recovery_mode", False))
    
    # 배치 모드인지 확인 (total_collected 키가 존재하면 배치 모드)
    total_collected = ctx.get("total_collected")
    
    st.markdown(f"#### {title}")
    
    if total_collected is not None and not is_quick_mode:
        m = _build_completion_metrics(ctx)
        c1, c2, c3, c4 = st.columns([0.9, 0.9, 1.0, 1.4])

        if m["est_total"]:
            c1.metric("예상 게시글 수(추정)", f"{int(m['est_total']):,}개")
        else:
            c1.metric("예상 게시글 수(추정)", "계산 중...")

        c2.metric("현재 수집 개수", f"{int(m['completed']):,}개")

        if m["elapsed_sec"] is not None:
            c3.metric("총 소요시간", _format_seconds_to_hhmm(m["elapsed_sec"]))
        else:
            c3.metric("총 소요시간", "계산 중...")

        if m["eta_total_sec"] is not None:
            remain_txt = _format_seconds_to_hhmm(m["eta_total_sec"])
            eta_value = f"{remain_txt} / 총 {_format_seconds_to_hhmm(m['total_sec'])}" if m["total_sec"] is not None else remain_txt
        else:
            eta_value = "계산 중..."
        c4.markdown(
            f"""
            <div style="background: linear-gradient(180deg, #f8fbff 0%, #f3f7fc 100%);
                        border: 1px solid #dbe5f2; border-radius: 12px; padding: 12px 14px;
                        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04); min-height: 110px;
                        display:flex; flex-direction:column; justify-content:center;">
              <div style="font-size:0.86rem;color:#64748b;font-weight:700;letter-spacing:-0.01em;">예상 남은 시간</div>
              <div style="font-size:1.30rem;line-height:1.35;color:#0f172a;font-weight:800;word-break:keep-all;white-space:normal;">{eta_value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if m["avg_sec"] is not None:
            st.markdown(
                f"<div style='font-size:1.0rem;color:#334155;font-weight:600;'>개당 평균 소요시간: {m['avg_sec']:.1f}초/건</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:1.0rem;color:#334155;font-weight:600;'>개당 평균 소요시간: 계산 중...</div>",
                unsafe_allow_html=True,
            )

        if m["last_scanned_page"] > 0:
            if m["scan_date_txt"]:
                st.markdown(
                    f"<div style='font-size:1.0rem;color:#334155;font-weight:600;'>탐색 페이지: 최근 {m['last_scanned_page']}p · 현재 탐색 기준 날짜: {m['scan_date_txt']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='font-size:1.0rem;color:#334155;font-weight:600;'>탐색 페이지: 최근 {m['last_scanned_page']}p</div>",
                    unsafe_allow_html=True,
                )
        
    else:
        # [전체 로드 모드] (구버전 호환 또는 빠른 복구 모드)
        total = int(len(ctx.get("articles", []))) if isinstance(ctx.get("articles", []), list) else 0
        idx = int(ctx.get("index", 0) or 0)
        ratio = (idx / total) if total > 0 else 0.0
        run_started_raw = str(ctx.get("run_started_at", "") or "").strip()
        elapsed_txt = "계산 중..."
        if run_started_raw:
            try:
                started_dt = datetime.fromisoformat(run_started_raw)
                elapsed_sec = max(1.0, (datetime.now() - started_dt).total_seconds())
                elapsed_txt = _format_seconds_to_hhmmss(elapsed_sec)
            except:
                pass
        c1, c2, c3, c4 = st.columns([0.9, 0.9, 1.0, 1.4])
        c1.metric("예상 게시글 수(추정)", f"{total:,}개")
        c2.metric("현재 수집 개수", f"{idx:,}개")
        c3.metric("총 소요시간", elapsed_txt)
        c4.metric("예상 남은 시간", "계산 중...")


if not st.session_state.crawl_checkpoint_bootstrapped:
    loaded = _load_crawl_checkpoint()
    if loaded:
        st.session_state.crawl_state = loaded
        st.session_state.crawl_checkpoint_available = True
        try:
            st.session_state.crawl_checkpoint_last_index = int(loaded.get("index", -1))
        except:
            st.session_state.crawl_checkpoint_last_index = -1
    st.session_state.crawl_checkpoint_bootstrapped = True


def _is_browser_opened() -> bool:
    crawler = st.session_state.get("crawler")
    if not crawler or not getattr(crawler, "driver", None):
        return False
    try:
        handles = crawler.driver.window_handles or []
        return len(handles) > 0
    except:
        return False



def _is_step2_ready() -> bool:
    if bool(st.session_state.get("login_confirmed", False)):
        return True
    crawler = st.session_state.get("crawler")
    if not crawler or not getattr(crawler, "driver", None):
        return False
    try:
        cookies = crawler.driver.get_cookies() or []
        cookie_names = {str(c.get("name", "")).upper() for c in cookies}
        return ("NID_SES" in cookie_names) or ("NID_AUT" in cookie_names)
    except:
        return False


def _is_overall_board_url(url: str) -> bool:
    """전체글보기 URL 여부 확인 (menuid 없는 ArticleList or /menus/0 형태)."""
    u = str(url or "").strip()
    if not u:
        return False
    if "ArticleList.nhn" in u and "search.menuid" not in u:
        return True
    if "/menus/0" in u or "/menus/all" in u:
        return True
    return False


## 로그인 유틸 함수들은 app.utils.naver_login 에서 import 됨
## _has_naver_login_cookie, _is_captcha_like_page, _auto_login_naver_with_js


# 시안 레이아웃: 가로 메뉴 → 대시보드 타이틀·가이드 → 3열 수집 설정 → 하단 col_main(실행·리스트)
# 상단 3열 수집 설정 → 실행/리스트는 col_main
default_exclude = "\n".join(
    [
        "공지&이벤트",
        "자유 게시판",
        "먹거리 / 맛집",
        "멘토단 전용 (중상급자)",
        "음악 웃음 힐링",
        "제품사은품후기",
        "진급축하 / 진급문의",
        "회원상품 홍보",
        "(조사기)중고 직거래",
        "썬드림 앱's",
    ]
)

def _normalize_board_name_ui(name: str) -> str:
    return str(name or "").strip().replace(" ", "").lower()


def _cafe_url_identity(url: str) -> str:
    """같은 카페인지 비교용 키 (URL이 달라도 clubid/슬러그 같으면 동일로 본다)."""
    u = str(url or "").strip()
    if not u:
        return ""
    m = re.search(r"clubid=(\d+)", u, re.I) or re.search(r"/cafes/(\d+)", u, re.I)
    if m:
        return f"club:{m.group(1)}"
    m = re.search(r"cafe\.naver\.com/([^\s/?#]+)", u, re.I)
    if m and m.group(1).lower() not in ("articlelist.nhn", "ca-fe", "f-e"):
        return f"slug:{m.group(1).lower()}"
    return u.split("?", 1)[0].rstrip("/").lower()


# 게시판 목록/선택 상태
if "extracted_boards" not in st.session_state:
    cfg_boards = config.get("extracted_boards", [])
    st.session_state.extracted_boards = cfg_boards if isinstance(cfg_boards, list) else []
if "_extracted_boards_cafe_sig" not in st.session_state:
    st.session_state._extracted_boards_cafe_sig = _cafe_url_identity(
        str(config.get("cafe_url", "") or "")
    )
if "cafe_name_input" not in st.session_state:
    st.session_state.cafe_name_input = str(config.get("cafe_name", DISPLAY_CAFE_NAME) or "").strip() or DISPLAY_CAFE_NAME
if "cafe_url_input" not in st.session_state:
    # 새로고침/재접속 시 마지막 저장 URL을 기본값으로 복원
    st.session_state.cafe_url_input = str(config.get("cafe_url", "") or "")
if "selected_board_urls" not in st.session_state:
    cfg_selected_urls = config.get("selected_board_urls", [])
    if isinstance(cfg_selected_urls, list) and cfg_selected_urls:
        st.session_state.selected_board_urls = [str(u).strip() for u in cfg_selected_urls if str(u).strip()]
    else:
        # 하위호환: 과거에는 board_url 문자열(줄바꿈 구분)로만 저장되던 케이스를 복원
        st.session_state.selected_board_urls = [
            u.strip() for u in str(config.get("board_url", "") or "").splitlines() if u.strip()
        ]
if "board_picker_version" not in st.session_state:
    st.session_state.board_picker_version = 0
if "board_picker_options_sig" not in st.session_state:
    st.session_state.board_picker_options_sig = ""
if "cafe_url_after_reset_save_mode" not in st.session_state:
    st.session_state.cafe_url_after_reset_save_mode = False
if "auto_login_after_reset_save_mode" not in st.session_state:
    st.session_state.auto_login_after_reset_save_mode = False

render_main_top_nav(active="app")

def _render_cafe_dashboard_header() -> None:
    _logo_path = Path(__file__).resolve().parent / "assets" / "CafeMonster_logo.png"
    
    _hdr_logo, _hdr_mid = st.columns([1, 5], gap="small")
    with _hdr_logo:
        render_logo_png(_logo_path, width_px=92)
    with _hdr_mid:
        _title_col, _guide_col = st.columns([1.95, 2.05], gap="small")
        with _title_col:
            st.markdown(
                '<h2 style="margin:0 0 0.15rem 0;padding:0;line-height:1.2;font-size:1.35rem;">네이버카페 게시글·댓글 수집기</h2>',
                unsafe_allow_html=True,
            )
        with _guide_col:
            with st.expander("📖 사용 가이드 (필독)", expanded=False):
                st.markdown(
                    """
                **1) 저장 버튼은 섹션별로 따로 동작합니다**
                - **왼쪽 `카페 URL 옆 저장`**: `카페명 + 카페 URL`을 즉시 영구 저장합니다.
                - **왼쪽 `게시판 목록 가져오기`**: 스캔한 게시판 목록은 자동 저장됩니다.
                - **게시판 체크 선택/해제**: 선택값도 자동 저장됩니다.
                - **가운데 `저장` 버튼**: 기간/필터/시작페이지 등 가운데 섹션 값만 저장합니다.

                **2) 기본 수집 동작**
                - 설정한 기간의 게시글을 수집합니다.
                - 이미 있는 글은 중복 저장을 피하고, 필요한 값만 보강합니다.
                - 종료일 기준 자동 시작페이지 모드를 권장합니다.
                - 처음 수집하는 카페는 **1년 이하 기간으로 나눠서** 순차 수집하는 것을 권장합니다. (예: 2025년 -> 2024년 -> 2023년)
                - 게시판 목록은 `50개씩 보기` 기준으로 탐색되며, 다음 회차 수집 시 자동 시작페이지가 최근 수집 구간 근처로 점프해 시간을 줄여줍니다.

                **3) 속도와 안정성**
                - 크롤러가 게시판 목록을 `50개씩 보기`로 자동 전환해 탐색을 최적화합니다.
                - 연속 실패가 누적되면 안전 중단 후 체크포인트를 남깁니다.
                - 네트워크/페이지 구조/본문 길이에 따라 건당 처리시간은 달라질 수 있습니다.

                **4) 작성자 ID 안내**
                - 상세 보기의 `작성자 ID`는 네이버 내부 식별값이라 길고 복잡하게 보일 수 있습니다.
                - 동일 작성자 추적/중복 판별용 키이며, 화면 표시용 닉네임과 역할이 다릅니다.
                                """
                )


_render_cafe_dashboard_header()


def _inject_cafe_connect_history_suggestions(cafe_names: list[str], cafe_urls: list[str]) -> None:
    inject_connect_history_suggestions(
        prefix="cafe",
        container_key_fragment="settings_card_1",
        cafe_names=cafe_names,
        cafe_urls=cafe_urls,
    )


if "settings_collapsed" not in st.session_state:
    st.session_state.settings_collapsed = True

def toggle_settings():
    st.session_state.settings_collapsed = not st.session_state.settings_collapsed

st.markdown('''
    <style>
    /* 투명하고 작은 우측 화살표 버튼 스타일 */
    div[class*="st-key-btn_fold_"] button {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        color: #94a3b8 !important;
        padding: 0 !important;
        min-height: 0 !important;
        height: auto !important;
        line-height: 1.5 !important;
        display: flex;
        justify-content: flex-end;
        margin-top: 0 !important;
    }
    div[class*="st-key-btn_fold_"] button:hover {
        color: #334155 !important;
        background: transparent !important;
    }
    div[class*="st-key-btn_fold_"] p {
        font-size: 1.1rem !important;
        margin: 0 !important;
    }
    
    /*
     * 설정 3카드: Streamlit은 key를 `st-key-$$ID-<해시>-settings_card_N` 클래스로 붙임.
     * 카드 루트가 곧 stVerticalBlock 이므로 줄 간격(gap)은 이 블록에 둔다 (자손 선택자만으론 루트에 안 먹음).
     */
    div[class*="st-key-"][class*="-settings_card_1"],
    div[class*="st-key-"][class*="-settings_card_2"],
    div[class*="st-key-"][class*="-settings_card_3"] {
        background: #eef4ff !important;
        border: 1px solid #cfdbf3 !important;
        border-radius: 0.65rem !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06) !important;
        padding: 0.15rem !important;
        box-sizing: border-box !important;
        gap: 0.55rem !important;
        row-gap: 0.55rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stVerticalBlockBorderWrapper"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stVerticalBlockBorderWrapper"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: #eef4ff !important;
        border-color: #cfdbf3 !important;
        border-radius: 0.6rem !important;
        padding: 0.58rem 1.1rem 0.72rem 1.1rem !important;
        box-sizing: border-box !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stVerticalBlock"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stVerticalBlock"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stVerticalBlock"] {
        background: #eef4ff !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        box-sizing: border-box !important;
        gap: 0.42rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] {
        gap: 0.42rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] .element-container,
    div[class*="st-key-"][class*="-settings_card_2"] .element-container,
    div[class*="st-key-"][class*="-settings_card_3"] .element-container {
        margin-bottom: 0 !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stCaptionContainer"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stCaptionContainer"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stCaptionContainer"] {
        margin-top: 0 !important;
        margin-bottom: 0.06rem !important;
        padding: 0.06rem 0 0.12rem 0.12rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stCaptionContainer"] p,
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stCaptionContainer"] p,
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stCaptionContainer"] p {
        margin: 0 0 0.1rem 0 !important;
        line-height: 1.45 !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stWidgetLabel"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stWidgetLabel"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stWidgetLabel"] {
        margin-bottom: 0.14rem !important;
        margin-top: 0 !important;
        padding: 0 0.05rem 0 0.12rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] .stTextInput,
    div[class*="st-key-"][class*="-settings_card_2"] .stTextInput,
    div[class*="st-key-"][class*="-settings_card_3"] .stTextInput,
    div[class*="st-key-"][class*="-settings_card_1"] .stDateInput,
    div[class*="st-key-"][class*="-settings_card_2"] .stDateInput,
    div[class*="st-key-"][class*="-settings_card_3"] .stDateInput,
    div[class*="st-key-"][class*="-settings_card_1"] .stTextArea,
    div[class*="st-key-"][class*="-settings_card_2"] .stTextArea,
    div[class*="st-key-"][class*="-settings_card_3"] .stTextArea,
    div[class*="st-key-"][class*="-settings_card_1"] .stNumberInput,
    div[class*="st-key-"][class*="-settings_card_2"] .stNumberInput,
    div[class*="st-key-"][class*="-settings_card_3"] .stNumberInput {
        margin-top: 0 !important;
        margin-bottom: 0.06rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stExpander"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stExpander"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stExpander"] {
        margin-top: 0 !important;
        margin-bottom: 0.34rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stButton"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stButton"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stButton"] {
        margin-top: 0.1rem !important;
        margin-bottom: 0.32rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] h3,
    div[class*="st-key-"][class*="-settings_card_1"] h4,
    div[class*="st-key-"][class*="-settings_card_2"] h3,
    div[class*="st-key-"][class*="-settings_card_2"] h4,
    div[class*="st-key-"][class*="-settings_card_3"] h3,
    div[class*="st-key-"][class*="-settings_card_3"] h4 {
        margin-top: 0.45rem !important;
        margin-bottom: 0.2rem !important;
        padding-left: 0.12rem !important;
        line-height: 1.4 !important;
    }
    /* 입력·날짜: 흰 박스 안 글자 여백 */
    div[class*="st-key-"][class*="-settings_card_1"] .stTextInput > div > div > input,
    div[class*="st-key-"][class*="-settings_card_2"] .stTextInput > div > div > input,
    div[class*="st-key-"][class*="-settings_card_3"] .stTextInput > div > div > input,
    div[class*="st-key-"][class*="-settings_card_1"] .stTextInput input,
    div[class*="st-key-"][class*="-settings_card_2"] .stTextInput input,
    div[class*="st-key-"][class*="-settings_card_3"] .stTextInput input,
    div[class*="st-key-"][class*="-settings_card_1"] .stDateInput > div > div > input,
    div[class*="st-key-"][class*="-settings_card_2"] .stDateInput > div > div > input,
    div[class*="st-key-"][class*="-settings_card_3"] .stDateInput > div > div > input,
    div[class*="st-key-"][class*="-settings_card_1"] .stDateInput input,
    div[class*="st-key-"][class*="-settings_card_2"] .stDateInput input,
    div[class*="st-key-"][class*="-settings_card_3"] .stDateInput input {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] .stTextArea textarea,
    div[class*="st-key-"][class*="-settings_card_2"] .stTextArea textarea,
    div[class*="st-key-"][class*="-settings_card_3"] .stTextArea textarea {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stMetric"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stMetric"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stMetric"] {
        margin-top: 0.28rem !important;
        margin-bottom: 0.12rem !important;
        padding: 0.5rem 0.85rem !important;
        min-height: 0 !important;
        justify-content: center !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stMetricLabel"] p,
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stMetricValue"],
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stMetricLabel"] p,
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stMetricValue"],
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stMetricLabel"] p,
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stMetricValue"] {
        padding-left: 0.15rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stExpander"] details summary,
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stExpander"] details summary,
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stExpander"] details summary {
        padding: 0.42rem 0.7rem !important;
    }
    [data-testid="stForm"] {
        padding: 0.8rem 1rem !important;
    }
    [data-testid="stExpander"] details {
        margin-bottom: 0.5rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] [data-testid="stExpander"] details,
    div[class*="st-key-"][class*="-settings_card_2"] [data-testid="stExpander"] details,
    div[class*="st-key-"][class*="-settings_card_3"] [data-testid="stExpander"] details {
        margin-bottom: 0.34rem !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] .cafe-monster-settings-card-title,
    div[class*="st-key-"][class*="-settings_card_2"] .cafe-monster-settings-card-title,
    div[class*="st-key-"][class*="-settings_card_3"] .cafe-monster-settings-card-title {
        text-align: center !important;
        font-size: 0.94rem !important;
        font-weight: 600 !important;
        color: #1e3a8a !important;
        letter-spacing: -0.015em !important;
        line-height: 1.35 !important;
        margin: 0 0 0.38rem 0 !important;
        padding: 0.34rem 0.55rem 0.42rem !important;
        border-radius: 0.45rem !important;
        background: rgba(255, 255, 255, 0.72) !important;
        border: 1px solid rgba(37, 99, 235, 0.22) !important;
        box-sizing: border-box !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] .cafe-monster-settings-card-title-icon,
    div[class*="st-key-"][class*="-settings_card_2"] .cafe-monster-settings-card-title-icon,
    div[class*="st-key-"][class*="-settings_card_3"] .cafe-monster-settings-card-title-icon {
        margin-right: 0.35rem !important;
        font-style: normal !important;
    }
    div[class*="st-key-"][class*="-settings_card_1"] .cafe-monster-settings-card-title-text,
    div[class*="st-key-"][class*="-settings_card_2"] .cafe-monster-settings-card-title-text,
    div[class*="st-key-"][class*="-settings_card_3"] .cafe-monster-settings-card-title-text {
        vertical-align: middle !important;
    }
    /* 설정 카드 밖 전역 입력은 기존 유지, 카드 안은 위에서 좌우 패딩 처리 */
    div.stTextInput > div > div > input {
        padding-top: 0.35rem !important;
        padding-bottom: 0.35rem !important;
    }
    div.stDateInput > div > div > input {
        padding-top: 0.35rem !important;
        padding-bottom: 0.35rem !important;
    }
    </style>
''', unsafe_allow_html=True)

st.markdown("#### ⚙️ 수집 설정")
_t1, _t2, _t3 = st.columns([1, 1, 1], gap="medium")
with _t1:
    with st.container(border=True, key="settings_card_1"):
        render_settings_card_title("카페 · 연결", icon="🏪")
        if st.session_state.pop("_pending_clear_cafe_name_input", False):
            st.session_state.cafe_name_input = ""
        cafe_name = st.text_input("카페명", key="cafe_name_input")

        try:
            _cu_url, _cu_btn = st.columns([5, 1], gap="small", vertical_alignment="center")
        except TypeError:
            _cu_url, _cu_btn = st.columns([5, 1], gap="small")
        with _cu_url:
            if st.session_state.pop("_pending_clear_cafe_url_input", False):
                st.session_state.cafe_url_input = ""
            cafe_url = st.text_input("카페 URL", key="cafe_url_input")
        _inject_cafe_connect_history_suggestions(
            (config.get("cafe_name_history", []) or []) + [str(config.get("cafe_name", "") or "")],
            (config.get("cafe_url_history", []) or []) + [str(config.get("cafe_url", "") or "")],
        )
        with _cu_btn:
            _cu_save_mode = bool(st.session_state.get("cafe_url_after_reset_save_mode", False))
            _cu_side_lbl = "저장" if _cu_save_mode else "리셋"
            _cu_side_help = (
                "카페명/카페 URL을 즉시 반영하고 설정 파일에도 영구 저장합니다."
                if _cu_save_mode
                else "게시판 목록·선택·미리보기 등 카페 관련 화면 데이터만 비웁니다."
            )
            if st.button(_cu_side_lbl, key="cafe_url_side_action_btn", use_container_width=True, help=_cu_side_help):
                if _cu_save_mode:
                    cfg_now = dict(load_config() or {})
                    saved_cafe_name = str(st.session_state.get("cafe_name_input", "") or "").strip()
                    saved_cafe_url = str(st.session_state.get("cafe_url_input", "") or "").strip()
                    cfg_now["cafe_name"] = saved_cafe_name
                    cfg_now["cafe_url"] = saved_cafe_url
                    if saved_cafe_name:
                        prev_name_hist = [str(x).strip() for x in (cfg_now.get("cafe_name_history", []) or []) if str(x).strip()]
                        cfg_now["cafe_name_history"] = ([saved_cafe_name] + [x for x in prev_name_hist if x != saved_cafe_name])[:20]
                    if saved_cafe_url:
                        prev_url_hist = [str(x).strip() for x in (cfg_now.get("cafe_url_history", []) or []) if str(x).strip()]
                        cfg_now["cafe_url_history"] = ([saved_cafe_url] + [x for x in prev_url_hist if x != saved_cafe_url])[:20]
                    save_config(cfg_now)
                    config.update(cfg_now)
                    st.session_state.cafe_url_after_reset_save_mode = False
                    st.session_state._extracted_boards_cafe_sig = _cafe_url_identity(
                        str(st.session_state.get("cafe_url_input", "") or "")
                    )
                    st.session_state._cafe_url_apply_ack = True
                    st.rerun()
                else:
                    st.session_state.extracted_boards = []
                    st.session_state.selected_board_urls = []
                    st.session_state.board_picker_version = int(st.session_state.get("board_picker_version", 0)) + 1
                    st.session_state.board_picker_options_sig = ""
                    st.session_state.pop("preview_start_page", None)
                    # 위젯 key와 동일한 세션 키는 text_input 생성 이후 수정 불가 → 다음 런에서 선행 비우기
                    st.session_state._pending_clear_cafe_name_input = True
                    st.session_state._pending_clear_cafe_url_input = True
                    st.session_state._extracted_boards_cafe_sig = ""
                    st.session_state.cafe_url_after_reset_save_mode = True
                    st.session_state._cafe_session_reset_done = True
                    st.rerun()

        if st.session_state.get("_cafe_session_reset_done"):
            st.session_state._cafe_session_reset_done = False
            st.success("카페 관련 데이터를 비웠고 **카페명/카페 URL 칸을 비웠습니다**. 새 값을 입력한 뒤 오른쪽 **저장**을 눌러 주세요.")
        if st.session_state.get("_cafe_url_apply_ack"):
            st.session_state._cafe_url_apply_ack = False
            st.success("카페명/카페 URL을 저장했습니다. URL을 바꿨다면 **게시판 목록 가져오기**를 다시 실행해 목록을 갱신하세요.")

        _cur_cafe_sig = _cafe_url_identity(cafe_url)
        st.session_state._extracted_boards_cafe_sig = _cur_cafe_sig or st.session_state.get("_extracted_boards_cafe_sig")

        with st.expander("🔐 자동로그인 설정", expanded=False):
            if st.session_state.pop("_pending_clear_auto_login_inputs", False):
                st.session_state.auto_login_enabled_input = False
                st.session_state.naver_id_input = ""
                st.session_state.naver_pw_input = ""
            auto_login_enabled = st.checkbox(
                "브라우저 열 때 자동로그인 실행",
                value=bool(config.get("auto_login_enabled", False)),
                key="auto_login_enabled_input",
                help="1단계 브라우저 열기 직후 저장된 계정으로 로그인을 시도합니다.",
            )
            _al_input_col, _al_btn_col = st.columns([4, 1], gap="small")
            with _al_input_col:
                naver_id = st.text_input(
                    "네이버 아이디",
                    value=str(config.get("naver_id", "") or ""),
                    key="naver_id_input",
                    placeholder="아이디 입력",
                )
                naver_pw = st.text_input(
                    "네이버 비밀번호",
                    value=str(config.get("naver_pw", "") or ""),
                    key="naver_pw_input",
                    type="password",
                    placeholder="비밀번호 입력",
                )
            if auto_login_enabled and (not naver_id or not naver_pw):
                st.warning("자동로그인을 켜려면 아이디/비밀번호를 모두 입력해주세요.")
            with _al_btn_col:
                st.markdown("<div style='margin-top: 88px;'></div>", unsafe_allow_html=True)
                _al_save_mode = bool(st.session_state.get("auto_login_after_reset_save_mode", False))
                _al_lbl = "저장" if _al_save_mode else "리셋"
                if st.button(_al_lbl, key="auto_login_side_action_btn", use_container_width=True):
                    if _al_save_mode:
                        cfg_now = dict(load_config() or {})
                        cfg_now["auto_login_enabled"] = bool(st.session_state.get("auto_login_enabled_input", False))
                        cfg_now["naver_id"] = str(st.session_state.get("naver_id_input", "") or "").strip()
                        cfg_now["naver_pw"] = str(st.session_state.get("naver_pw_input", "") or "")
                        save_config(cfg_now)
                        config.update(cfg_now)
                        st.session_state.auto_login_after_reset_save_mode = False
                        st.session_state._auto_login_save_ack = True
                        st.rerun()
                    else:
                        st.session_state._pending_clear_auto_login_inputs = True
                        st.session_state.auto_login_after_reset_save_mode = True
                        st.session_state._auto_login_reset_ack = True
                        st.rerun()
            if st.session_state.get("_auto_login_reset_ack"):
                st.session_state._auto_login_reset_ack = False
                st.success("자동로그인 설정 값을 비웠습니다. 새 값을 입력한 뒤 오른쪽 저장을 눌러주세요.")
            if st.session_state.get("_auto_login_save_ack"):
                st.session_state._auto_login_save_ack = False
                st.success("자동로그인 설정을 저장했습니다.")

        c_scan, c_tog1 = st.columns([0.9, 0.1])
        with c_tog1:
            st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_1", on_click=toggle_settings)
        
        scan_clicked = c_scan.button("🔍 게시판 목록 가져오기", help="현재 열린 카페 화면에서 모든 게시판 목록을 스캔합니다.", use_container_width=True)
        if scan_clicked:
            if not st.session_state.get("crawler") or not getattr(st.session_state.crawler, "driver", None):
                st.error("먼저 1단계 브라우저를 열어주세요.")
            else:
                try:
                    with st.spinner("게시판 목록 스캔 중..."):
                        crawler_obj = st.session_state.crawler
                        boards = []
                        if hasattr(crawler_obj, "get_all_board_urls"):
                            boards = crawler_obj.get_all_board_urls(cafe_url=cafe_url) or []

                        if not boards:
                            driver = crawler_obj.driver
                            seen = set()
                            target_cafe_url = str(cafe_url or "").strip()
                            if target_cafe_url:
                                try:
                                    driver.switch_to.default_content()
                                except Exception:
                                    pass
                                try:
                                    if hasattr(crawler_obj, "_convert_to_legacy_board_url"):
                                        target_cafe_url = crawler_obj._convert_to_legacy_board_url(target_cafe_url)
                                    driver.get(target_cafe_url)
                                    time.sleep(1.2)
                                except Exception:
                                    pass

                            def _is_board_href(href: str) -> bool:
                                u = str(href or "").strip()
                                if not u:
                                    return False
                                return (
                                    ("ArticleList.nhn" in u and "search.menuid" in u)
                                    or ("/menus/" in u and "/articles/" not in u)
                                )

                            def _append_boards_from_current_dom():
                                # 1) href 링크
                                for a in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                                    try:
                                        href = (a.get_attribute("href") or "").strip()
                                        name = (
                                            (a.text or "").strip()
                                            or (a.get_attribute("title") or "").strip()
                                            or (a.get_attribute("aria-label") or "").strip()
                                        )
                                        if not href or not name:
                                            continue
                                        if "javascript:" in href.lower():
                                            continue
                                        if not _is_board_href(href):
                                            continue
                                        if href in seen:
                                            continue
                                        seen.add(href)
                                        boards.append({"name": name, "url": href})
                                    except Exception:
                                        continue
                                # 2) onclick=goMenu(...) 패턴
                                for a in driver.find_elements(By.CSS_SELECTOR, "a[onclick]"):
                                    try:
                                        onclick = str(a.get_attribute("onclick") or "")
                                        if "goMenu" not in onclick:
                                            continue
                                        m = re.search(r"goMenu\('(\d+)'\)", onclick) or re.search(r"goMenu\((\d+)\)", onclick)
                                        if not m:
                                            continue
                                        menuid = m.group(1)
                                        cur_url = str(getattr(driver, "current_url", "") or "")
                                        m_club = re.search(r"clubid=(\d+)", cur_url) or re.search(r"/cafes/(\d+)", cur_url)
                                        if not m_club:
                                            continue
                                        clubid = m_club.group(1)
                                        href = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={clubid}&search.menuid={menuid}&search.boardtype=L"
                                        name = (a.text or "").strip() or f"게시판_{menuid}"
                                        if href in seen:
                                            continue
                                        seen.add(href)
                                        boards.append({"name": name, "url": href})
                                    except Exception:
                                        continue

                            # 현재 창 + 모든 iframe 스캔
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
                            st.session_state.extracted_boards = boards
                            # 목록이 바뀌면 선택 초기화(기본 비선택 유지)
                            st.session_state.selected_board_urls = []
                            st.session_state.board_picker_version = int(st.session_state.get("board_picker_version", 0)) + 1
                            cfg_now = dict(load_config() or {})
                            cfg_now["extracted_boards"] = boards
                            cfg_now["selected_board_urls"] = []
                            cfg_now["board_url"] = ""
                            save_config(cfg_now)
                            st.success(f"✅ 게시판 스캔 완료: {len(boards)}개")
                        else:
                            st.warning("게시판을 찾지 못했습니다. 카페 메인/메뉴가 보이는 화면에서 다시 시도해주세요.")
                except Exception as e:
                    st.error(f"오류: {e}")

        if not st.session_state.settings_collapsed:
            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            selected_urls_str = str(config.get("board_url", "") or "")
            if st.session_state.extracted_boards:
                st.markdown(f"##### 📋 게시판 선택 (총 {len(st.session_state.extracted_boards)}개)")
                all_boards = st.session_state.extracted_boards
                board_options = {f"{i+1:02d}. {b['name']}": b["url"] for i, b in enumerate(all_boards)}

                overall_url = ""
                for b in all_boards:
                    u = str(b.get("url", "") or "")
                    if "ArticleList.nhn" in u and "search.clubid=" in u:
                        m_club = re.search(r"search\.clubid=(\d+)", u)
                        if m_club:
                            overall_url = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={m_club.group(1)}&search.boardtype=L"
                            break
                    if "/f-e/cafes/" in u:
                        m_fe = re.search(r"/cafes/(\d+)/menus/(\d+)", u)
                        if m_fe:
                            overall_url = f"https://cafe.naver.com/f-e/cafes/{m_fe.group(1)}/menus/0?viewType=L"
                            break

                options_list = []
                if overall_url:
                    options_list.append("00. 전체글보기")
                options_list.extend(list(board_options.keys()))
                options_sig = "||".join(options_list)
                if options_sig != str(st.session_state.get("board_picker_options_sig", "")):
                    st.session_state.board_picker_options_sig = options_sig
                    st.session_state.board_picker_version = int(st.session_state.get("board_picker_version", 0)) + 1
                    st.session_state.selected_board_urls = []

                label_to_url = {}
                for label in options_list:
                    if label == "00. 전체글보기":
                        label_to_url[label] = overall_url
                    else:
                        label_to_url[label] = board_options.get(label, "")

                # 접기/펼치기는 전체선택과 독립
                with st.expander("게시판 목록 열기/접기", expanded=False):
                    v = int(st.session_state.get("board_picker_version", 0))
                    combo_key = f"board_combo_select_all_{v}"
                    label_to_idx = {label: i for i, label in enumerate(options_list)}
                    overall_label = "00. 전체글보기" if "00. 전체글보기" in options_list else None
                    combo_prev_key = f"_board_combo_select_all_prev_{v}"
                    overall_key = ""
                    if overall_label:
                        overall_idx = int(label_to_idx.get(overall_label, -1))
                        if overall_idx >= 0:
                            overall_key = f"board_chk_{v}_{overall_idx}"
                    if overall_key and bool(st.session_state.get(overall_key, False)):
                        # combo 위젯 생성 전에만 상태를 조정해야 Streamlit 예외를 피할 수 있음
                        st.session_state[combo_key] = False
                        st.session_state[combo_prev_key] = False
                    _combo_col, _count_col = st.columns([2.6, 1.4])
                    with _combo_col:
                        combo_checked_now = st.checkbox(
                            "✨ 전체 게시판 선택",
                            key=combo_key,
                            help="한 번에 전체 게시판을 체크합니다. 이후 제외할 게시판만 해제하세요.",
                        )
                    with _count_col:
                        selected_count_placeholder = st.empty()
                    combo_prev = bool(st.session_state.get(combo_prev_key, False))
                    if combo_checked_now and (not combo_prev):
                        for label in options_list:
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            chk_key = f"board_chk_{v}_{i}"
                            if overall_label and label == overall_label:
                                st.session_state[chk_key] = False
                            else:
                                st.session_state[chk_key] = True
                    elif (not combo_checked_now) and combo_prev:
                        # 전체 선택 토글 OFF 시 전체 해제
                        for label in options_list:
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            st.session_state[f"board_chk_{v}_{i}"] = False
                    st.session_state[combo_prev_key] = bool(combo_checked_now)

                    # 상호배타 강제: 둘 다 동시에 체크되지 않게 정리
                    if overall_key and bool(st.session_state.get(overall_key, False)):
                        combo_checked_now = False
                    elif combo_checked_now and overall_key:
                        st.session_state[overall_key] = False

                    wanted_urls = set(st.session_state.get("selected_board_urls", []) or [])
                    # key 초기화
                    for label in options_list:
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        u = str(label_to_url.get(label, "") or "")
                        chk_key = f"board_chk_{v}_{i}"
                        if chk_key not in st.session_state:
                            st.session_state[chk_key] = bool(u and u in wanted_urls)

                    # 전체글보기는 개별 게시판 선택과 상호배타
                    if overall_label:
                        overall_idx = int(label_to_idx.get(overall_label, -1))
                        overall_key = f"board_chk_{v}_{overall_idx}" if overall_idx >= 0 else ""
                        overall_checked = bool(st.session_state.get(overall_key, False)) if overall_key else False
                        other_checked = False
                        for label in options_list:
                            if label == overall_label:
                                continue
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            if bool(st.session_state.get(f"board_chk_{v}_{i}", False)):
                                other_checked = True
                                break
                        if overall_checked:
                            for label in options_list:
                                if label == overall_label:
                                    continue
                                i = int(label_to_idx.get(label, -1))
                                if i < 0:
                                    continue
                                st.session_state[f"board_chk_{v}_{i}"] = False
                        elif other_checked and overall_key:
                            st.session_state[overall_key] = False

                    try:
                        with st.container(height=360):
                            for label in options_list:
                                i = int(label_to_idx.get(label, -1))
                                if i < 0:
                                    continue
                                chk_key = f"board_chk_{v}_{i}"
                                disable_this = False
                                if overall_label and label != overall_label:
                                    oidx = int(label_to_idx.get(overall_label, -1))
                                    if oidx >= 0 and bool(st.session_state.get(f"board_chk_{v}_{oidx}", False)):
                                        disable_this = True
                                st.checkbox(
                                    label,
                                    key=chk_key,
                                    disabled=disable_this,
                                )
                    except TypeError:
                        for label in options_list:
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            chk_key = f"board_chk_{v}_{i}"
                            disable_this = False
                            if overall_label and label != overall_label:
                                oidx = int(label_to_idx.get(overall_label, -1))
                                if oidx >= 0 and bool(st.session_state.get(f"board_chk_{v}_{oidx}", False)):
                                    disable_this = True
                            st.checkbox(
                                label,
                                key=chk_key,
                                disabled=disable_this,
                            )

                    # 개별 선택은 클릭 즉시 반영 (선택 반영 버튼 제거)
                    selected_urls = []
                    for label in options_list:
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        if bool(st.session_state.get(f"board_chk_{v}_{i}", False)):
                            u = str(label_to_url.get(label, "") or "")
                            if u:
                                selected_urls.append(u)
                    selected_urls_dedup = list(dict.fromkeys(selected_urls))
                    st.session_state.selected_board_urls = selected_urls_dedup
                    # 게시판 선택은 즉시 자동 저장 (가운데 섹션 저장과 분리)
                    _selected_sig = "|".join(selected_urls_dedup)
                    if st.session_state.get("_selected_board_urls_saved_sig", "") != _selected_sig:
                        st.session_state._selected_board_urls_saved_sig = _selected_sig
                        cfg_now = dict(load_config() or {})
                        cfg_now["selected_board_urls"] = selected_urls_dedup
                        cfg_now["board_url"] = "\n".join(selected_urls_dedup)
                        save_config(cfg_now)

                    selected_count_placeholder.markdown(
                        f"<div style='font-size:0.92rem;color:#475569;text-align:right;"
                        f"padding-top:6px;'>[{len(selected_urls_dedup)}개 게시판 선택]</div>",
                        unsafe_allow_html=True,
                    )

                selected_urls = list(dict.fromkeys([u for u in (st.session_state.get("selected_board_urls", []) or []) if u]))
                selected_urls_str = "\n".join(selected_urls)
            else:
                # 추출 목록이 없을 때만 수동 입력 폴백
                selected_urls_str = st.text_input(
                    "게시판 URL (전체글보기 권장)",
                    value=str(config.get("board_url", "") or ""),
                )
            board_url = selected_urls_str
with _t2:
    with st.container(border=True, key="settings_card_2"):
        render_settings_card_title("수집 세부설정", icon="📅")
        exclude_boards_text = ""

        collect_mode = str(
            st.session_state.get("collect_mode_input", config.get("collect_mode", "posts_and_comments")) or "posts_and_comments"
        ).strip()
        if collect_mode not in ("posts_and_comments", "posts_only"):
            collect_mode = "posts_and_comments"
        with st.expander("🧩 수집 조건", expanded=False):
            collect_mode_label = st.radio(
                "수집 유형",
                options=["게시글 + 댓글", "게시글만"],
                index=0 if collect_mode == "posts_and_comments" else 1,
                key="collect_mode_input",
                horizontal=False,
            )
            collect_mode = "posts_and_comments" if collect_mode_label == "게시글 + 댓글" else "posts_only"
        st.subheader("📅 수집 기간")
        default_start = datetime.now() - timedelta(days=365)
        if "start_date" in config:
            try:
                default_start = datetime.strptime(config["start_date"], "%Y-%m-%d")
            except:
                pass

        default_end = datetime.now()
        if "end_date" in config:
            try:
                default_end = datetime.strptime(config["end_date"], "%Y-%m-%d")
            except:
                pass

        col1, col2, col_tog2 = st.columns([0.45, 0.45, 0.1])
        start_date = col1.date_input("시작일", default_start)
        end_date = col2.date_input("종료일", default_end)
        with col_tog2:
            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
            st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_2", on_click=toggle_settings)

        # 설정 접힘 시에도 아래 실행 제어·크롤이 동일 이름을 참조하므로 여기서 기본 정의
        auto_start_page = bool(
            st.session_state.get("auto_start_page_check", config.get("auto_start_page", True))
        )
        speed_profile = "fast"
        delay_min_sec = 1
        delay_max_sec = 2
        quick_recovery_mode = False
        retry_withdrawal = False
        fail_safe_enabled = True
        fail_safe_threshold = 40
        progress_log_every = 100
        if auto_start_page:
            start_page_manual = max(1, int(config.get("start_page_manual", 1) or 1))
            effective_start_page = 1
        else:
            start_page_manual = int(
                st.session_state.get(
                    "start_page_manual_input",
                    max(1, int(config.get("start_page_manual", 1) or 1)),
                )
            )
            effective_start_page = start_page_manual

        if not st.session_state.settings_collapsed:
            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            st.markdown("##### 🔧 작업 모드")
            speed_profile = "fast"
            delay_min_sec = 1
            delay_max_sec = 2

            auto_start_page = st.checkbox(
                "종료일 기준 자동 시작페이지 사용",
                value=bool(config.get("auto_start_page", True)),
                help=(
                    "체크하면 종료일이 포함된 페이지(게시판 50개씩 보기 기준)를 자동으로 찾아 시작합니다. "
                    "1년 단위로 나눠 연속 수집할 때 특히 유용합니다."
                ),
                key="auto_start_page_check",
            )

            if auto_start_page:
                if _is_browser_opened() and st.session_state.get("crawler"):
                    if st.button("🔍 추천 시작페이지 미리보기", key="preview_start_page_btn"):
                        with st.spinner("해당 기간의 페이지를 찾는 중..."):
                            try:
                                end_dt = datetime.combine(end_date, datetime.max.time())
                                page_no, dmin, dmax = st.session_state.crawler.recommend_start_page(board_url, end_dt)
                                if dmin and dmax:
                                    st.session_state.preview_start_page = {"page": page_no, "dmin": dmin, "dmax": dmax}
                                else:
                                    st.session_state.preview_start_page = {"page": page_no, "dmin": None, "dmax": None}
                                st.rerun()
                            except Exception as e:
                                st.session_state.preview_start_page = None
                                st.error(f"미리보기 실패: {e}")
                    if "preview_start_page" in st.session_state and st.session_state.preview_start_page:
                        pv = st.session_state.preview_start_page
                        if pv.get("dmin") and pv.get("dmax"):
                            st.success(f"추천: **{pv['page']}페이지** (날짜 범위: {pv['dmin']} ~ {pv['dmax']})")
                        else:
                            st.info(f"추천: **{pv['page']}페이지** (날짜 범위 확인 실패)")
            else:
                start_page_manual = int(
                    st.number_input(
                        "탐색 시작 페이지 (선택)",
                        min_value=1,
                        max_value=10000,
                        value=max(1, int(config.get("start_page_manual", 1) or 1)),
                        step=1,
                        help="기본값 1. 이전 실행의 마지막 탐색 페이지 근처로 지정하면 범위 탐색이 빨라집니다.",
                        key="start_page_manual_input",
                    )
                )

            # 자동 모드: start_page=1 전달 → 크롤러가 종료일 기준 자동 탐색
            effective_start_page = 1 if auto_start_page else start_page_manual

            st.caption("※ 안전 장치: 연속 40회 실패 시 작업이 자동 중단됩니다.")

            # 내부 고정 설정 (사용자에게 노출하지 않음)
            st.session_state.debug_mode = False
            level_backfill = False # 스마트 로직이 알아서 하므로 강제 옵션은 끔
            quick_recovery_mode = False
            retry_withdrawal = False
            fail_safe_enabled = True
            fail_safe_threshold = 40
            progress_log_every = 100

            st.markdown("---")
            if st.button("💾 저장", use_container_width=True):
                # 기존 키를 보존한 채, 화면에서 수정한 항목만 갱신
                new_config = dict(config or {})
                new_config.update({
                    "collect_mode": collect_mode,
                    "exclude_boards": "",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "start_page_manual": int(effective_start_page if not auto_start_page else (config.get("start_page_manual", 1) or 1)),
                    "auto_start_page": bool(auto_start_page),
                })
                save_config(new_config)
                st.success("✅ 설정이 저장되었습니다.")
with _t3:
    with st.container(border=True, key="settings_card_3"):
        render_settings_card_title("데이터/DB", icon="💾")
        db_full_path = os.path.abspath(DB_PATH)
        exists = os.path.exists(db_full_path)
        try:
            size_mb = os.path.getsize(db_full_path) / (1024 * 1024) if exists else 0.0
            mtime = datetime.fromtimestamp(os.path.getmtime(db_full_path)).strftime("%Y-%m-%d %H:%M:%S") if exists else "-"
        except:
            size_mb, mtime = 0.0, "-"
        st.caption(f"경로: `{db_full_path}`")
        st.caption(f"파일: {'존재함' if exists else '없음'} · 크기: {size_mb:.2f}MB · 수정: {mtime}")

        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            post_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM posts", conn)['cnt'][0]
            comment_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM comments", conn)['cnt'][0]
            last_post_date = pd.read_sql_query("SELECT MAX(date) as d FROM posts", conn)["d"][0]
            last_created_at = pd.read_sql_query("SELECT MAX(created_at) as t FROM posts", conn)["t"][0]
            conn.close()
            col_stat1, col_stat2 = st.columns(2)
            col_stat1.metric("게시글", f"{int(post_count):,}")
            col_stat2.metric("댓글", f"{int(comment_count):,}")
            c_cap, c_tog3 = st.columns([0.9, 0.1])
            with c_cap:
                st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
                st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")
            with c_tog3:
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)
        except:
            c_info, c_tog3 = st.columns([0.9, 0.1])
            with c_info:
                st.info("DB 통계를 읽을 수 없습니다.")
            with c_tog3:
                st.button("▼" if st.session_state.settings_collapsed else "▲", key="btn_fold_3", on_click=toggle_settings)

        if not st.session_state.settings_collapsed:
            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px dashed #e2e8f0;'>", unsafe_allow_html=True)
            col_db1, col_db2 = st.columns(2)
            with col_db1:
                if st.button("폴더 열기", use_container_width=True, key="open_db_folder"):
                    try:
                        import subprocess
                        subprocess.run(['explorer', '/select,', db_full_path])
                    except Exception as e:
                        st.error(f"폴더 열기 실패: {e}")
            with col_db2:
                log_dir = str(get_logs_dir())
                if st.button("로그 폴더", use_container_width=True, key="open_log_folder"):
                    try:
                        import subprocess
                        subprocess.run(['explorer', log_dir])
                    except Exception as e:
                        st.error(f"폴더 열기 실패: {e}")

            with st.expander("DB 위치 변경", expanded=False):
                db_path_override = st.text_input(
                    "DB 파일 절대경로 (예: D:\\CafeScraper\\data\\cafe_data.db)",
                    value=str(config.get("db_path", "") or ""),
                    placeholder=r"D:\CafeScraper\data\cafe_data.db",
                    key="db_path_override_input",
                )
                st.caption("우선순위: 환경변수 `CAFESCRAPER_DB_PATH` > 여기 입력한 경로 > 기본값")
                st.caption(f"현재 입력값: `{(db_path_override or '').strip() or '(비어있음)'}`")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("경로 저장(파일 이동 없음)", use_container_width=True, key="apply_db_path_only"):
                        target = (db_path_override or "").strip()
                        if not target:
                            st.error("대상 DB 경로가 비어 있습니다.")
                        else:
                            config["db_path"] = target
                            save_config(config)
                            st.success("✅ 저장 완료. 앱을 새로고침하세요.")
                with c2:
                    if st.button("현재 DB 복사 + 전환", use_container_width=True, key="copy_db_and_apply"):
                        target = (db_path_override or "").strip()
                        if not target:
                            st.error("대상 DB 경로가 비어 있습니다.")
                        else:
                            try:
                                os.makedirs(os.path.dirname(target), exist_ok=True)
                                shutil.copy2(db_full_path, target)
                                config["db_path"] = target
                                save_config(config)
                                st.success("✅ 복사/전환 완료. 앱을 새로고침하세요.")
                            except Exception as e:
                                st.error(f"복사/전환 실패: {e}")
col_main = st.container()

def _render_cafe_main_workspace():
    st.markdown("### 🚀 실행 제어")
    st.caption("1단계에서 로그인 브라우저를 준비하고, 2단계에서 수집을 실행/중단합니다.")

    step2_ready = _is_step2_ready()
    browser_opened = _is_browser_opened()
    recent_logs_lc = "\n".join([str(x) for x in (st.session_state.get("status_messages", []) or [])[-30:]]).lower()
    can_reset_runtime = bool(
        st.session_state.get("crawler")
        or st.session_state.get("login_confirmed", False)
        or st.session_state.get("crawl_state")
        or st.session_state.get("crawl_checkpoint_available", False)
    )
    needs_manual_login = bool(
        browser_opened
        and (not step2_ready)
        and (not st.session_state.crawl_running)
        and any(
            kw in recent_logs_lc
            for kw in (
                "자동로그인 실패",
                "수동 로그인",
                "캡챠",
                "추가 인증",
                "로그인 후",
            )
        )
    )
    runtime_inconsistent = bool(st.session_state.get("crawler")) and (not browser_opened) and (not st.session_state.crawl_running)
    runtime_error_hint = any(
        kw in recent_logs_lc
        for kw in (
            "invalid session id",
            "session",
            "세션",
            "driver",
            "disconnect",
            "체크포인트 저장 실패",
        )
    )
    show_reset_recovery = bool(can_reset_runtime and (runtime_inconsistent or runtime_error_hint))
    show_troubleshoot_panel = bool((not st.session_state.crawl_running) and (needs_manual_login or show_reset_recovery))

    # 한 줄 3버튼: 1단계 -> 로그인 완료 -> 2단계
    step_col1, step_col_login, step_col2 = st.columns([2.5, 1.1, 2.5])
    with step_col1:
        if st.button(
            "1단계: 브라우저 열기",
            use_container_width=True,
            disabled=bool(st.session_state.crawl_running) or bool(browser_opened),
            type="primary" if not step2_ready else "secondary",
            key="open_browser_btn",
        ):
            # 기존 드라이버가 끊긴 상태면 자동 정리 후 재생성
            crawler_ref = st.session_state.get("crawler")
            if crawler_ref and getattr(crawler_ref, "driver", None):
                try:
                    handles = crawler_ref.driver.window_handles or []
                    if len(handles) == 0:
                        crawler_ref.close()
                        st.session_state.crawler = None
                except:
                    try:
                        crawler_ref.close()
                    except:
                        pass
                    st.session_state.crawler = None

            if not st.session_state.crawler:
                st.session_state.crawler = NaverCafeCrawler("", debug_mode=st.session_state.debug_mode)
                st.session_state.crawler.set_status_callback(update_logs)
                # (추가) 중단 요청 실시간 확인을 위한 콜백 연결
                st.session_state.crawler.set_stop_check_callback(lambda: st.session_state.get("crawl_stop_requested", False))
                st.session_state.auto_login_attempted_this_session = False
            if hasattr(st.session_state.crawler, "set_speed_profile"):
                st.session_state.crawler.set_speed_profile(speed_profile)
            st.session_state.crawler.start_browser()
            auto_login_on = bool(st.session_state.get("auto_login_enabled_input", config.get("auto_login_enabled", False)))
            auto_login_id = str(st.session_state.get("naver_id_input", config.get("naver_id", "")) or "")
            auto_login_pw = str(st.session_state.get("naver_pw_input", config.get("naver_pw", "")) or "")
            if auto_login_on:
                # 과도한 반복 로그인 시도는 캡챠 확률을 높여서, 세션당 1회만 자동 시도
                if st.session_state.get("auto_login_attempted_this_session", False):
                    update_logs("ℹ️ 자동로그인은 이번 실행에서 이미 1회 시도되었습니다. 캡챠 방지를 위해 추가 자동시도는 생략합니다.")
                else:
                    st.session_state.auto_login_attempted_this_session = True
                    login_ok, reason = _auto_login_naver_with_js(
                        st.session_state.crawler,
                        auto_login_id,
                        auto_login_pw,
                    )
                    if login_ok:
                        st.session_state.login_confirmed = True
                        update_logs(f"✅ 자동로그인 성공 ({reason})")
                    else:
                        if "캡챠" in str(reason):
                            update_logs("🛡️ 캡챠 감지: 자동로그인을 즉시 중단했습니다. 브라우저에서 수동 로그인 후 '로그인 완료'를 눌러주세요.")
                        else:
                            update_logs(f"⚠️ 자동로그인 실패({reason}) 또는 추가 인증 필요. 수동 로그인 후 '로그인 완료'를 눌러주세요.")
            try:
                _target = str(cafe_url or "").strip()
                if _target.startswith("http") and getattr(st.session_state.crawler, "driver", None):
                    st.session_state.crawler.driver.get(_target)
                    time.sleep(random.uniform(0.35, 0.7))
            except Exception:
                pass
            # 브라우저를 새로 열면 로그인 확인 상태를 초기화
            if not bool(st.session_state.get("login_confirmed", False)):
                st.session_state.login_confirmed = False
            update_logs()
            st.rerun()

    with step_col_login:
        st.empty()

    with step_col2:
        if st.session_state.crawl_running:
            if st.button("⏹ 진행중... 중단", type="primary", use_container_width=True, key="stop_crawl_btn"):
                st.session_state.crawl_stop_requested = True
                update_logs("🛑 중단 요청이 접수되었습니다. 현재 항목 처리 후 중단합니다.")
        else:
            if st.button(
                "2단계: 게시글·댓글 수집 시작",
                type="primary",
                use_container_width=True,
                disabled=not step2_ready,
                key="start_crawl_btn",
            ):
                if not step2_ready:
                    st.error("먼저 1단계에서 브라우저를 열고 로그인을 완료해주세요.")
                else:
                    st.session_state.crawl_last_status_message = ""
                    collect_mode = str(
                        st.session_state.get("collect_mode_input", config.get("collect_mode", "posts_and_comments"))
                        or "posts_and_comments"
                    ).strip()
                    if collect_mode not in ("posts_and_comments", "posts_only"):
                        collect_mode = "posts_and_comments"

                    start_dt = datetime.combine(start_date, datetime.min.time())
                    end_dt = datetime.combine(end_date, datetime.max.time())
                    legacy_backfill = bool(config.get("update_existing", False)) and bool(config.get("meta_only", True))
                    level_backfill_mode = (
                        bool(config.get("level_backfill", False))
                        or bool(config.get("meta_backfill", False))
                        or legacy_backfill
                    )
                    board_urls = [url.strip() for url in (board_url or "").splitlines() if url.strip()]
                    if not board_urls:
                        st.error("게시판 URL을 입력해주세요.")
                        st.stop()
                    current_board_url = board_urls[0]
                    board_name_map = {}
                    for b in st.session_state.get("extracted_boards", []) or []:
                        bu = str((b or {}).get("url", "") or "").strip()
                        bn = str((b or {}).get("name", "") or "").strip()
                        if bu and bn:
                            board_name_map[bu] = bn
                    board_names_queue = []
                    for u in board_urls:
                        uu = str(u or "").strip()
                        if _is_overall_board_url(uu):
                            board_names_queue.append("전체글보기")
                        else:
                            board_names_queue.append(board_name_map.get(uu, ""))
                    # 일부 UI 분기(접힘/펼침)에서 값이 비어도 시작 시점에 기본값을 보장한다.
                    try:
                        effective_start_page = int(effective_start_page)
                    except Exception:
                        if bool(auto_start_page):
                            effective_start_page = 1
                        else:
                            effective_start_page = max(
                                1,
                                int(
                                    st.session_state.get(
                                        "start_page_manual_input",
                                        max(1, int(config.get("start_page_manual", 1) or 1)),
                                    )
                                ),
                            )
                    run_signature = _build_run_signature(
                        board_url=current_board_url,
                        start_date_value=start_date,
                        end_date_value=end_date,
                        exclude_boards_raw="",
                        level_backfill_mode=False, # 스마트 로직 사용
                        quick_recovery_mode=bool(quick_recovery_mode),
                        delay_min_sec=int(delay_min_sec),
                        delay_max_sec=int(delay_max_sec),
                        speed_profile=speed_profile,
                        start_page_manual=int(effective_start_page),
                        auto_start_page=bool(auto_start_page),
                    )

                    # 먼저 실행 상태로 전환해서 버튼이 즉시 '중단'으로 바뀌게 함
                    quick_mode_on = bool(quick_recovery_mode) # level_backfill_mode 조건 제거 (스마트 로직 사용)
                    st.session_state.crawl_state = {
                        "phase": "prepare",
                        "board_url": current_board_url,
                        "board_urls_queue": board_urls,
                        "board_names_queue": board_names_queue,
                        "current_board_idx": 0,
                        "start_dt": start_dt,
                        "end_dt": end_dt,
                        "exclude_boards": [],
                        "collect_mode": collect_mode,
                        "level_backfill_mode": False, # 스마트 로직 사용을 위해 False 고정
                        "quick_recovery_mode": quick_mode_on,
                        "retry_withdrawal": retry_withdrawal, # (추가) 탈퇴 재검사 옵션 전달
                        "start_page_manual": int(effective_start_page),
                        "crawl_delay_min": max(1.0, float(delay_min_sec)),
                        "crawl_delay_max": max(max(1.0, float(delay_min_sec)), float(delay_max_sec)),
                        "speed_profile": speed_profile,
                        "fail_safe_enabled": True,
                        "fail_safe_threshold": 40,
                        "progress_log_every": 100,
                        "consecutive_error_count": 0,
                        "last_progress_logged_index": 0,
                        "changed_level_count": 0,
                        "unchanged_level_count": 0,
                        "run_signature": run_signature,
                        "resume_base_index": 0,
                        "run_started_at": datetime.now().isoformat(),
                    }
                    st.session_state.crawl_running = True
                    st.session_state.crawl_stop_requested = False
                    _save_crawl_checkpoint(force=True)
                    first_board_name = str((board_names_queue[0] if board_names_queue else "") or "").strip()
                    if first_board_name:
                        update_logs(f"🔍 1단계: 첫 번째 게시판({first_board_name}) 목록 확보 시작...")
                    else:
                        update_logs(f"🔍 1단계: 첫 번째 게시판({current_board_url}) 목록 확보 시작...")
                    st.rerun()

    # 비상시만 문제 해결 패널 노출
    if show_troubleshoot_panel:
        with st.expander("⚠️ 문제 해결", expanded=True):
            if needs_manual_login:
                st.warning("로그인 감지에 문제가 있습니다. 브라우저에서 로그인 상태를 확인한 뒤 수동으로 진행하세요.")
                if st.button(
                    "로그인 완료",
                    use_container_width=True,
                    key="manual_login_confirm_btn_recovery",
                    disabled=(not browser_opened) or bool(step2_ready),
                ):
                    st.session_state.login_confirmed = True
                    st.rerun()

            if show_reset_recovery:
                if st.button("🔄 실행 상태 초기화 (리셋)", use_container_width=True, key="reset_runtime_btn_recovery"):
                    try:
                        crawler_ref = st.session_state.get("crawler")
                        if crawler_ref:
                            crawler_ref.close()
                    except:
                        pass
                    st.session_state.crawler = None
                    st.session_state.login_confirmed = False
                    st.session_state.crawl_stop_requested = False
                    st.session_state.crawl_running = False
                    st.session_state.crawl_state = {}
                    st.session_state.crawl_last_status_message = "ℹ️ 실행 상태를 초기화했습니다. 1단계부터 다시 시작하세요."
                    st.session_state.crawl_last_status_type = "info"
                    _clear_crawl_checkpoint()
                    update_logs("🔄 실행 상태 초기화 완료 (브라우저/체크포인트/진행 상태 리셋)")
                    st.rerun()

    # 실행 결과/진행 창 (고정 위치)
    st.markdown("#### 📋 실행 결과 / 진행")
    if st.session_state.crawl_last_status_message:
        _msg = st.session_state.crawl_last_status_message
        _typ = st.session_state.crawl_last_status_type
        if _typ == "success":
            st.success(_msg)
        elif _typ == "warning":
            st.warning(_msg)
        elif _typ == "error":
            st.error(_msg)
        else:
            st.info(_msg)
    else:
        if st.session_state.crawl_running:
            run_ctx = st.session_state.get("crawl_state", {}) or {}
            run_idx = int(run_ctx.get("index", 0) or 0)
            run_batch_total = int(run_ctx.get("batch_total", 0) or 0)
            run_is_finished_scan = bool(run_ctx.get("is_finished", False))
            run_board_url = str(run_ctx.get("board_url", "") or "").strip()
            run_board_i = int(run_ctx.get("current_board_idx", 0) or 0) + 1
            run_board_n = len(run_ctx.get("board_urls_queue", []) or [])
            run_board_names = run_ctx.get("board_names_queue", []) or []
            run_board_name = ""
            if run_board_i - 1 < len(run_board_names):
                run_board_name = str(run_board_names[run_board_i - 1] or "").strip()
            if run_board_url:
                if run_board_n > 0:
                    if run_board_name:
                        st.caption(f"📌 현재 게시판: {run_board_i}/{run_board_n} · {run_board_name}")
                    else:
                        st.caption(f"📌 현재 게시판: {run_board_i}/{run_board_n} · {run_board_url}")
                else:
                    st.caption(f"📌 현재 게시판: {run_board_url}")
            if run_is_finished_scan and run_batch_total > 0 and run_idx < run_batch_total:
                st.info(f"목록 탐색 완료 · 상세 저장 진행 중 ({run_idx:,}/{run_batch_total:,}건)")
            else:
                st.info("수집이 진행 중입니다. 아래 진행 요약/로그를 확인하세요.")
        else:
            st.info("아직 실행 결과가 없습니다. 1단계 브라우저 열기 후 2단계를 시작하세요.")

    # 체크포인트 UI는 전체 폭으로 표시 (좁은 컬럼에서 깨지는 현상 방지)
    if (not st.session_state.crawl_running) and st.session_state.crawl_checkpoint_available and st.session_state.crawl_state:
        legacy_backfill = bool(config.get("update_existing", False)) and bool(config.get("meta_only", True))
        current_level_backfill_mode = (
            bool(config.get("level_backfill", False))
            or bool(config.get("meta_backfill", False))
            or legacy_backfill
        )
        current_quick_recovery_mode = False
        current_signature = _build_run_signature(
            board_url=board_url,
            start_date_value=start_date,
            end_date_value=end_date,
            exclude_boards_raw="",
            level_backfill_mode=current_level_backfill_mode,
            quick_recovery_mode=current_quick_recovery_mode,
            delay_min_sec=int(delay_min_sec),
            delay_max_sec=int(delay_max_sec),
            speed_profile=speed_profile,
            start_page_manual=int(effective_start_page),
            auto_start_page=bool(auto_start_page),
        )
        saved_signature = st.session_state.crawl_state.get("run_signature", {})
        mismatches = _diff_run_signature(saved_signature, current_signature)

        if mismatches:
            mismatch_txt = "불일치 항목: " + ", ".join(mismatches)
            st.markdown(
                f'<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;padding:10px 16px;margin:8px 0;'
                f'color:#856404;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                f'현재 설정과 체크포인트 기준 설정이 다릅니다 - <span style="color:#000;">{mismatch_txt}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("중단된 작업 체크포인트가 있습니다.")

        if st.session_state.crawl_state.get("phase") == "run":
            # 불일치 시: 요약에 현재 설정(재개 시 적용될 값) 표시
            display_ctx = dict(st.session_state.crawl_state)
            if mismatches:
                display_ctx["crawl_delay_min"] = max(1.0, float(delay_min_sec))
                display_ctx["crawl_delay_max"] = max(max(1.0, float(delay_min_sec)), float(delay_max_sec))
            _render_crawl_summary(display_ctx, title="체크포인트 요약")
            if mismatches:
                st.caption("※ 재개 버튼을 누르면 현재 화면 설정으로 이어서 수집합니다.")

        st.caption("▶ 체크포인트 재개 — 중단된 지점부터 이어서 수집합니다. 새로 시작하려면 위의 2단계 크롤링 시작을 누르세요.")
        if st.button("▶ 체크포인트 재개", use_container_width=True, key="resume_from_checkpoint"):
            # 재개 시 현재 UI의 대기 설정을 반영 (저장된 예전 값 덮어쓰기)
            ctx = st.session_state.crawl_state
            # 재개 기준점 기록: 완료 요약에서 이미 처리된 건수를 스킵으로 표시
            ctx["resume_base_index"] = int(ctx.get("index", 0) or 0)
            # 재개 이후 구간 통계는 새로 집계
            ctx["skip_count"] = 0
            ctx["error_count"] = 0
            ctx["skip_reason_existing_level"] = 0
            ctx["skip_reason_existing_withdrawal"] = 0
            ctx["updated_level_count"] = 0
            ctx["consecutive_error_count"] = 0
            ctx["last_progress_logged_index"] = int(ctx.get("index", 0) or 0)
            ctx["fail_safe_enabled"] = bool(fail_safe_enabled)
            ctx["fail_safe_threshold"] = int(fail_safe_threshold)
            ctx["progress_log_every"] = int(progress_log_every)
            ctx["crawl_delay_min"] = max(1.0, float(delay_min_sec))
            ctx["crawl_delay_max"] = max(max(1.0, float(delay_min_sec)), float(delay_max_sec))
            ctx["speed_profile"] = speed_profile
            ctx["run_signature"] = current_signature
            ctx["run_started_at"] = datetime.now().isoformat()
            st.session_state.crawl_state = ctx
            st.session_state.crawl_last_status_message = ""
            st.session_state.crawl_running = True
            st.session_state.crawl_stop_requested = False
            update_logs("♻️ 체크포인트에서 작업을 재개합니다.")
            st.rerun()

    # 비동기처럼 동작하도록 한 건씩 처리 (중단 버튼 즉시 반영 가능)
    if st.session_state.crawl_running:
        ctx = st.session_state.crawl_state
        if st.session_state.get("crawler") and hasattr(st.session_state.crawler, "set_speed_profile"):
            st.session_state.crawler.set_speed_profile(str(ctx.get("speed_profile", "stable")))
        live_status = st.empty()
        phase = ctx.get("phase", "run")

        if phase == "prepare":
            # 초기화
            # 사용자가 시작 페이지를 지정하면 해당 위치부터 자동 탐색을 시작한다.
            ctx["page_cursor"] = max(1, int(ctx.get("start_page_manual", 1) or 1))
            ctx["last_scanned_page"] = 0
        
            ctx["articles"] = [] # 버퍼
            ctx["index"] = 0
            ctx["batch_total"] = 0
            ctx["total_collected"] = 0
            ctx["is_finished"] = False
            ctx["skip_reason_existing_level"] = 0
            ctx["skip_reason_existing_withdrawal"] = 0
        
            # DB Map Load (Common)
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            df_exist = pd.read_sql_query("SELECT post_id, member_level FROM posts", conn)
            existing_map = df_exist.set_index('post_id')['member_level'].to_dict()
            # (추가) member_id별 대표 등급 맵 (탈퇴 오판 복구용)
            df_mid_lvl = pd.read_sql_query(
                """
                SELECT member_id, member_level
                FROM posts
                WHERE member_id IS NOT NULL
                  AND TRIM(member_id) != ''
                  AND member_id != 'unknown'
                  AND member_level IS NOT NULL
                  AND TRIM(member_level) != ''
                  AND member_level != '탈퇴'
                  AND member_level != 'unknown'
                """,
                conn,
            )
            conn.close()
            ctx["existing_map"] = existing_map
            mid_level_map = {}
            if not df_mid_lvl.empty:
                # member_id별로 가장 자주 등장한 등급을 대표값으로 사용
                g = (
                    df_mid_lvl.groupby(["member_id", "member_level"])
                    .size()
                    .reset_index(name="cnt")
                    .sort_values(["member_id", "cnt"], ascending=[True, False])
                )
                mid_level_map = g.drop_duplicates(subset=["member_id"]).set_index("member_id")["member_level"].to_dict()
            ctx["member_level_map"] = mid_level_map

            if bool(ctx.get("quick_recovery_mode", False)):
                 # Quick Mode: Load everything at once
                 update_logs("⚡ 빠른 복구 모드: DB에서 등급 누락 항목을 조회합니다...")
             
                 retry_withdrawal_ctx = bool(ctx.get("retry_withdrawal", False))
                 start_s = ctx["start_dt"].strftime("%Y-%m-%d")
                 end_s = ctx["end_dt"].strftime("%Y-%m-%d")
             
                 # (수정) 날짜 범위(start_dt ~ end_dt)를 준수하며 복구 대상 조회
                 conn = sqlite3.connect(DB_PATH)
             
                 # 조건: 날짜 범위 내 AND (등급없음 OR (재검사=True AND 등급='탈퇴'))
                 # SQLite에서 날짜 비교는 문자열(YYYY-MM-DD)로 가능
                 query = f"""
                    SELECT post_id, url, title, member_id, nickname, member_level, date
                    FROM posts
                    WHERE date >= ? AND date <= ?
                    AND (
                        member_level IS NULL 
                        OR member_level = '' 
                        OR member_level = 'unknown' 
                        OR (? AND member_level = '탈퇴')
                    )
                    ORDER BY date DESC
                 """
                 params = (start_s, end_s, 1 if retry_withdrawal_ctx else 0)
             
                 df_targets = pd.read_sql_query(query, conn, params=params)
                 conn.close()
             
                 target_ids = df_targets['post_id'].tolist()
             
                 if not target_ids:
                      st.session_state.crawl_running = False
                      _clear_crawl_checkpoint()
                      update_logs(f"✅ 지정된 기간({start_s}~{end_s})에 복구 대상이 없습니다.")
                      st.session_state.crawl_last_status_type = "success"
                      st.session_state.crawl_last_status_message = f"✅ 지정된 기간({start_s}~{end_s})에 복구 대상이 없습니다."
                      st.rerun()
             
                 ctx["articles"] = df_targets.to_dict('records')
                 ctx["is_finished"] = True # No more fetching needed
                 update_logs(f"⚡ 기간({start_s}~{end_s}) 내 복구 대상 {len(ctx['articles'])}개를 찾았습니다.")
        
            ctx["phase"] = "run"
            _save_crawl_checkpoint(force=True)
            st.rerun()

        else:
            # Phase: run
            # (수정) 중단 요청이 있으면 즉시 처리 (배치 로직 진입 전)
            if st.session_state.crawl_stop_requested:
                st.session_state.crawl_running = False
                st.session_state.crawl_stop_requested = False
                _save_crawl_checkpoint(force=True)
                live_status.warning("⏹ 사용자 요청으로 중단되었습니다.")
                update_logs("🛑 중단 완료")
                st.session_state.crawl_last_status_type = "warning"
                st.session_state.crawl_last_status_message = "⏹ 사용자 요청으로 중단되었습니다."
                st.rerun()

            articles_buffer = ctx.get("articles", [])
            total_in_buffer = len(articles_buffer)
            idx = int(ctx.get("index", 0))
        
            # 버퍼가 비었거나 다 처리했으면 -> 다음 배치 가져오기 or 종료
            if idx >= total_in_buffer:
                if ctx.get("is_finished", False):
                    # 진짜 종료
                    resume_base_index = int(ctx.get("resume_base_index", 0) or 0)
                    skip_count = int(ctx.get("skip_count", 0))
                    error_count = int(ctx.get("error_count", 0))
                    updated_level_count = int(ctx.get("updated_level_count", 0))
                    changed_level_count = int(ctx.get("changed_level_count", 0))
                    unchanged_level_count = int(ctx.get("unchanged_level_count", 0))
                    total_processed = int(ctx.get("total_collected", 0))
                
                    # total_collected가 0이면 quick mode나 초기 상태일 수 있음
                    if total_processed == 0 and total_in_buffer > 0:
                        total_processed = total_in_buffer

                    success_count = max(0, total_processed - skip_count - error_count)

                    if skip_count > 0:
                        update_logs(f"💡 기존 수집분 {skip_count}개를 건너뛰었습니다.")
                        skip_existing_level = int(ctx.get("skip_reason_existing_level", 0) or 0)
                        skip_existing_withdrawal = int(ctx.get("skip_reason_existing_withdrawal", 0) or 0)
                        reasons = []
                        if skip_existing_level > 0:
                            reasons.append(f"기존 글(등급 보유) {skip_existing_level}건")
                        if skip_existing_withdrawal > 0:
                            reasons.append(f"기존 글(등급=탈퇴, 재검사 끔) {skip_existing_withdrawal}건")
                        if reasons:
                            update_logs(f"   └ 스킵 사유: {', '.join(reasons)}")
                    if updated_level_count > 0:
                        update_logs(f"🏷️ 등급 보강 완료: {updated_level_count}개")
                    if changed_level_count > 0 or unchanged_level_count > 0:
                        update_logs(f"🧾 등급 변경 {changed_level_count}개 / 동일 유지 {unchanged_level_count}개")
                    if error_count > 0:
                        update_logs(f"⚠️ {error_count}개 항목 수집 실패 (나머지는 정상 처리)")
                    if success_count > 0:
                        st.balloons()
                        update_logs(f"✨ {success_count}개 게시글 수집 완료!")
                    board_urls_queue = ctx.get("board_urls_queue", []) or []
                    current_board_idx = int(ctx.get("current_board_idx", 0) or 0)
                    board_names_queue = ctx.get("board_names_queue", []) or []
                    current_board_name = ""
                    if current_board_idx < len(board_names_queue):
                        current_board_name = str(board_names_queue[current_board_idx] or "").strip()
                    current_board_url = str(ctx.get("board_url", "") or "").strip()
                    if current_board_name:
                        update_logs(f"✅ 게시판 완료: {current_board_name} (성공 {success_count}건)")
                    else:
                        update_logs(f"✅ 게시판 완료: {current_board_url} (성공 {success_count}건)")

                    # 다음 게시판이 있으면 순차 진행
                    if board_urls_queue and current_board_idx + 1 < len(board_urls_queue):
                        next_idx = current_board_idx + 1
                        next_url = str(board_urls_queue[next_idx] or "").strip()
                        next_name = ""
                        if next_idx < len(board_names_queue):
                            next_name = str(board_names_queue[next_idx] or "").strip()

                        ctx["current_board_idx"] = next_idx
                        ctx["board_url"] = next_url
                        ctx["phase"] = "prepare"
                        ctx["articles"] = []
                        ctx["index"] = 0
                        ctx["batch_total"] = 0
                        ctx["total_collected"] = 0
                        ctx["is_finished"] = False
                        ctx["skip_reason_existing_level"] = 0
                        ctx["skip_reason_existing_withdrawal"] = 0
                        ctx["skip_count"] = 0
                        ctx["error_count"] = 0
                        ctx["updated_level_count"] = 0
                        ctx["changed_level_count"] = 0
                        ctx["unchanged_level_count"] = 0
                        ctx["last_scan_oldest_date"] = ""
                        ctx["last_scanned_page"] = 0
                        _save_crawl_checkpoint(force=True)
                        if next_name:
                            update_logs(f"🔄 다음 게시판({next_idx+1}/{len(board_urls_queue)})으로 이동합니다: {next_name}")
                        else:
                            update_logs(f"🔄 다음 게시판({next_idx+1}/{len(board_urls_queue)})으로 이동합니다: {next_url}")
                        st.rerun()
                    else:
                        st.session_state.crawl_running = False
                        _clear_crawl_checkpoint()
                        last_scanned_page = int(ctx.get("last_scanned_page", 0) or 0)
                        last_page_suffix = f" 마지막 탐색 페이지: {last_scanned_page}p" if last_scanned_page > 0 else ""
                        if success_count == 0:
                            done_msg = (
                                f"⚠️ 수집된 게시글이 없습니다. (성공: {success_count}, 스킵: {skip_count}, 실패: {error_count}, "
                                f"등급변경: {changed_level_count}, 등급동일: {unchanged_level_count}) "
                                f"- 기간/게시판/페이지 로딩 상태를 확인해주세요.{last_page_suffix}"
                            )
                            live_status.warning(done_msg)
                            st.session_state.crawl_last_status_type = "warning"
                        else:
                            done_msg = (
                                f"✅ 작업 완료 (성공: {success_count}, 스킵: {skip_count}, 실패: {error_count}, "
                                f"등급변경: {changed_level_count}, 등급동일: {unchanged_level_count}){last_page_suffix}"
                            )
                            live_status.success(done_msg)
                            st.session_state.crawl_last_status_type = "success"
                        st.session_state.crawl_last_status_message = done_msg
                        st.rerun()
                else:
                    # 다음 배치 가져오기
                    page_cursor = int(ctx.get("page_cursor", 1))
                    # (수정) 50개씩 보기 모드이므로, 배치 크기도 20페이지가 아닌 5페이지 정도로 줄여서
                    # 더 자주 저장하고 반응성을 높이는 게 좋음 (50개 * 5페이지 = 250개)
                    batch_size = 5
                
                    # 진행 상황 표시
                    total_collected = int(ctx.get("total_collected", 0))
                
                    # (수정) 실시간 상태 업데이트를 위해 spinner 대신 live_status와 콜백 활용
                    # 크롤러 내부에서 _update_status 호출 시 live_status도 갱신되도록 콜백 연결
                    def _dynamic_status_callback(msg):
                        update_logs(msg)
                        live_status.info(msg)
                
                    st.session_state.crawler.set_status_callback(_dynamic_status_callback)
                
                    # 초기 상태 메시지
                    cur_board_i = int(ctx.get("current_board_idx", 0) or 0) + 1
                    cur_board_n = len(ctx.get("board_urls_queue", []) or [])
                    cur_board_url = str(ctx.get("board_url", "") or "").strip()
                    cur_board_name = ""
                    bq = ctx.get("board_names_queue", []) or []
                    if cur_board_i - 1 < len(bq):
                        cur_board_name = str(bq[cur_board_i - 1] or "").strip()
                    if cur_board_n > 0 and cur_board_url:
                        if cur_board_name:
                            live_status.info(f"🔍 게시글 목록 수집 시작 ({cur_board_i}/{cur_board_n}) · {cur_board_name} · 페이지 {page_cursor} ~")
                        else:
                            live_status.info(f"🔍 게시글 목록 수집 시작 ({cur_board_i}/{cur_board_n}) · 페이지 {page_cursor} ~")
                    else:
                        live_status.info(f"🔍 게시글 목록 수집 시작 (페이지 {page_cursor} ~)...")
                
                    new_batch, is_finished = st.session_state.crawler.scrape_board_list(
                        ctx["board_url"],
                        ctx["start_dt"],
                        ctx["end_dt"],
                        exclude_boards=ctx.get("exclude_boards", []),
                        start_page=page_cursor,
                        max_pages=batch_size,
                    )
                    effective_start_page = int(getattr(st.session_state.crawler, "last_effective_start_page", page_cursor) or page_cursor)
                    scan_oldest_date = str(getattr(st.session_state.crawler, "last_scan_oldest_date", "") or "").strip()
                    last_scanned_page = int(getattr(st.session_state.crawler, "last_scanned_page", 0) or 0)
                    if scan_oldest_date:
                        ctx["last_scan_oldest_date"] = scan_oldest_date
                    if last_scanned_page > 0:
                        ctx["last_scanned_page"] = last_scanned_page
                
                    # 배치 종료 후 콜백 원복 (선택사항이지만 안전하게)
                    st.session_state.crawler.set_status_callback(update_logs)
                
                    if not new_batch and not is_finished:
                        # 이번 배치 공탕 -> 다음 페이지로 계속 (재귀적 rerun 방지 위해 cursor만 증가)
                        ctx["page_cursor"] = effective_start_page + batch_size
                        _save_crawl_checkpoint()
                        st.rerun()
                
                    if not new_batch and is_finished:
                        # 종료 조건 도달
                        ctx["is_finished"] = True
                        _save_crawl_checkpoint()
                        st.rerun()
                
                    # (수정) 날짜 범위에 맞는 글이 하나도 없는데 계속 진행되는 경우 방지
                    # 만약 이번 배치에서 수집된 글이 없고, last_seen_date가 start_date보다 과거라면 이미 다 지나친 것임
                    if not new_batch:
                        # scrape_board_list 내부에서 is_finished=True로 반환했으면 위에서 처리됨
                        # 여기는 is_finished=False인데 수집은 0개인 경우 (즉, 해당 페이지 글들이 모두 end_date보다 미래인 최신글이라 스킵됨)
                        # 따라서 계속 과거로 가야 함 (정상)
                    
                        # 페이지 수 기준 하드 스탑은 두지 않는다.
                        # 오래된 글이 많은 카페(수천/수만 페이지)도 정상 탐색할 수 있어야 한다.
                        empty_streak = int(ctx.get("empty_batch_streak", 0)) + 1
                        ctx["empty_batch_streak"] = empty_streak
                        if empty_streak % 20 == 0:
                            update_logs(
                                f"ℹ️ 해당 기간 글 탐색 중... (연속 공배치 {empty_streak}회, 계속 진행)"
                            )
                    else:
                        ctx["empty_batch_streak"] = 0 # 수집 성공하면 스트릭 초기화

                    # 새 배치 있음 (또는 빈 배치지만 계속 탐색)
                    ctx["articles"] = new_batch
                    ctx["index"] = 0
                    ctx["batch_total"] = len(new_batch)
                    ctx["page_cursor"] = effective_start_page + batch_size
                    ctx["is_finished"] = is_finished
                    ctx["total_collected"] = total_collected + len(new_batch)
                
                    update_logs(f"📋 {len(new_batch)}개 게시글 발견 (누적 {ctx['total_collected']}개). 상세 수집 진행...")
                    _save_crawl_checkpoint()
                    st.rerun()
        
            # 처리할 아이템이 있음
            art = articles_buffer[idx]
            total_collected_so_far = int(ctx.get("total_collected", total_in_buffer))
        
            # 진행률 표시
            _render_crawl_summary(ctx, title="실시간 진행 요약")

            # 도표는 최종 완료율 1개만 표시 (개수 기반)
            metrics = _build_completion_metrics(ctx)
            completion_ratio = metrics.get("completion_ratio")
            est_total = metrics.get("est_total")
            completed = int(metrics.get("completed", 0) or 0)
            if completion_ratio is not None and est_total:
                safe_ratio = float(min(max(completion_ratio, 0.0), 1.0))
                # 0.x%에서도 시각적으로 보이도록 최소 표시폭을 보장
                visual_ratio = safe_ratio if safe_ratio <= 0.0 else max(safe_ratio, 0.012)
                st.markdown(
                    f"""
                    <div style="width:100%;height:12px;background:#e5e7eb;border-radius:999px;overflow:hidden;margin-top:4px;">
                      <div style="height:100%;width:{visual_ratio*100:.3f}%;background:#2f80ed;border-radius:999px;"></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='text-align:right;color:#334155;font-size:1.0rem;font-weight:700;margin-top:6px;'>전체 완료율(추정): {completed:,}/{int(est_total):,} ({completion_ratio*100:.1f}%)</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="width:100%;height:12px;background:#e5e7eb;border-radius:999px;overflow:hidden;margin-top:4px;">
                      <div style="height:100%;width:0%;background:#2f80ed;border-radius:999px;"></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='text-align:right;color:#334155;font-size:1.0rem;font-weight:700;margin-top:6px;'>전체 완료율(추정): 계산 중... · 현재 수집 {completed:,}개</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)

            if st.session_state.crawl_stop_requested:
                st.session_state.crawl_running = False
                st.session_state.crawl_stop_requested = False
                _save_crawl_checkpoint(force=True)
                live_status.warning("⏹ 사용자 요청으로 중단되었습니다.")
                update_logs(f"🛑 중단 완료 (누적 {total_collected_so_far}개 처리 중)")
                st.session_state.crawl_last_status_type = "warning"
                st.session_state.crawl_last_status_message = "⏹ 사용자 요청으로 중단되었습니다."
                st.rerun()
            else:
                collect_mode_ctx = str(ctx.get("collect_mode", "posts_and_comments") or "posts_and_comments").strip()
                comment_mode_ctx = "all" if collect_mode_ctx == "posts_and_comments" else "none"
                level_backfill_mode = bool(ctx["level_backfill_mode"])
                crawl_delay_min = float(ctx["crawl_delay_min"])
                crawl_delay_max = float(ctx["crawl_delay_max"])
                before_error_count = int(ctx.get("error_count", 0))

                try:
                    # 30개마다 60초 휴식 (장시간 수집 시 차단 방지)
                    # 전체 누적 카운트 기반으로 휴식 체크
                    global_idx = int(ctx.get("global_processed_count", 0))
                    speed_profile_ctx = str(ctx.get("speed_profile", "stable") or "stable").lower()
                    rest_mult = 0.5 if speed_profile_ctx == "fast" else 1.0
                    if global_idx > 0 and global_idx % 30 == 0:
                        rest_sec = int(max(20, 60 * rest_mult))
                        update_logs(f"☕ 네이버 차단 방지를 위해 {rest_sec}초간 휴식합니다... (누적 {global_idx}개 처리)")
                        time.sleep(rest_sec)
                
                    ctx["global_processed_count"] = global_idx + 1

                    art_id = art['post_id']
                    # existing_map이 없으면(구버전 체크포인트 등) 빈 딕셔너리로 처리하여 안전하게 수집 시도
                    exist_map = ctx.get("existing_map", {})
                    is_exist = art_id in exist_map
                
                    # [스마트 스킵 결정 로직]
                    # 1. 아예 없는 글(New) -> 수집 (is_exist=False)
                    # 2. 있는 글인데 등급이 비어있음 -> 보강 (need_backfill=True)
                    # 3. 있는 글이고 등급도 있음 -> 스킵 (단, level_backfill_mode가 강제로 켜져있으면 보강)
                
                    db_level = str(exist_map.get(art_id) or "").strip()
                    # 등급이 없거나(빈문자열), '탈퇴'가 아닌데도 비어있는 경우 등
                    # (수정) retry_withdrawal 옵션이 켜져 있으면 '탈퇴'도 재검사 대상에 포함
                    retry_withdrawal_ctx = bool(ctx.get("retry_withdrawal", False))
                    need_backfill = is_exist and (
                        level_backfill_mode 
                        or not db_level 
                        or (retry_withdrawal_ctx and db_level == "탈퇴")
                    )
                
                    if is_exist and not need_backfill:
                        ctx["skip_count"] = int(ctx.get("skip_count", 0)) + 1
                        if db_level == "탈퇴" and not retry_withdrawal_ctx:
                            ctx["skip_reason_existing_withdrawal"] = int(ctx.get("skip_reason_existing_withdrawal", 0) or 0) + 1
                            skip_reason_txt = "이미 수집됨 + 기존 등급이 '탈퇴'(재검사 꺼짐)"
                        else:
                            ctx["skip_reason_existing_level"] = int(ctx.get("skip_reason_existing_level", 0) or 0) + 1
                            skip_reason_txt = "이미 수집됨 + 등급 보유"
                        update_logs(f"↩️ 스킵: '{art['title'][:20]}...' ({skip_reason_txt})")
                    else:
                        if is_exist and need_backfill:
                            live_status.text(f"🏷️ 등급 보강 중: {art['title'][:40]}...")
                            update_logs(f"🏷️ 등급 보강(스마트): '{art['title'][:20]}...'")
                            try:
                                # 1차: API 전용 경로(속도 우선)
                                if hasattr(st.session_state.crawler, "get_article_member_level"):
                                    lvl = str(st.session_state.crawler.get_article_member_level(art["url"]) or "").strip()
                                else:
                                    lvl = ""
                                    if not bool(ctx.get("warned_missing_level_method", False)):
                                        update_logs("⚠️ 구 세션 감지: 빠른 등급 API 메서드 없음 → 상세 폴백으로 자동 전환")
                                        ctx["warned_missing_level_method"] = True
                                # 2차: API가 비면 상세 1회 폴백(안정성 우선)
                                # 단, 빠른 복구 모드(quick_recovery_mode)일 때는 속도를 위해 폴백을 생략
                                quick_mode_on = bool(ctx.get("quick_recovery_mode", False))
                            
                                if not lvl:
                                    # (수정) 퀵 모드라도 API에서 등급을 못 찾으면, '부 매니저' 같은 특수 등급일 수 있으므로
                                    # 무조건 '탈퇴'로 단정하지 말고 상세 페이지(DOM)를 1회 확인해야 함.
                                    # 속도가 느려지더라도 정확도가 우선임 (사용자 불만: 멀쩡한 부매니저 탈퇴 처리됨)
                                    detail_fb = st.session_state.crawler.scrape_article_detail(
                                        art["url"],
                                        art.get("member_id", "unknown"),
                                        [],
                                        comment_mode="none",
                                    )
                                    lvl = str(detail_fb.get("member_level", "") or "").strip()

                                    # (추가) DB 기반 보정: 같은 member_id의 과거 정상 등급이 있으면 우선 사용
                                    if not lvl:
                                        mid = str(art.get("member_id") or "").strip()
                                        map_lvl = str(ctx.get("member_level_map", {}).get(mid) or "").strip()
                                        if map_lvl:
                                            lvl = map_lvl
                                            update_logs(f"🩹 DB 보정 적용: '{art['title'][:20]}...' (member_id 기준 → {lvl})")

                                    # 최종적으로도 근거 없으면 기존값 유지(오탐 방지)
                                    if not lvl:
                                        lvl = str(db_level or "").strip()
                                        if not lvl:
                                            lvl = "탈퇴"

                                conn_u = sqlite3.connect(DB_PATH, timeout=30.0)
                                cur_u = conn_u.cursor()
                                if lvl:
                                    # (추가) API/DOM 결과가 탈퇴여도, 같은 member_id의 과거 정상 등급이 있으면 복구
                                    if lvl == "탈퇴":
                                        mid = str(art.get("member_id") or "").strip()
                                        map_lvl = str(ctx.get("member_level_map", {}).get(mid) or "").strip()
                                        if map_lvl:
                                            update_logs(f"🩹 탈퇴 오판 보정: '{art['title'][:20]}...' (탈퇴 → {map_lvl})")
                                            lvl = map_lvl

                                    prev_lvl = str(db_level or "").strip()
                                    if lvl != prev_lvl:
                                        cur_u.execute(
                                            "UPDATE posts SET member_level = ? WHERE post_id = ?",
                                            (lvl, art["post_id"]),
                                        )
                                        ctx["updated_level_count"] = int(ctx.get("updated_level_count", 0)) + 1
                                        ctx["changed_level_count"] = int(ctx.get("changed_level_count", 0)) + 1
                                        update_logs(f"🔁 등급 변경: '{art['title'][:20]}...' ({prev_lvl or '공백'} → {lvl})")
                                        if prev_lvl == "탈퇴":
                                            live_status.info(f"🏷️ 등급 보강 중: {art['title'][:30]}... | 탈퇴 -> {lvl} 으로 수정")
                                    else:
                                        ctx["unchanged_level_count"] = int(ctx.get("unchanged_level_count", 0)) + 1
                                    # 탈퇴 회원은 로그에 명시
                                    if lvl == "탈퇴":
                                        update_logs(f"🏷️ 등급 보강(탈퇴): '{art['title'][:20]}...'")
                                else:
                                    ctx["error_count"] = int(ctx.get("error_count", 0)) + 1
                                    update_logs(f"⚠️ 등급 미확보: '{art['title'][:20]}...'")
                                conn_u.commit()
                                conn_u.close()
                            except Exception as meta_err:
                                ctx["error_count"] = int(ctx.get("error_count", 0)) + 1
                                update_logs(f"⚠️ 등급 보강 실패: {meta_err}")
                        else:
                            live_status.text(f"📄 수집 중: {art['title'][:40]}...")
                            update_logs(f"📄 '{art['title'][:20]}...' 수집 중")
                            try:
                                detail = st.session_state.crawler.scrape_article_detail(
                                    art['url'],
                                    art['member_id'],
                                    [],
                                    comment_mode=comment_mode_ctx,
                                )
                                art['content'] = detail['content']
                                if detail.get("category"):
                                    art["category"] = detail.get("category", "")
                                if detail.get("view_count") is not None:
                                    art["view_count"] = detail.get("view_count", 0)
                                if detail.get("like_count") is not None:
                                    art["like_count"] = detail.get("like_count", 0)
                                if detail.get("member_id") and detail.get("member_id") != "unknown":
                                    art["member_id"] = detail["member_id"]
                                if (not art.get("nickname") or art.get("nickname") == "unknown") and detail.get("nickname") and detail.get("nickname") != "unknown":
                                    art["nickname"] = detail["nickname"]
                                if (not art.get("board_name")) and detail.get("board_name"):
                                    art["board_name"] = detail["board_name"]
                                # 신규 수집 등급 결정 규칙:
                                # 1) 상세/API 등급
                                # 2) 같은 member_id의 DB 대표 등급 보정
                                # 3) 그래도 없으면 '탈퇴'
                                detail_level = str(detail.get("member_level", "") or "").strip()
                                final_level = detail_level
                                if not final_level:
                                    mid = str(art.get("member_id") or "").strip()
                                    map_lvl = str(ctx.get("member_level_map", {}).get(mid) or "").strip()
                                    if map_lvl:
                                        final_level = map_lvl
                                        update_logs(f"🩹 DB 보정 적용: '{art['title'][:20]}...' (member_id 기준 → {final_level})")
                                if not final_level:
                                    final_level = "탈퇴"
                                art["member_level"] = final_level
                                save_to_sqlite(art, detail['comments'])
                            
                                lvl_log = art.get("member_level", "")
                                update_logs(f"✅ '{art['title'][:20]}...' 저장 완료 (등급: {lvl_log})")
                            except Exception as detail_error:
                                ctx["error_count"] = int(ctx.get("error_count", 0)) + 1
                                update_logs(f"⚠️ '{art['title'][:20]}...' 수집 실패: {detail_error}")

                        # 항목 처리 후 딜레이
                        time.sleep(random.uniform(crawl_delay_min, crawl_delay_max))
                except Exception as loop_error:
                    ctx["error_count"] = int(ctx.get("error_count", 0)) + 1
                    # 에러 상세 내용을 로그에 남겨 원인 파악을 돕습니다.
                    error_detail = str(loop_error)
                    if len(error_detail) > 200:
                        error_detail = error_detail[:200] + "..."
                    update_logs(f"❌ 항목 처리 중 오류: {error_detail}")

                # 실패 감지/알림 강화
                after_error_count = int(ctx.get("error_count", 0))
                item_failed = after_error_count > before_error_count
                if item_failed:
                    ctx["consecutive_error_count"] = int(ctx.get("consecutive_error_count", 0)) + 1
                    consecutive = int(ctx.get("consecutive_error_count", 0))
                    # 과도한 로그 스팸을 막기 위해 1회/매 10회마다만 강조 로그
                    if consecutive == 1 or consecutive % 10 == 0:
                        update_logs(
                            f"🚨 실패 누적: 연속 {consecutive}건 / 총 실패 {after_error_count}건"
                        )
                else:
                    ctx["consecutive_error_count"] = 0

                # 주기적 진행 요약 로그(장시간 무응답처럼 보이는 문제 방지)
                log_every = max(10, int(ctx.get("progress_log_every", 100) or 100))
                current_processed = total_collected_so_far # 대략적
                last_logged = int(ctx.get("last_progress_logged_index", 0) or 0)
                if (current_processed - last_logged) >= log_every:
                    resume_base_index = int(ctx.get("resume_base_index", 0) or 0)
                    skip_count_now = int(ctx.get("skip_count", 0))
                    error_count_now = int(ctx.get("error_count", 0))
                    success_count_now = max(0, current_processed - (resume_base_index + skip_count_now + error_count_now))
                    update_logs(
                        f"📊 진행 요약: 누적 {current_processed}개 처리 중 "
                        f"(성공 {success_count_now}, 스킵 {resume_base_index + skip_count_now}, 실패 {error_count_now})"
                    )
                    ctx["last_progress_logged_index"] = current_processed

                # 연속 실패 자동 중단(시간 손실 방지)
                fail_safe_enabled_ctx = bool(ctx.get("fail_safe_enabled", True))
                fail_safe_threshold_ctx = max(5, int(ctx.get("fail_safe_threshold", 40) or 40))
                consecutive_now = int(ctx.get("consecutive_error_count", 0) or 0)
                if fail_safe_enabled_ctx and consecutive_now >= fail_safe_threshold_ctx:
                    st.session_state.crawl_running = False
                    st.session_state.crawl_stop_requested = False
                    st.session_state.crawl_state = ctx
                    _save_crawl_checkpoint(force=True)
                    stop_msg = (
                        f"🛑 안전 중단: 연속 실패 {consecutive_now}건(임계 {fail_safe_threshold_ctx}) "
                        f"- 원인 확인 후 재개하세요."
                    )
                    live_status.error(stop_msg)
                    update_logs(stop_msg)
                    st.session_state.crawl_last_status_type = "error"
                    st.session_state.crawl_last_status_message = stop_msg
                    st.rerun()

                ctx["index"] = idx + 1
                st.session_state.crawl_state = ctx
                _save_crawl_checkpoint()
                st.rerun()

    # 초기 로그 표시
    update_logs()

    # DB 관리 UI (데이터 조회 및 삭제)
    st.markdown("---")
    open_data_manager = st.checkbox(
        "📊 데이터 관리 열기 (기본 닫힘)",
        value=False,
        key="open_data_manager_toggle",
        help="크롤링 설정/게시판 선택과 무관한 DB 관리 화면입니다. 열 때만 데이터를 로드합니다.",
    )
    if not open_data_manager:
        st.caption("게시판 선택/크롤링만 사용할 때는 데이터 관리 로딩을 건너뜁니다.")
        st.stop()

    st.header("📊 데이터 관리")
    st.caption("수집된 게시글/댓글 데이터를 검토하고 선택 삭제 및 상세 확인을 진행합니다.")

    if "posts_editor_refresh" not in st.session_state:
        st.session_state.posts_editor_refresh = 0
    if "comments_editor_refresh" not in st.session_state:
        st.session_state.comments_editor_refresh = 0

    tab1, tab2 = st.tabs(["📝 게시글 관리", "💬 댓글 관리"])

    with tab1:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            df_posts = pd.read_sql_query(
                "SELECT post_id, member_id, nickname, member_level, title, content, date, board_name, view_count, like_count, url "
                "FROM posts ORDER BY date DESC",
                conn,
            )
        
            if not df_posts.empty:
                st.write(f"**표시: {len(df_posts):,}개 게시글**")
            
                # 선택된 게시글 저장
                if "selected_posts" not in st.session_state:
                    st.session_state.selected_posts = []
            
                # 게시글 테이블 표시용 데이터 (체크박스 선택)
                df_display = df_posts.copy()
                df_display.insert(0, "선택", False)
            
                # content는 미리보기로 (100자만)
                df_display['본문미리보기'] = df_display['content'].apply(lambda x: str(x)[:100] + '...' if x and len(str(x)) > 100 else str(x))
                df_display = df_display.drop(columns=['content'])  # 전체 본문은 숨김
                # 작성자ID는 공간 절약을 위해 축약 표시
                df_display["member_id"] = df_display["member_id"].apply(
                    lambda x: (f"{str(x)[:6]}...{str(x)[-4:]}" if x and len(str(x)) > 14 else str(x))
                )

                # 기존 선택 복원
                for idx, post_id in enumerate(df_display["post_id"]):
                    if post_id in st.session_state.selected_posts:
                        df_display.at[idx, "선택"] = True

                edited_df = st.data_editor(
                    df_display,
                    column_config={
                        "선택": st.column_config.CheckboxColumn("선택", default=False, width="small"),
                        "post_id": "게시글 ID",
                        "member_id": st.column_config.TextColumn("작성자 ID", width="small"),
                        "nickname": "닉네임",
                        "member_level": "등급",
                        "board_name": "게시판",
                        "view_count": "조회수",
                        "like_count": "좋아요",
                        "title": st.column_config.TextColumn("제목", width="medium"),
                        "본문미리보기": st.column_config.TextColumn("본문 미리보기", width="large"),
                        "date": "작성일",
                        "url": st.column_config.LinkColumn("URL", width="small")
                    },
                    hide_index=True,
                    use_container_width=True,
                    disabled=[
                        "post_id",
                        "member_id",
                        "nickname",
                        "member_level",
                        "title",
                        "본문미리보기",
                        "date",
                        "board_name",
                        "view_count",
                        "like_count",
                        "url",
                    ],
                    key=f"posts_editor_{st.session_state.posts_editor_refresh}",
                )
                pending_selected_posts = edited_df[edited_df["선택"] == True]["post_id"].tolist()

                st.caption("테이블 하단 좌측에서 선택/삭제를 처리하고, 우측에서 상세 내용을 확인합니다.")
                st.markdown("---")

                col_actions, col_detail = st.columns([1, 2], gap="medium")

                with col_actions:
                    st.markdown("#### 🧰 선택/삭제 작업")
                    st.caption(f"반영된 선택: {len(st.session_state.selected_posts)}개")

                    if st.button("✅ 선택 반영", use_container_width=True, key="apply_posts_selection_left"):
                        st.session_state.selected_posts = pending_selected_posts
                        st.session_state.posts_editor_refresh += 1
                        st.rerun()

                    if st.button("☑️ 전체 선택", use_container_width=True, key="select_all_posts"):
                        st.session_state.selected_posts = df_posts['post_id'].tolist()
                        st.session_state.posts_editor_refresh += 1
                        st.rerun()

                    if st.button("⬜ 전체 해제", use_container_width=True, key="deselect_all_posts"):
                        st.session_state.selected_posts = []
                        st.session_state.posts_editor_refresh += 1
                        st.rerun()

                    if st.session_state.selected_posts:
                        if "confirm_delete_posts" not in st.session_state:
                            st.session_state.confirm_delete_posts = False
                        if not st.session_state.confirm_delete_posts:
                            if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_posts)})", type="primary", use_container_width=True, key="delete_posts_req"):
                                st.session_state.confirm_delete_posts = True
                                st.rerun()
                        else:
                            st.button("삭제 대기 중...", disabled=True, use_container_width=True, key="delete_posts_wait")
                    else:
                        st.button("🗑️ 선택 항목 삭제", disabled=True, use_container_width=True, key="delete_posts_disabled")

                    if st.session_state.get("confirm_delete_posts", False):
                        st.warning(
                            f"선택한 {len(st.session_state.selected_posts)}개 게시글과 관련 댓글이 영구 삭제됩니다. 되돌릴 수 없습니다."
                        )
                        if st.button("✅ 예, 확실히 삭제합니다", type="primary", use_container_width=True, key="real_delete_posts"):
                            try:
                                cursor = conn.cursor()
                                for post_id in st.session_state.selected_posts:
                                    cursor.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
                                    cursor.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
                                conn.commit()
                                st.success(f"✅ {len(st.session_state.selected_posts)}개 게시글과 관련 댓글이 삭제되었습니다!")
                                st.session_state.selected_posts = []
                                st.session_state.posts_editor_refresh += 1
                                st.session_state.confirm_delete_posts = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")
                        if st.button("❌ 취소", use_container_width=True, key="cancel_delete_posts"):
                            st.session_state.confirm_delete_posts = False
                            st.rerun()

                with col_detail:
                    st.subheader("📄 게시글 상세 보기")
                    post_options = df_posts['post_id'].tolist()
                    selected_post_id = None
                    if st.session_state.selected_posts:
                        valid_selected = [pid for pid in st.session_state.selected_posts if pid in post_options]
                        if valid_selected:
                            selected_post_id = valid_selected[0]
                            st.caption(
                                f"현재 상세 표시: 체크 반영된 게시글 {len(valid_selected)}개 중 첫 번째 (`{selected_post_id}`)"
                            )
                    if selected_post_id is None:
                        selected_post_id = post_options[0] if post_options else None
                        if selected_post_id is not None:
                            st.caption(
                                f"체크 반영된 항목이 없어 최신 게시글 (`{selected_post_id}`)을 표시합니다."
                            )

                with col_detail:
                    if selected_post_id:
                        post_detail = df_posts[df_posts['post_id'] == selected_post_id].iloc[0]
                        df_post_comments = pd.DataFrame()

                        def _detail_info_box(label: str, value: str) -> str:
                            v = html.escape(str(value or "-"))
                            return f"""
                            <div style="border:1px solid #dfe6ef;border-radius:10px;padding:0.55rem 0.7rem;background:#fbfdff;min-height:84px;">
                                <div style="font-size:0.82rem;color:#64748b;font-weight:600;margin-bottom:0.25rem;">{label}</div>
                                <div style="font-size:1.02rem;line-height:1.35;color:#111827;font-weight:700;word-break:break-all;">{v}</div>
                            </div>
                            """

                        col_d1, col_d2, col_d3, col_d4 = st.columns([1, 1, 1, 1])
                        col_d1.markdown(_detail_info_box("작성자 ID (내부식별값)", post_detail.get('member_id', '')), unsafe_allow_html=True)
                        col_d2.markdown(_detail_info_box("닉네임", post_detail.get('nickname', '')), unsafe_allow_html=True)
                        col_d3.markdown(_detail_info_box("등급", post_detail.get('member_level', '')), unsafe_allow_html=True)
                        col_d4.markdown(_detail_info_box("작성일", post_detail.get('date', '')), unsafe_allow_html=True)
                        st.caption("※ 작성자 ID는 네이버 내부 식별값입니다. 길고 난수처럼 보여도 정상이며, 동일 작성자 추적용으로 사용됩니다.")

                        st.markdown(f"**제목:** {post_detail['title']}")
                        _detail_url = str(post_detail.get('url', '') or '').strip()
                        if _detail_url:
                            st.markdown(f"**URL:** [게시글로 바로가기]({_detail_url})")
                        else:
                            st.markdown("**URL:** -")
                        st.markdown("**본문:**")
                        st.markdown(
                            f"""
                            <div style="border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;padding:0.9rem 1rem;
                                        min-height:260px;max-height:380px;overflow:auto;white-space:pre-wrap;line-height:1.6;
                                        color:#111827;font-size:0.98rem;">
                                {html.escape(str(post_detail.get('content', '') or ''))}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # 해당 게시글의 댓글 조회
                        df_post_comments = pd.read_sql_query(
                            "SELECT * FROM comments WHERE post_id = ? ORDER BY comment_id DESC",
                            conn,
                            params=(selected_post_id,),
                        )
                    else:
                        st.info("표시할 게시글이 없습니다.")

                if selected_post_id:
                    st.markdown("**💬 댓글 ({:,}개)**".format(len(df_post_comments)))
                    if not df_post_comments.empty:
                        st.dataframe(df_post_comments, use_container_width=True, hide_index=True)
                    else:
                        st.info("수집된 댓글이 없습니다.")
            else:
                st.info("수집된 게시글이 없습니다.")
        
            conn.close()
        except Exception as e:
            st.error(f"DB 조회 중 오류: {e}")

    with tab2:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            df_comments = pd.read_sql_query("""
                SELECT c.comment_id, c.post_id, c.writer_id, c.nickname, c.content, c.is_target, p.title as post_title
                FROM comments c
                LEFT JOIN posts p ON c.post_id = p.post_id
                ORDER BY c.comment_id DESC
            """, conn)
        
            if not df_comments.empty:
                st.write(f"**표시: {len(df_comments):,}개 댓글**")
            
                if "selected_comments" not in st.session_state:
                    st.session_state.selected_comments = []
            
                df_comment_display = df_comments.copy()
                df_comment_display.insert(0, "선택", False)
            
                for idx, comment_id in enumerate(df_comment_display['comment_id']):
                    if comment_id in st.session_state.selected_comments:
                        df_comment_display.at[idx, "선택"] = True
            
                edited_comments = st.data_editor(
                    df_comment_display,
                    column_config={
                        "선택": st.column_config.CheckboxColumn("선택", default=False),
                        "comment_id": "댓글 ID",
                        "post_id": "게시글 ID",
                        "writer_id": "작성자 ID",
                        "nickname": "닉네임",
                        "content": st.column_config.TextColumn("댓글 내용", width="large"),
                        "is_target": st.column_config.CheckboxColumn("수집 대상"),
                        "post_title": "원글 제목"
                    },
                    hide_index=True,
                    use_container_width=True,
                    disabled=["comment_id", "post_id", "writer_id", "nickname", "content", "is_target", "post_title"],
                    key=f"comments_editor_{st.session_state.comments_editor_refresh}"
                )
            
                st.session_state.selected_comments = edited_comments[edited_comments["선택"] == True]['comment_id'].tolist()
            
                # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
                st.markdown("---")
                col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
                with col_action1:
                    if st.button("☑️ 전체 선택", use_container_width=True, key="select_all_comments"):
                        st.session_state.selected_comments = df_comments['comment_id'].tolist()
                        st.session_state.comments_editor_refresh += 1
                        st.rerun()
            
                with col_action2:
                    if st.button("⬜ 전체 해제", use_container_width=True, key="deselect_all_comments"):
                        st.session_state.selected_comments = []
                        st.session_state.comments_editor_refresh += 1
                        st.rerun()
            
                with col_action3:
                    if st.session_state.selected_comments:
                        # 삭제 확인 상태 초기화
                        if "confirm_delete_comments" not in st.session_state:
                            st.session_state.confirm_delete_comments = False

                        if not st.session_state.confirm_delete_comments:
                            if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_comments)})", type="primary", use_container_width=True, key="delete_comments_req"):
                                st.session_state.confirm_delete_comments = True
                                st.rerun()
                        else:
                            st.button("삭제 대기 중...", disabled=True, use_container_width=True, key="delete_comments_wait")
                    else:
                        st.button("🗑️ 선택 항목 삭제", disabled=True, use_container_width=True, key="delete_comments_disabled")

                # 삭제 확인 UI
                if st.session_state.get("confirm_delete_comments", False):
                    st.markdown(
                        f"""
                        <div style="background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; margin-top: 10px; margin-bottom: 10px; border: 1px solid #ffeeba;">
                            ⚠️ <b>경고:</b> 선택한 {len(st.session_state.selected_comments)}개의 댓글이 영구적으로 삭제됩니다.<br>
                            이 작업은 되돌릴 수 없습니다.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    col_conf1, col_conf2 = st.columns([1, 1])
                    with col_conf1:
                        if st.button("✅ 예, 확실히 삭제합니다", type="primary", use_container_width=True, key="real_delete_comments"):
                            try:
                                cursor = conn.cursor()
                                for comment_id in st.session_state.selected_comments:
                                    cursor.execute("DELETE FROM comments WHERE comment_id = ?", (comment_id,))
                                conn.commit()
                                st.success(f"✅ {len(st.session_state.selected_comments)}개 댓글이 삭제되었습니다!")
                                st.session_state.selected_comments = []
                                st.session_state.comments_editor_refresh += 1
                                st.session_state.confirm_delete_comments = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")
                    with col_conf2:
                        if st.button("❌ 취소", use_container_width=True, key="cancel_delete_comments"):
                            st.session_state.confirm_delete_comments = False
                            st.rerun()
            else:
                st.info("수집된 댓글이 없습니다.")
        
            conn.close()
        except Exception as e:
            st.error(f"DB 조회 중 오류: {e}")


with col_main:
    with st.container(border=True):
        _render_cafe_main_workspace()

