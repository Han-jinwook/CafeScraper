import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import os
import time
import random
import json
from pathlib import Path
from selenium.webdriver.common.by import By

from app.products.scraper.crawler import NaverCafeCrawler
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
from app.utils.streamlit_top_nav import (
    inject_settings_three_cards_css,
    render_main_top_nav,
    render_settings_card_title,
)


st.set_page_config(page_title="이벤트 댓글 수집", layout="wide")

st.markdown(
    """
    <style>
    /* 진행 중 '중단' 버튼을 빨간 톤으로 강조 */
    div[data-testid="stButton"] > button[kind="secondary"] {
        background-color: #d92d20 !important;
        border-color: #b42318 !important;
        color: #ffffff !important;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background-color: #b42318 !important;
        border-color: #912018 !important;
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_main_top_nav(active="event")

# 메인 크롤링 구동 중에는 다른 메뉴 작업을 잠시 차단
if st.session_state.get("crawl_running", False):
    st.warning("⚠️ 메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

inject_settings_three_cards_css(key_basename="event_settings_card")

CONFIG_PATH = str(get_config_path())
SAFE_DELAY_MIN_SEC = 2.5
SAFE_DELAY_MAX_SEC = 4.5
BACKOFF_STEP_MIN_SEC = 0.7
BACKOFF_STEP_MAX_SEC = 1.2
BACKOFF_MAX_MIN_SEC = 7.0
BACKOFF_MAX_MAX_SEC = 10.0
COPY_COMMENT_CHAR_BASE = 10


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
if "event_extracted_boards" not in st.session_state:
    _cfg_boards = config.get("event_extracted_boards", [])
    st.session_state.event_extracted_boards = _cfg_boards if isinstance(_cfg_boards, list) else []
if "event_selected_board_urls" not in st.session_state:
    _cfg_selected_urls = config.get("event_selected_board_urls", [])
    if isinstance(_cfg_selected_urls, list) and _cfg_selected_urls:
        st.session_state.event_selected_board_urls = [str(u).strip() for u in _cfg_selected_urls if str(u).strip()]
    else:
        st.session_state.event_selected_board_urls = [
            u.strip() for u in str(config.get("event_board_url", "") or "").splitlines() if u.strip()
        ]
if "event_selected_board_url" not in st.session_state:
    st.session_state.event_selected_board_url = (
        st.session_state.event_selected_board_urls[0]
        if st.session_state.event_selected_board_urls
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


def _build_final_summary_report(db_path: str) -> dict:
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

    def _base_coupon(chars: int) -> int:
        if chars <= 20:
            return 1
        if chars <= 60:
            return 2
        return 3

    df_sum_raw["base_coupon"] = df_sum_raw["effective_chars"].apply(lambda v: _base_coupon(int(v)))
    df_sum_raw["extra_coupon"] = (
        (df_sum_raw["emoji_count"] > 0) | (df_sum_raw["inline_image_count"] > 0)
    ).astype(int)
    df_sum_raw["coupon_per_comment"] = (df_sum_raw["base_coupon"] + df_sum_raw["extra_coupon"]).clip(upper=4)

    # 중복/복붙 보정: 같은 별명+같은 내용 그룹에서 첫 댓글(원문) 제외 나머지는 쿠폰 1개로 고정
    df_sum_raw["dup_idx"] = df_sum_raw.groupby(["nickname", "comment_content"]).cumcount()
    dup_group_size = df_sum_raw.groupby(["nickname", "comment_content"])["id"].transform("size")
    copy_mask = (dup_group_size > 1) & (df_sum_raw["dup_idx"] > 0)
    df_sum_raw.loc[copy_mask, "coupon_per_comment"] = 1

    sum_df = (
        df_sum_raw.groupby("nickname", as_index=False)
        .agg(
            comment_count=("id", "count"),
            coupon_1=("coupon_per_comment", lambda s: int((s == 1).sum())),
            coupon_2=("coupon_per_comment", lambda s: int((s == 2).sum())),
            coupon_3=("coupon_per_comment", lambda s: int((s == 3).sum())),
            coupon_4=("coupon_per_comment", lambda s: int((s == 4).sum())),
            total_coupon=("coupon_per_comment", "sum"),
        )
        .sort_values(["total_coupon", "comment_count"], ascending=[False, False])
    )
    return {"status": "data", "df": sum_df}


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


def _ensure_event_analysis_reports(*, force: bool = False) -> None:
    if st.session_state.get("event_running") or st.session_state.get("event_run_pending"):
        return

    current_sig = _get_event_db_signature(EVENT_DB_PATH)
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
    _hdr_logo, _hdr_mid = st.columns([0.55, 4.45], gap="small")
    with _hdr_logo:
        if _logo_path.exists():
            st.image(str(_logo_path), width=92)
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
_comment_search_default_end = _comment_default_end
if config.get("event_comment_search_start_date"):
    try:
        _comment_search_default_start = datetime.strptime(config["event_comment_search_start_date"], "%Y-%m-%d")
    except Exception:
        pass
if config.get("event_comment_search_end_date"):
    try:
        _comment_search_default_end = datetime.strptime(config["event_comment_search_end_date"], "%Y-%m-%d")
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

st.markdown("#### ⚙️ 수집 설정")
_ev1, _ev2, _ev3 = st.columns([1, 1, 1], gap="medium")
with _ev1:
    with st.container(border=True, key="event_settings_card_1", gap=None):
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
                st.session_state.event_auto_login_enabled_input = False
                st.session_state.event_naver_id_input = ""
                st.session_state.event_naver_pw_input = ""
            event_auto_login_enabled = st.checkbox(
                "브라우저 열 때 자동로그인 실행",
                value=bool(config.get("event_auto_login_enabled", False)),
                key="event_auto_login_enabled_input",
                help="이벤트 수집용 브라우저 열기 직후 저장된 계정으로 로그인을 시도합니다.",
            )
            _ev_al_input_col, _ev_al_btn_col = st.columns([4, 1], gap="small")
            with _ev_al_input_col:
                event_naver_id = st.text_input(
                    "네이버 아이디",
                    value=str(config.get("event_naver_id", "") or ""),
                    key="event_naver_id_input",
                    placeholder="아이디 입력",
                )
                event_naver_pw = st.text_input(
                    "네이버 비밀번호",
                    value=str(config.get("event_naver_pw", "") or ""),
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
                st.session_state.event_board_picker_version = int(st.session_state.get("event_board_picker_version", 0)) + 1
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
    with st.container(border=True, key="event_settings_card_2", gap=None):
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
        _exclude_post_count = len([x for x in _exclude_post_src.splitlines() if str(x).strip()])
        _exclude_comment_count = len([x for x in _exclude_comment_src.splitlines() if str(x).strip()])
        with st.expander(
            f"🚫 제외 설정 (게시글 {_exclude_post_count}명 · 댓글 {_exclude_comment_count}명)",
            expanded=False,
        ):
            _epc, _ecc = st.columns(2)
            with _epc:
                exclude_post_nicks_text = st.text_area(
                    "게시글 제외 별명 (줄바꿈 구분)",
                    value=config.get("event_exclude_post_nicks", "마법사멀린"),
                    height=90,
                    help="해당 별명이 작성한 게시글은 수집/분석 대상에서 제외합니다.",
                    key="event_exclude_post_nicks_text",
                )
            with _ecc:
                exclude_comment_nicks_text = st.text_area(
                    "댓글 제외 별명 (줄바꿈 구분)",
                    value=config.get("event_exclude_comment_nicks", config.get("event_exclude_nicks", "마법사멀린\n해나라")),
                    height=90,
                    help="해당 별명이 작성한 댓글은 저장/집계에서 제외합니다.",
                    key="event_exclude_comment_nicks_text",
                )
        with st.expander("🧩 수집 조건", expanded=False):
            _mode_options = ["조건1", "조건2"]
            _current_comment_enabled = bool(st.session_state.get("event_condition_comment_enabled", True))
            _current_mode_idx = 0 if _current_comment_enabled else 1
            selected_mode = st.radio(
                "실행 조건 선택 (하나만 선택)",
                _mode_options,
                index=_current_mode_idx,
                key="event_condition_mode_radio",
                horizontal=False,
                format_func=lambda x: "조건1. 댓글 수집·분석" if x == "조건1" else "조건2. 게시글 수집·분석",
            )
            cond1_checked = selected_mode == "조건1"
            cond2_checked = selected_mode == "조건2"
            st.session_state.event_condition_comment_enabled = bool(cond1_checked)
            st.session_state.event_condition_post_enabled = bool(cond2_checked)

            st.markdown("**조건1. 댓글 수집·분석**")
            st.caption("목표 기간(댓글 작성일 기준)")
            _c1t1, _c1t2 = st.columns(2)
            with _c1t1:
                comment_start_date = st.date_input(
                    "목표 시작일",
                    _comment_default_start,
                    key="event_comment_start_date_input",
                    disabled=not cond1_checked,
                )
            with _c1t2:
                comment_end_date = st.date_input(
                    "목표 종료일",
                    _comment_default_end,
                    key="event_comment_end_date_input",
                    disabled=not cond1_checked,
                )

            st.caption("탐색 기간(게시글 검색 범위)")
            _c1s1, _c1s2 = st.columns(2)
            with _c1s1:
                comment_search_start_date = st.date_input(
                    "탐색 시작일",
                    _comment_search_default_start,
                    key="event_comment_search_start_date_input",
                    disabled=not cond1_checked,
                )
            with _c1s2:
                comment_search_end_date = st.date_input(
                    "탐색 종료일",
                    _comment_search_default_end,
                    key="event_comment_search_end_date_input",
                    disabled=not cond1_checked,
                )

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            st.markdown("**조건2. 게시글 수집·분석**")
            _p1, _p2 = st.columns(2)
            with _p1:
                post_start_date = st.date_input(
                    "조건2 시작일",
                    _post_default_start,
                    key="event_post_start_date_input",
                    disabled=not cond2_checked,
                )
            with _p2:
                post_end_date = st.date_input(
                    "조건2 종료일",
                    _post_default_end,
                    key="event_post_end_date_input",
                    disabled=not cond2_checked,
                )
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        if st.button("💾 저장", width="stretch", key="event_save_settings_btn"):
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
            config["event_comment_search_end_date"] = comment_search_end_date.strftime("%Y-%m-%d")
            config["event_condition_post_enabled"] = bool(st.session_state.get("event_condition_post_enabled", False))
            config["event_post_start_date"] = post_start_date.strftime("%Y-%m-%d")
            config["event_post_end_date"] = post_end_date.strftime("%Y-%m-%d")
            config["event_max_posts"] = 0
            config["event_exclude_post_nicks"] = exclude_post_nicks_text
            config["event_exclude_comment_nicks"] = exclude_comment_nicks_text
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
            st.success("✅ 설정이 저장되었습니다.")
            time.sleep(1)
            st.rerun()

with _ev3:
    with st.container(border=True, key="event_settings_card_3", gap=None):
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
        if st.button("🗑️ 이벤트 DB 초기화", type="primary", width="stretch", key="reset_event_db_btn"):
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
comment_search_end_date = st.session_state.get("event_comment_search_end_date_input", _comment_search_default_end)
post_start_date = st.session_state.get("event_post_start_date_input", _post_default_start)
post_end_date = st.session_state.get("event_post_end_date_input", _post_default_end)

comment_start_dt = datetime.combine(comment_start_date, datetime.min.time())
comment_end_dt = datetime.combine(comment_end_date, datetime.max.time())
comment_search_start_dt = datetime.combine(comment_search_start_date, datetime.min.time())
comment_search_end_dt = datetime.combine(comment_search_end_date, datetime.max.time())

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
event_step2_ready = bool(event_browser_opened and str(board_url or "").strip() and event_any_condition_enabled)

with step_col1:
    if st.button(
        "1단계: 브라우저 열기",
        width="stretch",
        disabled=bool(st.session_state.event_running) or event_browser_opened,
        type="primary" if not event_browser_opened else "secondary",
        key="event_open_browser_btn",
    ):
        if not st.session_state.event_crawler:
            st.session_state.event_crawler = NaverCafeCrawler("", debug_mode=False)
            st.session_state.event_crawler.set_status_callback(update_logs)
        st.session_state.event_crawler.start_browser()
        update_logs("✅ 브라우저가 열렸습니다. 로그인 후 2단계를 진행하세요.")
        st.rerun()

with step_col_login:
    st.empty()

with step_col2:
    if st.session_state.event_running:
        _run_btn_col, _stop_btn_col = st.columns([4.5, 1.5], gap="small")
        with _run_btn_col:
            st.button(
                "2단계: 댓글 수집·분석 진행 중...",
                type="primary",
                width="stretch",
                disabled=False,
                key="event_running_btn",
            )
        with _stop_btn_col:
            if st.button("중단", type="secondary", width="stretch", key="event_stop_btn"):
                st.session_state.event_stop_requested = True
                update_logs("🛑 중단 요청을 받았습니다. 현재 처리 단위 완료 후 중단합니다.")
    else:
        if st.button(
            "2단계: 댓글 수집·분석 시작",
            type="primary",
            width="stretch",
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

if st.session_state.event_running:
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

    prog = st.progress(max(0.0, min(1.0, float(st.session_state.get("event_progress_ratio", 0.0) or 0.0))))
    prog_msg = st.empty()

    def _set_event_progress(ratio: float, msg: str) -> None:
        rr = max(0.0, min(1.0, float(ratio)))
        st.session_state.event_progress_ratio = rr
        st.session_state.event_progress_label = str(msg or "")
        prog.progress(rr)
        prog_msg.caption(str(msg or ""))

    try:
        update_logs("🔍 선택한 조건 실행 시작...")
        inserted_total = 0
        comments_seen_total = 0
        excluded_total = 0
        excluded_post_total = 0
        unknown_date_excluded_total = 0
        failed_articles = 0
        total_articles_processed = 0
        post_analysis_saved_total = 0
        def _norm_nick(v: str) -> str:
            return "".join(str(v or "").strip().lower().split())

        exclude_post_set = {_norm_nick(x) for x in exclude_post_nicks_raw.splitlines() if str(x).strip()}
        exclude_comment_set = {_norm_nick(x) for x in exclude_comment_nicks_raw.splitlines() if str(x).strip()}
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
                if not comment_enabled:
                    save_event_post(
                        EVENT_DB_PATH,
                        art,
                        comments_seen=0,
                        comments_saved=0,
                        comments_excluded=0,
                        author_nickname=list_author_nick,
                    )

                title = (art.get("title") or "")[:30]
                update_logs(f"💬 ({i+1}/{len(articles)}) '{title}...' 댓글 조회 중")
                try:
                    if comment_enabled:
                        comments = st.session_state.event_crawler.get_all_comments_for_article(art.get("url") or "")
                        raw_comments_count = len(comments)
                        target_window_comments = []

                        filtered = []
                        for c in comments:
                            cdt = _parse_comment_date(str(c.get("date") or ""))
                            if cdt is None:
                                # 조건1은 목표기간 엄격 적용: 날짜 미확인은 제외
                                unknown_date_excluded_total += 1
                                continue
                            if not (comment_target_start_dt <= cdt <= comment_target_end_dt):
                                continue
                            target_window_comments.append(c)
                            nn = str(c.get("nickname") or "").strip()
                            if nn and _norm_nick(nn) in exclude_comment_set:
                                excluded_total += 1
                                continue
                            filtered.append(c)

                        comments_seen_total += raw_comments_count

                        ins = save_event_comments(EVENT_DB_PATH, art, filtered)
                        excluded_now = len(target_window_comments) - len(filtered)
                        inserted_total += ins
                        if len(target_window_comments) > 0:
                            save_event_post(
                                EVENT_DB_PATH,
                                art,
                                comments_seen=len(target_window_comments),
                                comments_saved=ins,
                                comments_excluded=excluded_now,
                                author_nickname=list_author_nick,
                            )

                        stable_success_streak += 1
                        if stable_success_streak >= 5:
                            adaptive_delay_min = max(SAFE_DELAY_MIN_SEC, adaptive_delay_min - 0.4)
                            adaptive_delay_max = max(SAFE_DELAY_MAX_SEC, adaptive_delay_max - 0.6)
                            stable_success_streak = 0

                        update_logs(
                            f"✅ 댓글 전체 {raw_comments_count:,}개 중 목표기간 {len(target_window_comments):,}개 / "
                            f"제외 {excluded_now:,}개 / 신규 저장 {ins:,}개 (누적 신규 {inserted_total:,})"
                        )
                    else:
                        # 댓글 조건 미선택일 때도 게시글 메타는 보존
                        save_event_post(
                            EVENT_DB_PATH,
                            art,
                            comments_seen=0,
                            comments_saved=0,
                            comments_excluded=0,
                            author_nickname=list_author_nick,
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
                    update_logs(
                        f"⚠️ 댓글 조회/저장 실패: {title}... ({e}) "
                        f"→ 대기 {adaptive_delay_min:.1f}~{adaptive_delay_max:.1f}초로 상향"
                    )

                if adaptive_delay_max < adaptive_delay_min:
                    adaptive_delay_min, adaptive_delay_max = adaptive_delay_max, adaptive_delay_min
                time.sleep(random.uniform(adaptive_delay_min, adaptive_delay_max))

        done_msg = (
            f"✅ 완료: 게시판 {len(board_urls):,}개, 게시글 {total_articles_processed:,}개 처리, "
            f"게시글 제외 {excluded_post_total:,}개, 댓글 조회 {comments_seen_total:,}개, 댓글 제외 {excluded_total:,}개, "
            f"날짜 미확인 제외 {unknown_date_excluded_total:,}개, "
            f"신규 저장 {inserted_total:,}개, 게시글 분석 저장 {post_analysis_saved_total:,}개, 실패 {failed_articles:,}개"
        )
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
st.caption(
    f"🏷️ 제외 설정 적용 중 · 게시글 제외 별명 {_badge_post_count}명 · 댓글 제외 별명 {_badge_comment_count}명"
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
            ec.comment_nickname,
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
            width="stretch",
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
            width="stretch",
        )

except Exception as e:
    st.error(f"DB 조회 오류: {e}")

# -----------------------------------------------------------------------------
# Post Analysis Section (Condition 2)
# -----------------------------------------------------------------------------
st.markdown("### 📝 조건2 게시글 수집·분석 결과")
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
        st.info("조건2 게시글 분석 결과가 없습니다.")
    else:
        st.dataframe(
            df_post,
            width="stretch",
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
except Exception as e:
    st.error(f"조건2 결과 조회 오류: {e}")


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
    st.markdown("### 2. 최종 집계 (참여자 랭킹)")
    try:
        _sum_indent_col, _sum_body_col = st.columns([0.05, 0.95])
        with _sum_body_col:
            st.caption(
                "쿠폰 산정 규칙: 글자수 20자 이하=쿠폰 1개, 21~60자=쿠폰 2개, 61자 이상=쿠폰 3개, "
                "아이콘 또는 사진이 1개라도 있으면 +1개(최대 4개)."
            )

            final_summary_report = st.session_state.get("event_final_summary_report")
            if final_summary_report:
                if str(final_summary_report.get("status") or "") == "empty":
                    st.info("아직 집계할 데이터가 없습니다.")
                elif str(final_summary_report.get("status") or "") == "data":
                    sum_df = final_summary_report.get("df")
                    if isinstance(sum_df, pd.DataFrame) and not sum_df.empty:
                        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
                        st.dataframe(
                            sum_df,
                            width="stretch",
                            hide_index=True,
                            column_config={
                                "nickname": "별명",
                                "comment_count": st.column_config.NumberColumn("댓글수", format="%d개"),
                                "coupon_1": st.column_config.NumberColumn("쿠폰 1개", format="%d개"),
                                "coupon_2": st.column_config.NumberColumn("쿠폰 2개", format="%d개"),
                                "coupon_3": st.column_config.NumberColumn("쿠폰 3개", format="%d개"),
                                "coupon_4": st.column_config.NumberColumn("쿠폰 4개", format="%d개"),
                                "total_coupon": st.column_config.NumberColumn("총 쿠폰수", format="%d개"),
                            },
                        )

                        sum_bytes = sum_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                        st.download_button(
                            "⬇️ 랭킹 리포트 다운로드",
                            data=sum_bytes,
                            file_name=f"event_ranking_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            width="stretch",
                        )
            elif not st.session_state.event_running:
                st.info("아직 자동 집계 결과가 없습니다. 댓글 수집을 완료하면 자동으로 표시됩니다.")
    except Exception as e:
        st.error(f"집계 오류: {e}")
