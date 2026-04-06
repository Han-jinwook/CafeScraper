import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import os
import re
import time
import random
import json
from pathlib import Path
from selenium.webdriver.common.by import By

from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.naver_login import auto_login_naver_with_js as _auto_login_naver_with_js
from app.utils.paths import get_config_path, resolve_event_db_path
from app.utils.event_db import (
    init_event_db,
    save_event_comments,
    save_event_post,
    save_event_post_analysis,
    get_event_comments_count,
    get_event_posts_count,
)
from app.utils.streamlit_input_history import inject_connect_history_suggestions
from app.utils.streamlit_brand import render_logo_png
from app.utils.streamlit_top_nav import (
    inject_settings_three_cards_css,
    render_main_top_nav,
    render_settings_card_title,
)


st.set_page_config(page_title="이벤트 댓글 수집", layout="wide")

render_main_top_nav(active="event")

# 메인 크롤링 구동 중에는 다른 메뉴 작업을 잠시 차단
if st.session_state.get("crawl_running", False):
    st.warning("⚠️ 메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

inject_settings_three_cards_css(key_basename="event_settings_card")

st.markdown(
    """
    <style>
    /* 조건(1)(2) 소제목 행: 가벼운 박스 (st.container key 노드) */
    div[class*="st-key-event_cond_row_post"],
    div[class*="st-key-event_cond_row_comment"] {
        background: rgba(255, 255, 255, 0.78) !important;
        border-radius: 0.5rem !important;
        padding: 0.38rem 0.7rem 0.42rem 0.7rem !important;
        margin: 0 0 0.45rem 0 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.07) !important;
        box-sizing: border-box !important;
    }
    div[class*="st-key-event_cond_row_post"] .element-container,
    div[class*="st-key-event_cond_row_comment"] .element-container {
        margin-bottom: 0 !important;
    }
    /* Streamlit 체크박스가 Root에 align-items:start + Checkmark에 margin-top을 넣어 박스가 아래로 꺼짐 → 덮어씀 */
    div[class*="st-key-event_cond_row_post"] [data-testid="stCheckbox"],
    div[class*="st-key-event_cond_row_comment"] [data-testid="stCheckbox"] {
        width: fit-content !important;
        max-width: 100% !important;
        display: flex !important;
        align-items: center !important;
        min-height: 0 !important;
    }
    div[class*="st-key-event_cond_row_post"] .stCheckbox label[data-baseweb="checkbox"],
    div[class*="st-key-event_cond_row_comment"] .stCheckbox label[data-baseweb="checkbox"] {
        flex-direction: row-reverse !important;
        align-items: center !important;
        gap: 0.35rem !important;
        margin: 0 !important;
    }
    div[class*="st-key-event_cond_row_post"] .stCheckbox label[data-baseweb="checkbox"] > span:first-of-type,
    div[class*="st-key-event_cond_row_comment"] .stCheckbox label[data-baseweb="checkbox"] > span:first-of-type {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        align-self: center !important;
    }
    div[class*="st-key-event_cond_row_post"] [data-testid="stCheckbox"] [data-testid="stWidgetLabel"],
    div[class*="st-key-event_cond_row_comment"] [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] {
        margin: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        align-self: center !important;
    }
    div[class*="st-key-event_cond_row_post"] .stCheckbox label[data-baseweb="checkbox"] > div:last-child,
    div[class*="st-key-event_cond_row_comment"] .stCheckbox label[data-baseweb="checkbox"] > div:last-child {
        font-weight: 700 !important;
        line-height: 1.25 !important;
        padding: 0 !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CONFIG_PATH = str(get_config_path())
SAFE_DELAY_MIN_SEC = 2.5
SAFE_DELAY_MAX_SEC = 4.5
BACKOFF_STEP_MIN_SEC = 0.7
BACKOFF_STEP_MAX_SEC = 1.2
BACKOFF_MAX_MIN_SEC = 7.0
BACKOFF_MAX_MAX_SEC = 10.0
COPY_COMMENT_CHAR_BASE = 10
DEFAULT_COMMENT_LEVEL_MAP_TEXT = """# 댓글 등급코드 -> 카페별 표시명
sprout=새싹멤버
1=일반멤버
2=준초급
3=초급자
4=중급자
v=상급자
s=스탭
m=매니저
sub_manager=부 매니저
"""


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
EVENT_DB_PATH = str(resolve_event_db_path(config.get("event_db_path")))
init_event_db(EVENT_DB_PATH)


if "event_crawler" not in st.session_state:
    st.session_state.event_crawler = None
if "event_logs" not in st.session_state:
    st.session_state.event_logs = []
if "event_cafe_name_input" not in st.session_state:
    st.session_state.event_cafe_name_input = str(config.get("event_cafe_name", "") or "")
if "event_cafe_url_input" not in st.session_state:
    st.session_state.event_cafe_url_input = str(config.get("event_cafe_url", "") or "")
if "event_extracted_boards" not in st.session_state or not st.session_state.event_extracted_boards:
    _cfg_boards = config.get("event_extracted_boards", [])
    if isinstance(_cfg_boards, list) and _cfg_boards:
        st.session_state.event_extracted_boards = _cfg_boards
    elif "event_extracted_boards" not in st.session_state:
        st.session_state.event_extracted_boards = []
if "event_selected_board_urls" not in st.session_state or not st.session_state.get("event_selected_board_urls"):
    _cfg_selected_urls = config.get("event_selected_board_urls", [])
    if isinstance(_cfg_selected_urls, list) and _cfg_selected_urls:
        st.session_state.event_selected_board_urls = [str(u).strip() for u in _cfg_selected_urls if str(u).strip()]
    elif "event_selected_board_urls" not in st.session_state:
        st.session_state.event_selected_board_urls = [
            u.strip() for u in str(config.get("event_board_url", "") or "").splitlines() if u.strip()
        ]
if "event_selected_board_url" not in st.session_state or not st.session_state.get("event_selected_board_url"):
    _fallback_urls = st.session_state.get("event_selected_board_urls", []) or []
    st.session_state.event_selected_board_url = (
        _fallback_urls[0]
        if _fallback_urls
        else str(config.get("event_board_url", "") or "").strip()
    )
if "event_board_picker_version" not in st.session_state:
    st.session_state.event_board_picker_version = 0
if "event_board_picker_options_sig" not in st.session_state:
    st.session_state.event_board_picker_options_sig = ""
if "event_cafe_url_after_reset_save_mode" not in st.session_state:
    st.session_state.event_cafe_url_after_reset_save_mode = False
if "event_auto_login_after_reset_save_mode" not in st.session_state:
    st.session_state.event_auto_login_after_reset_save_mode = False
if "event_dup_collapsed" not in st.session_state:
    st.session_state.event_dup_collapsed = False
if "event_dup_report" not in st.session_state:
    st.session_state.event_dup_report = None
if "event_running" not in st.session_state:
    st.session_state.event_running = False
if "event_run_pending" not in st.session_state:
    st.session_state.event_run_pending = False
if "event_run_payload" not in st.session_state:
    st.session_state.event_run_payload = None
if "event_stop_requested" not in st.session_state:
    st.session_state.event_stop_requested = False
if "event_progress_ratio" not in st.session_state:
    st.session_state.event_progress_ratio = 0.0
if "event_progress_label" not in st.session_state:
    st.session_state.event_progress_label = "대기 중..."
if "event_last_run_message" not in st.session_state:
    st.session_state.event_last_run_message = ""
if "event_final_summary_report" not in st.session_state:
    st.session_state.event_final_summary_report = None
if "event_analysis_signature" not in st.session_state:
    st.session_state.event_analysis_signature = ""
if "event_last_processed_posts" not in st.session_state:
    st.session_state.event_last_processed_posts = 0
if "event_last_seen_comments" not in st.session_state:
    st.session_state.event_last_seen_comments = 0
if "event_last_excluded_comments" not in st.session_state:
    st.session_state.event_last_excluded_comments = 0
if "event_condition_comment_enabled" not in st.session_state:
    st.session_state.event_condition_comment_enabled = bool(config.get("event_condition_comment_enabled", True))
if "event_condition_post_enabled" not in st.session_state:
    st.session_state.event_condition_post_enabled = bool(config.get("event_condition_post_enabled", False))


def update_logs(msg: str | None = None):
    if msg:
        ts = datetime.now().strftime("%H:%M:%S")
        st.session_state.event_logs.append(f"[{ts}] {msg}")


def _build_dup_report(db_path: str) -> dict:
    conn_an = sqlite3.connect(db_path, timeout=30.0)
    df_an = pd.read_sql_query("SELECT comment_nickname, comment_content, comment_length FROM event_comments", conn_an)
    conn_an.close()

    if df_an.empty:
        return {"status": "empty"}

    dup_check = df_an.groupby(["comment_nickname", "comment_content"]).size().reset_index(name="count")
    dups_only = dup_check[dup_check["count"] > 1].copy()
    if dups_only.empty:
        return {"status": "clean"}

    dups_only["orig_len"] = dups_only["comment_content"].apply(lambda x: len(str(x)))
    dups_only["copy_count"] = dups_only["count"] - 1
    dups_only["copy_chars_adjusted"] = dups_only["copy_count"] * int(COPY_COMMENT_CHAR_BASE)

    total_dup_count = int(dups_only["count"].sum())
    total_dup_groups = int(len(dups_only))
    total_copy_count = int(dups_only["copy_count"].sum())
    total_copy_chars_adjusted = int(dups_only["copy_chars_adjusted"].sum())

    spammers = dups_only.groupby("comment_nickname")
    spammer_rows = []
    for nick, group in spammers:
        total_c = int(group["count"].sum())
        g = group[["comment_content", "orig_len", "copy_count"]].copy()
        spammer_rows.append(
            {
                "nick": str(nick),
                "total_count": total_c,
                "rows": g.to_dict(orient="records"),
            }
        )
    spammer_rows.sort(key=lambda x: x["total_count"], reverse=True)

    return {
        "status": "data",
        "total_dup_count": total_dup_count,
        "total_dup_groups": total_dup_groups,
        "total_copy_count": total_copy_count,
        "total_copy_chars_adjusted": total_copy_chars_adjusted,
        "spammers": spammer_rows,
    }


def _resolve_ticket_weight(input_key: str, config_key: str, fallback: int = 100) -> int:
    raw = st.session_state.get(input_key, "")
    try:
        if isinstance(raw, (int, float)):
            return max(1, int(raw))
        s = str(raw or "").strip()
        if s:
            return max(1, int(s))
    except Exception:
        pass
    try:
        return max(1, int(config.get(config_key, fallback) or fallback))
    except Exception:
        return max(1, int(fallback))


def _init_ticket_text_input_from_config(state_key: str, config_key: str) -> None:
    """config에 값이 있으면 최초 한 번 입력칸을 실제 값으로 채운다(저장 후·재접속 시 진한 본문색)."""
    if state_key in st.session_state:
        return
    raw = config.get(config_key)
    try:
        if raw is None:
            st.session_state[state_key] = ""
            return
        s = str(raw).strip()
        if not s:
            st.session_state[state_key] = ""
            return
        st.session_state[state_key] = str(max(1, int(s)))
    except Exception:
        st.session_state[state_key] = ""


_EVENT_PENDING_TICKET_INPUT_MATERIALIZE = "_event_pending_ticket_input_materialize"


def _queue_ticket_inputs_materialize_after_save(cfg: dict) -> None:
    """저장 다음 실행에서, 위젯 생성 전에 session_state를 채우도록 예약(Streamlit은 같은 런에서 위젯 생성 후 해당 키를 수정 불가)."""
    st.session_state[_EVENT_PENDING_TICKET_INPUT_MATERIALIZE] = {
        "event_post_chars_per_ticket_input": str(max(1, int(cfg["event_post_chars_per_ticket"]))),
        "event_post_images_per_ticket_input": str(max(1, int(cfg["event_post_images_per_ticket"]))),
        "event_comment_chars_per_ticket_input": str(max(1, int(cfg["event_comment_chars_per_ticket"]))),
        "event_comment_media_ticket_bonus_input": str(max(1, int(cfg["event_comment_media_ticket_bonus"]))),
    }


def _build_final_summary_report(db_path: str) -> dict:
    comment_chars_per_ticket = _resolve_ticket_weight(
        "event_comment_chars_per_ticket_input",
        "event_comment_chars_per_ticket",
        100,
    )
    comment_media_ticket_bonus = _resolve_ticket_weight(
        "event_comment_media_ticket_bonus_input",
        "event_comment_media_ticket_bonus",
        1,
    )

    conn3 = sqlite3.connect(db_path, timeout=30.0)
    df_sum_raw = pd.read_sql_query(
        """
        SELECT
            id,
            COALESCE(NULLIF(TRIM(comment_nickname), ''), 'unknown') AS nickname,
            COALESCE(comment_content, '') AS comment_content,
            COALESCE(comment_length, LENGTH(COALESCE(comment_content, '')), 0) AS comment_length,
            COALESCE(text_char_count, 0) AS text_char_count,
            COALESCE(emoji_count, 0) AS emoji_count,
            COALESCE(inline_image_count, 0) AS inline_image_count
        FROM event_comments
        """,
        conn3,
    )
    conn3.close()

    if df_sum_raw.empty:
        return {"status": "empty"}

    df_sum_raw["nickname"] = df_sum_raw["nickname"].astype(str)
    for _ncol in ["comment_length", "text_char_count", "emoji_count", "inline_image_count"]:
        df_sum_raw[_ncol] = pd.to_numeric(df_sum_raw[_ncol], errors="coerce").fillna(0).astype(int)

    df_sum_raw["effective_chars"] = df_sum_raw["text_char_count"].where(
        df_sum_raw["text_char_count"] > 0,
        df_sum_raw["comment_length"],
    )

    def _text_ticket(chars: int) -> int:
        if chars <= 0:
            return 0
        return max(1, (chars - 1) // comment_chars_per_ticket + 1)

    df_sum_raw["text_ticket"] = df_sum_raw["effective_chars"].apply(lambda v: _text_ticket(int(v)))
    df_sum_raw["image_ticket"] = (
        (df_sum_raw["emoji_count"] > 0) | (df_sum_raw["inline_image_count"] > 0)
    ).astype(int) * int(comment_media_ticket_bonus)
    df_sum_raw["ticket_per_comment"] = df_sum_raw["text_ticket"] + df_sum_raw["image_ticket"]

    # 중복/복붙 보정: 같은 별명+같은 내용 그룹에서 첫 댓글(원문) 제외 나머지는 글자수 10 기준(=티켓 1)
    df_sum_raw["dup_idx"] = df_sum_raw.groupby(["nickname", "comment_content"]).cumcount()
    dup_group_size = df_sum_raw.groupby(["nickname", "comment_content"])["id"].transform("size")
    copy_mask = (dup_group_size > 1) & (df_sum_raw["dup_idx"] > 0)
    df_sum_raw.loc[copy_mask, "ticket_per_comment"] = 1

    base_agg = (
        df_sum_raw.groupby("nickname", as_index=False)
        .agg(
            댓글수=("id", "count"),
            글자티켓=("text_ticket", "sum"),
            이미지티켓=("image_ticket", "sum"),
            총티켓수=("ticket_per_comment", "sum"),
        )
        .rename(columns={"nickname": "별명"})
    )

    max_ticket = int(df_sum_raw["ticket_per_comment"].max()) if not df_sum_raw.empty else 1
    for tv in range(1, max_ticket + 1):
        col_name = f"티켓{tv}"
        ticket_counts = (
            df_sum_raw[df_sum_raw["ticket_per_comment"] == tv]
            .groupby("nickname")["id"].count()
            .rename(col_name)
        )
        base_agg = base_agg.merge(
            ticket_counts, left_on="별명", right_index=True, how="left"
        )
        base_agg[col_name] = base_agg[col_name].fillna(0).astype(int)

    ticket_cols = [c for c in base_agg.columns if c.startswith("티켓") and c != "총티켓수"]
    ordered = ["별명", "총티켓수", "댓글수"] + sorted(ticket_cols, key=lambda x: int(x.replace("티켓", ""))) + ["글자티켓", "이미지티켓"]
    sum_df = base_agg[[c for c in ordered if c in base_agg.columns]].sort_values(
        ["총티켓수", "댓글수"], ascending=[False, False]
    )
    return {
        "status": "data",
        "df": sum_df,
        "comment_chars_per_ticket": comment_chars_per_ticket,
        "comment_media_ticket_bonus": comment_media_ticket_bonus,
    }


def _get_event_db_signature(db_path: str) -> str:
    try:
        conn_sig = sqlite3.connect(db_path, timeout=30.0)
        sig_row = pd.read_sql_query(
            """
            SELECT
                COUNT(*) AS n,
                COALESCE(MAX(id), 0) AS max_id,
                COALESCE(MAX(created_at), '') AS max_created_at
            FROM event_comments
            """,
            conn_sig,
        ).iloc[0]
        conn_sig.close()
        return f"{int(sig_row['n'])}:{int(sig_row['max_id'])}:{str(sig_row['max_created_at'])}"
    except Exception:
        return "0:0:"


def _get_event_ticket_option_signature() -> str:
    _comment_chars = _resolve_ticket_weight(
        "event_comment_chars_per_ticket_input",
        "event_comment_chars_per_ticket",
        100,
    )
    _post_chars = _resolve_ticket_weight(
        "event_post_chars_per_ticket_input",
        "event_post_chars_per_ticket",
        100,
    )
    _comment_media_bonus = _resolve_ticket_weight(
        "event_comment_media_ticket_bonus_input",
        "event_comment_media_ticket_bonus",
        1,
    )
    _post_images_per_ticket = _resolve_ticket_weight(
        "event_post_images_per_ticket_input",
        "event_post_images_per_ticket",
        1,
    )
    return (
        f"comment_chars:{_comment_chars}|post_chars:{_post_chars}"
        f"|comment_media_bonus:{_comment_media_bonus}|post_images_per_ticket:{_post_images_per_ticket}"
    )


def _ensure_event_analysis_reports(*, force: bool = False) -> None:
    if st.session_state.get("event_running") or st.session_state.get("event_run_pending"):
        return

    current_sig = f"{_get_event_db_signature(EVENT_DB_PATH)}|{_get_event_ticket_option_signature()}"
    has_reports = (
        st.session_state.get("event_dup_report") is not None
        and st.session_state.get("event_final_summary_report") is not None
    )
    sig_unchanged = (str(st.session_state.get("event_analysis_signature") or "") == current_sig)
    if (not force) and has_reports and sig_unchanged:
        return

    st.session_state.event_dup_report = _build_dup_report(EVENT_DB_PATH)
    st.session_state.event_final_summary_report = _build_final_summary_report(EVENT_DB_PATH)
    st.session_state.event_analysis_signature = current_sig


def _render_event_dashboard_header() -> None:
    """메인·논문 수집과 동일: 로고 + 제목 + 가이드."""
    _logo_path = Path(__file__).resolve().parent.parent / "assets" / "CafeMonster_logo.png"
    _hdr_logo, _hdr_mid = st.columns([1, 5], gap="small")
    with _hdr_logo:
        render_logo_png(_logo_path, width_px=92)
    with _hdr_mid:
        _title_col, _guide_col = st.columns([2.65, 1.35], gap="small")
        with _title_col:
            st.markdown(
                '<h2 style="margin:0 0 0.15rem 0;padding:0;line-height:1.2;font-size:1.35rem;">'
                "이벤트 댓글 분석 스튜디오</h2>",
                unsafe_allow_html=True,
            )
        with _guide_col:
            with st.expander("📖 사용 가이드 (필독)", expanded=False):
                st.markdown(
                    """
                특정 **기간**의 게시판 글을 찾은 뒤 각 글의 **댓글**을 모아 전용 DB에 저장하고, 중복·랭킹 분석을 할 수 있습니다.
                
                **권장 순서**
                1. **수집 설정** 3칸에서 카페·게시판·기간·DB를 맞추고 **설정 저장**합니다.
                2. **브라우저 열기** 후 네이버에 로그인합니다.
                3. **댓글 수집 시작**으로 목록·댓글을 저장합니다.
                
                메인 카페 크롤링이 실행 중이면 이 메뉴는 사용할 수 없습니다.
                    """
                )


_render_event_dashboard_header()


def _inject_event_connect_history_suggestions(cafe_names: list[str], cafe_urls: list[str]) -> None:
    inject_connect_history_suggestions(
        prefix="event",
        container_key_fragment="event_settings_card_1",
        cafe_names=cafe_names,
        cafe_urls=cafe_urls,
    )

_default_start = datetime.now() - timedelta(days=7)
if config.get("event_start_date"):
    try:
        _default_start = datetime.strptime(config["event_start_date"], "%Y-%m-%d")
    except Exception:
        pass
_default_end = datetime.now()
if config.get("event_end_date"):
    try:
        _default_end = datetime.strptime(config["event_end_date"], "%Y-%m-%d")
    except Exception:
        pass

_comment_default_start = _default_start
_comment_default_end = _default_end
if config.get("event_comment_start_date"):
    try:
        _comment_default_start = datetime.strptime(config["event_comment_start_date"], "%Y-%m-%d")
    except Exception:
        pass
if config.get("event_comment_end_date"):
    try:
        _comment_default_end = datetime.strptime(config["event_comment_end_date"], "%Y-%m-%d")
    except Exception:
        pass

_comment_search_default_start = _comment_default_start
if config.get("event_comment_search_start_date"):
    try:
        _comment_search_default_start = datetime.strptime(config["event_comment_search_start_date"], "%Y-%m-%d")
    except Exception:
        pass

_post_default_start = _default_start
_post_default_end = _default_end
if config.get("event_post_start_date"):
    try:
        _post_default_start = datetime.strptime(config["event_post_start_date"], "%Y-%m-%d")
    except Exception:
        pass
if config.get("event_post_end_date"):
    try:
        _post_default_end = datetime.strptime(config["event_post_end_date"], "%Y-%m-%d")
    except Exception:
        pass

_comment_chars_per_ticket_default = int(config.get("event_comment_chars_per_ticket", 100) or 100)
_post_chars_per_ticket_default = int(config.get("event_post_chars_per_ticket", 100) or 100)
_comment_chars_per_ticket_default = max(1, _comment_chars_per_ticket_default)
_post_chars_per_ticket_default = max(1, _post_chars_per_ticket_default)
_comment_media_ticket_bonus_default = int(config.get("event_comment_media_ticket_bonus", 1) or 1)
_post_images_per_ticket_default = int(config.get("event_post_images_per_ticket", 1) or 1)
_comment_media_ticket_bonus_default = max(1, _comment_media_ticket_bonus_default)
_post_images_per_ticket_default = max(1, _post_images_per_ticket_default)
_pending_ticket_vals = st.session_state.pop(_EVENT_PENDING_TICKET_INPUT_MATERIALIZE, None)
if _pending_ticket_vals is not None:
    for _pt_key, _pt_val in _pending_ticket_vals.items():
        st.session_state[_pt_key] = _pt_val
_init_ticket_text_input_from_config("event_comment_chars_per_ticket_input", "event_comment_chars_per_ticket")
_init_ticket_text_input_from_config("event_post_chars_per_ticket_input", "event_post_chars_per_ticket")
_init_ticket_text_input_from_config("event_comment_media_ticket_bonus_input", "event_comment_media_ticket_bonus")
_init_ticket_text_input_from_config("event_post_images_per_ticket_input", "event_post_images_per_ticket")

st.markdown("#### ⚙️ 수집 설정")
_ev1, _ev2, _ev3 = st.columns([1, 1, 1], gap="medium")
with _ev1:
    with st.container(border=True, key="event_settings_card_1"):
        render_settings_card_title("카페 · 연결", icon="🏪")
        if st.session_state.pop("_event_pending_clear_cafe_name_input", False):
            st.session_state.event_cafe_name_input = ""
        event_cafe_name = st.text_input(
            "카페명",
            key="event_cafe_name_input",
        )
        try:
            _ev_url_col, _ev_btn_col = st.columns([5, 1], gap="small", vertical_alignment="center")
        except TypeError:
            _ev_url_col, _ev_btn_col = st.columns([5, 1], gap="small")
        with _ev_url_col:
            if st.session_state.pop("_event_pending_clear_cafe_url_input", False):
                st.session_state.event_cafe_url_input = ""
            cafe_url = st.text_input(
                "카페 URL",
                key="event_cafe_url_input",
            )
        _inject_event_connect_history_suggestions(
            (config.get("event_cafe_name_history", []) or []) + [str(config.get("event_cafe_name", "") or "")],
            (config.get("event_cafe_url_history", []) or []) + [str(config.get("event_cafe_url", "") or "")],
        )
        with _ev_btn_col:
            _ev_save_mode = bool(st.session_state.get("event_cafe_url_after_reset_save_mode", False))
            _ev_side_lbl = "저장" if _ev_save_mode else "리셋"
            _ev_side_help = (
                "카페명/카페 URL을 이벤트 수집 설정에 저장합니다."
                if _ev_save_mode
                else "이벤트 게시판 목록/선택 데이터를 비웁니다."
            )
            if st.button(_ev_side_lbl, key="event_cafe_url_side_action_btn", use_container_width=True, help=_ev_side_help):
                if _ev_save_mode:
                    cfg_now = dict(load_config() or {})
                    saved_event_cafe_name = str(st.session_state.get("event_cafe_name_input", "") or "").strip()
                    saved_event_cafe_url = str(st.session_state.get("event_cafe_url_input", "") or "").strip()
                    cfg_now["event_cafe_name"] = saved_event_cafe_name
                    cfg_now["event_cafe_url"] = saved_event_cafe_url
                    if saved_event_cafe_name:
                        prev_event_name_hist = [str(x).strip() for x in (cfg_now.get("event_cafe_name_history", []) or []) if str(x).strip()]
                        cfg_now["event_cafe_name_history"] = ([saved_event_cafe_name] + [x for x in prev_event_name_hist if x != saved_event_cafe_name])[:20]
                    if saved_event_cafe_url:
                        prev_event_url_hist = [str(x).strip() for x in (cfg_now.get("event_cafe_url_history", []) or []) if str(x).strip()]
                        cfg_now["event_cafe_url_history"] = ([saved_event_cafe_url] + [x for x in prev_event_url_hist if x != saved_event_cafe_url])[:20]
                    save_config(cfg_now)
                    config.update(cfg_now)
                    st.session_state.event_cafe_url_after_reset_save_mode = False
                    st.session_state._event_cafe_url_apply_ack = True
                    st.rerun()
                else:
                    st.session_state.event_extracted_boards = []
                    st.session_state.event_selected_board_urls = []
                    st.session_state.event_selected_board_url = ""
                    st.session_state.event_cafe_url_after_reset_save_mode = True
                    st.session_state._event_pending_clear_cafe_name_input = True
                    st.session_state._event_pending_clear_cafe_url_input = True
                    st.session_state._event_cafe_reset_done = True
                    st.rerun()
        if st.session_state.get("_event_cafe_reset_done"):
            st.session_state._event_cafe_reset_done = False
            st.success("카페 관련 데이터를 비웠고 카페명/카페 URL 칸을 비웠습니다. 새 값을 입력 후 오른쪽 저장을 눌러주세요.")
        if st.session_state.get("_event_cafe_url_apply_ack"):
            st.session_state._event_cafe_url_apply_ack = False
            st.success("카페 연결 정보를 저장했습니다.")

        _saved_event_login_id = str(config.get("event_naver_id", "") or "").strip()
        _saved_event_login_pw = str(config.get("event_naver_pw", "") or "")
        _event_auto_login_done = bool(_saved_event_login_id and _saved_event_login_pw)
        _event_auto_login_title = "🔐 자동로그인 설정 (완료)" if _event_auto_login_done else "🔐 자동로그인 설정"
        with st.expander(_event_auto_login_title, expanded=False):
            if st.session_state.pop("_event_pending_clear_auto_login_inputs", False):
                st.session_state.pop("event_auto_login_enabled_input", None)
                st.session_state.pop("event_naver_id_input", None)
                st.session_state.pop("event_naver_pw_input", None)
            if "event_auto_login_enabled_input" not in st.session_state:
                st.session_state.event_auto_login_enabled_input = bool(config.get("event_auto_login_enabled", False))
            event_auto_login_enabled = st.checkbox(
                "브라우저 열 때 자동로그인 실행",
                key="event_auto_login_enabled_input",
                help="이벤트 수집용 브라우저 열기 직후 저장된 계정으로 로그인을 시도합니다.",
            )
            _ev_al_input_col, _ev_al_btn_col = st.columns([4, 1], gap="small")
            with _ev_al_input_col:
                if "event_naver_id_input" not in st.session_state:
                    st.session_state.event_naver_id_input = str(config.get("event_naver_id", "") or "")
                if "event_naver_pw_input" not in st.session_state:
                    st.session_state.event_naver_pw_input = str(config.get("event_naver_pw", "") or "")
                event_naver_id = st.text_input(
                    "네이버 아이디",
                    key="event_naver_id_input",
                    placeholder="아이디 입력",
                )
                event_naver_pw = st.text_input(
                    "네이버 비밀번호",
                    key="event_naver_pw_input",
                    type="password",
                    placeholder="비밀번호 입력",
                )
            with _ev_al_btn_col:
                st.markdown("<div style='margin-top: 88px;'></div>", unsafe_allow_html=True)
                _ev_al_save_mode = bool(st.session_state.get("event_auto_login_after_reset_save_mode", False))
                _ev_al_lbl = "저장" if _ev_al_save_mode else "리셋"
                if st.button(_ev_al_lbl, key="event_auto_login_side_action_btn", use_container_width=True):
                    if _ev_al_save_mode:
                        cfg_now = dict(load_config() or {})
                        cfg_now["event_auto_login_enabled"] = bool(st.session_state.get("event_auto_login_enabled_input", False))
                        cfg_now["event_naver_id"] = str(st.session_state.get("event_naver_id_input", "") or "").strip()
                        cfg_now["event_naver_pw"] = str(st.session_state.get("event_naver_pw_input", "") or "")
                        save_config(cfg_now)
                        config.update(cfg_now)
                        st.session_state.event_auto_login_after_reset_save_mode = False
                        st.session_state._event_auto_login_save_ack = True
                        st.rerun()
                    else:
                        st.session_state._event_pending_clear_auto_login_inputs = True
                        st.session_state.event_auto_login_after_reset_save_mode = True
                        st.session_state._event_auto_login_reset_ack = True
                        st.rerun()
            if st.session_state.get("_event_auto_login_reset_ack"):
                st.session_state._event_auto_login_reset_ack = False
                st.success("자동로그인 설정 값을 비웠습니다. 새 값을 입력한 뒤 오른쪽 저장을 눌러주세요.")
            if st.session_state.get("_event_auto_login_save_ack"):
                st.session_state._event_auto_login_save_ack = False
                st.success("자동로그인 설정을 저장했습니다.")

        if st.button("🔍 게시판 목록 가져오기", key="event_scan_boards_btn", use_container_width=True):
            if not st.session_state.get("event_crawler") or not getattr(st.session_state.event_crawler, "driver", None):
                st.error("먼저 아래에서 1단계: 브라우저 열기를 실행해주세요.")
            else:
                try:
                    with st.spinner("게시판 목록 스캔 중..."):
                        crawler_obj = st.session_state.event_crawler
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
                                        import re
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
                        st.session_state.event_extracted_boards = boards
                        st.session_state.event_selected_board_urls = []
                        st.session_state.event_selected_board_url = ""
                        st.session_state.event_board_picker_version = int(st.session_state.get("event_board_picker_version", 0)) + 1
                        cfg_now = dict(load_config() or {})
                        cfg_now["event_extracted_boards"] = boards
                        cfg_now["event_selected_board_urls"] = []
                        cfg_now["event_board_url"] = ""
                        save_config(cfg_now)
                        st.success(f"✅ 게시판 스캔 완료: {len(boards)}개")
                    else:
                        st.warning("게시판을 찾지 못했습니다. 카페 메인/메뉴가 보이는 화면에서 다시 시도해주세요.")
                except Exception as e:
                    st.error(f"게시판 목록 스캔 실패: {e}")

        if st.session_state.event_extracted_boards:
            total_board_count = len(st.session_state.event_extracted_boards)
            selected_count_header = st.empty()
            _selected_now = len(list(dict.fromkeys([u for u in (st.session_state.get("event_selected_board_urls", []) or []) if u])))
            selected_count_header.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;gap:12px;white-space:nowrap;"
                f"padding:4px 0 8px 0;margin:2px 0 6px 0;'>"
                f"<div style='font-size:1.32rem;font-weight:700;line-height:1.2;'>📋 게시판 선택 (총 {total_board_count}개)</div>"
                f"<div style='font-size:0.92rem;color:#475569;'>[{_selected_now}개 게시판 선택]</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            options = st.session_state.event_extracted_boards
            board_options = {}
            for i, b in enumerate(options, start=1):
                name = str((b or {}).get("name", "") or "").strip() or f"게시판_{i}"
                url = str((b or {}).get("url", "") or "").strip()
                board_options[f"{i:02d}. {name}"] = url

            overall_url = ""
            try:
                import re as _re
                for b in options:
                    u = str((b or {}).get("url", "") or "")
                    if "ArticleList.nhn" in u and "search.clubid=" in u:
                        m_club = _re.search(r"search\.clubid=(\d+)", u)
                        if m_club:
                            overall_url = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={m_club.group(1)}&search.boardtype=L"
                            break
                    if "/f-e/cafes/" in u:
                        m_fe = _re.search(r"/cafes/(\d+)/menus/(\d+)", u)
                        if m_fe:
                            overall_url = f"https://cafe.naver.com/f-e/cafes/{m_fe.group(1)}/menus/0?viewType=L"
                            break
            except Exception:
                overall_url = ""

            options_list = []
            if overall_url:
                options_list.append("00. 전체글보기")
            options_list.extend(list(board_options.keys()))

            options_sig = "||".join(options_list)
            if options_sig != str(st.session_state.get("event_board_picker_options_sig", "")):
                st.session_state.event_board_picker_options_sig = options_sig
                _new_version = int(st.session_state.get("event_board_picker_version", 0)) + 1
                st.session_state.event_board_picker_version = _new_version
                _available_urls = [str(u).strip() for u in board_options.values() if str(u).strip()]
                if overall_url:
                    _available_urls.insert(0, str(overall_url).strip())
                _available_set = set(_available_urls)
                _existing_selected = list(
                    dict.fromkeys(
                        [str(u).strip() for u in (st.session_state.get("event_selected_board_urls", []) or []) if str(u).strip()]
                    )
                )
                _preserved = [u for u in _existing_selected if u in _available_set]
                st.session_state.event_selected_board_urls = _preserved
                st.session_state.event_selected_board_url = _preserved[0] if _preserved else ""
                # 새 버전 체크박스 키에 보존된 선택값 미리 설정
                _preserved_set = set(_preserved)
                _url_to_idx = {}
                for _lb in options_list:
                    _idx = options_list.index(_lb)
                    _u = ""
                    if _lb == "00. 전체글보기":
                        _u = overall_url
                    else:
                        _u = board_options.get(_lb, "")
                    if _u:
                        _url_to_idx[_u] = _idx
                for _u, _idx in _url_to_idx.items():
                    st.session_state[f"event_board_chk_{_new_version}_{_idx}"] = bool(_u in _preserved_set)

            label_to_url = {}
            for label in options_list:
                if label == "00. 전체글보기":
                    label_to_url[label] = overall_url
                else:
                    label_to_url[label] = board_options.get(label, "")

            with st.expander("게시판 목록 열기/접기", expanded=False):
                v = int(st.session_state.get("event_board_picker_version", 0))
                label_to_idx = {label: i for i, label in enumerate(options_list)}
                overall_label = "00. 전체글보기" if "00. 전체글보기" in options_list else None
                combo_key = f"event_board_combo_select_all_{v}"
                combo_prev_key = f"_event_board_combo_select_all_prev_{v}"
                wanted_urls = set(st.session_state.get("event_selected_board_urls", []) or [])

                overall_key = ""
                if overall_label:
                    overall_idx = int(label_to_idx.get(overall_label, -1))
                    if overall_idx >= 0:
                        overall_key = f"event_board_chk_{v}_{overall_idx}"
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
                        chk_key = f"event_board_chk_{v}_{i}"
                        if overall_label and label == overall_label:
                            st.session_state[chk_key] = False
                        else:
                            st.session_state[chk_key] = True
                elif (not combo_checked_now) and combo_prev:
                    for label in options_list:
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        st.session_state[f"event_board_chk_{v}_{i}"] = False
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
                    chk_key = f"event_board_chk_{v}_{i}"
                    if chk_key not in st.session_state:
                        st.session_state[chk_key] = bool(u and u in wanted_urls)

                if overall_label:
                    overall_idx = int(label_to_idx.get(overall_label, -1))
                    overall_key = f"event_board_chk_{v}_{overall_idx}" if overall_idx >= 0 else ""
                    overall_checked = bool(st.session_state.get(overall_key, False)) if overall_key else False
                    other_checked = False
                    for label in options_list:
                        if label == overall_label:
                            continue
                        i = int(label_to_idx.get(label, -1))
                        if i < 0:
                            continue
                        if bool(st.session_state.get(f"event_board_chk_{v}_{i}", False)):
                            other_checked = True
                            break
                    if overall_checked:
                        for label in options_list:
                            if label == overall_label:
                                continue
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            st.session_state[f"event_board_chk_{v}_{i}"] = False
                    elif other_checked and overall_key:
                        st.session_state[overall_key] = False

                try:
                    with st.container(height=360):
                        for label in options_list:
                            i = int(label_to_idx.get(label, -1))
                            if i < 0:
                                continue
                            chk_key = f"event_board_chk_{v}_{i}"
                            disable_this = False
                            if overall_label and label != overall_label:
                                oidx = int(label_to_idx.get(overall_label, -1))
                                if oidx >= 0 and bool(st.session_state.get(f"event_board_chk_{v}_{oidx}", False)):
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
                        chk_key = f"event_board_chk_{v}_{i}"
                        disable_this = False
                        if overall_label and label != overall_label:
                            oidx = int(label_to_idx.get(overall_label, -1))
                            if oidx >= 0 and bool(st.session_state.get(f"event_board_chk_{v}_{oidx}", False)):
                                disable_this = True
                        st.checkbox(
                            label,
                            key=chk_key,
                            disabled=disable_this,
                        )

                selected_urls = []
                for label in options_list:
                    i = int(label_to_idx.get(label, -1))
                    if i < 0:
                        continue
                    if bool(st.session_state.get(f"event_board_chk_{v}_{i}", False)):
                        u = str(label_to_url.get(label, "") or "")
                        if u:
                            selected_urls.append(u)
                selected_urls_dedup = list(dict.fromkeys(selected_urls))
                st.session_state.event_selected_board_urls = selected_urls_dedup
                st.session_state.event_selected_board_url = selected_urls_dedup[0] if selected_urls_dedup else ""

                _selected_sig = "|".join(selected_urls_dedup)
                if st.session_state.get("_event_selected_board_urls_saved_sig", "") != _selected_sig:
                    st.session_state._event_selected_board_urls_saved_sig = _selected_sig
                    cfg_now = dict(load_config() or {})
                    cfg_now["event_selected_board_urls"] = selected_urls_dedup
                    cfg_now["event_board_url"] = "\n".join(selected_urls_dedup)
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

            selected_urls = list(dict.fromkeys([u for u in (st.session_state.get("event_selected_board_urls", []) or []) if u]))
            board_url = "\n".join(selected_urls)
        else:
            board_url = ""
            st.info("먼저 **1단계: 브라우저 열기**를 실행한 뒤 **게시판 목록 가져오기**를 눌러주세요. 그 다음 게시판을 선택해주세요.")

with _ev2:
    with st.container(border=True, key="event_settings_card_2"):
        render_settings_card_title("분석 세부설정", icon="🧾")
        _exclude_post_src = str(
            st.session_state.get(
                "event_exclude_post_nicks_text",
                config.get("event_exclude_post_nicks", "마법사멀린"),
            )
            or ""
        )
        _exclude_comment_src = str(
            st.session_state.get(
                "event_exclude_comment_nicks_text",
                config.get("event_exclude_comment_nicks", config.get("event_exclude_nicks", "마법사멀린\n해나라")),
            )
            or ""
        )
        _apply_comment_exclude = bool(
            st.session_state.get(
                "event_apply_comment_exclude_checkbox",
                config.get("event_apply_comment_exclude", False),
            )
        )
        _apply_post_exclude = bool(
            st.session_state.get(
                "event_apply_post_exclude_checkbox",
                config.get("event_apply_post_exclude", True),
            )
        )
        def _parse_level_map(raw_text: str) -> dict[str, str]:
            out: dict[str, str] = {}
            for ln in str(raw_text or "").splitlines():
                s = str(ln or "").strip()
                if (not s) or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                elif ":" in s:
                    k, v = s.split(":", 1)
                else:
                    continue
                kk = str(k or "").strip().lower()
                vv = str(v or "").strip()
                if kk and vv:
                    out[kk] = vv
            return out
        _exclude_post_count = len([x for x in _exclude_post_src.splitlines() if str(x).strip()])
        _exclude_comment_count = len([x for x in _exclude_comment_src.splitlines() if str(x).strip()])
        with st.expander(
            f"🚫 제외 설정 (게시글 {_exclude_post_count}명 · 댓글 {_exclude_comment_count}명)",
            expanded=False,
        ):
            _post_left, _post_right = st.columns([4.9, 1.3], gap="medium")
            with _post_left:
                exclude_post_nicks_text = st.text_area(
                    "게시글 제외 별명 (줄바꿈 구분)",
                    value=config.get("event_exclude_post_nicks", "마법사멀린"),
                    height=170,
                    help="줄바꿈으로 별명을 구분합니다. 게시글 제외 적용 체크가 ON일 때만 이 목록을 실행에 반영하며, OFF면 저장만 됩니다.",
                    key="event_exclude_post_nicks_text",
                )
            with _post_right:
                apply_post_exclude = st.checkbox(
                    "적용",
                    value=_apply_post_exclude,
                    key="event_apply_post_exclude_checkbox",
                )

            _comment_left, _comment_right = st.columns([4.9, 1.3], gap="medium")
            with _comment_left:
                exclude_comment_nicks_text = st.text_area(
                    "댓글 제외 별명 (줄바꿈 구분)",
                    value=config.get("event_exclude_comment_nicks", config.get("event_exclude_nicks", "마법사멀린\n해나라")),
                    height=220,
                    help="줄바꿈으로 별명을 구분합니다. 댓글 제외 적용 체크가 ON일 때만 이 목록을 실행에 반영하며, OFF면 저장만 됩니다.",
                    key="event_exclude_comment_nicks_text",
                )
            with _comment_right:
                apply_comment_exclude = st.checkbox(
                    "적용",
                    value=_apply_comment_exclude,
                    key="event_apply_comment_exclude_checkbox",
                )
        with st.expander("🧩 수집 조건", expanded=False):
            if "event_cond_pick_post_checkbox" not in st.session_state:
                st.session_state.event_cond_pick_post_checkbox = bool(
                    st.session_state.get("event_condition_post_enabled", False)
                )
            if "event_cond_pick_comment_checkbox" not in st.session_state:
                st.session_state.event_cond_pick_comment_checkbox = bool(
                    st.session_state.get("event_condition_comment_enabled", True)
                )
            # 초기 진입 시 둘 다 같으면(둘 다 true/false) 댓글 조건을 기본으로 둠
            if st.session_state.event_cond_pick_post_checkbox == st.session_state.event_cond_pick_comment_checkbox:
                st.session_state.event_cond_pick_post_checkbox = False
                st.session_state.event_cond_pick_comment_checkbox = True

            def _pick_post_mode():
                if st.session_state.get("event_cond_pick_post_checkbox", False):
                    st.session_state.event_cond_pick_comment_checkbox = False
                elif not st.session_state.get("event_cond_pick_comment_checkbox", False):
                    st.session_state.event_cond_pick_comment_checkbox = True

            def _pick_comment_mode():
                if st.session_state.get("event_cond_pick_comment_checkbox", False):
                    st.session_state.event_cond_pick_post_checkbox = False
                elif not st.session_state.get("event_cond_pick_post_checkbox", False):
                    st.session_state.event_cond_pick_post_checkbox = True

            cond1_checked = bool(st.session_state.get("event_cond_pick_post_checkbox", False))  # UI 조건1 = 게시글
            cond2_checked = bool(st.session_state.get("event_cond_pick_comment_checkbox", True))  # UI 조건2 = 댓글
            st.session_state.event_condition_post_enabled = bool(cond1_checked)
            st.session_state.event_condition_comment_enabled = bool(cond2_checked)

            with st.container(key="event_cond_row_post"):
                st.checkbox(
                    "**조건(1)** 게시글 수집·분석",
                    key="event_cond_pick_post_checkbox",
                    on_change=_pick_post_mode,
                    width="content",
                )
            _p1, _p2 = st.columns(2)
            with _p1:
                post_start_date = st.date_input(
                    "시작일",
                    _post_default_start,
                    key="event_post_start_date_input",
                    disabled=not cond1_checked,
                )
            with _p2:
                post_end_date = st.date_input(
                    "종료일",
                    _post_default_end,
                    key="event_post_end_date_input",
                    disabled=not cond1_checked,
                )
            _post_chars_preview = _resolve_ticket_weight(
                "event_post_chars_per_ticket_input",
                "event_post_chars_per_ticket",
                _post_chars_per_ticket_default,
            )
            _post_images_preview = _resolve_ticket_weight(
                "event_post_images_per_ticket_input",
                "event_post_images_per_ticket",
                _post_images_per_ticket_default,
            )
            _p_t1, _p_t2 = st.columns(2)
            with _p_t1:
                st.text_input(
                    "게시글 글자수 기준",
                    value=str(st.session_state.get("event_post_chars_per_ticket_input", "") or ""),
                    placeholder=str(_post_chars_per_ticket_default),
                    key="event_post_chars_per_ticket_input",
                    disabled=not cond1_checked,
                )
            with _p_t2:
                st.text_input(
                    "티켓 수",
                    value=str(st.session_state.get("event_post_images_per_ticket_input", "") or ""),
                    placeholder=str(_post_images_per_ticket_default),
                    key="event_post_images_per_ticket_input",
                    disabled=not cond1_checked,
                )
            if cond1_checked:
                _post_rule_panel = "background:rgba(37,99,235,0.08);color:#1e3a8a;"
            else:
                _post_rule_panel = "background:rgba(100,116,139,0.06);color:#475569;"
            st.markdown(
                f"<div style='margin:0.35rem 0 0.5rem;padding:0.45rem 0.6rem;border-radius:0.4rem;"
                f"{_post_rule_panel}"
                f"font-weight:600;font-size:0.96rem;letter-spacing:-0.02em;line-height:1.35;'>"
                f"[ {_post_chars_preview} ] 자 당 {_post_images_preview}티켓</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)
            st.markdown("---")
            with st.container(key="event_cond_row_comment"):
                st.checkbox(
                    "**조건(2)** 댓글 수집·분석",
                    key="event_cond_pick_comment_checkbox",
                    on_change=_pick_comment_mode,
                    width="content",
                )
            st.caption("목표 기간(댓글 작성일 기준)")
            _c1t1, _c1t2 = st.columns(2)
            with _c1t1:
                comment_start_date = st.date_input(
                    "목표 시작일",
                    _comment_default_start,
                    key="event_comment_start_date_input",
                    disabled=not cond2_checked,
                )
            with _c1t2:
                comment_end_date = st.date_input(
                    "목표 종료일",
                    _comment_default_end,
                    key="event_comment_end_date_input",
                    disabled=not cond2_checked,
                )

            st.caption("게시글 탐색 범위(댓글 목표기간 보완용)")
            comment_search_start_date = st.date_input(
                "게시글 탐색 시작일",
                _comment_search_default_start,
                key="event_comment_search_start_date_input",
                disabled=not cond2_checked,
            )
            st.caption("탐색 종료 기준은 목표 종료일과 동일하게 자동 적용됩니다.")
            _comment_chars_preview = _resolve_ticket_weight(
                "event_comment_chars_per_ticket_input",
                "event_comment_chars_per_ticket",
                _comment_chars_per_ticket_default,
            )
            _comment_media_preview = _resolve_ticket_weight(
                "event_comment_media_ticket_bonus_input",
                "event_comment_media_ticket_bonus",
                _comment_media_ticket_bonus_default,
            )
            _c_t1, _c_t2 = st.columns(2)
            with _c_t1:
                st.text_input(
                    "댓글 글자수 기준",
                    value=str(st.session_state.get("event_comment_chars_per_ticket_input", "") or ""),
                    placeholder=str(_comment_chars_per_ticket_default),
                    key="event_comment_chars_per_ticket_input",
                    disabled=not cond2_checked,
                )
            with _c_t2:
                st.text_input(
                    "아이콘 or 사진 1장 = ( ) 티켓",
                    value=str(st.session_state.get("event_comment_media_ticket_bonus_input", "") or ""),
                    placeholder=str(_comment_media_ticket_bonus_default),
                    key="event_comment_media_ticket_bonus_input",
                    disabled=not cond2_checked,
                )
            if cond2_checked:
                _comment_rule_panel = "background:rgba(37,99,235,0.08);color:#1e3a8a;"
            else:
                _comment_rule_panel = "background:rgba(100,116,139,0.06);color:#475569;"
            st.markdown(
                f"<div style='margin:0.35rem 0 0.5rem;padding:0.45rem 0.6rem;border-radius:0.4rem;"
                f"{_comment_rule_panel}"
                f"font-weight:600;font-size:0.96rem;letter-spacing:-0.02em;line-height:1.35;'>"
                f"[ {_comment_chars_preview} ] 자당 1티켓 · 이미지 1장 {_comment_media_preview}티켓</div>",
                unsafe_allow_html=True,
            )
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        if st.button("💾 저장", use_container_width=True, key="event_save_settings_btn"):
            config["event_cafe_name"] = str(event_cafe_name or "").strip()
            config["event_cafe_url"] = cafe_url
            config["event_board_url"] = board_url
            config["event_selected_board_urls"] = st.session_state.get("event_selected_board_urls", [])
            config["event_start_date"] = comment_start_date.strftime("%Y-%m-%d")
            config["event_end_date"] = comment_end_date.strftime("%Y-%m-%d")
            config["event_condition_comment_enabled"] = bool(st.session_state.get("event_condition_comment_enabled", True))
            config["event_comment_start_date"] = comment_start_date.strftime("%Y-%m-%d")
            config["event_comment_end_date"] = comment_end_date.strftime("%Y-%m-%d")
            config["event_comment_search_start_date"] = comment_search_start_date.strftime("%Y-%m-%d")
            # 하위호환: 기존 키는 목표 종료일과 동일 값으로 유지
            config["event_comment_search_end_date"] = comment_end_date.strftime("%Y-%m-%d")
            config["event_condition_post_enabled"] = bool(st.session_state.get("event_condition_post_enabled", False))
            config["event_post_start_date"] = post_start_date.strftime("%Y-%m-%d")
            config["event_post_end_date"] = post_end_date.strftime("%Y-%m-%d")
            config["event_comment_chars_per_ticket"] = _resolve_ticket_weight(
                "event_comment_chars_per_ticket_input",
                "event_comment_chars_per_ticket",
                _comment_chars_per_ticket_default,
            )
            config["event_post_chars_per_ticket"] = _resolve_ticket_weight(
                "event_post_chars_per_ticket_input",
                "event_post_chars_per_ticket",
                _post_chars_per_ticket_default,
            )
            config["event_comment_media_ticket_bonus"] = _resolve_ticket_weight(
                "event_comment_media_ticket_bonus_input",
                "event_comment_media_ticket_bonus",
                _comment_media_ticket_bonus_default,
            )
            config["event_post_images_per_ticket"] = _resolve_ticket_weight(
                "event_post_images_per_ticket_input",
                "event_post_images_per_ticket",
                _post_images_per_ticket_default,
            )
            config["event_max_posts"] = 0
            config["event_exclude_post_nicks"] = exclude_post_nicks_text
            config["event_exclude_comment_nicks"] = exclude_comment_nicks_text
            config["event_apply_post_exclude"] = bool(
                st.session_state.get("event_apply_post_exclude_checkbox", True)
            )
            config["event_apply_comment_exclude"] = bool(
                st.session_state.get("event_apply_comment_exclude_checkbox", False)
            )
            # 하위호환: 기존 키에도 댓글 제외값 동기화
            config["event_exclude_nicks"] = exclude_comment_nicks_text
            config["event_auto_login_enabled"] = bool(event_auto_login_enabled)
            config["event_naver_id"] = str(event_naver_id or "").strip()
            config["event_naver_pw"] = str(event_naver_pw or "")
            config["event_extracted_boards"] = st.session_state.get("event_extracted_boards", [])
            config["event_db_path"] = str(
                st.session_state.get("event_db_path_input", config.get("event_db_path", ""))
            ).strip()
            save_config(config)
            _queue_ticket_inputs_materialize_after_save(config)
            st.success("✅ 설정이 저장되었습니다.")
            time.sleep(1)
            st.rerun()

with _ev3:
    with st.container(border=True, key="event_settings_card_3"):
        render_settings_card_title("DB 경로/초기화", icon="💾")
        event_db_path_text = st.text_input(
            "DB 경로",
            value=str(config.get("event_db_path", "")),
            placeholder=r"D:\CafeScraper\data\event_comments.db",
            key="event_db_path_input",
        )
        st.caption(f"활성 DB 파일: `{os.path.basename(EVENT_DB_PATH)}`")
        _ec1, _ec2 = st.columns(2)
        _ec1.metric(
            "저장 게시글/댓글",
            f"{get_event_posts_count(EVENT_DB_PATH):,}개 / {get_event_comments_count(EVENT_DB_PATH):,}건",
        )
        _ec2.metric("파일", "있음" if os.path.exists(EVENT_DB_PATH) else "없음")
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        st.warning("초기화하지 않으면 데이터가 계속 누적됩니다. 기존 작업 결과가 필요하면 먼저 CSV/리포트를 다운로드한 뒤 초기화를 진행하세요.")
        if st.button("🗑️ 이벤트 DB 초기화", type="primary", use_container_width=True, key="reset_event_db_btn"):
            try:
                # DB 초기화는 새 작업 시작 신호로 간주: 브라우저/실행 상태도 함께 리셋
                try:
                    if st.session_state.get("event_crawler") and getattr(st.session_state.event_crawler, "driver", None):
                        st.session_state.event_crawler.close()
                except Exception:
                    pass
                st.session_state.event_crawler = None
                st.session_state.event_running = False
                st.session_state.event_run_pending = False
                st.session_state.event_run_payload = None
                st.session_state.event_progress_ratio = 0.0
                st.session_state.event_progress_label = "대기 중..."

                conn_reset = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
                cur_reset = conn_reset.cursor()
                cur_reset.execute("DELETE FROM event_post_analysis")
                cur_reset.execute("DELETE FROM event_posts")
                cur_reset.execute("DELETE FROM event_comments")
                cur_reset.execute("DELETE FROM sqlite_sequence WHERE name = 'event_post_analysis'")
                cur_reset.execute("DELETE FROM sqlite_sequence WHERE name = 'event_posts'")
                cur_reset.execute("DELETE FROM sqlite_sequence WHERE name = 'event_comments'")
                conn_reset.commit()
                conn_reset.close()
                st.session_state.event_dup_report = None
                st.session_state.event_final_summary_report = None
                st.session_state.event_analysis_signature = ""
                st.success("✅ 이벤트 DB를 초기화했습니다.")
                time.sleep(0.8)
                st.rerun()
            except Exception as e:
                st.error(f"DB 초기화 실패: {e}")

# 실행용 조건값 정규화
comment_condition_enabled = bool(st.session_state.get("event_condition_comment_enabled", True))
post_condition_enabled = bool(st.session_state.get("event_condition_post_enabled", False))

comment_start_date = st.session_state.get("event_comment_start_date_input", _comment_default_start)
comment_end_date = st.session_state.get("event_comment_end_date_input", _comment_default_end)
comment_search_start_date = st.session_state.get("event_comment_search_start_date_input", _comment_search_default_start)
post_start_date = st.session_state.get("event_post_start_date_input", _post_default_start)
post_end_date = st.session_state.get("event_post_end_date_input", _post_default_end)
comment_chars_per_ticket = _resolve_ticket_weight(
    "event_comment_chars_per_ticket_input",
    "event_comment_chars_per_ticket",
    _comment_chars_per_ticket_default,
)
comment_media_ticket_bonus = _resolve_ticket_weight(
    "event_comment_media_ticket_bonus_input",
    "event_comment_media_ticket_bonus",
    _comment_media_ticket_bonus_default,
)
post_chars_per_ticket = _resolve_ticket_weight(
    "event_post_chars_per_ticket_input",
    "event_post_chars_per_ticket",
    _post_chars_per_ticket_default,
)
post_images_per_ticket = _resolve_ticket_weight(
    "event_post_images_per_ticket_input",
    "event_post_images_per_ticket",
    _post_images_per_ticket_default,
)

comment_start_dt = datetime.combine(comment_start_date, datetime.min.time())
comment_end_dt = datetime.combine(comment_end_date, datetime.max.time())
comment_search_start_dt = datetime.combine(comment_search_start_date, datetime.min.time())
# 댓글 조건(조건2) 게시글 탐색 종료는 별도 입력 없이 목표 종료일로 고정
comment_search_end_dt = comment_end_dt

post_start_dt = datetime.combine(post_start_date, datetime.min.time())
post_end_dt = datetime.combine(post_end_date, datetime.max.time())

# 대시보드 표시 기간(우선순위: 댓글조건 > 게시글조건)
if comment_condition_enabled:
    dashboard_start_date = comment_start_date
    dashboard_end_date = comment_end_date
else:
    dashboard_start_date = post_start_date
    dashboard_end_date = post_end_date

st.markdown("---")

# -----------------------------------------------------------------------------
# Control Panel
# -----------------------------------------------------------------------------
st.markdown("### 🚀 실행 제어")
st.caption("1단계에서 로그인 브라우저를 준비하고, 2단계에서 선택한 수집 조건을 실행합니다.")
step_col1, step_col_login, step_col2 = st.columns([2.5, 1.1, 2.5])
_event_crawler_obj = st.session_state.get("event_crawler")
event_browser_opened = bool(
    _event_crawler_obj is not None and getattr(_event_crawler_obj, "driver", None) is not None
)
event_any_condition_enabled = bool(comment_condition_enabled or post_condition_enabled)
_board_url_ok = bool(str(board_url or "").strip())
event_step2_ready = bool(event_browser_opened and _board_url_ok and event_any_condition_enabled)
if event_browser_opened and not event_step2_ready:
    _missing = []
    if not _board_url_ok:
        _missing.append("게시판 미선택")
    if not event_any_condition_enabled:
        _missing.append("조건 미선택")
    st.warning(f"⚠️ 2단계 비활성 원인: {', '.join(_missing)}")

with step_col1:
    if st.button(
        "1단계: 브라우저 열기",
        use_container_width=True,
        disabled=bool(st.session_state.event_running) or event_browser_opened,
        type="primary" if not event_browser_opened else "secondary",
        key="event_open_browser_btn",
    ):
        try:
            if not st.session_state.event_crawler:
                st.session_state.event_crawler = NaverCafeCrawler("", debug_mode=False)
                st.session_state.event_crawler.set_status_callback(update_logs)
            st.session_state.event_crawler.start_browser()
            update_logs("✅ 브라우저가 열렸습니다.")
        except Exception as _br_err:
            update_logs(f"❌ 브라우저 열기 실패: {_br_err}")
            st.rerun()

        # 자동로그인 실행
        try:
            _ev_auto_on = bool(
                st.session_state.get("event_auto_login_enabled_input", config.get("event_auto_login_enabled", False))
            )
            _ev_login_id = str(
                st.session_state.get("event_naver_id_input", config.get("event_naver_id", "")) or ""
            ).strip()
            _ev_login_pw = str(
                st.session_state.get("event_naver_pw_input", config.get("event_naver_pw", "")) or ""
            )
            update_logs(f"🔍 자동로그인 조건: enabled={_ev_auto_on}, id_len={len(_ev_login_id)}, pw_len={len(_ev_login_pw)}")
            if _ev_auto_on and _ev_login_id and _ev_login_pw:
                update_logs("🔐 자동로그인 시도 중...")
                login_ok, reason = _auto_login_naver_with_js(
                    st.session_state.event_crawler, _ev_login_id, _ev_login_pw,
                )
                if login_ok:
                    update_logs(f"✅ 자동로그인 성공 ({reason})")
                else:
                    update_logs(f"⚠️ 자동로그인 실패: {reason} — 브라우저에서 수동 로그인해주세요.")
            else:
                update_logs("💡 자동로그인 미설정. 브라우저에서 로그인 후 2단계를 진행하세요.")
        except Exception as _login_err:
            update_logs(f"❌ 자동로그인 예외: {_login_err}")

        st.rerun()

with step_col_login:
    st.empty()

with step_col2:
    if st.session_state.event_running:
        st.markdown(
            """
            <style>
            .st-key-event_step2_running div[data-testid="stButton"] > button {
                background-color: #d92d20 !important;
                border-color: #b42318 !important;
                color: #ffffff !important;
            }
            .st-key-event_step2_running div[data-testid="stButton"] > button:hover {
                background-color: #b42318 !important;
                border-color: #912018 !important;
                color: #ffffff !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="event_step2_running"):
            if st.button(
                "2단계: 댓글 수집·분석 진행 중 (중단)",
                type="secondary",
                use_container_width=True,
                key="event_running_btn",
            ):
                st.session_state.event_stop_requested = True
                update_logs("🛑 중단 요청을 받았습니다. 현재 처리 단위 완료 후 중단합니다.")
    else:
        if st.button(
            "2단계: 댓글 수집·분석 시작",
            type="primary",
            use_container_width=True,
            disabled=bool(st.session_state.event_running) or (not event_step2_ready),
            key="event_start_run_btn",
        ):
            if not st.session_state.event_crawler or not st.session_state.event_crawler.driver:
                st.error("먼저 브라우저를 열어주세요.")
            elif not str(board_url or "").strip():
                st.error("먼저 게시판 목록을 가져오고, 게시판을 선택해주세요.")
            elif not event_any_condition_enabled:
                st.error("수집 조건에서 최소 1개(조건1 또는 조건2)를 체크해주세요.")
            else:
                board_urls = [u.strip() for u in str(board_url or "").splitlines() if u.strip()]
                if not board_urls:
                    st.error("수집할 게시판이 없습니다. 게시판을 먼저 선택해주세요.")
                else:
                    st.session_state.event_run_payload = {
                        "board_urls": board_urls,
                        "comment_enabled": bool(comment_condition_enabled),
                        "comment_target_start_dt": comment_start_dt,
                        "comment_target_end_dt": comment_end_dt,
                        "comment_search_start_dt": comment_search_start_dt,
                        "comment_search_end_dt": comment_search_end_dt,
                        "post_enabled": bool(post_condition_enabled),
                        "post_start_dt": post_start_dt,
                        "post_end_dt": post_end_dt,
                        "exclude_post_nicks_text": str(exclude_post_nicks_text or ""),
                        "exclude_comment_nicks_text": str(exclude_comment_nicks_text or ""),
                        "apply_post_exclude": bool(st.session_state.get("event_apply_post_exclude_checkbox", True)),
                        "apply_comment_exclude": bool(st.session_state.get("event_apply_comment_exclude_checkbox", False)),
                    }
                    st.session_state.event_running = True
                    st.session_state.event_run_pending = True
                    st.session_state.event_stop_requested = False
                    st.session_state.event_progress_ratio = 0.0
                    st.session_state.event_progress_label = "준비 중..."
                    st.session_state.event_last_run_message = ""
                    st.session_state.event_dup_report = None
                    st.session_state.event_final_summary_report = None
                    st.session_state.event_analysis_signature = ""
                    st.rerun()

if st.session_state.event_running and not st.session_state.get("event_run_pending", False):
    _run_label = str(st.session_state.get("event_progress_label", "진행 중...") or "진행 중...")
    _run_ratio = float(st.session_state.get("event_progress_ratio", 0.0) or 0.0)
    st.progress(max(0.0, min(1.0, _run_ratio)))
    st.caption(_run_label)
elif st.session_state.get("event_last_run_message"):
    st.success(str(st.session_state.get("event_last_run_message") or ""))

if st.session_state.event_run_pending and st.session_state.event_running:
    payload = st.session_state.get("event_run_payload") or {}
    board_urls = [u.strip() for u in (payload.get("board_urls") or []) if str(u).strip()]
    comment_enabled = bool(payload.get("comment_enabled"))
    comment_target_start_dt = payload.get("comment_target_start_dt")
    comment_target_end_dt = payload.get("comment_target_end_dt")
    comment_search_start_dt = payload.get("comment_search_start_dt")
    comment_search_end_dt = payload.get("comment_search_end_dt")
    post_enabled = bool(payload.get("post_enabled"))
    post_start_dt = payload.get("post_start_dt")
    post_end_dt = payload.get("post_end_dt")
    exclude_post_nicks_raw = str(payload.get("exclude_post_nicks_text") or "")
    exclude_comment_nicks_raw = str(payload.get("exclude_comment_nicks_text") or "")
    apply_post_exclude_runtime = bool(payload.get("apply_post_exclude", True))
    apply_comment_exclude_runtime = bool(payload.get("apply_comment_exclude", False))

    prog = st.progress(max(0.0, min(1.0, float(st.session_state.get("event_progress_ratio", 0.0) or 0.0))))
    _metrics_placeholder = st.empty()
    _detail_placeholder = st.empty()
    _run_start_time = time.time()

    def _fmt_duration(sec: float) -> str:
        sec = max(0, int(sec))
        if sec < 60:
            return f"{sec}초"
        m, s = divmod(sec, 60)
        if m < 60:
            return f"{int(m)}분 {s}초"
        h, m = divmod(int(m), 60)
        return f"{h}시간 {int(m)}분"

    def _set_event_progress(ratio: float, msg: str) -> None:
        rr = max(0.0, min(1.0, float(ratio)))
        st.session_state.event_progress_ratio = rr
        st.session_state.event_progress_label = str(msg or "")
        prog.progress(rr)
        elapsed = time.time() - _run_start_time
        eta_str = "계산 중..."
        eta_total_str = ""
        if rr > 0.02:
            eta = elapsed / rr * (1.0 - rr)
            total_est = elapsed + eta
            eta_str = _fmt_duration(eta)
            eta_total_str = f" / 총 {_fmt_duration(total_est)}"
        _done = int(total_articles_processed)
        _fail = int(failed_articles)
        _seen = int(comments_seen_total)
        _saved = int(inserted_total)
        _avg = (elapsed / _done) if _done > 0 else 0

        with _metrics_placeholder.container():
            _mc1, _mc2, _mc3, _mc4 = st.columns([1, 1, 1, 1.4])
            _mc1.metric("처리 게시글", f"{_done:,}개", delta=f"실패 {_fail}개" if _fail else None, delta_color="inverse" if _fail else "off")
            _mc2.metric("댓글 조회", f"{_seen:,}개", delta=f"저장 {_saved:,}개")
            _mc3.metric("경과 시간", _fmt_duration(elapsed))
            _mc4.markdown(
                f"<div style='background:linear-gradient(180deg,#f8fbff 0%,#f3f7fc 100%);"
                f"border:1px solid #dbe5f2;border-radius:12px;padding:12px 14px;"
                f"box-shadow:0 2px 8px rgba(15,23,42,0.04);min-height:90px;"
                f"display:flex;flex-direction:column;justify-content:center;'>"
                f"<div style='font-size:0.86rem;color:#64748b;font-weight:700;'>예상 남은 시간</div>"
                f"<div style='font-size:1.25rem;line-height:1.35;color:#0f172a;font-weight:800;'>"
                f"{eta_str}{eta_total_str}</div></div>",
                unsafe_allow_html=True,
            )

        _detail_placeholder.markdown(
            f"<div style='font-size:0.95rem;color:#334155;font-weight:600;padding:2px 0 6px 0;'>"
            f"{msg}"
            f"{(' · 평균 ' + f'{_avg:.1f}초/건') if _done > 0 else ''}"
            f"</div>",
            unsafe_allow_html=True,
        )

    try:
        update_logs("🔍 선택한 조건 실행 시작...")
        inserted_total = 0
        comments_seen_total = 0
        excluded_total = 0
        excluded_post_total = 0
        unknown_date_excluded_total = 0
        date_filter_relaxed_articles = 0
        failed_articles = 0
        total_articles_processed = 0
        post_analysis_saved_total = 0
        def _norm_nick(v: str) -> str:
            return "".join(str(v or "").strip().lower().split())
        def _parse_level_map(raw_text: str) -> dict[str, str]:
            out: dict[str, str] = {}
            for ln in str(raw_text or "").splitlines():
                s = str(ln or "").strip()
                if (not s) or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                elif ":" in s:
                    k, v = s.split(":", 1)
                else:
                    continue
                kk = str(k or "").strip().lower()
                vv = str(v or "").strip()
                if kk and vv:
                    out[kk] = vv
            return out

        exclude_post_set = (
            {_norm_nick(x) for x in exclude_post_nicks_raw.splitlines() if str(x).strip()}
            if apply_post_exclude_runtime
            else set()
        )
        exclude_comment_set = (
            {_norm_nick(x) for x in exclude_comment_nicks_raw.splitlines() if str(x).strip()}
            if apply_comment_exclude_runtime
            else set()
        )
        comment_level_name_map = _parse_level_map(DEFAULT_COMMENT_LEVEL_MAP_TEXT)
        adaptive_delay_min = float(SAFE_DELAY_MIN_SEC)
        adaptive_delay_max = float(SAFE_DELAY_MAX_SEC)
        stable_success_streak = 0

        if (not comment_enabled) and (not post_enabled):
            raise RuntimeError("조건1/조건2 중 최소 1개를 선택해야 합니다.")

        def _in_post_window(art: dict) -> bool:
            if not post_enabled:
                return False
            try:
                d = datetime.strptime(str(art.get("date") or ""), "%Y-%m-%d")
                return bool(post_start_dt <= d <= post_end_dt)
            except Exception:
                return False

        def _parse_comment_date(val: str) -> datetime | None:
            s = str(val or "").strip()
            if not s:
                return None
            try:
                return datetime.strptime(s[:10], "%Y-%m-%d")
            except Exception:
                pass
            try:
                return datetime.strptime(s, "%Y.%m.%d")
            except Exception:
                pass
            # YYYY.MM.DD HH:MM[:SS]
            m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
            if m:
                try:
                    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except Exception:
                    pass
            # MM.DD (연도 생략)
            m2 = re.search(r"\b(\d{1,2})[./-](\d{1,2})\b", s)
            if m2:
                try:
                    now = datetime.now()
                    mm, dd = int(m2.group(1)), int(m2.group(2))
                    yy = now.year - 1 if (mm, dd) > (now.month, now.day) else now.year
                    return datetime(yy, mm, dd)
                except Exception:
                    pass
            # 상대 표기
            if "오늘" in s or "방금" in s:
                return datetime.now()
            if "어제" in s:
                return datetime.now() - timedelta(days=1)
            m3 = re.search(r"(\d+)\s*일\s*전", s)
            if m3:
                try:
                    return datetime.now() - timedelta(days=int(m3.group(1)))
                except Exception:
                    pass
            m4 = re.search(r"(\d+)\s*시간\s*전", s)
            if m4:
                try:
                    return datetime.now() - timedelta(hours=int(m4.group(1)))
                except Exception:
                    pass
            m5 = re.search(r"(\d+)\s*분\s*전", s)
            if m5:
                try:
                    return datetime.now() - timedelta(minutes=int(m5.group(1)))
                except Exception:
                    pass
            return None

        for b_idx, board_url_each in enumerate(board_urls, start=1):
            if st.session_state.get("event_stop_requested", False):
                update_logs("🛑 사용자 요청으로 실행을 중단합니다.")
                break
            _set_event_progress((b_idx - 1) / max(1, len(board_urls)), f"게시판 {b_idx}/{len(board_urls)} 목록 수집 중...")
            update_logs(f"📌 게시판 {b_idx}/{len(board_urls)} 목록 수집: {board_url_each}")
            result = st.session_state.event_crawler.scrape_board_list(
                board_url_each,
                (comment_search_start_dt if comment_enabled else post_start_dt),
                (comment_search_end_dt if comment_enabled else post_end_dt),
                exclude_boards=[],
            )
            if isinstance(result, tuple) and len(result) == 2:
                articles, _is_finished = result
            else:
                articles, _is_finished = result, False
            if not articles:
                update_logs(f"⚠️ 게시판 {b_idx}/{len(board_urls)}에서 기간 내 게시글을 찾지 못했습니다.")
                _set_event_progress(b_idx / max(1, len(board_urls)), f"게시판 {b_idx}/{len(board_urls)} 완료(대상 없음)")
                continue

            update_logs(f"✅ 게시판 {b_idx}/{len(board_urls)} 대상 게시글 {len(articles):,}개 확보. 댓글 수집 시작...")
            for i, art in enumerate(articles):
                if st.session_state.get("event_stop_requested", False):
                    update_logs("🛑 사용자 요청으로 실행을 중단합니다.")
                    break
                board_prog = (i + 1) / len(articles)
                total_prog = ((b_idx - 1) + board_prog) / max(1, len(board_urls))
                _set_event_progress(total_prog, f"진행률 {int(total_prog * 100)}% · 게시판 {b_idx}/{len(board_urls)}")
                total_articles_processed += 1
                list_author_nick = str(art.get("nickname") or "unknown").strip() or "unknown"

                # 게시글 제외별명: 목록 작성자 + (불명확 시) 상세 작성자까지 확인
                post_author_nick = str(art.get("nickname") or "")
                post_author_norm = _norm_nick(post_author_nick)
                detail_for_author = None
                if exclude_post_set:
                    if post_author_norm and post_author_norm in exclude_post_set:
                        excluded_post_total += 1
                        update_logs(f"⏭️ 게시글 제외(작성자): {(art.get('title') or '')[:30]}...")
                        continue
                    if (not post_author_norm) or (post_author_norm == "unknown"):
                        try:
                            detail_for_author = st.session_state.event_crawler.scrape_article_detail(
                                art.get("url") or "",
                                art.get("member_id") or "unknown",
                                admin_nicks=[],
                                comment_mode="none",
                            )
                            detail_author = str((detail_for_author or {}).get("nickname") or "")
                            detail_author_norm = _norm_nick(detail_author)
                            if detail_author_norm and detail_author_norm in exclude_post_set:
                                excluded_post_total += 1
                                update_logs(f"⏭️ 게시글 제외(상세작성자): {(art.get('title') or '')[:30]}...")
                                continue
                        except Exception:
                            pass

                # 목록 작성자 별명이 unknown/공백이면 상세에서 1회 보정
                resolved_author_nick = list_author_nick
                if _norm_nick(resolved_author_nick) in ("", "unknown"):
                    try:
                        if detail_for_author is None:
                            detail_for_author = st.session_state.event_crawler.scrape_article_detail(
                                art.get("url") or "",
                                art.get("member_id") or "unknown",
                                admin_nicks=[],
                                comment_mode="none",
                            )
                        detail_author_nick = str((detail_for_author or {}).get("nickname") or "").strip()
                        if detail_author_nick:
                            resolved_author_nick = detail_author_nick
                    except Exception:
                        pass
                if not comment_enabled:
                    save_event_post(
                        EVENT_DB_PATH,
                        art,
                        comments_seen=0,
                        comments_saved=0,
                        comments_excluded=0,
                        author_nickname=resolved_author_nick,
                    )

                title = (art.get("title") or "")[:30]
                update_logs(f"💬 ({i+1}/{len(articles)}) '{title}...' 댓글 조회 중")
                try:
                    if comment_enabled:
                        art_url = art.get("url") or ""
                        comments = st.session_state.event_crawler.get_all_comments_for_article(art_url)
                        raw_comments_count = len(comments)
                        list_comment_hint = int(art.get("list_comment_count") or 0)
                        dbg = getattr(st.session_state.event_crawler, "last_comment_fetch_debug", {}) or {}
                        update_logs(
                            f"🔍 댓글 수집 상세: post_id={art.get('post_id')} "
                            f"목록표시={list_comment_hint} 실수집={raw_comments_count} "
                            f"API={int(dbg.get('api_count') or 0)} DOM={int(dbg.get('dom_count') or 0)} "
                            f"병합={int(dbg.get('merged_count') or 0)} source={str(dbg.get('source') or '')} "
                            f"url={art_url[:80]}"
                        )
                        if list_comment_hint > 0 and raw_comments_count < list_comment_hint:
                            update_logs(
                                f"🧪 댓글 누락 의심: 목록표시 {list_comment_hint}개 > 수집 {raw_comments_count}개"
                            )
                        target_window_comments = []

                        filtered = []
                        unknown_date_samples = 0
                        parsed_rows = []
                        known_date_count = 0
                        for c in comments:
                            raw_dt = str(c.get("date") or "")
                            cdt = _parse_comment_date(raw_dt)
                            parsed_rows.append((c, cdt, raw_dt))
                            if cdt is not None:
                                known_date_count += 1

                        # 실운영 대응: 날짜가 전부 비어오면 기간 필터를 완화해 전량 누락을 막는다.
                        relax_date_filter = bool(len(parsed_rows) > 0 and known_date_count == 0)
                        if relax_date_filter:
                            date_filter_relaxed_articles += 1
                            update_logs(
                                f"⚠️ 댓글 날짜를 전부 파싱하지 못해 기간 필터를 완화합니다. "
                                f"(게시글 '{title}...', 댓글 {len(parsed_rows):,}개)"
                            )

                        for c, cdt, raw_dt in parsed_rows:
                            if cdt is None:
                                if not relax_date_filter:
                                    unknown_date_excluded_total += 1
                                    if unknown_date_samples < 2:
                                        update_logs(
                                            f"🧪 날짜 파싱 실패 샘플: date='{raw_dt[:50]}' "
                                            f"comment_id='{str(c.get('comment_id') or '')[:30]}'"
                                        )
                                        unknown_date_samples += 1
                                    continue
                            else:
                                if not (comment_target_start_dt <= cdt <= comment_target_end_dt):
                                    continue

                            target_window_comments.append(c)
                            nn = str(c.get("nickname") or "").strip()
                            if nn and _norm_nick(nn) in exclude_comment_set:
                                excluded_total += 1
                                continue
                            lv_code = str(c.get("level_code") or "").strip().lower()
                            lv_name_raw = str(c.get("level") or "").strip()
                            lv_name = str(comment_level_name_map.get(lv_code, lv_name_raw) or lv_name_raw).strip()
                            c["level_code"] = lv_code
                            c["level"] = lv_name
                            filtered.append(c)

                        comments_seen_total += raw_comments_count

                        ins = save_event_comments(EVENT_DB_PATH, art, filtered)
                        excluded_now = len(target_window_comments) - len(filtered)
                        inserted_total += ins
                        save_event_post(
                            EVENT_DB_PATH,
                            art,
                            comments_seen=len(target_window_comments),
                            comments_saved=ins,
                            comments_excluded=excluded_now,
                            author_nickname=resolved_author_nick,
                        )

                        stable_success_streak += 1
                        if stable_success_streak >= 5:
                            adaptive_delay_min = max(SAFE_DELAY_MIN_SEC, adaptive_delay_min - 0.4)
                            adaptive_delay_max = max(SAFE_DELAY_MAX_SEC, adaptive_delay_max - 0.6)
                            stable_success_streak = 0

                        ignored_by_unique = max(0, len(filtered) - ins)
                        update_logs(
                            f"✅ 댓글 전체 {raw_comments_count:,}개 중 목표기간 {len(target_window_comments):,}개 / "
                            f"제외 {excluded_now:,}개 / 중복무시 {ignored_by_unique:,}개 / "
                            f"신규 저장 {ins:,}개 (누적 신규 {inserted_total:,})"
                        )
                    else:
                        # 댓글 조건 미선택일 때도 게시글 메타는 보존
                        save_event_post(
                            EVENT_DB_PATH,
                            art,
                            comments_seen=0,
                            comments_saved=0,
                            comments_excluded=0,
                            author_nickname=resolved_author_nick,
                        )

                    if _in_post_window(art):
                        detail = detail_for_author
                        if detail is None:
                            detail = st.session_state.event_crawler.scrape_article_detail(
                                art.get("url") or "",
                                art.get("member_id") or "unknown",
                                admin_nicks=[],
                                comment_mode="none",
                            )
                        # 상세 작성자 기준으로도 최종 제외 확인
                        detail_author_norm = _norm_nick(str((detail or {}).get("nickname") or ""))
                        if detail_author_norm and detail_author_norm in exclude_post_set:
                            excluded_post_total += 1
                            update_logs(f"⏭️ 게시글 제외(상세작성자): {(art.get('title') or '')[:30]}...")
                            continue
                        save_event_post_analysis(
                            EVENT_DB_PATH,
                            art,
                            author_nickname=str(detail.get("nickname") or art.get("nickname") or "unknown"),
                            post_char_count=int(detail.get("post_char_count") or 0),
                            post_image_count=int(detail.get("post_image_count") or 0),
                        )
                        save_event_post(
                            EVENT_DB_PATH,
                            art,
                            comments_seen=0 if not comment_enabled else len(comments),
                            comments_saved=0 if not comment_enabled else ins,
                            comments_excluded=0 if not comment_enabled else excluded_now,
                            author_nickname=str(detail.get("nickname") or art.get("nickname") or "unknown"),
                            post_char_count=int(detail.get("post_char_count") or 0),
                            post_image_count=int(detail.get("post_image_count") or 0),
                        )
                        post_analysis_saved_total += 1
                except Exception as e:
                    failed_articles += 1
                    stable_success_streak = 0
                    adaptive_delay_min = min(BACKOFF_MAX_MIN_SEC, adaptive_delay_min + BACKOFF_STEP_MIN_SEC)
                    adaptive_delay_max = min(BACKOFF_MAX_MAX_SEC, adaptive_delay_max + BACKOFF_STEP_MAX_SEC)
                    import traceback as _tb
                    _err_detail = _tb.format_exc()
                    update_logs(
                        f"⚠️ 댓글 조회/저장 실패: {title}... ({e}) "
                        f"→ 대기 {adaptive_delay_min:.1f}~{adaptive_delay_max:.1f}초로 상향"
                    )
                    update_logs(f"🔍 실패 상세: {_err_detail[-300:]}")

                if adaptive_delay_max < adaptive_delay_min:
                    adaptive_delay_min, adaptive_delay_max = adaptive_delay_max, adaptive_delay_min
                time.sleep(random.uniform(adaptive_delay_min, adaptive_delay_max))

        _total_elapsed = time.time() - _run_start_time
        done_msg = (
            f"✅ 완료: 게시판 {len(board_urls):,}개, 게시글 {total_articles_processed:,}개 처리, "
            f"게시글 제외 {excluded_post_total:,}개, 댓글 조회 {comments_seen_total:,}개, 댓글 제외 {excluded_total:,}개, "
            f"날짜 미확인 제외 {unknown_date_excluded_total:,}개, "
            f"기간완화 {date_filter_relaxed_articles:,}개 글, "
            f"신규 저장 {inserted_total:,}개, 게시글 분석 저장 {post_analysis_saved_total:,}개, 실패 {failed_articles:,}개 "
            f"(소요 {_fmt_duration(_total_elapsed)})"
        )
        _avg_final = (_total_elapsed / total_articles_processed) if total_articles_processed > 0 else 0
        with _metrics_placeholder.container():
            _fc1, _fc2, _fc3, _fc4 = st.columns(4)
            _fc1.metric("처리 게시글", f"{total_articles_processed:,}개", delta=f"실패 {failed_articles}개" if failed_articles else "전부 성공", delta_color="inverse" if failed_articles else "normal")
            _fc2.metric("댓글 조회", f"{comments_seen_total:,}개", delta=f"저장 {inserted_total:,}개")
            _fc3.metric("소요 시간", _fmt_duration(_total_elapsed))
            _fc4.metric("평균 처리", f"{_avg_final:.1f}초/건" if _avg_final else "-")
        _detail_placeholder.markdown(
            f"<div style='font-size:0.95rem;color:#16a34a;font-weight:700;padding:2px 0 6px 0;'>✅ 수집 완료</div>",
            unsafe_allow_html=True,
        )
        # 디버그 로그를 파일로 저장
        try:
            _log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
            os.makedirs(_log_dir, exist_ok=True)
            _log_file = os.path.join(_log_dir, f"event_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
            with open(_log_file, "w", encoding="utf-8") as _lf:
                _lf.write("\n".join(st.session_state.get("event_logs", [])))
            update_logs(f"📄 실행 로그 저장: {_log_file}")
        except Exception:
            pass
        st.session_state.event_last_processed_posts = int(total_articles_processed)
        st.session_state.event_last_seen_comments = int(comments_seen_total)
        st.session_state.event_last_excluded_comments = int(excluded_total)
        if comment_enabled:
            try:
                _ensure_event_analysis_reports(force=True)
                st.session_state.event_dup_collapsed = False
                update_logs("🧠 수집 완료 후 분석 1/2 자동 집계를 완료했습니다.")
            except Exception as analysis_e:
                update_logs(f"⚠️ 자동 분석 집계 중 오류: {analysis_e}")
        update_logs(done_msg)
        st.session_state.event_last_run_message = done_msg
        _set_event_progress(1.0, "완료")
    except Exception as e:
        st.error(f"댓글 수집 실행 중 오류: {e}")
        update_logs(f"❌ 댓글 수집 실행 중 오류: {e}")
        st.session_state.event_last_run_message = f"⚠️ 실행 중 오류: {e}"
    finally:
        st.session_state.event_run_pending = False
        st.session_state.event_running = False
        st.session_state.event_run_payload = None
        st.session_state.event_stop_requested = False
        st.rerun()

# -----------------------------------------------------------------------------
# Data Dashboard
# -----------------------------------------------------------------------------
update_logs()

st.markdown("### 📊 데이터 관리")
_badge_post_count = len(
    [x for x in str(st.session_state.get("event_exclude_post_nicks_text", "") or "").splitlines() if str(x).strip()]
)
_badge_comment_count = len(
    [x for x in str(st.session_state.get("event_exclude_comment_nicks_text", "") or "").splitlines() if str(x).strip()]
)
_badge_post_enabled = bool(st.session_state.get("event_apply_post_exclude_checkbox", True))
_badge_comment_enabled = bool(st.session_state.get("event_apply_comment_exclude_checkbox", False))
st.caption(
    f"🏷️ 제외 설정 적용 중 · 게시글 제외 별명 {'ON' if _badge_post_enabled else 'OFF'}({_badge_post_count}명) · "
    f"댓글 제외 별명 {'ON' if _badge_comment_enabled else 'OFF'}({_badge_comment_count}명)"
)

try:
    conn_stats = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
    stats_row = pd.read_sql_query(
        """
        SELECT
            (SELECT COUNT(*) FROM event_posts) AS posts_cnt,
            COUNT(*) AS comments_cnt,
            COUNT(DISTINCT comment_writer_id) AS people_cnt,
            COALESCE(SUM(comment_length), 0) AS chars_cnt
        FROM event_comments
        """,
        conn_stats,
    ).iloc[0]
    conn_stats.close()

    st.caption(
        f"📅 표시 기간: **{dashboard_start_date.strftime('%Y-%m-%d')} ~ {dashboard_end_date.strftime('%Y-%m-%d')}**"
    )
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("저장 게시글", f"{int(stats_row['posts_cnt']):,}개")
    m2.metric("수집된 댓글", f"{int(stats_row['comments_cnt']):,}개")
    m3.metric("참여 인원", f"{int(stats_row['people_cnt']):,}명")
    m4.metric("총 글자수", f"{int(stats_row['chars_cnt']):,}자")
    _last_processed = int(st.session_state.get("event_last_processed_posts", 0) or 0)
    _last_seen_comments = int(st.session_state.get("event_last_seen_comments", 0) or 0)
    _last_excluded_comments = int(st.session_state.get("event_last_excluded_comments", 0) or 0)
    if _last_processed > 0:
        st.caption(
            f"최근 실행 기준: 게시글 {_last_processed:,}개 처리 · 댓글 조회 {_last_seen_comments:,}개 · 제외 {_last_excluded_comments:,}개"
        )

    st.divider()

    conn = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
    df = pd.read_sql_query(
        """
        SELECT
            ec.post_date,
            ec.board_name,
            COALESCE(NULLIF(ep.author_nickname, ''), NULLIF(epa.author_nickname, ''), 'unknown') AS post_author_nickname,
            ec.post_title,
            COALESCE(NULLIF(TRIM(ec.comment_nickname), ''), 'unknown') AS comment_nickname,
            ec.text_char_count,
            ec.emoji_count,
            ec.inline_image_count,
            ec.comment_content,
            ec.post_url
        FROM event_comments ec
        LEFT JOIN event_posts ep ON ep.post_id = ec.post_id
        LEFT JOIN event_post_analysis epa ON epa.post_id = ec.post_id
        ORDER BY ec.post_date DESC, ec.post_id DESC, ec.id ASC
        """,
        conn,
    )
    conn.close()

    # 구버전 DB/NULL 데이터와 무관하게 수치 컬럼은 항상 노출되도록 보정
    for _metric_col in ["text_char_count", "emoji_count", "inline_image_count"]:
        if _metric_col not in df.columns:
            df[_metric_col] = 0
        df[_metric_col] = pd.to_numeric(df[_metric_col], errors="coerce").fillna(0).astype(int)

    if df.empty:
        st.info("📭 아직 저장된 데이터가 없습니다. 수집을 시작해보세요.")
    else:
        st.data_editor(
            df,
            column_config={
                "post_date": "게시일",
                "board_name": "게시판",
                "post_author_nickname": "게시글작성자(별명)",
                "post_title": st.column_config.TextColumn("게시글 제목", width="medium"),
                "comment_nickname": "별명",
                "post_url": st.column_config.LinkColumn("원글 링크"),
                "text_char_count": st.column_config.NumberColumn("글자수", format="%d"),
                "emoji_count": st.column_config.NumberColumn("아이콘수", format="%d"),
                "inline_image_count": st.column_config.NumberColumn("이미지수", format="%d"),
                "comment_content": st.column_config.TextColumn("댓글 내용", width="large"),
            },
            hide_index=True,
            use_container_width=True,
            disabled=True,
            key="event_editor_readonly",
        )

        # 하단 액션 버튼: CSV 저장만 유지
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "⬇️ CSV 저장",
            data=csv_bytes,
            file_name=f"event_comments_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

except Exception as e:
    st.error(f"DB 조회 오류: {e}")

# -----------------------------------------------------------------------------
# Post Analysis Section (Condition 2)
# -----------------------------------------------------------------------------
st.markdown("### 📝 조건1 게시글 수집·분석 결과")
try:
    conn_post = sqlite3.connect(EVENT_DB_PATH, timeout=30.0)
    df_post = pd.read_sql_query(
        """
        SELECT
            post_date,
            board_name,
            post_title,
            author_nickname,
            post_char_count,
            post_image_count
        FROM event_post_analysis
        ORDER BY
            post_date DESC,
            CASE WHEN post_id GLOB '[0-9]*' THEN CAST(post_id AS INTEGER) ELSE 0 END DESC,
            id DESC
        """,
        conn_post,
    )
    conn_post.close()
    if df_post.empty:
        st.info("조건1 게시글 분석 결과가 없습니다.")
    else:
        st.dataframe(
            df_post,
            use_container_width=True,
            hide_index=True,
            column_config={
                "post_date": "날짜",
                "board_name": "게시판명",
                "post_title": st.column_config.TextColumn("게시글제목", width="large"),
                "author_nickname": "별명",
                "post_char_count": st.column_config.NumberColumn("글자수", format="%d"),
                "post_image_count": st.column_config.NumberColumn("사진수", format="%d"),
            },
        )
    if not df_post.empty:
        st.markdown("#### 🎫 조건1 참여자 티켓수 집계")
        _post_sum_indent, _post_sum_body = st.columns([0.05, 0.95])
        with _post_sum_body:
            st.caption(
                f"티켓 산정 규칙: 글자수(제목 포함) {post_chars_per_ticket}자당 티켓 1개 / 사진 {post_images_per_ticket}장당 티켓 1개"
            )

            _df_p = df_post.copy()
            for _nc in ["post_char_count", "post_image_count"]:
                _df_p[_nc] = pd.to_numeric(_df_p[_nc], errors="coerce").fillna(0).astype(int)
            _df_p["_title_len"] = _df_p["post_title"].apply(lambda t: len(str(t or "")))
            _df_p["_total_chars"] = _df_p["post_char_count"] + _df_p["_title_len"]

            def _text_ticket(chars: int) -> int:
                if chars <= 0:
                    return 0
                return max(1, (chars - 1) // post_chars_per_ticket + 1)

            _df_p["텍스트티켓"] = _df_p["_total_chars"].apply(_text_ticket)
            _df_p["사진티켓"] = (_df_p["post_image_count"] // max(1, int(post_images_per_ticket))).astype(int)
            _df_p["티켓합"] = _df_p["텍스트티켓"] + _df_p["사진티켓"]

            _post_base = (
                _df_p.groupby("author_nickname")
                .agg(
                    게시글수=("post_title", "count"),
                    텍스트티켓=("텍스트티켓", "sum"),
                    사진티켓=("사진티켓", "sum"),
                    총티켓수=("티켓합", "sum"),
                )
                .rename_axis("별명")
            )

            _max_t = int(_df_p["티켓합"].max()) if not _df_p.empty else 1
            for _tv in range(1, _max_t + 1):
                _col = f"티켓{_tv}"
                _tc = (
                    _df_p[_df_p["티켓합"] == _tv]
                    .groupby("author_nickname")["post_title"].count()
                    .rename(_col)
                )
                _post_base = _post_base.merge(_tc, left_index=True, right_index=True, how="left")
                _post_base[_col] = _post_base[_col].fillna(0).astype(int)

            _tcols = [c for c in _post_base.columns if c.startswith("티켓") and c not in ("총티켓수",)]
            _ordered = ["총티켓수", "게시글수"] + sorted(_tcols, key=lambda x: int(x.replace("티켓", ""))) + ["텍스트티켓", "사진티켓"]
            _post_sum = _post_base[[c for c in _ordered if c in _post_base.columns]].sort_values(
                ["총티켓수", "게시글수"], ascending=[False, False]
            )

            _p_people = len(_post_sum)
            _p_posts = int(_post_sum["게시글수"].sum()) if "게시글수" in _post_sum.columns else 0
            _p_total_tickets = int(_post_sum["총티켓수"].sum()) if "총티켓수" in _post_sum.columns else 0
            _p_text_t = int(_post_sum["텍스트티켓"].sum()) if "텍스트티켓" in _post_sum.columns else 0
            _p_img_t = int(_post_sum["사진티켓"].sum()) if "사진티켓" in _post_sum.columns else 0
            _pm1, _pm2, _pm3, _pm4, _pm5 = st.columns(5)
            _pm1.metric("참여자", f"{_p_people}명")
            _pm2.metric("총 게시글", f"{_p_posts}개")
            _pm3.metric("총 티켓", f"{_p_total_tickets:,}개")
            _pm4.metric("글자 티켓", f"{_p_text_t:,}개")
            _pm5.metric("사진 티켓", f"{_p_img_t:,}개")

            st.dataframe(
                _post_sum,
                use_container_width=True,
                hide_index=False,
            )

            _post_sum_bytes = _post_sum.to_csv(index=True, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "⬇️ 조건1 티켓 집계 다운로드",
                data=_post_sum_bytes,
                file_name=f"event_post_ticket_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="post_ticket_download",
            )

except Exception as e:
    st.error(f"조건1 결과 조회 오류: {e}")


# -----------------------------------------------------------------------------
# Duplicate Analysis Section
# -----------------------------------------------------------------------------
if comment_condition_enabled:
    try:
        _ensure_event_analysis_reports()
    except Exception as _auto_analysis_e:
        update_logs(f"⚠️ 자동 집계 재실행 오류: {_auto_analysis_e}")

if comment_condition_enabled:
    st.markdown("### 1. 중복/복붙 댓글 정밀 분석")
    _dup_indent_col, _dup_body_col = st.columns([0.05, 0.95])
    with _dup_body_col:
        st.caption("동일한 작성자가 똑같은 내용을 반복해서 작성한 경우를 찾아냅니다. (어뷰징 탐지)")
        st.caption("수집 완료 후 자동 분석됩니다.")
        _dup_action_left, _dup_action_spacer, _dup_action_fold = st.columns([0.01, 0.84, 0.15])
        with _dup_action_fold:
            _fold_icon = "▶️" if st.session_state.event_dup_collapsed else "🔽"
            if st.button(_fold_icon, key="toggle_dup_analysis_fold_btn", help="중복 분석 결과 접기/펼치기"):
                st.session_state.event_dup_collapsed = not bool(st.session_state.event_dup_collapsed)
                st.rerun()

    _dup_indent_col2, _dup_body_col2 = st.columns([0.05, 0.95])
    with _dup_body_col2:
        dup_report = st.session_state.get("event_dup_report")
        if dup_report:
            if st.session_state.event_dup_collapsed:
                st.caption("중복 분석 결과가 접혀 있습니다.")
            else:
                status = str(dup_report.get("status") or "")
                if status == "empty":
                    st.warning("분석할 데이터가 없습니다.")
                elif status == "clean":
                    st.success("✅ 클린! 중복/복붙 댓글이 발견되지 않았습니다.")
                elif status == "data":
                    total_dup_count = int(dup_report.get("total_dup_count", 0))
                    total_dup_groups = int(dup_report.get("total_dup_groups", 0))
                    total_copy_count = int(dup_report.get("total_copy_count", 0))
                    total_copy_chars_adjusted = int(dup_report.get("total_copy_chars_adjusted", 0))

                    m1, m2, m3 = st.columns(3)
                    m1.metric("총 중복 댓글 수", f"{total_dup_count:,}개", delta="어뷰징 의심", delta_color="inverse")
                    m2.metric("중복 패턴 수", f"{total_dup_groups:,}개")
                    m3.metric("복붙 건수", f"{total_copy_count:,}개")
                    st.caption(f"복붙 댓글은 1건당 {COPY_COMMENT_CHAR_BASE}자로 환산합니다. (환산 합계: {total_copy_chars_adjusted:,}자)")

                    st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
                    st.markdown("#### 📋 중복 작성자 상세 리포트")
                    for item in (dup_report.get("spammers") or []):
                        nick = str(item.get("nick") or "unknown")
                        count = int(item.get("total_count", 0))
                        rows = item.get("rows") or []
                        with st.expander(f"👤 {nick} (총 {count}개 중복 발견)"):
                            display_df = pd.DataFrame(rows)
                            if display_df.empty:
                                st.info("표시할 데이터가 없습니다.")
                            else:
                                display_df["중복 내용"] = display_df["comment_content"].apply(
                                    lambda x: (str(x)[:64] + "...") if len(str(x)) > 64 else str(x)
                                )
                                display_df["원문 글자수"] = display_df["orig_len"].astype(int)
                                display_df["복붙"] = display_df["copy_count"].astype(int).apply(lambda n: f"복붙 {n}개")
                                display_df = display_df[["중복 내용", "원문 글자수", "복붙"]]
                                st.table(display_df)
        elif not st.session_state.event_running:
            st.info("아직 자동 분석 결과가 없습니다. 댓글 수집을 완료하면 자동으로 표시됩니다.")


# -----------------------------------------------------------------------------
# Summary Section
# -----------------------------------------------------------------------------
if comment_condition_enabled:
    st.markdown("### 2. 조건2 참여자 티켓수 집계")
    try:
        _sum_indent_col, _sum_body_col = st.columns([0.05, 0.95])
        with _sum_body_col:
            st.caption(
                f"티켓 산정 규칙: 글자수 {comment_chars_per_ticket}자당 티켓 1개 / 아이콘 또는 사진 1장 = +{comment_media_ticket_bonus}티켓 / 복붙 댓글은 티켓 1개 고정"
            )

            final_summary_report = st.session_state.get("event_final_summary_report")
            if final_summary_report:
                if str(final_summary_report.get("status") or "") == "empty":
                    st.info("아직 집계할 데이터가 없습니다.")
                elif str(final_summary_report.get("status") or "") == "data":
                    sum_df = final_summary_report.get("df")
                    if isinstance(sum_df, pd.DataFrame) and not sum_df.empty:
                        _c_people = len(sum_df)
                        _c_comments = int(sum_df["댓글수"].sum()) if "댓글수" in sum_df.columns else 0
                        _c_total = int(sum_df["총티켓수"].sum()) if "총티켓수" in sum_df.columns else 0
                        _c_text = int(sum_df["글자티켓"].sum()) if "글자티켓" in sum_df.columns else 0
                        _c_img = int(sum_df["이미지티켓"].sum()) if "이미지티켓" in sum_df.columns else 0
                        _cm1, _cm2, _cm3, _cm4, _cm5 = st.columns(5)
                        _cm1.metric("참여자", f"{_c_people}명")
                        _cm2.metric("총 댓글", f"{_c_comments}개")
                        _cm3.metric("총 티켓", f"{_c_total:,}개")
                        _cm4.metric("글자 티켓", f"{_c_text:,}개")
                        _cm5.metric("이미지 티켓", f"{_c_img:,}개")
                        st.dataframe(
                            sum_df,
                            use_container_width=True,
                            hide_index=True,
                        )

                        sum_bytes = sum_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                        st.download_button(
                            "⬇️ 조건2 티켓 집계 다운로드",
                            data=sum_bytes,
                            file_name=f"event_comment_ticket_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
            elif not st.session_state.event_running:
                st.info("아직 자동 집계 결과가 없습니다. 댓글 수집을 완료하면 자동으로 표시됩니다.")
    except Exception as e:
        st.error(f"집계 오류: {e}")

