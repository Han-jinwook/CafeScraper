import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import os
import subprocess
import time
import json
import re
from pathlib import Path

from app.products.scraper.crawler import VitaminDWikiCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, resolve_paper_db_path
from app.utils.streamlit_brand import render_logo_png
from app.utils.streamlit_top_nav import (
    inject_settings_three_cards_css,
    render_main_top_nav,
    render_settings_card_title,
)


st.set_page_config(
    page_title="마케팅 몬스터 · 사이트 콘텐츠 수집",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_main_top_nav(active="papers")

if st.session_state.get("crawl_running", False):
    st.warning("메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

inject_settings_three_cards_css(key_basename="papers_settings_card")

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
if "paper_db_path_input" not in st.session_state:
    st.session_state.paper_db_path_input = str(config.get("paper_db_path", "") or "")
DB_PATH = str(resolve_paper_db_path(config.get("paper_db_path")))

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


def _format_elapsed(started_ts) -> str:
    try:
        sec = int(time.time() - float(started_ts))
        if sec < 0:
            return "-"
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}시간 {m:02d}분 {s:02d}초"
        if m:
            return f"{m}분 {s:02d}초"
        return f"{s}초"
    except:
        return "-"


import queue
import threading
import uuid

@st.cache_resource
def get_jobs_registry():
    return {}

JOBS = get_jobs_registry()

def run_crawl_thread(crawler, start_url, initial_visited_urls, log_queue, stats, db_path):
    try:
        gen = crawler.crawl_auto(start_url=start_url, initial_visited_urls=initial_visited_urls)
        for paper in gen:
            if stats.get("stop_requested", False):
                break
            
            if paper is not None:
                max_retries = 3
                retry_delay = 0.5
                saved = False
                for attempt in range(max_retries):
                    try:
                        conn = sqlite3.connect(db_path, timeout=30.0)
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
                        saved = True
                        break
                    except sqlite3.OperationalError as e:
                        if "locked" in str(e) and attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        log_queue.put(f"⚠️ DB 잠김 오류 (재시도): {e}")
                    except Exception as e:
                        log_queue.put(f"⚠️ 저장 오류: {e}")
                        break
                if saved:
                    stats["processed"] += 1
            
            stats["fetch_stats"] = dict(getattr(crawler, "fetch_stats", {}) or {})
            
        if stats.get("stop_requested", False):
            stats["status"] = "stopped"
            log_queue.put("🛑 수집 중단됨")
        else:
            stats["status"] = "completed"
            log_queue.put("✅ 전수 조사 완료")
    except Exception as e:
        stats["status"] = "error"
        log_queue.put(f"❌ 오류 발생: {e}")
        import traceback
        log_queue.put(traceback.format_exc())
    finally:
        stats["status"] = "done"

# ── 세션 초기화 ────────────────────────────────────────────────
for _k, _v in [
    ("wiki_running", False),
    ("wiki_stop_requested", False),
    ("wiki_job_id", None),
    ("wiki_stats", {}),
    ("wiki_started_ts", None),   # Unix timestamp(float) — ISO 파싱 이슈 방지
    ("wiki_fetch_stats", {}),    # 배치 완료 후 crawler.fetch_stats 스냅샷
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


def _render_papers_dashboard_header() -> None:
    """메인 `_render_cafe_dashboard_header`와 동일 그리드: 로고 + 제목·가이드."""
    _logo_path = Path(__file__).resolve().parent.parent / "assets" / "CafeMonster_logo.png"

    _hdr_logo, _hdr_mid = st.columns([1, 5], gap="small")
    with _hdr_logo:
        render_logo_png(_logo_path, width_px=92)
    with _hdr_mid:
        _title_col, _guide_col = st.columns([2.65, 1.35], gap="small")
        with _title_col:
            st.markdown(
                '<h2 style="margin:0 0 0.15rem 0;padding:0;line-height:1.2;font-size:1.35rem;">'
                "사이트 콘텐츠 수집</h2>",
                unsafe_allow_html=True,
            )
        with _guide_col:
            with st.expander("📖 사용 가이드 (필독)", expanded=False):
                st.markdown(
                    """
        #### 1) 이 도구가 하는 일
        - 시작 URL의 **도메인**을 기준으로, **웹 표준 방식**으로 글(페이지) 목록을 만든 뒤 **한 건씩 방문**해 DB(`papers` 테이블)에 저장합니다.
        - **① sitemap.xml** 이 있으면 → 사이트맵에 적힌 URL을 순서대로 수집합니다.
        - **② 없으면** → **RSS / Atom 피드**(`/feed`, `/rss` 등)를 자동으로 찾아, 피드에 있는 링크만 수집합니다.
        - 예시: [VitaminDWiki](https://vitamindwiki.com), WordPress 공식 로케일, 블로그·뉴스(피드 열린 곳) 등.

        #### 2) 이 도구가 하지 **않**는 일 (기대치 조절)
        - **모든 사이트**를 보장하지 않습니다. sitemap·RSS가 없거나, **403·캡차** 등으로 막히면 수집할 수 없습니다. (우회·해킹 기능 없음)
        - **저작권·이용약관·robots 정책**은 사용자가 직접 확인해야 합니다.
        - **카페 몬스터(네이버 카페 전용)** 기능은 메인 앱에서만 처리합니다.

        #### 3) 수집이 어떻게 진행되나 (순서)
        1. `시작 URL`의 호스트에 대해 `/sitemap.xml` 요청
        2. **성공**이고 내용이 사이트맵 형식이면 → 하위 sitemap까지 펼쳐 URL 목록 생성 → **신규 URL만** 방문·저장
        3. **실패**하면 → RSS 후보 URL을 순서대로 시도 → 피드에서 링크 추출 → **신규만** 방문·저장
        4. 둘 다 안 되면 로그에 **지원 불가** 안내

        #### 4) 화면 숫자가 의미하는 것
        | 항목 | 의미 |
        |---|---|
        | **신규 수집 논문** | 이번 실행에서 DB에 **새로 넣은** 글 수(라벨은 ‘논문’이지만 **일반 웹 글** 포함) |
        | **방문한 페이지** | HTTP로 **본문 읽기 시도**한 횟수(내부 통계와 동기화) |
        | **이미 수집(스킵)** | DB에 이미 있어 **저장 생략**한 URL 수 |
        | **읽기 실패** | 404·403·타임아웃 등으로 **내용 미수신** |
        | **소요 시간** | 이번 작업 시작 기준 경과 시간 |

        #### 5) 사이트맵·피드 용어
        | 용어 | 의미 |
        |---|---|
        | **sitemap.xml** | 사이트 **URL 목록** 표준 파일. 있으면 가장 안정적으로 수집 |
        | **RSS / Atom** | **최근 글 링크** XML. sitemap 없을 때 대안 |
        | **시작 URL** | 도메인·정책 기준 **첫 주소**(특정 글일 필요 없음) |
        | **딜레이** | 요청 간격(초). 너무 짧으면 **429·403** 증가 |
        | **최대 페이지** | 처리 **URL 개수 상한**(0=무제한). 테스트·부하 조절 |

        #### 6) 실패·차단 시 대처
        | 증상 | 의미 | 대처 |
        |---|---|---|
        | **403 / 차단** | 자동 요청 거부 | 딜레이 **1~2초**, 시간 두고 재시도 또는 **해당 사이트 포기** |
        | **429** | 과다 요청 | 딜레이 증가 |
        | **404** | 없는 URL | 일부는 정상 |
        | **타임아웃** | 일시 오류 | 재실행 |

        #### 7) 권장 설정 (첫 실행)
        - **이미 수집한 URL 재방문 스킵**: ✅ (중복 방지)
        - **딜레이**: `0.5`초부터 → 막히면 `1.0` 이상
        - **최대 페이지**: 처음 **`100~300`** 시험 후 확대
        - **DB**: 운영 전 **백업** 또는 테스트 DB

        #### 8) 브랜드 정리
        - **3Monster** — 우산 브랜드
        - **마케팅 몬스터** — 이 화면(공개 웹 콘텐츠)
        - **카페 몬스터** — 메인(네이버 카페)
        - (예정) **앱 몬스터** · 필요 시 **세일 몬스터** 분화
                    """
                )


# ── 메인 헤더 (카페 수집기와 동일 레이아웃) ───────────────────
_render_papers_dashboard_header()

st.markdown("#### ⚙️ 수집 설정")
_pw1, _pw2, _pw3 = st.columns([1, 1, 1], gap="medium")
with _pw1:
    with st.container(border=True, key="papers_settings_card_1"):
        render_settings_card_title("사이트 · 연결", icon="🌐")
        wiki_start_url = st.text_input(
            "시작 URL",
            value=config.get("wiki_start_url", "https://vitamindwiki.com/pages/health-problems-and-d/"),
            disabled=st.session_state.wiki_running,
        )
        with st.expander("🐞 고급 · 디버그", expanded=False):
            st.session_state.wiki_debug_mode = st.checkbox(
                "🐞 디버그 모드",
                value=bool(config.get("wiki_debug_mode", False)),
                disabled=st.session_state.wiki_running,
            )

with _pw2:
    with st.container(border=True, key="papers_settings_card_2"):
        render_settings_card_title("수집 옵션", icon="⚙️")
        wiki_delay = st.number_input(
            "요청 딜레이(초)",
            min_value=0.0,
            max_value=3.0,
            value=float(config.get("wiki_delay", 0.5)),
            step=0.1,
            disabled=st.session_state.wiki_running,
        )
        wiki_max_pages = st.number_input(
      # ── 실시간 현황 및 제어 (Fragment) ─────────────────────────────────────────
@st.fragment(run_every=1.0)
def render_crawl_section_ui():
    # 1. 활성 백그라운드 스레드 탐색 및 세션 상태 복원
    active_job_id = None
    for jid, jdata in list(JOBS.items()):
        thread = jdata.get("thread")
        if thread and thread.is_alive():
            active_job_id = jid
            break

    if active_job_id:
        st.session_state.wiki_job_id = active_job_id
        st.session_state.wiki_running = True
    else:
        # 실행 중으로 표시되어 있었으나 실제 스레드가 없으면 정지 처리
        if st.session_state.wiki_running:
            if st.session_state.wiki_job_id and st.session_state.wiki_job_id in JOBS:
                job = JOBS[st.session_state.wiki_job_id]
                # 마지막 남은 로그 drain
                q = job["log_queue"]
                while True:
                    try:
                        m = q.get_nowait()
                        if not m.startswith("["):
                            ts = datetime.now().strftime("%H:%M:%S")
                            m = f"[{ts}] {m}"
                        st.session_state.wiki_status_messages.append(m)
                        st.session_state.wiki_last_msg = m
                    except queue.Empty:
                        break
                # 최종 통계 반영
                st.session_state.wiki_stats = dict(job["stats"])
                st.session_state.wiki_fetch_stats = dict(job["stats"].get("fetch_stats", {}))
            st.session_state.wiki_running = False

    # 2. 실행 중인 경우 로그 큐 drain
    if st.session_state.wiki_running and st.session_state.wiki_job_id in JOBS:
        job = JOBS[st.session_state.wiki_job_id]
        q = job["log_queue"]
        new_logs = []
        while True:
            try:
                new_logs.append(q.get_nowait())
            except queue.Empty:
                break
        if new_logs:
            for m in new_logs:
                if not m.startswith("["):
                    ts = datetime.now().strftime("%H:%M:%S")
                    m = f"[{ts}] {m}"
                st.session_state.wiki_status_messages.append(m)
                st.session_state.wiki_last_msg = m
            # 수집 중인 상태의 통계 업데이트
            st.session_state.wiki_stats = dict(job["stats"])
            st.session_state.wiki_fetch_stats = dict(job["stats"].get("fetch_stats", {}))

    # 3. 데이터 및 통계 취합
    stats = st.session_state.get("wiki_stats", {})
    processed = int(stats.get("processed", 0))
    skipped = int(stats.get("skipped", 0))
    started_ts = st.session_state.get("wiki_started_ts")

    s = st.session_state.get("wiki_fetch_stats") or {}
    total_fail = sum(s.get(k, 0) for k in ("fail_404", "fail_403", "fail_429", "fail_other", "fail_timeout"))
    
    # 상태 메시지에서 탐색 페이지 수 파싱 → 방문 페이지 수 보완
    last_msg = st.session_state.get("wiki_last_msg", "")
    msg_pages = 0
    m_pages = re.search(r"탐색\s*([\d,]+)페이지", last_msg)
    if m_pages:
        msg_pages = int(m_pages.group(1).replace(",", ""))
    ok_cnt = max(s.get("ok", 0), msg_pages)

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

    queue_remaining = ""
    m_queue = re.search(r"대기\s*([\d,]+)건", last_msg)
    if m_queue and st.session_state.wiki_running:
        queue_remaining = f"· 대기 {m_queue.group(1)}건"

    elapsed = _format_elapsed(started_ts) if started_ts else "-"

    # 4. 화면 출력 (수집 현황 요약)
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

    # 5. 제어 버튼
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.session_state.wiki_running:
            if st.button("⏹ 수집 중... 중단하기", type="primary", use_container_width=True, key="stop_wiki_btn"):
                # 활성 작업에 중단 요청 전송
                if st.session_state.wiki_job_id in JOBS:
                    JOBS[st.session_state.wiki_job_id]["stats"]["stop_requested"] = True
                    st.session_state.wiki_status_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 중단 요청을 백그라운드로 보냈습니다.")
                st.session_state.wiki_stop_requested = True
                st.rerun()
        else:
            if st.button("🚀 전수 조사 시작", type="primary", use_container_width=True, key="start_wiki_btn"):
                # 새 작업 ID 생성 및 초기화
                job_id = str(uuid.uuid4())
                log_q = queue.Queue()
                
                # 기존 수집 URL 로드
                existing_urls = load_existing_paper_urls() if skip_existing else set()
                
                stats_obj = {
                    "processed": 0,
                    "skipped": len(existing_urls),
                    "status": "running",
                    "started_ts": time.time(),
                    "stop_requested": False,
                    "fetch_stats": {}
                }
                
                crawler_obj = VitaminDWikiCrawler(
                    delay_sec=float(wiki_delay),
                    debug_mode=bool(st.session_state.wiki_debug_mode),
                )
                
                # 콜백 함수: thread-safe queue에 직접 put
                def make_log_callback(q):
                    return lambda msg: q.put(msg)
                
                crawler_obj.set_status_callback(make_log_callback(log_q))
                
                # 백그라운드 스레드 생성 및 구동
                t = threading.Thread(
                    target=run_crawl_thread,
                    args=(crawler_obj, wiki_start_url, existing_urls, log_q, stats_obj, DB_PATH),
                    daemon=True
                )
                
                JOBS[job_id] = {
                    "crawler": crawler_obj,
                    "log_queue": log_q,
                    "stats": stats_obj,
                    "thread": t
                }
                
                st.session_state.wiki_job_id = job_id
                st.session_state.wiki_running = True
                st.session_state.wiki_started_ts = stats_obj["started_ts"]
                st.session_state.wiki_stats = stats_obj
                st.session_state.wiki_fetch_stats = {}
                st.session_state.wiki_status_messages = [
                    f"[{datetime.now().strftime('%H:%M:%S')}] 📚 sitemap 전수 조사 시작 (기존 {len(existing_urls):,}개 스킵 예정)"
                ]
                st.session_state.wiki_last_msg = ""
                st.session_state.wiki_stop_requested = False
                
                t.start()
                st.rerun()

    with col_btn2:
        if not st.session_state.wiki_running:
            if st.button("🔄 현황 새로고침", use_container_width=True, key="refresh_wiki_btn"):
                st.rerun()
        else:
            st.button("🔄 현황 새로고침", use_container_width=True, disabled=True, key="refresh_wiki_btn_dis")

    # 6. 실시간 진행 현황판 렌더링
    if started_ts or processed or ok_cnt:
        st.markdown(
            f"#### 🔄 진행 현황 {queue_remaining}" if st.session_state.wiki_running
            else "#### ✅ 완료 현황"
        )
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("신규 수집 논문", f"{processed:,}개")
        c2.metric("방문한 페이지", f"{ok_cnt:,}개")
        c3.metric("이미 수집(스킵)", f"{skipped:,}개")
        c4.metric("읽기 실패", f"{total_fail:,}개")
        c5.metric("실패 원인", detail)
        c6.metric("소요 시간", elapsed)

    # 7. 상태 알림 메시지
    if st.session_state.wiki_last_msg:
        if "완료" in st.session_state.wiki_last_msg:
            st.success(f"✅ {st.session_state.wiki_last_msg}")
        elif "중단" in st.session_state.wiki_last_msg:
            st.warning(f"🛑 {st.session_state.wiki_last_msg}")
        elif "차단" in st.session_state.wiki_last_msg or "속도 제한" in st.session_state.wiki_last_msg:
            st.error(f"🚨 {st.session_state.wiki_last_msg}")

    # 8. 작업 로그 화면 출력 (st.code로 대체하여 리프레시 시 DOM 깨짐 해결)
    if st.session_state.wiki_status_messages:
        _log_expanded = bool(st.session_state.wiki_debug_mode) and not st.session_state.wiki_running
        with st.expander(
            f"📋 실행 로그 ({len(st.session_state.wiki_status_messages)}줄)"
            + (" — 디버그 모드 ON" if st.session_state.wiki_debug_mode else ""),
            expanded=_log_expanded,
        ):
            log_text = "\n".join(reversed(st.session_state.wiki_status_messages[-300:]))
            st.code(log_text, language="log")
            if st.button("🗑️ 로그 초기화", key="clear_wiki_log"):
                st.session_state.wiki_status_messages = []
                st.session_state.wiki_last_msg = ""
                st.rerun()

render_crawl_section_ui()
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
                st.button(
                    "🗑️ 선택 항목 삭제",
                    disabled=True,
                    use_container_width=True,
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

