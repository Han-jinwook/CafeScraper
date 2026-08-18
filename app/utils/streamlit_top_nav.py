# -*- coding: utf-8 -*-
"""멀티페이지 앱용 상단 가로 메뉴 (기본 사이드바 페이지 목록은 config에서 끔)."""
from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components
from app.utils.auth_helper import CafeMonsterAuthHelper

SETTINGS_CARD_TITLE_CLASS = "cafe-monster-settings-card-title"
SETTINGS_CARD_TITLE_ICON_CLASS = "cafe-monster-settings-card-title-icon"

PAGE_HOME = "app.py"
PAGE_EVENT = "pages/03_event_comment_lottery.py"
PAGE_COMMENTER = "pages/04_auto_commenter.py"

# (session active 키, 스크립트 경로, 표시 라벨) — 순서 고정.
# `st.switch_page`로 같은 Streamlit 세션·탭 내 전환(외부 `<a href>` 새 탭·연결 끊김 완화).
_NAV_PAGE_LINKS: tuple[tuple[str, str, str], ...] = (
    ("app", PAGE_HOME, "카페 수집"),
    ("event", PAGE_EVENT, "이벤트 댓글 분석"),
    ("commenter", PAGE_COMMENTER, "자동 댓글러"),
)

_TOP_NAV_CONTAINER_KEY = "cafe_monster_top_nav"


def render_main_top_nav(*, active: str) -> None:
    """
    active: "app" | "event" | "commenter"
    """
    # 멀티페이지(pages/*.py)는 app.py 단일 진입과 달리 상단 헤더·첫 블록이 겹쳐
    # 탭 버튼 위가 잘려 보일 수 있어 본문 상단 패딩을 여유롭게 보정.
    _block_padding_top = "0.75rem"
    
    active_licenses = CafeMonsterAuthHelper.get_active_products()

    # 정품 보유 여부에 따른 개별 버튼 스타일 정의 (Pro vs Trial)
    trial_styles = ""
    for nav_key, prod_id in [("app", "CafeCrawler"), ("event", "EventStats"), ("commenter", "AutoComment")]:
        if prod_id in active_licenses:
            # 정품 (Pro) 디자인
            trial_styles += f"""
            /* 정품 - 미선택 */
            [class*="st-key-cm_topnav_{nav_key}"] div[data-testid="stButton"] > button:not(:disabled) {{
                background: #ffffff !important;
                border: 1.5px solid #3b82f6 !important; /* 강렬한 블루 테두리 */
                color: #1d4ed8 !important; /* 선명한 블루 텍스트 */
            }}
            [class*="st-key-cm_topnav_{nav_key}"] div[data-testid="stButton"] > button:not(:disabled):hover {{
                background: #eff6ff !important;
                border-color: #2563eb !important;
                color: #1e40af !important;
            }}
            /* 정품 - 선택됨 (활성화) */
            [class*="st-key-cm_topnav_{nav_key}"] div[data-testid="stButton"] > button:disabled {{
                background: #004d3d !important; /* 선명한 포레스트 그린 */
                border: 1.5px solid #004d3d !important;
                color: #ffffff !important;
                opacity: 1 !important;
            }}
            """
        else:
            # 무료체험 (Trial) 디자인
            trial_styles += f"""
            /* 무료체험 - 미선택 */
            [class*="st-key-cm_topnav_{nav_key}"] div[data-testid="stButton"] > button:not(:disabled) {{
                background: #e2e8f0 !important; /* 어두운 회색 배경 */
                border: 1.5px solid #94a3b8 !important; /* 회색 테두리 */
                color: #475569 !important; /* 어두운 회색 글씨 */
            }}
            [class*="st-key-cm_topnav_{nav_key}"] div[data-testid="stButton"] > button:not(:disabled):hover {{
                background: #cbd5e1 !important;
                border-color: #64748b !important;
                color: #334155 !important;
            }}
            /* 무료체험 - 선택됨 (활성화) */
            [class*="st-key-cm_topnav_{nav_key}"] div[data-testid="stButton"] > button:disabled {{
                background: #475569 !important; /* 차분한 어두운 회색 활성화 */
                border: 1.5px solid #334155 !important;
                color: #ffffff !important;
                opacity: 1 !important;
            }}
            """

    st.markdown(
        f"""
        <style>
            /* Streamlit 기본 헤더 공간 숨김으로 여백 최적화 */
            header[data-testid="stHeader"],
            div[data-testid="stAppHeader"],
            [data-testid="stAppHeader"] {{
                display: none !important;
                height: 0px !important;
                min-height: 0px !important;
                padding: 0 !important;
                margin: 0 !important;
            }}

            /* 사이드바 진입점(collapsedControl 및 stSidebarCollapseButton) 숨김 */
            div[data-testid="collapsedControl"],
            button[data-testid="collapsedControl"],
            [data-testid="collapsedControl"],
            div[data-testid="stSidebarCollapseButton"],
            button[data-testid="stSidebarCollapseButton"],
            [data-testid="stSidebarCollapseButton"] {{
                display: none !important;
                width: 0px !important;
                height: 0px !important;
                opacity: 0 !important;
                visibility: hidden !important;
            }}

            /* 사이드바·멀티페이지 기본 네비 완전 숨김 (첫 페인트 후 잔상·유령 메뉴 최소화) */
            section[data-testid="stSidebar"],
            div[data-testid="stSidebar"],
            [data-testid="stSidebar"] {{
                display: none !important;
                min-width: 0 !important;
                width: 0 !important;
            }}
            [data-testid="stSidebarNav"],
            [data-testid="stSidebarNavItems"] {{
                display: none !important;
            }}

            /*
             * 본문 폭: app.py와 동일 max-width. 서브페이지도 `.block-container`에 직접 적용.
             */
            .block-container {{
                max-width: 1450px !important;
                padding-top: {_block_padding_top} !important;
                padding-bottom: 2.25rem !important;
                margin-left: auto !important;
                margin-right: auto !important;
                box-sizing: border-box !important;
            }}
            /* 상단 메뉴: switch_page 버튼 — 예전 HTML nav 링크와 동일한 칩 스타일 */
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] {{
                margin-top: -0.5rem !important;
                margin-bottom: 0px !important;
                border-bottom: 1px solid rgba(192,201,195,0.35) !important;
                padding-bottom: 0.4rem !important;
            }}
            /* 탭 컬럼들이 수직으로 균일하게 정렬되도록 */
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] div[data-testid="column"] {{
                display: flex !important;
                align-items: center !important;
            }}
            /* 제목 헤더 컨테이너: 탭과의 여백 약 1cm 수준으로 축소 */
            [class*="st-key-dashboard_header"] {{
                margin-top: -2.5rem !important;
                margin-bottom: -1.0rem !important;
            }}
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] div[data-testid="column"] div[data-testid="stVerticalBlock"] {{
                flex: 1 1 0% !important;
                min-width: 0 !important;
                width: 100% !important;
            }}
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] div[data-testid="stButton"] {{
                width: 100% !important;
            }}
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] div[data-testid="stButton"] > button {{
                width: 100% !important;
                min-height: 2.55rem !important;
                justify-content: center !important;
                text-align: center !important;
                font-weight: 600 !important;
                font-size: 0.92rem !important;
                line-height: 1.35 !important;
                padding: 0.55rem 0.35rem !important;
                border-radius: 0.45rem !important;
                border: 1px solid #cfdbf3 !important;
                background: #ffffff !important;
                color: #191c1d !important;
                box-sizing: border-box !important;
            }}
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] div[data-testid="stButton"] > button:not(:disabled):hover {{
                background: #eef4ff !important;
                border-color: #cfdbf3 !important;
                color: #191c1d !important;
            }}
            [class*="st-key-{_TOP_NAV_CONTAINER_KEY}"] div[data-testid="stButton"] > button:disabled {{
                width: 100% !important;
                min-height: 2.55rem !important;
                justify-content: center !important;
                text-align: center !important;
                font-weight: 600 !important;
                font-size: 0.92rem !important;
                line-height: 1.35 !important;
                padding: 0.55rem 0.35rem !important;
                border-radius: 0.45rem !important;
                border: 1px solid #003629 !important;
                background: #003629 !important;
                color: #ffffff !important;
                opacity: 1 !important;
                cursor: default !important;
                box-sizing: border-box !important;
            }}

            /* 전 페이지 공통: 드롭다운(selectbox) 호버 시 입력(I-beam) 커서가 아닌 포인터 적용 */
            div[data-baseweb="select"],
            div[data-baseweb="select"] * {{
                cursor: pointer !important;
            }}
            /* 호버 시 옅은 배경색으로 시각적 피드백 */
            div[data-baseweb="select"]:hover > div {{
                background-color: #f0f2f6 !important;
                transition: background-color 0.2s ease;
            }}

            /* 드롭다운 옵션 목록에서 선택된 항목 하이라이트 */
            li[role="option"][aria-selected="true"] {{
                background-color: #eef4ff !important;
                color: #1e3a8a !important;
                font-weight: 700 !important;
                font-size: 0.92rem !important;
            }}
            /* 옵션 목록 호버 피드백 */
            li[role="option"]:hover {{
                background-color: #f8fafc !important;
            }}

            /* Edge 브라우저의 자체 비밀번호 표시/숨김 및 지우기(X) 아이콘 숨김 */
            input::-ms-reveal,
            input::-ms-clear {{
                display: none !important;
            }}

            /* 동적 체험판 스타일 삽입 */
            {trial_styles}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key=_TOP_NAV_CONTAINER_KEY):
        cols = st.columns(len(_NAV_PAGE_LINKS), gap="small")
        for col, (nav_key, page_path, label) in zip(cols, _NAV_PAGE_LINKS, strict=True):
            prod_id = None
            if nav_key == "app":
                prod_id = "CafeCrawler"
            elif nav_key == "event":
                prod_id = "EventStats"
            elif nav_key == "commenter":
                prod_id = "AutoComment"
                
            display_label = label
            if prod_id and prod_id not in active_licenses:
                display_label = f"{label} (무료체험 50건)"

            with col:
                go = st.button(
                    display_label,
                    key=f"cm_topnav_{nav_key}",
                    type="secondary",
                    use_container_width=True,
                    disabled=(active == nav_key),
                )
                if go:
                    st.switch_page(page_path)

    # date_input 팝업(캘린더)의 월/요일 영문 라벨을 한국어로 보정
    components.html(
        """
        <script>
        (function () {
          const doc = window.parent && window.parent.document ? window.parent.document : document;
          const MONTH_MAP = {
            January: "1월", February: "2월", March: "3월", April: "4월",
            May: "5월", June: "6월", July: "7월", August: "8월",
            September: "9월", October: "10월", November: "11월", December: "12월",
            Jan: "1월", Feb: "2월", Mar: "3월", Apr: "4월",
            Jun: "6월", Jul: "7월", Aug: "8월", Sep: "9월", Sept: "9월",
            Oct: "10월", Nov: "11월", Dec: "12월"
          };
          const WEEKDAY_MAP = {
            Su: "일", Sun: "일",
            Mo: "월", Mon: "월",
            Tu: "화", Tue: "화",
            We: "수", Wed: "수",
            Th: "목", Thu: "목",
            Fr: "금", Fri: "금",
            Sa: "토", Sat: "토"
          };

          function normalizeText(raw) {
            const t = String(raw || "").trim();
            if (!t) return null;
            if (MONTH_MAP[t]) return MONTH_MAP[t];
            if (WEEKDAY_MAP[t]) return WEEKDAY_MAP[t];
            return null;
          }

          function replaceCalendarLabels(root) {
            if (!root) return;
            const targets = root.querySelectorAll(
              '[data-baseweb="calendar"], [role="dialog"], [role="listbox"], [role="option"], [data-baseweb="popover"], [data-baseweb="menu"]'
            );
            targets.forEach((node) => {
              const walker = doc.createTreeWalker(node, NodeFilter.SHOW_TEXT);
              let cur = walker.nextNode();
              while (cur) {
                const mapped = normalizeText(cur.nodeValue);
                if (mapped) cur.nodeValue = mapped;
                cur = walker.nextNode();
              }
            });
          }

          function apply() {
            try { replaceCalendarLabels(doc); } catch (_) {}
          }

          apply();
          const mo = new MutationObserver(() => apply());
          mo.observe(doc.body, { childList: true, subtree: true, characterData: true });
          [120, 400, 900, 1500].forEach((ms) => setTimeout(apply, ms));
        })();
        </script>
        """,
        height=2,
        width=720,
        scrolling=False,
    )


def render_settings_card_title(label: str, *, icon: str | None = None) -> None:
    """
    설정 3카드 상단 제목 — 가운데 정렬·강조색·동일 타이포 (inject_settings_three_cards_css와 짝).
    """
    safe_label = html.escape(label.strip())
    if icon:
        safe_icon = html.escape(icon)
        inner = (
            f'<span class="{SETTINGS_CARD_TITLE_ICON_CLASS}" aria-hidden="true">{safe_icon}</span>'
            f'<span class="{SETTINGS_CARD_TITLE_CLASS}-text">{safe_label}</span>'
        )
    else:
        inner = f'<span class="{SETTINGS_CARD_TITLE_CLASS}-text">{safe_label}</span>'
    st.markdown(
        f'<div class="{SETTINGS_CARD_TITLE_CLASS}">{inner}</div>',
        unsafe_allow_html=True,
    )


def inject_settings_three_cards_css(*, key_basename: str) -> None:
    """
    메인(카페)·논문 수집 등 동일한 상단 3카드 설정 블록 스타일.
    st.container(border=True, key=f"{key_basename}_1") 와 짝.

    key_basename 예: "settings_card", "papers_settings_card"
    Streamlit 1.5x: `key=` 가 붙은 노드가 곧 `data-testid="stVerticalBlock"` 이므로
    gap 은 **자손** `[data-testid="stVerticalBlock"]` 가 아니라 아래 sel_root 에 둬야 함.
    """
    sel_root = ",\n    ".join(
        f'div[class*="st-key-"][class*="-{key_basename}_{i}"]' for i in (1, 2, 3)
    )

    def sel_desc(rest: str) -> str:
        return ",\n    ".join(
            f'div[class*="st-key-"][class*="-{key_basename}_{i}"] {rest}'
            for i in (1, 2, 3)
        )

    sel_wrapper = ",\n    ".join(
        f'div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[class*="st-key-"][class*="-{key_basename}_{i}"])'
        for i in (1, 2, 3)
    )

    st.markdown(
        f"""
    <style>
    {sel_root} {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        box-shadow: none !important;
    }}
    {sel_wrapper} {{
        background: #ffffff !important;
        border: 1.5px solid #8c9ba5 !important;
        border-radius: 8px !important;
        padding: 1rem !important;
        box-shadow: none !important;
        box-sizing: border-box !important;
    }}
    
    /* 카드 제목 디자인 */
    {sel_desc(f".{SETTINGS_CARD_TITLE_CLASS}")} {{
        text-align: center !important;
        font-size: 1.0rem !important;
        font-weight: 700 !important;
        color: #1e3a8a !important; /* 딥 네이비 */
        margin-top: 0 !important;
        margin-bottom: 0.8rem !important;
        padding-bottom: 0.5rem !important;
        border-bottom: 2px solid #2563eb !important; /* 블루 포인트 */
        background: transparent !important;
        border-top: none !important;
        border-left: none !important;
        border-right: none !important;
        border-radius: 0 !important;
        box-sizing: border-box !important;
    }}
    {sel_desc(f".{SETTINGS_CARD_TITLE_ICON_CLASS}")} {{
        margin-right: 0.35rem !important;
        font-style: normal !important;
    }}
    {sel_desc(f".{SETTINGS_CARD_TITLE_CLASS}-text")} {{
        vertical-align: middle !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )
