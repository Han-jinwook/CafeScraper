import streamlit as st
import pandas as pd
import os
import time
import json
import re
import traceback
import html
from datetime import datetime, timedelta
from pathlib import Path

from selenium.webdriver.common.by import By

from app.products.commenter.bot import NaverCafeCommenter
from app.utils.paths import get_config_path, resolve_commenter_db_path
from app.utils.event_db import (
    init_event_db,
    load_commenter_targets,
    replace_commenter_targets,
    update_commenter_target_comment_status,
    clear_commenter_targets,
)
from app.utils.streamlit_brand import render_logo_png
from app.utils.streamlit_input_history import inject_connect_history_suggestions
from app.utils.streamlit_top_nav import (
    inject_settings_three_cards_css,
    render_main_top_nav,
    render_settings_card_title,
)
from app.utils.naver_login import auto_login_naver_with_js

st.set_page_config(page_title="댓글 자동화 - CafeScraper", layout="wide")

render_main_top_nav(active="commenter")

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
        padding-bottom: 2.25rem !important;
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


config = load_config()
COMMENTER_DB_PATH = str(resolve_commenter_db_path(config.get("commenter_db_path")))
init_event_db(COMMENTER_DB_PATH)

# 댓글 작업 시 글과 글 사이 **추가** 대기(초) — 이보다 짧게는 UI에서 설정 불가
COMMENTER_GAP_MIN_SEC = 60

TEMPLATES_FILE = "comment_templates.json"

# ----- 이벤트 페이지와 동일한 event_* 세션 키 (카페·게시판 설정 공유) -----
if "event_crawler" not in st.session_state:
    st.session_state.event_crawler = None
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
if "event_selected_board_urls" not in st.session_state or not st.session_state.get(
    "event_selected_board_urls"
):
    _cfg_selected_urls = config.get("event_selected_board_urls", [])
    if isinstance(_cfg_selected_urls, list) and _cfg_selected_urls:
        st.session_state.event_selected_board_urls = [
            str(u).strip() for u in _cfg_selected_urls if str(u).strip()
        ]
    elif "event_selected_board_urls" not in st.session_state:
        st.session_state.event_selected_board_urls = [
            u.strip() for u in str(config.get("event_board_url", "") or "").splitlines() if u.strip()
        ]
if "event_selected_board_url" not in st.session_state or not st.session_state.get(
    "event_selected_board_url"
):
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
if "commenter_gap_sec_input" not in st.session_state:
    try:
        _g0 = int(config.get("commenter_between_posts_sec", COMMENTER_GAP_MIN_SEC))
    except (TypeError, ValueError):
        _g0 = COMMENTER_GAP_MIN_SEC
    st.session_state.commenter_gap_sec_input = max(COMMENTER_GAP_MIN_SEC, _g0)


def _commenter_ensure_comment_cols(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        return
    if "comment_status" not in df.columns:
        df["comment_status"] = ""
    if "comment_detail" not in df.columns:
        df["comment_detail"] = ""
    df["comment_status"] = df["comment_status"].fillna("").astype(str)
    df["comment_detail"] = df["comment_detail"].fillna("").astype(str)


def _commenter_apply_comment_result(url: str, status: str, detail: str) -> None:
    detail = (detail or "")[:500]
    status = str(status or "")
    u = str(url).strip()
    for _key in ("target_df", "commenter_target_df_full"):
        _df = st.session_state.get(_key)
        if _df is None or getattr(_df, "empty", True):
            continue
        _commenter_ensure_comment_cols(_df)
        if "url" not in _df.columns:
            continue
        _m = _df["url"].astype(str) == u
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


if st.session_state.target_df is None:
    try:
        _snap_rows = load_commenter_targets(COMMENTER_DB_PATH)
        if _snap_rows:
            _td = pd.DataFrame(_snap_rows)
            _commenter_ensure_comment_cols(_td)
            st.session_state.target_df = _td
            st.session_state.commenter_target_df_full = _td.copy()
    except Exception:
        pass
else:
    if st.session_state.commenter_target_df_full is None and st.session_state.target_df is not None:
        try:
            _commenter_ensure_comment_cols(st.session_state.target_df)
            st.session_state.commenter_target_df_full = st.session_state.target_df.copy()
        except Exception:
            pass


def _inject_commenter_cafe_history_suggestions(cafe_names: list[str], cafe_urls: list[str]) -> None:
    inject_connect_history_suggestions(
        prefix="event",
        container_key_fragment="commenter_settings_card_1",
        cafe_names=cafe_names,
        cafe_urls=cafe_urls,
    )


def _event_overall_url_from_boards(boards: list) -> str:
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


def load_templates():
    default_templates = [
        "안녕하세요 {닉네임}님! 좋은 글 잘 보고 갑니다 ^^",
        "{닉네임}님, 저도 비슷한 고민이 있었는데 도움 되네요.",
        "반갑습니다 {닉네임}님! 혹시 실례가 안된다면 질문 드려도 될까요?",
        "(직접 입력)",
    ]
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                return saved + default_templates
        except Exception:
            pass
    return default_templates


def save_new_template(content):
    if not content or content.strip() == "":
        return
    current = []
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                current = json.load(f)
        except Exception:
            pass
    if content not in current:
        current.insert(0, content)
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)


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
    boards = st.session_state.get("event_extracted_boards") or []
    needle = str(board_url).strip()
    for b in boards:
        if str((b or {}).get("url") or "").strip() == needle:
            return str((b or {}).get("name") or "").strip()
    return ""


def _collect_commenter_targets_into_session() -> None:
    try:
        crw = st.session_state.commenter
        if not crw or not getattr(crw, "driver", None):
            st.warning("먼저 **1단계: 브라우저 열기**를 해주세요.")
            return
        board_urls = list(
            dict.fromkeys(
                [
                    str(u).strip()
                    for u in (st.session_state.get("event_selected_board_urls") or [])
                    if str(u).strip()
                ]
            )
        )
        if not board_urls:
            st.warning("왼쪽에서 **게시판을 선택**해주세요.")
            return
        _start_d, _end_d = _commenter_normalized_target_range()
        if _start_d is None:
            st.warning("수집 기간을 확인해주세요.")
            return
        exclude_keyword = str(st.session_state.get("commenter_exclude_nicks", "") or "")
        start_dt = datetime.combine(_start_d, datetime.min.time())
        end_dt = datetime.combine(_end_d, datetime.max.time())
        by_url: dict[str, dict] = {}
        prog = st.progress(0.0)
        status_ph = st.empty()
        for b_idx, board_url_each in enumerate(board_urls, start=1):
            status_ph.text(f"게시판 {b_idx}/{len(board_urls)} 목록 수집 중…")
            prog.progress((b_idx - 1) / max(1, len(board_urls)))
            articles: list = []
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
                    board_name = _commenter_board_label_for_url(board_url_each)
                if crw._is_noise_board_label(board_name):
                    board_name = ""
                nickname = str(art.get("nickname") or "").strip() or "unknown"
                member_id = str(art.get("member_id") or "").strip() or "unknown"
                need_detail = (nickname == "unknown") or (not board_name)
                if need_detail:
                    try:
                        detail = crw.scrape_article_detail(
                            u,
                            member_id,
                            admin_nicks=[],
                            comment_mode="none",
                        )
                        if detail:
                            dn = str(detail.get("nickname") or "").strip()
                            if dn and dn != "unknown":
                                nickname = dn
                            dbn = str(detail.get("board_name") or "").strip()
                            if dbn and not crw._is_noise_board_label(dbn):
                                board_name = dbn
                    except Exception:
                        pass
                if crw._is_noise_board_label(board_name):
                    board_name = _commenter_board_label_for_url(board_url_each) or ""
                by_url[u] = {
                    "post_id": art.get("post_id", ""),
                    "nickname": nickname,
                    "title": art.get("title", ""),
                    "date": art.get("date", ""),
                    "url": u,
                    "board_name": board_name,
                }
        prog.progress(1.0)
        status_ph.empty()
        df = pd.DataFrame(list(by_url.values()))
        if not df.empty:
            df["_sort_d"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("_sort_d", ascending=False).drop(columns=["_sort_d"])
        excludes = [x.strip() for x in exclude_keyword.split(",") if x.strip()]
        if excludes and not df.empty:
            mask = df["nickname"].apply(lambda x: not any(exc in str(x) for exc in excludes))
            df = df[mask]
        _commenter_ensure_comment_cols(df)
        st.session_state.target_df = df
        st.session_state.commenter_target_df_full = df.copy()
        try:
            replace_commenter_targets(
                COMMENTER_DB_PATH, df.to_dict("records") if not df.empty else []
            )
        except Exception:
            pass
        if df.empty:
            st.warning("선택한 기간·게시판에서 수집된 글이 없습니다.")
        else:
            st.success(f"{len(df)}건 수집 완료")
    except Exception as e:
        ph = locals().get("status_ph")
        if ph is not None:
            try:
                ph.empty()
            except Exception:
                pass
        st.error(f"수집 실패: {e}")
    finally:
        st.session_state.commenter_collecting = False


def _render_commenter_dashboard_header() -> None:
    _logo_path = Path(__file__).resolve().parent.parent / "assets" / "CafeMonster_logo.png"
    _hdr_logo, _hdr_mid = st.columns([1, 5], gap="small")
    with _hdr_logo:
        render_logo_png(_logo_path, width_px=92)
    with _hdr_mid:
        _title_col, _guide_col = st.columns([1.95, 2.05], gap="small")
        with _title_col:
            st.markdown(
                '<h2 style="margin:0 0 0.15rem 0;padding:0;line-height:1.2;font-size:1.35rem;">'
                "자동 댓글러</h2>",
                unsafe_allow_html=True,
            )
        with _guide_col:
            with st.expander("📖 사용 가이드 (필독)", expanded=False):
                st.markdown(
                    f"""
                타겟 글은 **브라우저로 게시판 목록을 직접 스크랩**합니다. (`event_posts` 조회 없음)

                1. **카페 · 연결**: 카페 URL·자동로그인·게시판 목록·게시판 선택.
                2. **타겟 수집 설정**: 수집 기간·제외 닉네임 → **💾 저장**.
                3. **실행 제어**(설정 아래): 1단계(브라우저) → 2단계(목록 수집) → **데이터 관리**에서 현황 확인.
                4. **댓글 · 실행**: 글 사이 **추가 대기(초)** — 최소 {COMMENTER_GAP_MIN_SEC}초, 템플릿 → **댓글 작성 시작**.

                메인 카페 크롤링이 실행 중이면 이 화면을 사용할 수 없습니다.
                    """
                )


_render_commenter_dashboard_header()

st.markdown("#### ⚙️ 설정")
_col1, _col2, _col3 = st.columns([1, 1, 1], gap="medium")

with _col1:
    with st.container(border=True, key="commenter_settings_card_1"):
        render_settings_card_title("카페 · 연결", icon="🏪")
        if st.session_state.pop("_event_pending_clear_cafe_name_input", False):
            st.session_state.event_cafe_name_input = ""
        st.text_input("카페명", key="event_cafe_name_input")
        try:
            _ev_url_col, _ev_btn_col = st.columns([5, 1], gap="small", vertical_alignment="center")
        except TypeError:
            _ev_url_col, _ev_btn_col = st.columns([5, 1], gap="small")
        with _ev_url_col:
            if st.session_state.pop("_event_pending_clear_cafe_url_input", False):
                st.session_state.event_cafe_url_input = ""
            cafe_url = st.text_input("카페 URL", key="event_cafe_url_input")
        _inject_commenter_cafe_history_suggestions(
            (config.get("event_cafe_name_history", []) or []) + [str(config.get("event_cafe_name", "") or "")],
            (config.get("event_cafe_url_history", []) or []) + [str(config.get("event_cafe_url", "") or "")],
        )
        with _ev_btn_col:
            _ev_save_mode = bool(st.session_state.get("event_cafe_url_after_reset_save_mode", False))
            _ev_side_lbl = "저장" if _ev_save_mode else "리셋"
            _ev_side_help = (
                "카페명/카페 URL을 이벤트(자동댓글러) 설정에 저장합니다."
                if _ev_save_mode
                else "이벤트 게시판 목록/선택 데이터를 비웁니다."
            )
            if st.button(
                _ev_side_lbl,
                key="commenter_event_cafe_side_btn",
                use_container_width=True,
                help=_ev_side_help,
                disabled=_commenter_ui_busy(),
            ):
                if _ev_save_mode:
                    cfg_now = dict(load_config() or {})
                    saved_event_cafe_name = str(st.session_state.get("event_cafe_name_input", "") or "").strip()
                    saved_event_cafe_url = str(st.session_state.get("event_cafe_url_input", "") or "").strip()
                    cfg_now["event_cafe_name"] = saved_event_cafe_name
                    cfg_now["event_cafe_url"] = saved_event_cafe_url
                    if saved_event_cafe_name:
                        prev_event_name_hist = [
                            str(x).strip()
                            for x in (cfg_now.get("event_cafe_name_history", []) or [])
                            if str(x).strip()
                        ]
                        cfg_now["event_cafe_name_history"] = (
                            [saved_event_cafe_name]
                            + [x for x in prev_event_name_hist if x != saved_event_cafe_name]
                        )[:20]
                    if saved_event_cafe_url:
                        prev_event_url_hist = [
                            str(x).strip()
                            for x in (cfg_now.get("event_cafe_url_history", []) or [])
                            if str(x).strip()
                        ]
                        cfg_now["event_cafe_url_history"] = (
                            [saved_event_cafe_url]
                            + [x for x in prev_event_url_hist if x != saved_event_cafe_url]
                        )[:20]
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
            st.success(
                "카페 관련 데이터를 비웠고 카페명/카페 URL 칸을 비웠습니다. 새 값을 입력 후 오른쪽 저장을 눌러주세요."
            )
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
                st.session_state.event_auto_login_enabled_input = bool(
                    config.get("event_auto_login_enabled", False)
                )
            st.checkbox(
                "브라우저 열 때 자동로그인 실행",
                key="event_auto_login_enabled_input",
                help="브라우저 열기 직후 저장된 계정으로 로그인을 시도합니다.",
            )
            _ev_al_input_col, _ev_al_btn_col = st.columns([4, 1], gap="small")
            with _ev_al_input_col:
                if "event_naver_id_input" not in st.session_state:
                    st.session_state.event_naver_id_input = str(config.get("event_naver_id", "") or "")
                if "event_naver_pw_input" not in st.session_state:
                    st.session_state.event_naver_pw_input = str(config.get("event_naver_pw", "") or "")
                st.text_input("네이버 아이디", key="event_naver_id_input", placeholder="아이디 입력")
                st.text_input(
                    "네이버 비밀번호",
                    key="event_naver_pw_input",
                    type="password",
                    placeholder="비밀번호 입력",
                )
            with _ev_al_btn_col:
                st.markdown("<div style='margin-top: 88px;'></div>", unsafe_allow_html=True)
                _ev_al_save_mode = bool(st.session_state.get("event_auto_login_after_reset_save_mode", False))
                _ev_al_lbl = "저장" if _ev_al_save_mode else "리셋"
                if st.button(
                    _ev_al_lbl,
                    key="commenter_event_auto_login_side_btn",
                    use_container_width=True,
                    disabled=_commenter_ui_busy(),
                ):
                    if _ev_al_save_mode:
                        cfg_now = dict(load_config() or {})
                        cfg_now["event_auto_login_enabled"] = bool(
                            st.session_state.get("event_auto_login_enabled_input", False)
                        )
                        cfg_now["event_naver_id"] = str(
                            st.session_state.get("event_naver_id_input", "") or ""
                        ).strip()
                        cfg_now["event_naver_pw"] = str(
                            st.session_state.get("event_naver_pw_input", "") or ""
                        )
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

        if st.button(
            "🔍 게시판 목록 가져오기",
            key="commenter_event_scan_boards_btn",
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
                        st.session_state.event_extracted_boards = boards
                        st.session_state.event_selected_board_urls = []
                        st.session_state.event_selected_board_url = ""
                        st.session_state.event_board_picker_version = int(
                            st.session_state.get("event_board_picker_version", 0)
                        ) + 1
                        cfg_now = dict(load_config() or {})
                        cfg_now["event_extracted_boards"] = boards
                        cfg_now["event_selected_board_urls"] = []
                        cfg_now["event_board_url"] = ""
                        save_config(cfg_now)
                        config.update(cfg_now)
                        st.success(f"✅ 게시판 스캔 완료: {len(boards)}개")
                    else:
                        st.warning("게시판을 찾지 못했습니다. 카페 메인/메뉴가 보이는 화면에서 다시 시도해주세요.")
                except Exception as e:
                    st.error(f"게시판 목록 스캔 실패: {e}")

        if st.session_state.event_extracted_boards:
            total_board_count = len(st.session_state.event_extracted_boards)
            selected_count_header = st.empty()
            _selected_now = len(
                list(
                    dict.fromkeys(
                        [u for u in (st.session_state.get("event_selected_board_urls", []) or []) if u]
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
            options = st.session_state.event_extracted_boards
            board_options: dict[str, str] = {}
            for i, b in enumerate(options, start=1):
                name = str((b or {}).get("name", "") or "").strip() or f"게시판_{i}"
                url = str((b or {}).get("url", "") or "").strip()
                board_options[f"{i:02d}. {name}"] = url

            overall_url = _event_overall_url_from_boards(options)

            options_list: list[str] = []
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
                        [
                            str(u).strip()
                            for u in (st.session_state.get("event_selected_board_urls", []) or [])
                            if str(u).strip()
                        ]
                    )
                )
                _preserved = [u for u in _existing_selected if u in _available_set]
                st.session_state.event_selected_board_urls = _preserved
                st.session_state.event_selected_board_url = _preserved[0] if _preserved else ""
                _preserved_set = set(_preserved)
                for _lb in options_list:
                    _idx = options_list.index(_lb)
                    _u = overall_url if _lb == "00. 전체글보기" else board_options.get(_lb, "")
                    if _u:
                        st.session_state[f"event_board_chk_{_new_version}_{_idx}"] = bool(_u in _preserved_set)

            label_to_url: dict[str, str] = {}
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
                            st.checkbox(label, key=chk_key, disabled=disable_this)
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
                        st.checkbox(label, key=chk_key, disabled=disable_this)

                selected_urls: list[str] = []
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
                st.session_state.event_selected_board_url = (
                    selected_urls_dedup[0] if selected_urls_dedup else ""
                )

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
            try:
                _gap_save = int(st.session_state.get("commenter_gap_sec_input", COMMENTER_GAP_MIN_SEC))
            except (TypeError, ValueError):
                _gap_save = COMMENTER_GAP_MIN_SEC
            cfg_now["commenter_between_posts_sec"] = max(COMMENTER_GAP_MIN_SEC, _gap_save)
            save_config(cfg_now)
            config.update(cfg_now)
            st.success("✅ 타겟 수집 설정이 저장되었습니다.")
            time.sleep(1)
            st.rerun()

with _col3:
    with st.container(border=True, key="commenter_settings_card_3"):
        render_settings_card_title("댓글 · 실행", icon="💬")
        st.session_state.template_list = load_templates()
        selected_template = st.selectbox(
            "템플릿", st.session_state.template_list, label_visibility="collapsed"
        )
        with st.expander("⚙️ 댓글 설정 접기/펼치기", expanded=True):
            default_text = "" if selected_template == "(직접 입력)" else selected_template
            final_template = st.text_area(
                "댓글 내용 입력",
                value=default_text,
                height=170,
                help="{닉네임}, {제목} 치환 가능",
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
            st.number_input(
                f"글 사이 추가 대기 (초, 최소 {COMMENTER_GAP_MIN_SEC})",
                min_value=COMMENTER_GAP_MIN_SEC,
                step=5,
                format="%d",
                key="commenter_gap_sec_input",
                help=(
                    "한 글에 댓글을 단 뒤 **다음 글로 가기 전**에만 추가로 쉬는 시간입니다. "
                    "글 열기·댓글 입력·등록 버튼 후 대기는 `write_comment` 안에서 별도로 둡니다. "
                    f"차단 완화를 위해 **{COMMENTER_GAP_MIN_SEC}초 미만은 선택할 수 없습니다.** "
                    "실제 대기 시간은 입력값을 중심으로 **±10초 범위에서 무작위**로 정해집니다."
                ),
            )
            st.caption(
                f"기본·하한 **{COMMENTER_GAP_MIN_SEC}초** — 더 짧게는 불가, 길게만 가능. "
                "실제 간격은 ±10초 랜덤. 값은 가운데 **💾 저장**에 포함됩니다."
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
                    sample_nick = "홍길동"
                    sample_title = "게시글 제목 예시"
                    if st.session_state.target_df is not None and not st.session_state.target_df.empty:
                        sample_nick = st.session_state.target_df.iloc[0]["nickname"]
                        sample_title = st.session_state.target_df.iloc[0]["title"]

                    preview_text = final_template.replace("{닉네임}", str(sample_nick)).replace(
                        "{제목}", str(sample_title)
                    )
                    _nick_h = html.escape(str(sample_nick))
                    _body_h = html.escape(str(preview_text))
                    st.markdown(
                        f'<div style="padding:0.65rem 0.85rem;background:#e8f4fc;border-radius:0.45rem;'
                        f'font-size:0.95rem;line-height:1.5;border-left:4px solid #2196f3;">'
                        f"<strong>To. {_nick_h}</strong>: {_body_h}</div>",
                        unsafe_allow_html=True,
                    )
                elif _show_preview:
                    st.caption("작업 진행 중에는 미리보기를 잠시 숨깁니다.")

# 실제 write_comment 루프는 파일 하단(표·메트릭 아래)에서 실행 →
# 여기서 먼저 표가 그려지므로 직전까지 댓글결과가 보입니다.
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
if st.session_state.get("is_running", False):
    st.info("현재 단계: 댓글 작성 중 — 중지는 오른쪽 카드의 **⏹ 댓글 작성 중지** 버튼")
elif st.session_state.get("commenter_collecting", False):
    st.info("현재 단계: 타겟 수집 중 — 수집 완료 후 댓글 작성 시작이 자동으로 활성화됩니다.")
elif not commenter_browser_opened:
    st.info("현재 단계: 대기 — **1단계 브라우저 열기**부터 진행하세요.")
elif not _has_targets_now:
    st.info("현재 단계: 브라우저 준비 완료 — 다음은 **2단계: 타겟 목록 수집**입니다.")
else:
    st.success("현재 단계: 작성 준비 완료 — 템플릿 확인 후 **🚀 댓글 작성 시작**을 누르세요.")
with st.container(key="commenter_exec_btns"):
    if st.session_state.pop("_commenter_run_collect", False):
        if st.session_state.get("is_running", False):
            # 댓글 작업 중에는 수집을 시작하지 않도록 강제 차단 (로그 뒤죽박죽 방지)
            st.session_state.commenter_collecting = False
            st.warning("댓글 작업 진행 중에는 2단계 수집을 시작할 수 없습니다.")
        else:
            _collect_commenter_targets_into_session()
            # 실행 제어 영역이 화면 하단에 있어, 수집 완료 후 위쪽 카드(댓글 시작 버튼)가
            # 같은 런에서 이전 상태로 남을 수 있으므로 한 번 더 rerun으로 동기화.
            st.rerun()
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
                        "event_auto_login_enabled_input", config.get("event_auto_login_enabled", False)
                    )
                )
                _ev_login_id = str(
                    st.session_state.get("event_naver_id_input", config.get("event_naver_id", "")) or ""
                ).strip()
                _ev_login_pw = str(
                    st.session_state.get("event_naver_pw_input", config.get("event_naver_pw", "")) or ""
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
        if st.button(
            "2단계: 타겟 목록 수집",
            use_container_width=True,
            disabled=not commenter_browser_opened
            or st.session_state.get("commenter_collecting", False)
            or st.session_state.get("is_running", False),
            type="primary" if commenter_browser_opened else "secondary",
            key="commenter_target_collect_step2_btn",
        ):
            st.session_state.commenter_collecting = True
            st.session_state._commenter_run_collect = True
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
_n_boards_dm = len(st.session_state.get("event_selected_board_urls") or [])
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
with st.container(border=True):
    st.caption(f"DB: `{COMMENTER_DB_PATH}`")
    st.markdown(
        '<p style="margin:0 0 0.35rem 0;font-size:1.05rem;font-weight:600;">📋 타겟 목록</p>',
        unsafe_allow_html=True,
    )
    _fb1, _fb2 = st.columns(2, gap="small")
    with _fb1:
        if st.button(
            "🔁 실패만 재시도 대상으로",
            use_container_width=True,
            key="commenter_filter_failed_only_btn",
            help="comment_status가 fail인 행만 남기고 댓글 작성 시작 시 그 글만 순회합니다.",
            disabled=_commenter_ui_busy(),
        ):
            _fbase = _commenter_full_dataframe()
            if _fbase is None or _fbase.empty:
                st.warning("목록이 없습니다.")
            else:
                _commenter_ensure_comment_cols(_fbase)
                _only_f = _fbase[
                    _fbase["comment_status"].fillna("").astype(str).str.strip().str.lower()
                    == "fail"
                ].copy()
                if _only_f.empty:
                    st.info("실패(fail)로 기록된 행이 없습니다.")
                else:
                    st.session_state.target_df = _only_f
                    st.success(f"재시도 대상 **{len(_only_f)}**건으로 제한했습니다. 댓글 작성 시작을 누르세요.")
                    st.rerun()
    with _fb2:
        if st.button(
            "📋 전체 목록 다시 보기",
            use_container_width=True,
            key="commenter_restore_full_targets_btn",
            disabled=_commenter_ui_busy(),
        ):
            _full = st.session_state.get("commenter_target_df_full")
            if _full is not None and not _full.empty:
                _commenter_ensure_comment_cols(_full)
                st.session_state.target_df = _full.copy()
                st.rerun()
            else:
                try:
                    _rows_restore = load_commenter_targets(COMMENTER_DB_PATH)
                    if _rows_restore:
                        _tdr = pd.DataFrame(_rows_restore)
                        _commenter_ensure_comment_cols(_tdr)
                        st.session_state.commenter_target_df_full = _tdr.copy()
                        st.session_state.target_df = _tdr.copy()
                        st.rerun()
                    else:
                        st.info("DB에 저장된 타겟이 없습니다.")
                except Exception as _e_restore:
                    st.warning(f"목록 복원 실패: {_e_restore}")

    if st.session_state.target_df is not None and not st.session_state.target_df.empty:
        _commenter_ensure_comment_cols(st.session_state.target_df)
        _show_df = st.session_state.target_df
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
                st.success("작업 완료!")
                st.balloons()
                _commenter_reset_run_state()
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
                        f"[{idx + 1}/{total}] '{row['title']}' ({row.get('nickname')}) 방문 중..."
                    )
                    res = st.session_state.commenter.write_comment(
                        article_url=row["url"],
                        template=_tpl,
                        nickname=str(row.get("nickname") or ""),
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
                    else:
                        log_msg(f"❌ 실패: {res['message']}")
                    st.session_state.commenter_run_index = idx + 1
                    if idx + 1 >= total:
                        st.success("작업 완료!")
                        st.balloons()
                        _commenter_reset_run_state()
                    else:
                        try:
                            _gap_run = float(
                                st.session_state.get(
                                    "commenter_gap_sec_input", COMMENTER_GAP_MIN_SEC
                                )
                            )
                        except (TypeError, ValueError):
                            _gap_run = float(COMMENTER_GAP_MIN_SEC)
                        st.session_state.commenter.human_sleep_between(
                            max(COMMENTER_GAP_MIN_SEC, _gap_run)
                        )
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
