import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
import time
import json
from pathlib import Path

from crawler import VitaminDWikiCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, resolve_db_path


st.set_page_config(page_title="VitaminDWiki 전수 조사", layout="wide")

# 프로젝트 루트 기준 경로 고정 (실행 위치가 달라도 DB/설정이 안 갈라지게)
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


# 설정 로드 및 DB 경로 확정 (환경변수/설정값/기본값)
config = load_config()
DB_PATH = str(resolve_db_path(config.get("db_path")))

init_db(DB_PATH)

def ensure_papers_schema():
    """
    기존 DB(papers 테이블)에 content 컬럼이 없을 수 있어 런타임에 보정.
    - content 없으면 ALTER TABLE로 추가
    - 기존 summary 값은 content로 백필(데이터 보존)
    """
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(papers)")
        cols = [row[1] for row in cur.fetchall()]
        if "content" not in cols:
            cur.execute("ALTER TABLE papers ADD COLUMN content TEXT")
            cur.execute("UPDATE papers SET content = summary WHERE content IS NULL OR content = ''")
            conn.commit()
        conn.close()
    except:
        try:
            conn.close()
        except:
            pass


# DB 스키마 보정(구 DB 호환)
ensure_papers_schema()


def save_paper_to_sqlite(paper: dict):
    max_retries = 3
    retry_delay = 0.5
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO papers (url, title, summary, content, category, collected_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.get("url", ""),
                    paper.get("title", ""),
                    paper.get("summary", ""),
                    paper.get("content", ""),
                    paper.get("category", ""),
                    paper.get("collected_date", ""),
                ),
            )
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            raise
        finally:
            try:
                conn.close()
            except:
                pass


def get_papers_count() -> int:
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cnt = pd.read_sql_query("SELECT COUNT(*) as cnt FROM papers", conn)["cnt"][0]
        conn.close()
        return int(cnt)
    except:
        return 0


def load_existing_paper_urls() -> set[str]:
    """DB에 이미 저장된 papers.url 목록을 메모리 set으로 로드 (resume/중복방지)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        rows = pd.read_sql_query("SELECT url FROM papers", conn)["url"].tolist()
        conn.close()
        return {str(u) for u in rows if u}
    except:
        try:
            conn.close()
        except:
            pass
        return set()


if "wiki_status_messages" not in st.session_state:
    st.session_state.wiki_status_messages = []
if "wiki_debug_mode" not in st.session_state:
    st.session_state.wiki_debug_mode = False
if "papers_editor_refresh" not in st.session_state:
    st.session_state.papers_editor_refresh = 0


st.title("📚 논문 수집 (VitaminDWiki 전체)")
st.caption("카페 수집과 독립된 전수 조사 페이지입니다.")
col_nav1, col_nav2 = st.columns([1, 3])
with col_nav1:
    if st.button("🏠 카페 수집", use_container_width=True):
        # 1) switch_page 우선
        try:
            st.switch_page("app.py")
            st.stop()
        except Exception:
            pass

        st.error(
            "메인 페이지로 이동할 수 없습니다. "
            "왼쪽 사이드바 페이지 목록에서 메인 페이지를 선택하거나, Streamlit을 재시작해 주세요."
        )
with col_nav2:
    st.caption("돌아가기 버튼이 안 되면, 왼쪽 사이드바에서 메인 페이지를 선택하세요.")
st.markdown("---")

log_placeholder = st.empty()


def update_logs(msg=None):
    if msg:
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.wiki_status_messages.append(f"[{timestamp}] {msg}")

    try:
        log_placeholder.markdown("### 📋 실시간 로그")
        recent = "\n\n".join(reversed(st.session_state.wiki_status_messages[-30:]))
        log_placeholder.text_area("", recent, height=280, label_visibility="collapsed", disabled=True)
    except:
        pass


with st.sidebar:
    st.header("⚙️ 설정")
    st.session_state.wiki_debug_mode = st.checkbox("🐞 디버그 모드", value=bool(config.get("wiki_debug_mode", False)))

    st.subheader("🌐 전수 조사 옵션")
    wiki_start_url = st.text_input(
        "시작 URL",
        value=config.get("wiki_start_url", "https://vitamindwiki.com/pages/health-problems-and-d/"),
    )
    wiki_delay = st.number_input(
        "요청 딜레이(초)",
        min_value=0.0,
        max_value=3.0,
        value=float(config.get("wiki_delay", 0.5)),
        step=0.1,
    )
    wiki_max_pages = st.number_input(
        "최대 페이지(0=무제한)",
        min_value=0,
        max_value=500000,
        value=int(config.get("wiki_max_pages", 0)),
        step=100,
    )
    skip_existing = st.checkbox("✅ 이미 수집한 URL 재방문 스킵(추천)", value=bool(config.get("wiki_skip_existing", True)))

    if st.button("💾 설정 저장", use_container_width=True):
        config["wiki_debug_mode"] = bool(st.session_state.wiki_debug_mode)
        config["wiki_start_url"] = wiki_start_url
        config["wiki_delay"] = float(wiki_delay)
        config["wiki_max_pages"] = int(wiki_max_pages)
        config["wiki_skip_existing"] = bool(skip_existing)
        save_config(config)
        st.success("✅ 설정 저장 완료")

    st.markdown("---")
    st.subheader("💾 DB")
    st.caption(f"경로: {os.path.abspath(DB_PATH)}")
    st.metric("현재 수집된 논문 수", f"{get_papers_count():,}개")

st.caption(
    f"현재 설정: 시작 URL=`{wiki_start_url}` · 딜레이={float(wiki_delay):.1f}s · "
    + (f"최대페이지={int(wiki_max_pages):,}개" if int(wiki_max_pages) else "최대페이지=무제한")
)

metric_placeholder = st.empty()
metric_placeholder.metric("현재 수집된 논문 수", f"{get_papers_count():,}개")

col_run1, col_run2 = st.columns([1, 1])
with col_run1:
    start_btn = st.button("🚀 전수 조사 시작", type="primary", use_container_width=True)
with col_run2:
    refresh_btn = st.button("🔄 카운트 새로고침", use_container_width=True)

if refresh_btn:
    metric_placeholder.metric("현재 수집된 논문 수", f"{get_papers_count():,}개")
    update_logs("🔄 카운트 새로고침")

if start_btn:
    update_logs("📚 VitaminDWiki 전수 조사 시작...")
    wiki_crawler = VitaminDWikiCrawler(delay_sec=float(wiki_delay), debug_mode=bool(st.session_state.wiki_debug_mode))
    wiki_crawler.set_status_callback(update_logs)

    processed = 0
    skipped = 0
    max_pages_val = None if int(wiki_max_pages) == 0 else int(wiki_max_pages)
    existing_urls = load_existing_paper_urls() if skip_existing else set()
    if existing_urls:
        update_logs(f"♻️ 기존 URL {len(existing_urls):,}개 로드 완료 (재방문 스킵)")

    for paper in wiki_crawler.crawl_full(
        start_url=wiki_start_url,
        max_pages=max_pages_val,
        initial_visited_urls=existing_urls,
    ):
        processed += 1
        try:
            save_paper_to_sqlite(paper)
        except Exception as e:
            update_logs(f"⚠️ 저장 실패: {paper.get('url','')} ({e})")

        if processed % 25 == 0:
            metric_placeholder.metric("현재 수집된 논문 수", f"{get_papers_count():,}개")
            update_logs(f"📄 처리 중... (신규 저장 시도: {processed:,}개)")

    metric_placeholder.metric("현재 수집된 논문 수", f"{get_papers_count():,}개")
    update_logs(f"✅ VitaminDWiki 전수 조사 종료 (신규 저장 시도: {processed:,}개)")


update_logs()

st.markdown("---")
st.header("📊 데이터 관리 (papers)")

try:
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    df = pd.read_sql_query(
        """
        SELECT url, title, category, collected_date, summary, content
        FROM papers
        ORDER BY collected_date DESC
        LIMIT 200
        """,
        conn,
    )

    if df.empty:
        st.info("수집된 논문이 없습니다.")
    else:
        st.write(f"**총 {len(df)}개 논문** (최근 200개 표시)")

        if "selected_papers" not in st.session_state:
            st.session_state.selected_papers = []

        df_display = df.copy()
        df_display.insert(0, "선택", False)
        df_display["요약미리보기"] = df_display["summary"].apply(
            lambda x: (str(x)[:140] + "...") if x and len(str(x)) > 140 else str(x)
        )
        df_display = df_display.drop(columns=["summary", "content"])

        for idx, url in enumerate(df_display["url"]):
            if url in st.session_state.selected_papers:
                df_display.at[idx, "선택"] = True

        edited = st.data_editor(
            df_display,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", default=False),
                "url": st.column_config.LinkColumn("URL"),
                "title": st.column_config.TextColumn("제목", width="medium"),
                "category": st.column_config.TextColumn("카테고리", width="medium"),
                "collected_date": "수집일",
                "요약미리보기": st.column_config.TextColumn("미리보기", width="large"),
            },
            hide_index=True,
            use_container_width=True,
            disabled=["url", "title", "category", "collected_date", "요약미리보기"],
            key=f"papers_editor_{st.session_state.papers_editor_refresh}",
        )

        st.session_state.selected_papers = edited[edited["선택"] == True]["url"].tolist()

        st.markdown("---")
        a1, a2, a3 = st.columns([1, 1, 1])
        with a1:
            if st.button("☑️ 전체 선택", use_container_width=True, key="select_all_papers"):
                st.session_state.selected_papers = df["url"].tolist()
                st.session_state.papers_editor_refresh += 1
                st.rerun()
        with a2:
            if st.button("⬜ 전체 해제", use_container_width=True, key="deselect_all_papers"):
                st.session_state.selected_papers = []
                st.session_state.papers_editor_refresh += 1
                st.rerun()
        with a3:
            if st.session_state.selected_papers:
                if st.button(
                    f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_papers)})",
                    type="primary",
                    use_container_width=True,
                    key="delete_papers",
                ):
                    cur = conn.cursor()
                    for u in st.session_state.selected_papers:
                        cur.execute("DELETE FROM papers WHERE url = ?", (u,))
                    conn.commit()
                    st.success("✅ 삭제 완료")
                    st.session_state.selected_papers = []
                    st.session_state.papers_editor_refresh += 1
                    st.rerun()
            else:
                st.button("🗑️ 선택 항목 삭제", disabled=True, use_container_width=True, key="delete_papers_disabled")

        st.markdown("---")
        st.subheader("📄 논문 상세 보기")
        urls = df["url"].tolist()
        if "detail_paper_url" not in st.session_state:
            st.session_state.detail_paper_url = urls[0]
        if st.session_state.detail_paper_url not in urls:
            st.session_state.detail_paper_url = urls[0]

        selected_url = st.selectbox(
            "논문 선택",
            urls,
            index=urls.index(st.session_state.detail_paper_url),
            format_func=lambda x: df[df["url"] == x]["title"].values[0],
            key="paper_detail_selector",
        )
        st.session_state.detail_paper_url = selected_url
        row = df[df["url"] == selected_url].iloc[0]
        st.markdown(f"**제목:** {row['title']}")
        st.markdown(f"**URL:** {row['url']}")
        st.markdown(f"**카테고리:** {row['category']}")
        st.markdown(f"**수집일:** {row['collected_date']}")
        st.markdown("**본문(전체):**")
        st.text_area("", row["content"] if row.get("content") else row["summary"], height=320, disabled=True, label_visibility="collapsed")

    conn.close()
except Exception as e:
    st.error(f"DB 조회 중 오류: {e}")

