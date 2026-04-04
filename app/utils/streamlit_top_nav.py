# -*- coding: utf-8 -*-
"""멀티페이지 앱용 상단 가로 메뉴 (기본 사이드바 페이지 목록은 config에서 끔)."""
from __future__ import annotations

import html
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

SETTINGS_CARD_TITLE_CLASS = "cafe-monster-settings-card-title"
SETTINGS_CARD_TITLE_ICON_CLASS = "cafe-monster-settings-card-title-icon"

PAGE_HOME = "app.py"
PAGE_PAPERS = "pages/02_논문_수집.py"
PAGE_EVENT = "pages/03_이벤트_댓글_추첨.py"
PAGE_COMMENTER = "pages/04_자동_댓글러.py"

# (session active 키, URL 경로명, 표시 라벨) — 순서 고정
_NAV_ENTRIES: tuple[tuple[str, str, str], ...] = (
    ("app", "", "카페 수집"),
    ("event", "이벤트_댓글_추첨", "이벤트 댓글 분석"),
    ("papers", "논문_수집", "논문 수집"),
    ("commenter", "자동_댓글러", "자동 댓글러"),
)


def _nav_href(page_name: str) -> str:
    """Streamlit MPA `url_pathname` 규칙과 동일: 메인은 `/`, 나머지는 `/` + page_name(인코딩)."""
    if not page_name:
        return "/"
    return "/" + quote(page_name, safe="_")


def _html_top_nav_row(*, active: str) -> str:
    parts: list[str] = [
        '<nav class="cafe-monster-topnav" role="navigation" aria-label="메인 메뉴">'
    ]
    for nav_key, pathname, label in _NAV_ENTRIES:
        href = _nav_href(pathname)
        current = ' aria-current="page"' if active == nav_key else ""
        parts.append(
            f'<a href="{html.escape(href)}"{current}>{html.escape(label)}</a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def render_main_top_nav(*, active: str) -> None:
    """
    active: "app" | "papers" | "event" | "commenter"
    """
    # 멀티페이지(pages/*.py)는 app.py 단일 진입과 달리 상단 헤더·첫 블록이 겹쳐
    # 탭 버튼 위가 잘려 보일 수 있어 본문 상단 패딩만 소폭 추가.
    _block_padding_top = "3.35rem" if active == "app" else "4.35rem"

    st.markdown(
        f"""
        <style>
            /*
             * 본문 폭: app.py와 동일 max-width. 서브페이지도 `.block-container`에 직접 적용.
             */
            .block-container {{
                max-width: 1450px !important;
                padding-top: {_block_padding_top} !important;
                padding-bottom: 4.5rem !important;
                margin-left: auto !important;
                margin-right: auto !important;
                box-sizing: border-box !important;
            }}
            /* 상단 메뉴: Streamlit column/page_link 조합이 세로로 쌓이는 환경 대비 — 순수 flex HTML */
            nav.cafe-monster-topnav {{
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: nowrap !important;
                gap: 0.5rem !important;
                width: 100% !important;
                box-sizing: border-box !important;
                margin: 0 0 0.45rem 0 !important;
                padding: 0 !important;
            }}
            nav.cafe-monster-topnav > a {{
                flex: 1 1 0% !important;
                min-width: 0 !important;
                text-align: center !important;
                text-decoration: none !important;
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
            nav.cafe-monster-topnav > a:hover {{
                background: #eef4ff !important;
            }}
            nav.cafe-monster-topnav > a[aria-current="page"] {{
                background: #003629 !important;
                border-color: #003629 !important;
                color: #ffffff !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(_html_top_nav_row(active=active), unsafe_allow_html=True)

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

    st.markdown(
        '<div style="height:0;margin:0.15rem 0 0.55rem 0;border:none;'
        'border-top:1px solid rgba(192,201,195,0.35);"></div>',
        unsafe_allow_html=True,
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

    st.markdown(
        f"""
    <style>
    {sel_root} {{
        background: #eef4ff !important;
        border: 1px solid #cfdbf3 !important;
        border-radius: 0.65rem !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06) !important;
        padding: 0.15rem !important;
        box-sizing: border-box !important;
        gap: 0.55rem !important;
        row-gap: 0.55rem !important;
    }}
    {sel_desc('[data-testid="stVerticalBlockBorderWrapper"]')} {{
        background: #eef4ff !important;
        border-color: #cfdbf3 !important;
        border-radius: 0.6rem !important;
        padding: 0.58rem 1.1rem 0.72rem 1.1rem !important;
        box-sizing: border-box !important;
    }}
    {sel_desc('[data-testid="stVerticalBlock"]')} {{
        background: #eef4ff !important;
        padding: 0 !important;
        box-sizing: border-box !important;
        gap: 0.42rem !important;
    }}
    {sel_desc('[data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"]')} {{
        gap: 0.42rem !important;
    }}
    {sel_desc(".element-container")} {{
        margin-bottom: 0 !important;
    }}
    {sel_desc('[data-testid="stCaptionContainer"]')} {{
        margin-top: 0 !important;
        margin-bottom: 0.06rem !important;
        padding: 0.06rem 0 0.12rem 0.12rem !important;
    }}
    {sel_desc('[data-testid="stCaptionContainer"] p')} {{
        margin: 0 0 0.1rem 0 !important;
        line-height: 1.45 !important;
    }}
    {sel_desc('[data-testid="stWidgetLabel"]')} {{
        margin-bottom: 0.14rem !important;
        margin-top: 0 !important;
        padding: 0 0.05rem 0 0.12rem !important;
    }}
    {sel_desc(".stTextInput")},
    {sel_desc(".stDateInput")},
    {sel_desc(".stTextArea")},
    {sel_desc(".stNumberInput")} {{
        margin-top: 0 !important;
        margin-bottom: 0.06rem !important;
    }}
    {sel_desc('[data-testid="stExpander"]')} {{
        margin-top: 0 !important;
        margin-bottom: 0.34rem !important;
    }}
    {sel_desc('[data-testid="stButton"]')} {{
        margin-top: 0.1rem !important;
        margin-bottom: 0.32rem !important;
    }}
    {sel_desc("h3")},
    {sel_desc("h4")} {{
        margin-top: 0.45rem !important;
        margin-bottom: 0.2rem !important;
        padding-left: 0.12rem !important;
        line-height: 1.4 !important;
    }}
    {sel_desc(".stTextInput > div > div > input")},
    {sel_desc(".stTextInput input")},
    {sel_desc(".stDateInput > div > div > input")},
    {sel_desc(".stDateInput input")},
    {sel_desc(".stNumberInput input")} {{
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }}
    {sel_desc(".stTextArea textarea")} {{
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }}
    {sel_desc('[data-testid="stMetric"]')} {{
        margin-top: 0.28rem !important;
        margin-bottom: 0.12rem !important;
        padding: 0.5rem 0.85rem !important;
        min-height: 0 !important;
        justify-content: center !important;
    }}
    {sel_desc('[data-testid="stMetricLabel"] p')},
    {sel_desc('[data-testid="stMetricValue"]')} {{
        padding-left: 0.15rem !important;
    }}
    {sel_desc('[data-testid="stExpander"] details summary')} {{
        padding: 0.42rem 0.7rem !important;
    }}
    {sel_desc('[data-testid="stExpander"] details')} {{
        margin-bottom: 0.34rem !important;
    }}
    {sel_desc(f".{SETTINGS_CARD_TITLE_CLASS}")} {{
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
