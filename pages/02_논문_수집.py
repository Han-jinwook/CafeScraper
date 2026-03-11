import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
import subprocess
import time
import json

from app.products.scraper.crawler import VitaminDWikiCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, resolve_db_path


st.set_page_config(page_title="VitaminDWiki 전수 조사", layout="wide")

if st.session_state.get("crawl_running", False):
    st.warning("메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

CONFIG_PATH = str(get_config_path())

BATCH_SIZE = 15  # 한 번의 Streamlit 재실행에서 처리할 URL 수


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
DB_PATH = str(resolve_db_path(config.get("db_path")))

init_db(DB_PATH)


def ensure_papers_schema():
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


def get_papers_stats():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        total = int(pd.read_sql_query("SELECT COUNT(*) as cnt FROM papers", conn)["cnt"][0])
        cats = int(pd.read_sql_query(
            "SELECT COUNT(DISTINCT category) as cnt FROM papers WHERE category IS NOT NULL AND category != ''",
            conn,
        )["cnt"][0])
        last_date = pd.read_sql_query("SELECT MAX(collected_date) as d FROM papers", conn)["d"][0]
        conn.close()
        return total, cats, str(last_date) if last_date else "-"
    except:
        try:
            conn.close()
        except:
            pass
        return 0, 0, "-"


def load_existing_paper_urls() -> set[str]:
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


def _format_elapsed(started_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(started_iso)
        sec = int((datetime.now() - dt).total_seconds())
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}시간 {m:02d}분 {s:02d}초"
        if m:
            return f"{m}분 {s:02d}초"
        return f"{s}초"
    except:
        return "-"


# ── 세션 초기화 ────────────────────────────────────────────────
for _k, _v in [
    ("wiki_running", False),
    ("wiki_stop_requested", False),
    ("wiki_generator", None),
    ("wiki_crawler_obj", None),
    ("wiki_stats", {}),
    ("wiki_started_at", None),
    ("wiki_last_msg", ""),
    ("wiki_status_messages", []),
    ("wiki_debug_mode", False),
    ("papers_editor_refresh", 0),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


def add_log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.wiki_status_messages.append(f"[{ts}] {msg}")
    st.session_state.wiki_last_msg = msg


# ── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    st.session_state.wiki_debug_mode = st.checkbox(
        "🐞 디버그 모드", value=bool(config.get("wiki_debug_mode", False))
    )

    st.subheader("🌐 전수 조사 옵션")
    wiki_start_url = st.text_input(
        "시작 URL",
        value=config.get("wiki_start_url", "https://vitamindwiki.com/pages/health-problems-and-d/"),
        disabled=st.session_state.wiki_running,
    )
    wiki_delay = st.number_input(
        "요청 딜레이(초)",
        min_value=0.0,
        max_value=3.0,
        value=float(config.get("wiki_delay", 0.5)),
        step=0.1,
        disabled=st.session_state.wiki_running,
    )
    wiki_max_pages = st.number_input(
        "최대 페이지(0=무제한)",
        min_value=0,
        max_value=500000,
        value=int(config.get("wiki_max_pages", 0)),
        step=100,
        disabled=st.session_state.wiki_running,
    )
    skip_existing = st.checkbox(
        "✅ 이미 수집한 URL 재방문 스킵(추천)",
        value=bool(config.get("wiki_skip_existing", True)),
        disabled=st.session_state.wiki_running,
    )

    if st.button("💾 설정 저장", width="stretch", disabled=st.session_state.wiki_running):
        config["wiki_debug_mode"] = bool(st.session_state.wiki_debug_mode)
        config["wiki_start_url"] = wiki_start_url
        config["wiki_delay"] = float(wiki_delay)
        config["wiki_max_pages"] = int(wiki_max_pages)
        config["wiki_skip_existing"] = bool(skip_existing)
        save_config(config)
        st.success("✅ 설정 저장 완료")

    st.markdown("---")
    st.subheader("💾 DB")
    db_full_path = os.path.abspath(DB_PATH)
    st.caption(f"경로: {db_full_path}")
    _t, _c, _d = get_papers_stats()
    st.metric("수집된 논문 수", f"{_t:,}개")
    if st.button("📂 DB 폴더 열기", width="stretch", key="open_db_folder_papers"):
        try:
            subprocess.run(["explorer", "/select,", db_full_path])
        except Exception:
            st.info(f"경로: {db_full_path}")


# ── 메인 헤더 ─────────────────────────────────────────────────
st.title("📚 논문 수집 (VitaminDWiki 전체)")
st.caption("카페 수집과 독립된 전수 조사 페이지입니다.")

with st.expander("📖 사용 가이드 (용어 설명 포함)", expanded=False):
    st.markdown(
        """
        #### 🌐 이 페이지에서 하는 일
        [VitaminDWiki.com](https://vitamindwiki.com) 사이트 전체를 자동으로 탐색하여,
        비타민D 관련 논문·연구 요약 페이지를 수집해 DB에 저장합니다.

        ---

        #### 📌 용어 설명
        | 용어 | 의미 |
        |---|---|
        | **논문 페이지** | 실제 논문·연구 내용이 담긴 VitaminDWiki의 각 글 페이지 |
        | **주제 분류(태그)** | 논문들을 묶어 보여주는 카테고리 목록 페이지 (탐색 경로로만 활용, 직접 저장 안 함) |
        | **탐색 대기 목록** | 아직 방문하지 않고 예약된 URL 목록. 숫자가 클수록 아직 할 일이 많다는 의미 |
        | **방문한 페이지** | 크롤러가 정상적으로 내용을 읽어온 페이지 수 (논문 + 태그 + 색인 전부 포함) |
        | **신규 수집** | 처음 발견되어 DB에 새로 저장된 논문 수 |
        | **이미 수집(스킵)** | 이미 DB에 있어서 다시 저장하지 않고 건너뛴 논문 수 (시간 절약) |
        | **읽기 실패** | 페이지를 읽지 못한 경우 (아래 실패 원인으로 구분) |

        #### ⚠️ 실패 원인별 의미와 대처
        | 원인 | 뜻 | 대처 |
        |---|---|---|
        | **없는 페이지(404)** | 링크는 있지만 실제 페이지 없음 — **정상 범위** | 별도 조치 불필요 |
        | **속도 제한(429)** | 요청이 너무 빠름 | 딜레이를 **1.0초 이상**으로 늘려 재시도 |
        | **접근 차단(403)** | 서버가 봇으로 판단하여 의도적 차단 | 딜레이를 늘리거나 잠시 후 재시도 |
        | **타임아웃** | 서버 응답 없음 (일시적 네트워크 문제) | 대부분 자동 재시도로 해결됨 |

        #### ✅ 권장 설정
        - **딜레이**: `0.5초` (기본값) — 403/429 발생 시 `1.0~1.5초`로 증가
        - **이미 수집한 URL 재방문 스킵**: 항상 체크 권장 (중복 저장 방지 + 속도 향상)
        - **최대 페이지 = 0**: 무제한 전수 조사
        """
    )

st.markdown("---")

# ── 수집 현황 통계 (상단 요약) ────────────────────────────────
st.subheader("📊 수집 현황")
_total, _cat_cnt, _last_date = get_papers_stats()
sc1, sc2, sc3, sc4 = st.columns(4)
sc1.metric("총 수집 논문", f"{_total:,}개")
sc2.metric("카테고리 수", f"{_cat_cnt:,}개")
sc3.metric("마지막 수집일", _last_date)
sc4.metric(
    "상태",
    "🟢 수집 중..." if st.session_state.wiki_running else "⚫ 대기 중",
)

st.caption(
    f"설정: 시작 URL=`{wiki_start_url}` · 딜레이={float(wiki_delay):.1f}s · "
    + (f"최대 {int(wiki_max_pages):,}페이지" if int(wiki_max_pages) else "무제한")
)
st.markdown("---")

# ── 실행 버튼 (시작 ↔ 중지 토글) ─────────────────────────────
col_btn1, col_btn2 = st.columns([1, 1])

with col_btn1:
    if st.session_state.wiki_running:
        if st.button("⏹ 수집 중... 중단하기", type="primary", width="stretch", key="stop_wiki_btn"):
            st.session_state.wiki_stop_requested = True
            add_log("🛑 중단 요청 접수. 현재 배치 완료 후 중단합니다.")
            st.rerun()
    else:
        if st.button("🚀 전수 조사 시작", type="primary", width="stretch", key="start_wiki_btn"):
            wiki_crawler = VitaminDWikiCrawler(
                delay_sec=float(wiki_delay),
                debug_mode=bool(st.session_state.wiki_debug_mode),
            )
            wiki_crawler.set_status_callback(add_log)
            existing_urls = load_existing_paper_urls() if skip_existing else set()
            max_pages_val = None if int(wiki_max_pages) == 0 else int(wiki_max_pages)
            gen = wiki_crawler.crawl_full(
                start_url=wiki_start_url,
                max_pages=max_pages_val,
                initial_visited_urls=existing_urls,
            )
            st.session_state.wiki_crawler_obj = wiki_crawler
            st.session_state.wiki_generator = gen
            st.session_state.wiki_stats = {
                "processed": 0,
                "skipped": len(existing_urls),
            }
            st.session_state.wiki_started_at = datetime.now().isoformat()
            st.session_state.wiki_running = True
            st.session_state.wiki_stop_requested = False
            st.session_state.wiki_status_messages = []
            add_log(f"📚 전수 조사 시작 (기존 {len(existing_urls):,}개 스킵 예정)")
            st.rerun()

with col_btn2:
    if not st.session_state.wiki_running:
        if st.button("🔄 현황 새로고침", width="stretch", key="refresh_wiki_btn"):
            st.rerun()
    else:
        st.button("🔄 현황 새로고침", width="stretch", disabled=True, key="refresh_wiki_btn_dis")

# ── 실시간 진행 현황판 ────────────────────────────────────────
live_stats = st.empty()
live_msg = st.empty()

def _render_live_stats():
    crawler = st.session_state.get("wiki_crawler_obj")
    stats = st.session_state.get("wiki_stats", {})
    started = st.session_state.get("wiki_started_at")
    processed = int(stats.get("processed", 0))
    skipped = int(stats.get("skipped", 0))

    if not crawler and not processed:
        return

    s = getattr(crawler, "fetch_stats", {}) if crawler else {}
    total_fail = sum(s.get(k, 0) for k in ("fail_404", "fail_403", "fail_429", "fail_other", "fail_timeout"))

    if s.get("fail_403"):
        detail = f"🚫 차단 {s['fail_403']}건"
    elif s.get("fail_429"):
        detail = f"⏱️ 속도제한 {s['fail_429']}건"
    elif s.get("fail_timeout"):
        detail = f"⌛ 타임아웃 {s['fail_timeout']}건"
    elif s.get("fail_404"):
        detail = f"없는 페이지 {s['fail_404']}건"
    else:
        detail = "없음"

    elapsed = _format_elapsed(started) if started else "-"

    with live_stats.container():
        st.markdown("#### 🔄 진행 현황" if st.session_state.wiki_running else "#### ✅ 완료 현황")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("신규 수집 논문", f"{processed:,}개")
        c2.metric("방문한 페이지", f"{s.get('ok', 0):,}개")
        c3.metric("이미 수집(스킵)", f"{skipped:,}개")
        c4.metric("읽기 실패", f"{total_fail:,}개")
        c5.metric("실패 원인", detail)
        c6.metric("소요 시간", elapsed)


# ── 수집 루프 (배치 처리) ─────────────────────────────────────
if st.session_state.wiki_running:
    _render_live_stats()

    gen = st.session_state.wiki_generator
    crawler_obj = st.session_state.wiki_crawler_obj
    if crawler_obj:
        crawler_obj.set_status_callback(add_log)

    done = False
    count = 0

    while count < BATCH_SIZE:
        if st.session_state.wiki_stop_requested:
            break
        try:
            paper = next(gen)
            try:
                save_paper_to_sqlite(paper)
            except Exception as e:
                add_log(f"⚠️ 저장 실패: {paper.get('url', '')} ({e})")
            st.session_state.wiki_stats["processed"] += 1
            count += 1

            # 배치 중간 상태 메시지 업데이트
            live_msg.info(f"📡 {st.session_state.wiki_last_msg}")

        except StopIteration:
            done = True
            break

    if done:
        st.session_state.wiki_running = False
        st.session_state.wiki_generator = None
        p = st.session_state.wiki_stats.get("processed", 0)
        add_log(f"✅ 전수 조사 완료 — 신규 저장 {p:,}개")
        _render_live_stats()
        live_msg.success(f"✅ 전수 조사 완료 — 신규 저장 {p:,}개")
        st.rerun()
    elif st.session_state.wiki_stop_requested:
        st.session_state.wiki_running = False
        st.session_state.wiki_stop_requested = False
        st.session_state.wiki_generator = None
        p = st.session_state.wiki_stats.get("processed", 0)
        add_log(f"🛑 중단됨 — 신규 저장 {p:,}개")
        _render_live_stats()
        live_msg.warning(f"🛑 수집 중단됨 — 신규 저장 {p:,}개")
        st.rerun()
    else:
        # 다음 배치를 위해 재실행
        st.rerun()

else:
    # 비실행 중: 마지막 현황판 표시 (있는 경우)
    _render_live_stats()
    if st.session_state.wiki_last_msg:
        if "완료" in st.session_state.wiki_last_msg:
            live_msg.success(f"✅ {st.session_state.wiki_last_msg}")
        elif "중단" in st.session_state.wiki_last_msg:
            live_msg.warning(f"🛑 {st.session_state.wiki_last_msg}")
        elif "차단" in st.session_state.wiki_last_msg or "속도 제한" in st.session_state.wiki_last_msg:
            live_msg.error(f"🚨 {st.session_state.wiki_last_msg}")

# ── 실행 로그 ─────────────────────────────────────────────────
if st.session_state.wiki_status_messages:
    with st.expander(
        f"📋 실행 로그 ({len(st.session_state.wiki_status_messages)}줄)"
        + (" — 디버그 모드 ON" if st.session_state.wiki_debug_mode else ""),
        expanded=bool(st.session_state.wiki_debug_mode),
    ):
        log_text = "\n".join(reversed(st.session_state.wiki_status_messages[-300:]))
        st.text_area(
            "",
            log_text,
            height=280,
            disabled=True,
            label_visibility="collapsed",
            key="wiki_log_area",
        )
        if st.button("🗑️ 로그 초기화", key="clear_wiki_log"):
            st.session_state.wiki_status_messages = []
            st.session_state.wiki_last_msg = ""
            st.rerun()

st.markdown("---")

# ── 데이터 관리 ───────────────────────────────────────────────
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
        st.write(f"**총 {_total:,}개 논문** (최근 200개 표시)")

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
            width="stretch",
            disabled=["url", "title", "category", "collected_date", "요약미리보기"],
            key=f"papers_editor_{st.session_state.papers_editor_refresh}",
        )

        st.session_state.selected_papers = edited[edited["선택"] == True]["url"].tolist()

        st.markdown("---")
        a1, a2, a3 = st.columns([1, 1, 1])
        with a1:
            if st.button("☑️ 전체 선택", width="stretch", key="select_all_papers"):
                st.session_state.selected_papers = df["url"].tolist()
                st.session_state.papers_editor_refresh += 1
                st.rerun()
        with a2:
            if st.button("⬜ 전체 해제", width="stretch", key="deselect_all_papers"):
                st.session_state.selected_papers = []
                st.session_state.papers_editor_refresh += 1
                st.rerun()
        with a3:
            if st.session_state.selected_papers:
                if st.button(
                    f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_papers)})",
                    type="primary",
                    width="stretch",
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
                st.button(
                    "🗑️ 선택 항목 삭제",
                    disabled=True,
                    width="stretch",
                    key="delete_papers_disabled",
                )

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
        st.text_area(
            "",
            row["content"] if row.get("content") else row["summary"],
            height=320,
            disabled=True,
            label_visibility="collapsed",
        )

    conn.close()
except Exception as e:
    st.error(f"DB 조회 중 오류: {e}")
