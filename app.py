import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import os
import sys
import time
import random
import json
from pathlib import Path
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, get_logs_dir, get_project_root, resolve_db_path
import shutil
import streamlit.components.v1 as components

# 페이지 설정
_logo_for_icon = Path(__file__).resolve().parent / "assets" / "CafeMonster_logo.png"
st.set_page_config(
    page_title="[카페 몬스터] 카페 추출기 Pro V1.0",
    page_icon=str(_logo_for_icon) if _logo_for_icon.exists() else "☕",
    layout="wide",
)

# 커스텀 CSS: 판매용 UI 톤 정리(기능 영향 없음)
st.markdown("""
<style>
    /* 기본 레이아웃 */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 1450px;
    }

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
        margin: 1rem 0 1rem 0 !important;
        border-color: #e7e9ef !important;
    }

    /* metric 카드 안정감 */
    div[data-testid="stMetric"] {
        background: #f7f9fc;
        border: 1px solid #e4e8f0;
        border-radius: 10px;
        padding: 10px 12px;
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

# date_input 팝업의 영문 월명을 한글(1월~12월)로 치환
components.html(
    """
    <script>
    (function () {
      const monthMap = {
        January: "1월", February: "2월", March: "3월", April: "4월",
        May: "5월", June: "6월", July: "7월", August: "8월",
        September: "9월", October: "10월", November: "11월", December: "12월"
      };

      function replaceMonthText(root) {
        if (!root) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        let node = walker.nextNode();
        while (node) {
          const raw = (node.nodeValue || "").trim();
          if (monthMap[raw]) {
            node.nodeValue = node.nodeValue.replace(raw, monthMap[raw]);
          }
          node = walker.nextNode();
        }
      }

      function run() {
        const doc = window.parent && window.parent.document ? window.parent.document : document;
        replaceMonthText(doc.body);
      }

      run();
      const doc = window.parent && window.parent.document ? window.parent.document : document;
      const observer = new MutationObserver(run);
      observer.observe(doc.body, { childList: true, subtree: true, characterData: true });
    })();
    </script>
    """,
    height=0,
    width=0,
)

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

# UI 구성: 로고 + 제목 한 줄
_logo_path = Path(__file__).resolve().parent / "assets" / "CafeMonster_logo.png"
_col_logo, _col_title = st.columns([2, 5])
with _col_logo:
    if _logo_path.exists():
        st.image(str(_logo_path), width=240)
with _col_title:
    st.markdown("## [카페 몬스터] 카페 추출기 Pro V1.0")
    st.caption("안정형 수집 워크플로우 · 설정 저장 → 브라우저 열기 → 크롤링 시작")

    with st.expander("📖 사용 가이드 (필독)", expanded=False):
        st.markdown(
            """
            **1. 기본 수집(단일 모드)**
            - 설정된 기간의 게시글을 수집합니다.
            - 새로운 글은 추가하고, 이미 수집된 글 중 **등급이 비어있는 경우 자동으로 채웁니다.**
            - 별도 복구 모드를 고르지 않아도 스마트 보강이 함께 동작합니다.
            
            **2. 속도 향상 팁 (자동 적용)**
            - **50개씩 보기**: 크롤러가 자동으로 게시판 목록을 '50개씩 보기'로 전환하여 탐색 속도를 높입니다.
            - **자동 시작 페이지 탐색**: 지정한 기간에 맞는 페이지를 자동으로 찾아 점프합니다.
            - **수동 시작 페이지(선택)**: 이전 실행 로그의 마지막 페이지를 기준으로, 다음 실행 시작 위치를 직접 지정할 수 있습니다.
            
            **3. 안전 장치 (자동 적용)**
            - **연속 실패 자동 중단**: 40회 이상 연속으로 수집에 실패하면 작업이 자동 중단되고 체크포인트가 저장됩니다.
            - **중복 방지**: 이미 수집된 글은 건너뛰며, 필요한 경우에만 업데이트합니다.
            """
        )

def _go_to_papers_page():
    # 1) switch_page (가장 정상적인 방법)
    try:
        st.switch_page("pages/2_papers.py")
        return
    except Exception:
        pass

    st.error(
        "논문 페이지로 이동할 수 없습니다. "
        "Streamlit이 새 `pages/` 파일을 아직 인식하지 못한 상태일 수 있어요.\n\n"
        "해결: 실행 중인 Streamlit을 완전히 종료(Ctrl+C)한 뒤 `streamlit run app.py`로 재실행하세요."
    )


col_nav1, col_nav2 = st.columns([1, 3])
# with col_nav1:
#     if st.button("📚 논문 수집", width="stretch"):
#         _go_to_papers_page()
# with col_nav2:
    # page_link는 특정 환경에서 KeyError(url_pathname)로 앱을 죽여서 기본 사용은 보류
    # st.caption("페이지 목록이 안 보이면 Streamlit 재시작이 필요할 수 있습니다.")
# st.markdown("---")

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


def _render_crawl_summary(ctx: dict, title: str = "진행 요약"):
    # 빠른 복구 모드인지 확인 (한 번에 로드하는 방식)
    is_quick_mode = bool(ctx.get("quick_recovery_mode", False))
    
    # 배치 모드인지 확인 (total_collected 키가 존재하면 배치 모드)
    total_collected = ctx.get("total_collected")
    
    delay_min = float(ctx.get("crawl_delay_min", 0) or 0)
    delay_max = float(ctx.get("crawl_delay_max", 0) or 0)
    
    st.markdown(f"#### {title}")
    
    if total_collected is not None and not is_quick_mode:
        # [배치/스트리밍 모드]
        # 전체 진행률 기반으로 누적/총량 추정/전체 ETA 표시
        page_cursor = ctx.get("page_cursor", 1)
        last_scanned_page = int(ctx.get("last_scanned_page", 0) or 0)
        progress_ratio, est_total, eta_total_sec = _estimate_overall_progress(ctx)
        total_collected_int = int(total_collected)
        idx = int(ctx.get("index", 0) or 0)
        batch_total = int(ctx.get("batch_total", 0) or 0)
        remain_in_batch = max(0, batch_total - idx)
        is_finished_scan = bool(ctx.get("is_finished", False))
        avg_delay = (delay_min + delay_max) / 2.0
        eta_finish_sec = remain_in_batch * (8.0 + avg_delay)

        c1, c2, c3, c4 = st.columns(4)
        if is_finished_scan and batch_total > 0:
            # 사용자가 가장 궁금해하는 '지금 남은 상세 처리'를 최우선으로 표시
            c1.metric("상세 처리 진행", f"{idx:,}/{batch_total:,}건")
            if last_scanned_page > 0:
                c2.metric("목록 탐색", f"완료 (최근 {last_scanned_page}p)")
            else:
                c2.metric("목록 탐색", "완료")
            c3.metric("대기 범위", f"{delay_min:.0f}~{delay_max:.0f}초")
            c4.metric("마무리 남은 시간", _format_seconds_to_hhmmss(eta_finish_sec))
            st.caption(f"목록은 끝났고, 상세 저장만 남았습니다. ({idx:,}/{batch_total:,}건 처리)")
        else:
            # 목록 탐색 중에는 목록 관점 수치 표시
            if est_total:
                c1.metric("목록 확보", f"{total_collected_int:,}/{est_total:,}개")
            else:
                c1.metric("목록 확보", f"{total_collected_int:,}개")
            if last_scanned_page > 0:
                c2.metric("탐색 페이지", f"최근 {last_scanned_page}p (다음 {page_cursor}p)")
            else:
                c2.metric("탐색 페이지", f"{page_cursor}p부터")
            c3.metric("대기 범위", f"{delay_min:.0f}~{delay_max:.0f}초")
            if eta_total_sec is not None:
                c4.metric("예상 남은 시간(전체)", _format_seconds_to_hhmmss(eta_total_sec))
                scan_date_txt = str(ctx.get("last_scan_oldest_date", "") or "").strip()
                if scan_date_txt:
                    st.caption(f"현재 탐색 기준 날짜: {scan_date_txt}")
            else:
                c4.metric("예상 남은 시간(전체)", "계산 중...")
        
    else:
        # [전체 로드 모드] (구버전 호환 또는 빠른 복구 모드)
        total = int(len(ctx.get("articles", []))) if isinstance(ctx.get("articles", []), list) else 0
        idx = int(ctx.get("index", 0) or 0)
        remain = max(0, total - idx)
        
        avg_delay = (delay_min + delay_max) / 2.0
        base_sec = 0.5 if ctx.get("level_backfill_mode") else 8.0
        eta_sec = remain * (base_sec + avg_delay)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("진행", f"{idx:,}/{total:,}")
        c2.metric("남은 건수", f"{remain:,}건")
        c3.metric("대기 범위", f"{delay_min:.0f}~{delay_max:.0f}초")
        c4.metric("예상 남은 시간", _format_seconds_to_hhmmss(eta_sec))


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

with st.sidebar:
    st.header("⚙️ 수집 설정")

    cafe_url = st.text_input("카페 URL", value=config.get("cafe_url", "https://cafe.naver.com/sundreamd"))
    board_url = st.text_input("게시판 URL (전체글보기 권장)", value=config.get("board_url", "https://cafe.naver.com/f-e/cafes/27870803/menus/0"))

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

    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", default_start)
    end_date = col2.date_input("종료일", default_end)

    with st.expander("🚫 제외 게시판 / 운영자 닉네임", expanded=False):
        admin_nicks = st.text_area(
            "운영자 닉네임 (쉼표로 구분)",
            value=config.get("admin_nicks", "마법사멀린, 멀린스타크, 멀린"),
        )
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
        exclude_boards_text = st.text_area(
            "줄바꿈으로 구분 (해당 게시판은 수집 대상에서 제외)",
            value=config.get("exclude_boards", default_exclude),
            height=160,
        )

    st.subheader("🔧 작업 모드")
    st.caption("기간별 스마트 수집 (기본) 단일 모드로 동작합니다.")

    with st.expander("속도 설정 (고급)", expanded=False):
        speed_profile_label = st.selectbox(
            "속도 프로파일",
            ["안정형 (기본)", "고속형 (약 2배)"],
            index=0 if str(config.get("speed_profile", "stable")) != "fast" else 1,
            help="내부 고정 휴식만 조정합니다. 아래 최소/최대 대기(초) 설정은 그대로 유지됩니다.",
        )
        speed_profile = "fast" if speed_profile_label.startswith("고속형") else "stable"
        st.caption("크롤링 대기 시간 범위 (하한선: 1초)")
        col_delay1, col_delay2 = st.columns(2)
        delay_min_sec = col_delay1.number_input(
            "최소 대기(초)",
            min_value=1,
            max_value=300,
            value=max(1, int(config.get("delay_min_sec", 2))),
            step=1,
        )
        delay_max_sec = col_delay2.number_input(
            "최대 대기(초)",
            min_value=max(1, int(delay_min_sec)),
            max_value=300,
            value=max(max(1, int(delay_min_sec)), int(config.get("delay_max_sec", 4))),
            step=1,
        )
        st.caption("※ 안전 장치: 연속 40회 실패 시 작업이 자동 중단됩니다.")
        start_page_manual = int(
            st.number_input(
                "탐색 시작 페이지 (선택)",
                min_value=1,
                max_value=10000,
                value=max(1, int(config.get("start_page_manual", 1) or 1)),
                step=1,
                help="기본값 1(자동). 예: 이전 실행의 마지막 탐색이 406p면 400~420 부근으로 시작해 빠르게 범위를 찾을 수 있습니다.",
            )
        )

    # 내부 고정 설정 (사용자에게 노출하지 않음)
    st.session_state.debug_mode = False
    level_backfill = False # 스마트 로직이 알아서 하므로 강제 옵션은 끔
    quick_recovery_mode = False
    retry_withdrawal = False
    fail_safe_enabled = True
    fail_safe_threshold = 40
    progress_log_every = 100

    st.markdown("---")
    if st.button("💾 설정 저장", width="stretch"):
        new_config = {
            "admin_nicks": admin_nicks,
            "exclude_boards": exclude_boards_text,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "cafe_url": cafe_url,
            "board_url": board_url,
            "delay_min_sec": int(delay_min_sec),
            "delay_max_sec": int(delay_max_sec),
            "speed_profile": speed_profile,
            "start_page_manual": int(start_page_manual),
            "db_path": str(config.get("db_path", "") or "").strip(),
        }
        save_config(new_config)
        st.success("✅ 설정이 저장되었습니다.")

    st.markdown("---")
    st.header("💾 데이터/DB")
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
        st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
        st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")
    except:
        st.info("DB 통계를 읽을 수 없습니다.")

    col_db1, col_db2 = st.columns(2)
    with col_db1:
        if st.button("폴더 열기", width="stretch", key="open_db_folder"):
            try:
                import subprocess
                subprocess.run(['explorer', '/select,', db_full_path])
            except Exception as e:
                st.error(f"폴더 열기 실패: {e}")
    with col_db2:
        log_dir = str(get_logs_dir())
        if st.button("로그 폴더", width="stretch", key="open_log_folder"):
            try:
                import subprocess
                subprocess.run(['explorer', log_dir])
            except Exception as e:
                st.error(f"폴더 열기 실패: {e}")

    with st.expander("DB 위치 변경", expanded=False):
        db_path_override = st.text_input(
            "DB 파일 절대경로 (예: D:\\CafeBreaker\\cafe_data.db)",
            value=str(config.get("db_path", "") or ""),
            placeholder=r"D:\CafeBreaker\cafe_data.db",
            key="db_path_override_input",
        )
        st.caption("우선순위: 환경변수 `CAFESCRAPER_DB_PATH` > 여기 입력한 경로 > 기본값")
        st.caption(f"현재 입력값: `{(db_path_override or '').strip() or '(비어있음)'}`")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("경로 저장(파일 이동 없음)", width="stretch", key="apply_db_path_only"):
                target = (db_path_override or "").strip()
                if not target:
                    st.error("대상 DB 경로가 비어 있습니다.")
                else:
                    config["db_path"] = target
                    save_config(config)
                    st.success("✅ 저장 완료. 앱을 새로고침하세요.")
        with c2:
            if st.button("현재 DB 복사 + 전환", width="stretch", key="copy_db_and_apply"):
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

# 메인 화면
st.markdown("### 🚀 실행 제어")
st.caption("1단계에서 로그인 브라우저를 준비하고, 2단계에서 수집을 실행/중단합니다.")

# 2단계 활성화 조건: 브라우저가 열려 있고(드라이버 존재), 로그인 세션 쿠키가 있어야 함
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
        # 네이버 로그인 세션 핵심 쿠키
        return ("NID_SES" in cookie_names) or ("NID_AUT" in cookie_names)
    except:
        return False

step2_ready = _is_step2_ready()
browser_opened = _is_browser_opened()

# 한 줄 3버튼: 1단계 -> 로그인 완료 -> 2단계
step_col1, step_col_login, step_col2 = st.columns([2.5, 1.1, 2.5])
with step_col1:
    if st.button(
        "1단계: 브라우저 열기",
        width="stretch",
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
            # 수동 로그인 모드
            st.session_state.crawler = NaverCafeCrawler("", debug_mode=st.session_state.debug_mode)
            st.session_state.crawler.set_status_callback(update_logs)
            # (추가) 중단 요청 실시간 확인을 위한 콜백 연결
            st.session_state.crawler.set_stop_check_callback(lambda: st.session_state.get("crawl_stop_requested", False))
        if hasattr(st.session_state.crawler, "set_speed_profile"):
            st.session_state.crawler.set_speed_profile(speed_profile)
        st.session_state.crawler.start_browser()
        # 브라우저를 새로 열면 로그인 확인 상태를 초기화
        st.session_state.login_confirmed = False
        update_logs()
        st.rerun()

with step_col_login:
    if st.button(
        "로그인 완료",
        width="stretch",
        key="manual_login_confirm_btn_inline",
        disabled=bool(st.session_state.crawl_running) or (not browser_opened) or bool(step2_ready),
    ):
        st.session_state.login_confirmed = True
        st.rerun()

with step_col2:
    if st.session_state.crawl_running:
        if st.button("⏹ 진행중... 중단", type="primary", width="stretch", key="stop_crawl_btn"):
            st.session_state.crawl_stop_requested = True
            update_logs("🛑 중단 요청이 접수되었습니다. 현재 항목 처리 후 중단합니다.")
    else:
        if st.button(
            "2단계: 크롤링 시작",
            type="primary",
            width="stretch",
            disabled=not step2_ready,
            key="start_crawl_btn",
        ):
            if not step2_ready:
                st.error("먼저 1단계에서 브라우저를 열고 로그인을 완료해주세요.")
            else:
                st.session_state.crawl_last_status_message = ""
                admin_list = [n.strip() for n in admin_nicks.split(",") if n.strip()]
                st.session_state.crawler.admin_nickname = admin_list[0] if admin_list else "멀린"

                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                legacy_backfill = bool(config.get("update_existing", False)) and bool(config.get("meta_only", True))
                level_backfill_mode = (
                    bool(config.get("level_backfill", False))
                    or bool(config.get("meta_backfill", False))
                    or legacy_backfill
                )
                run_signature = _build_run_signature(
                    board_url=board_url,
                    start_date_value=start_date,
                    end_date_value=end_date,
                    exclude_boards_raw=exclude_boards_text,
                    level_backfill_mode=False, # 스마트 로직 사용
                    quick_recovery_mode=bool(quick_recovery_mode),
                    delay_min_sec=int(delay_min_sec),
                    delay_max_sec=int(delay_max_sec),
                    speed_profile=speed_profile,
                    start_page_manual=int(start_page_manual),
                )

                # 먼저 실행 상태로 전환해서 버튼이 즉시 '중단'으로 바뀌게 함
                quick_mode_on = bool(quick_recovery_mode) # level_backfill_mode 조건 제거 (스마트 로직 사용)
                st.session_state.crawl_state = {
                    "phase": "prepare",
                    "board_url": board_url,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "exclude_boards": [x.strip() for x in (exclude_boards_text or "").splitlines() if x.strip()],
                    "admin_list": admin_list,
                    "level_backfill_mode": False, # 스마트 로직 사용을 위해 False 고정
                    "quick_recovery_mode": quick_mode_on,
                    "retry_withdrawal": retry_withdrawal, # (추가) 탈퇴 재검사 옵션 전달
                    "start_page_manual": int(start_page_manual),
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
                update_logs("🔍 1단계: 대상 게시글 목록 확보 시작...")
                st.rerun()

# 완료/오류 후 재시작이 꼬일 때를 대비한 실행 상태 초기화 버튼
if not st.session_state.crawl_running:
    can_reset_runtime = bool(
        st.session_state.get("crawler")
        or st.session_state.get("login_confirmed", False)
        or st.session_state.get("crawl_state")
        or st.session_state.get("crawl_checkpoint_available", False)
    )
    if st.button("🔄 실행 상태 초기화 (리셋)", width="stretch", key="reset_runtime_btn", disabled=not can_reset_runtime):
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
    if not can_reset_runtime:
        st.caption("현재 초기화할 실행 상태가 없습니다.")

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
        exclude_boards_raw=exclude_boards_text,
        level_backfill_mode=current_level_backfill_mode,
        quick_recovery_mode=current_quick_recovery_mode,
        delay_min_sec=int(delay_min_sec),
        delay_max_sec=int(delay_max_sec),
        speed_profile=speed_profile,
        start_page_manual=int(start_page_manual),
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
            st.caption(f"※ 재개 버튼을 누르면 위 대기 범위({int(delay_min_sec)}~{int(delay_max_sec)}초)로 적용됩니다.")

    st.caption("▶ 체크포인트 재개 — 중단된 지점부터 이어서 수집합니다. 새로 시작하려면 위의 2단계 크롤링 시작을 누르세요.")
    if st.button("▶ 체크포인트 재개", width="stretch", key="resume_from_checkpoint"):
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
                    
                    # 단, 너무 많이 허탕을 치면(예: 1000페이지 넘게) 뭔가 이상하므로 안전장치
                    empty_streak = int(ctx.get("empty_batch_streak", 0)) + 1
                    ctx["empty_batch_streak"] = empty_streak
                    
                    if empty_streak > 200: # 5페이지 * 200번 = 1000페이지 동안 수집 0개면 중단
                        st.session_state.crawl_running = False
                        _clear_crawl_checkpoint()
                        update_logs("⛔ 1000페이지 이상 탐색했으나 해당 기간의 글을 찾지 못했습니다. 날짜 설정을 확인해주세요.")
                        st.session_state.crawl_last_status_type = "error"
                        st.session_state.crawl_last_status_message = "⛔ 1000페이지 이상 탐색했으나 해당 기간의 글을 찾지 못했습니다."
                        st.rerun()
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
        
        # 진행률 표시 (전체 개수를 모르므로, 현재 배치 내 진행률 or 그냥 스피너)
        # (수정) 중복 표시 제거: live_status가 이미 상단에 있으므로 여기서는 _render_crawl_summary만 호출
        _render_crawl_summary(ctx, title="실시간 진행 요약")
        # 진행 막대는 전체 진행률(기간 기준) 우선 사용
        overall_ratio, _, _ = _estimate_overall_progress(ctx)
        if overall_ratio is not None:
            progress = st.progress(float(min(max(overall_ratio, 0.0), 1.0)))
            st.markdown(
                f"<div style='text-align:right;color:#6b7280;font-size:0.85rem;'>{overall_ratio*100:.1f}%</div>",
                unsafe_allow_html=True,
            )
        else:
            progress = st.progress((idx / total_in_buffer) if total_in_buffer > 0 else 0.0)
            st.caption("전체 진행률 계산 중...")

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
            admin_list = ctx["admin_list"]
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
                                    admin_list,
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
                            detail = st.session_state.crawler.scrape_article_detail(art['url'], art['member_id'], admin_list)
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
            progress.progress((ctx["index"] / total_in_buffer) if total_in_buffer > 0 else 1.0)
            st.rerun()

# 초기 로그 표시
update_logs()

# DB 관리 UI (데이터 조회 및 삭제)
st.markdown("---")
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

            with st.form("posts_selection_form", clear_on_submit=False):
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
                    width="stretch",
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
                apply_selection = st.form_submit_button("선택 반영", width="stretch")

            if apply_selection:
                st.session_state.selected_posts = edited_df[edited_df["선택"] == True]["post_id"].tolist()
                st.session_state.posts_editor_refresh += 1
                st.rerun()

            st.caption("체크한 행은 즉시 하이라이트됩니다. 삭제 대상 반영은 [선택 반영] 버튼으로 확정하세요.")
            st.caption(f"반영된 선택: {len(st.session_state.selected_posts)}개")
            
            # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
            st.markdown("---")
            col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
            with col_action1:
                if st.button("☑️ 전체 선택", width="stretch", key="select_all_posts"):
                    st.session_state.selected_posts = df_posts['post_id'].tolist()
                    st.session_state.posts_editor_refresh += 1
                    st.rerun()
            
            with col_action2:
                if st.button("⬜ 전체 해제", width="stretch", key="deselect_all_posts"):
                    st.session_state.selected_posts = []
                    st.session_state.posts_editor_refresh += 1
                    st.rerun()
            
            with col_action3:
                # 삭제 버튼 (선택된 항목이 있을 때만 활성화)
                if st.session_state.selected_posts:
                    # 삭제 확인 상태 초기화
                    if "confirm_delete_posts" not in st.session_state:
                        st.session_state.confirm_delete_posts = False

                    # 삭제 요청 버튼
                    if not st.session_state.confirm_delete_posts:
                        if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_posts)})", type="primary", width="stretch", key="delete_posts_req"):
                            st.session_state.confirm_delete_posts = True
                            st.rerun()
                    else:
                        st.button("삭제 대기 중...", disabled=True, width="stretch", key="delete_posts_wait")
                else:
                    st.button("🗑️ 선택 항목 삭제", disabled=True, width="stretch", key="delete_posts_disabled")
            
            # 삭제 확인 UI
            if st.session_state.get("confirm_delete_posts", False):
                st.markdown(
                    f"""
                    <div style="background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; margin-top: 10px; margin-bottom: 10px; border: 1px solid #ffeeba;">
                        ⚠️ <b>경고:</b> 선택한 {len(st.session_state.selected_posts)}개의 게시글과 관련 댓글이 영구적으로 삭제됩니다.<br>
                        이 작업은 되돌릴 수 없습니다.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                col_conf1, col_conf2 = st.columns([1, 1])
                with col_conf1:
                    if st.button("✅ 예, 확실히 삭제합니다", type="primary", width="stretch", key="real_delete_posts"):
                        try:
                            cursor = conn.cursor()
                            for post_id in st.session_state.selected_posts:
                                # 관련 댓글도 함께 삭제
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
                with col_conf2:
                    if st.button("❌ 취소", width="stretch", key="cancel_delete_posts"):
                        st.session_state.confirm_delete_posts = False
                        st.rerun()
            
            # 게시글 상세 보기
            st.markdown("---")
            st.subheader("📄 게시글 상세 보기")
            
            # 세션 상태에 선택된 게시글 ID 저장
            if "detail_view_post_id" not in st.session_state:
                st.session_state.detail_view_post_id = df_posts['post_id'].tolist()[0] if not df_posts.empty else None
            
            # selectbox의 key를 사용하여 선택 변경 감지
            post_options = df_posts['post_id'].tolist()
            
            # 현재 선택된 ID가 목록에 없으면 첫 번째 항목으로 초기화
            if st.session_state.detail_view_post_id not in post_options:
                st.session_state.detail_view_post_id = post_options[0] if post_options else None
            
            selected_post_id = st.selectbox(
                "게시글 선택", 
                post_options, 
                index=post_options.index(st.session_state.detail_view_post_id) if st.session_state.detail_view_post_id in post_options else 0,
                format_func=lambda x: f"{x} - {df_posts[df_posts['post_id']==x]['title'].values[0]}",
                key="detail_post_selector"
            )
            
            # 선택이 변경되면 세션 상태 업데이트
            st.session_state.detail_view_post_id = selected_post_id
            
            if selected_post_id:
                post_detail = df_posts[df_posts['post_id'] == selected_post_id].iloc[0]
                
                col_d1, col_d2, col_d3, col_d4 = st.columns([1, 1, 1, 1])
                col_d1.metric("작성자 ID", post_detail['member_id'])
                col_d2.metric("닉네임", post_detail['nickname'])
                col_d3.metric("등급", post_detail.get('member_level', ''))
                col_d4.metric("작성일", post_detail['date'])
                
                st.markdown(f"**제목:** {post_detail['title']}")
                st.markdown(f"**URL:** {post_detail['url']}")
                st.markdown("**본문:**")
                st.text_area("게시글 본문", post_detail['content'], height=300, disabled=True, label_visibility="collapsed")
                
                # 해당 게시글의 댓글 조회
                df_post_comments = pd.read_sql_query(f"SELECT * FROM comments WHERE post_id = '{selected_post_id}'", conn)
                if not df_post_comments.empty:
                    st.markdown(f"**💬 댓글 ({len(df_post_comments)}개)**")
                    st.dataframe(df_post_comments, width="stretch", hide_index=True)
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
                width="stretch",
                disabled=["comment_id", "post_id", "writer_id", "nickname", "content", "is_target", "post_title"],
                key=f"comments_editor_{st.session_state.comments_editor_refresh}"
            )
            
            st.session_state.selected_comments = edited_comments[edited_comments["선택"] == True]['comment_id'].tolist()
            
            # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
            st.markdown("---")
            col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
            with col_action1:
                if st.button("☑️ 전체 선택", width="stretch", key="select_all_comments"):
                    st.session_state.selected_comments = df_comments['comment_id'].tolist()
                    st.session_state.comments_editor_refresh += 1
                    st.rerun()
            
            with col_action2:
                if st.button("⬜ 전체 해제", width="stretch", key="deselect_all_comments"):
                    st.session_state.selected_comments = []
                    st.session_state.comments_editor_refresh += 1
                    st.rerun()
            
            with col_action3:
                if st.session_state.selected_comments:
                    # 삭제 확인 상태 초기화
                    if "confirm_delete_comments" not in st.session_state:
                        st.session_state.confirm_delete_comments = False

                    if not st.session_state.confirm_delete_comments:
                        if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_comments)})", type="primary", width="stretch", key="delete_comments_req"):
                            st.session_state.confirm_delete_comments = True
                            st.rerun()
                    else:
                        st.button("삭제 대기 중...", disabled=True, width="stretch", key="delete_comments_wait")
                else:
                    st.button("🗑️ 선택 항목 삭제", disabled=True, width="stretch", key="delete_comments_disabled")

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
                    if st.button("✅ 예, 확실히 삭제합니다", type="primary", width="stretch", key="real_delete_comments"):
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
                    if st.button("❌ 취소", width="stretch", key="cancel_delete_comments"):
                        st.session_state.confirm_delete_comments = False
                        st.rerun()
        else:
            st.info("수집된 댓글이 없습니다.")
        
        conn.close()
    except Exception as e:
        st.error(f"DB 조회 중 오류: {e}")
