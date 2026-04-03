import streamlit as st
import pandas as pd
import sqlite3
import os
import time
import random
import json
from datetime import datetime, timedelta
from pathlib import Path

from app.products.commenter.bot import NaverCafeCommenter
from app.utils.paths import get_project_root, resolve_db_path
from app.utils.sqlite_db import init_db
from app.utils.streamlit_top_nav import (
    inject_settings_three_cards_css,
    render_main_top_nav,
    render_settings_card_title,
)

st.set_page_config(page_title="댓글 자동화 - CafeScraper", layout="wide")

render_main_top_nav(active="commenter")

# 메인 크롤링 구동 중에는 다른 메뉴 작업을 잠시 차단
if st.session_state.get("crawl_running", False):
    st.warning("메인 크롤링이 진행 중입니다. 메인 페이지에서 중단 후 다시 시도해주세요.")
    st.stop()

inject_settings_three_cards_css(key_basename="commenter_settings_card")

# DB 경로 설정 — 메인 DB는 설정 파일(crawler_config.json)의 db_path 사용
PROJECT_ROOT = get_project_root()
MAIN_DB_PATH = str(resolve_db_path())                          # D:\CafeScraper\data\cafe_data.db
_event_dir = str(resolve_db_path().parent)
EVENT_DB_PATH = str(resolve_db_path().parent / "cafe_data_event.db")
TEMPLATES_FILE = "comment_templates.json"  # 템플릿 저장용 파일

if "commenter" not in st.session_state:
    st.session_state.commenter = None
if "comment_logs" not in st.session_state:
    st.session_state.comment_logs = []
if "target_df" not in st.session_state:
    st.session_state.target_df = None

# --- 템플릿 관리 함수 ---
def load_templates():
    default_templates = [
        "안녕하세요 {닉네임}님! 좋은 글 잘 보고 갑니다 ^^",
        "{닉네임}님, 저도 비슷한 고민이 있었는데 도움 되네요.",
        "반갑습니다 {닉네임}님! 혹시 실례가 안된다면 질문 드려도 될까요?",
        "(직접 입력)"
    ]
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                return saved + default_templates
        except:
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
        except:
            pass
    
    # 중복 체크
    if content not in current:
        current.insert(0, content) # 최신순
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

if "template_list" not in st.session_state:
    st.session_state.template_list = load_templates()

def reset_target_df():
    st.session_state.target_df = None

def log_msg(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    st.session_state.comment_logs.append(f"[{timestamp}] {msg}")

def save_articles_to_db(articles, db_path):
    """수집된 리스트를 DB에 저장 (구조 동일)"""
    init_db(db_path) # 없으면 생성
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    count = 0
    try:
        for art in articles:
            # posts 테이블 스키마에 맞게 삽입 (없는 컬럼은 기본값)
            cursor.execute("""
                INSERT OR REPLACE INTO posts (
                    post_id, member_id, nickname, title, date, url, board_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (
                str(art['post_id']), 
                art.get('member_id', 'unknown'), 
                art['nickname'], 
                art['title'], 
                art['date'], 
                art['url'], 
                art.get('board_name', '')
            ))
            count += 1
        conn.commit()
    except Exception as e:
        st.error(f"DB 저장 중 오류: {e}")
    finally:
        conn.close()
    return count

def _render_commenter_dashboard_header() -> None:
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
                "자동 댓글러</h2>",
                unsafe_allow_html=True,
            )
        with _guide_col:
            with st.expander("📖 사용 가이드 (필독)", expanded=False):
                st.markdown(
                    """
                **메인 DB** 또는 **이벤트 DB**에서 글 목록을 만든 뒤, 선택한 **템플릿**으로 댓글을 자동 작성합니다.

                1. **타겟** 카드에서 소스·기간·필터를 정하고 검색하거나 이벤트 DB를 불러옵니다.
                2. **댓글 내용** 카드에서 문구를 고르고 `{닉네임}`, `{제목}` 치환을 확인합니다.
                3. **실행** 카드에서 브라우저를 연 뒤 댓글 작성을 시작합니다.

                메인 카페 크롤링이 실행 중이면 이 화면을 사용할 수 없습니다.
                    """
                )


_render_commenter_dashboard_header()

st.markdown("#### ⚙️ 설정")
_col1, _col2, _col3 = st.columns([1, 1, 1], gap="medium")

with _col1:
    with st.container(border=True, key="commenter_settings_card_1", gap=None):
        render_settings_card_title("타겟 · 소스", icon="🎯")
        target_source = st.radio(
            "타겟 소스",
            ["📂 메인 DB (상시)", "📂 이벤트 DB (직접)"],
            horizontal=True,
            key="target_source_selection",
            on_change=reset_target_df,
        )
        current_db_path = MAIN_DB_PATH if "메인" in target_source else EVENT_DB_PATH

        if "메인" in target_source:
            col_days, col_custom = st.columns([2, 1])
            with col_days:
                days_option = st.selectbox(
                    "기간 선택",
                    [1, 3, 7, 30, 90, 180, 365, "직접입력"],
                    index=3,
                    format_func=lambda x: f"최근 {x}일" if isinstance(x, int) else x,
                )

            days_lookback = 30  # default
            if days_option == "직접입력":
                with col_custom:
                    days_lookback = st.number_input("일수", 1, 3650, 1)
            else:
                days_lookback = days_option

            exclude_keyword = st.text_input("제외 닉네임", "운영자,매니저,스탭")

            # 게시판/카테고리/등급 필터 (DB 스키마 확인 필요 - 현재는 board_name만 있음)
            # 1. DB에서 게시판 목록 가져오기
            board_options = []
            try:
                if os.path.exists(current_db_path):
                    conn = sqlite3.connect(current_db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT board_name FROM posts WHERE board_name IS NOT NULL AND board_name != ''")
                    board_options = [row[0] for row in cursor.fetchall()]
                    conn.close()
            except:
                pass

            selected_boards = st.multiselect("게시판 필터 (비어있으면 전체)", board_options, default=[])

            # 등급 필터
            level_options = []
            try:
                if os.path.exists(current_db_path):
                    conn = sqlite3.connect(current_db_path)
                    cursor = conn.cursor()
                    # member_level 컬럼이 있는지 확인
                    cursor.execute("PRAGMA table_info(posts)")
                    cols = [row[1] for row in cursor.fetchall()]
                    if "member_level" in cols:
                        cursor.execute("SELECT DISTINCT member_level FROM posts WHERE member_level IS NOT NULL AND member_level != ''")
                        level_options = [row[0] for row in cursor.fetchall()]
                    conn.close()
            except:
                pass

            selected_levels = st.multiselect("등급 필터 (비어있으면 전체)", level_options, default=[])

            if st.button("🔍 타겟 검색", type="secondary", use_container_width=True):
                try:
                    if not os.path.exists(current_db_path):
                        st.warning("DB 없음")
                    else:
                        conn = sqlite3.connect(current_db_path)
                        cutoff_date = (datetime.now() - timedelta(days=days_lookback)).strftime("%Y-%m-%d")

                        # 동적 쿼리 생성
                        query_parts = [f"date >= '{cutoff_date}'"]

                        if selected_boards:
                            boards_str = "', '".join(selected_boards)
                            query_parts.append(f"board_name IN ('{boards_str}')")

                        if selected_levels:
                            levels_str = "', '".join(selected_levels)
                            query_parts.append(f"member_level IN ('{levels_str}')")

                        where_clause = " AND ".join(query_parts)

                        # member_level 컬럼 존재 여부 확인 후 쿼리
                        cursor = conn.cursor()
                        cursor.execute("PRAGMA table_info(posts)")
                        has_level_col = "member_level" in [row[1] for row in cursor.fetchall()]

                        sel_cols = "post_id, nickname, title, date, url, board_name"
                        if has_level_col:
                            sel_cols += ", member_level"

                        query = f"""
                            SELECT {sel_cols}
                            FROM posts
                            WHERE {where_clause}
                            ORDER BY date DESC
                            LIMIT 1000
                        """
                        df = pd.read_sql_query(query, conn)
                        conn.close()

                        excludes = [x.strip() for x in exclude_keyword.split(",") if x.strip()]
                        if excludes:
                            mask = df["nickname"].apply(lambda x: not any(exc in str(x) for exc in excludes))
                            df = df[mask]

                        st.session_state.target_df = df
                        st.success(f"{len(df)}건 검색 완료")
                except Exception as e:
                    st.error(f"검색 실패: {e}")

            # --- 1.1 등급 업데이트 도구 ---
            with st.expander("🛠️ 기존 데이터 등급 업데이트 (긴급)"):
                st.info("기존에 수집된 데이터에 '등급' 정보가 비어있는 경우, 다시 방문하여 채워넣습니다.")
                if st.button("등급 빈칸 채우기 시작"):
                    if not st.session_state.commenter or not st.session_state.commenter.driver:
                        st.error("브라우저 먼저 실행!")
                    else:
                        try:
                            conn = sqlite3.connect(current_db_path)
                            # member_level 컬럼 확인/추가
                            cursor = conn.cursor()
                            cursor.execute("PRAGMA table_info(posts)")
                            cols = [row[1] for row in cursor.fetchall()]
                            if "member_level" not in cols:
                                cursor.execute("ALTER TABLE posts ADD COLUMN member_level TEXT DEFAULT ''")
                                conn.commit()

                            # 등급 비어있는 글 조회
                            cursor.execute("SELECT post_id, url, nickname FROM posts WHERE member_level IS NULL OR member_level = ''")
                            targets = cursor.fetchall()
                            conn.close()

                            if not targets:
                                st.success("업데이트할 대상이 없습니다. (모두 등급 정보 있음)")
                            else:
                                progress = st.progress(0)
                                status = st.empty()
                                updated_count = 0

                                for i, (pid, url, nick) in enumerate(targets):
                                    status.text(f"업데이트 중: {i+1}/{len(targets)} - {nick}")

                                    # 상세 페이지 방문 (봇 재사용)
                                    detail = st.session_state.commenter.scrape_article_detail(url, "", [])
                                    lvl = detail.get("member_level", "")

                                    if lvl:
                                        conn = sqlite3.connect(current_db_path)
                                        cur = conn.cursor()
                                        cur.execute("UPDATE posts SET member_level = ? WHERE post_id = ?", (lvl, pid))
                                        conn.commit()
                                        conn.close()
                                        updated_count += 1

                                    progress.progress((i + 1) / len(targets))
                                    time.sleep(random.uniform(1.5, 3.0))  # 너무 빠르면 차단

                                st.success(f"완료! {updated_count}건의 등급 정보를 업데이트했습니다.")
                                st.rerun()

                        except Exception as e:
                            st.error(f"오류 발생: {e}")

        else:  # 이벤트 DB
            with st.expander("게시판 수집 설정", expanded=False):
                direct_board_url = st.text_input("게시판 URL", placeholder="https://cafe.naver.com/...")
                max_pages = st.number_input("페이지 수", 1, 50, 3)
                exclude_boards_input = st.text_input("제외 게시판", "공지사항")

                if st.button("수집 시작", use_container_width=True):
                    if not st.session_state.commenter or not st.session_state.commenter.driver:
                        st.error("브라우저 먼저 실행!")
                    else:
                        with st.spinner("수집 중..."):
                            start_dt = datetime.now() - timedelta(days=365)
                            end_dt = datetime.now()
                            excludes = [x.strip() for x in exclude_boards_input.split(",") if x.strip()]

                            articles = st.session_state.commenter.scrape_board_list(
                                direct_board_url,
                                start_dt,
                                end_dt,
                                exclude_boards=excludes,
                                max_pages=max_pages,
                            )
                            if articles:
                                save_articles_to_db(articles, EVENT_DB_PATH)
                                st.success(f"{len(articles)}건 저장 완료")
                                conn = sqlite3.connect(EVENT_DB_PATH)
                                df = pd.read_sql_query(
                                    "SELECT post_id, nickname, title, date, url, board_name FROM posts ORDER BY created_at DESC LIMIT 1000",
                                    conn,
                                )
                                conn.close()
                                st.session_state.target_df = df
                            else:
                                st.warning("수집 실패")

            if st.button("📂 저장된 목록 불러오기", use_container_width=True):
                if os.path.exists(EVENT_DB_PATH):
                    conn = sqlite3.connect(EVENT_DB_PATH)
                    df = pd.read_sql_query(
                        "SELECT post_id, nickname, title, date, url, board_name FROM posts ORDER BY created_at DESC LIMIT 1000",
                        conn,
                    )
                    conn.close()
                    st.session_state.target_df = df
                    st.success(f"{len(df)}건 로드 완료")
                else:
                    st.info("데이터 없음")

    with _col2:
        with st.container(border=True, key="commenter_settings_card_2", gap=None):
            render_settings_card_title("댓글 내용", icon="💬")
            st.session_state.template_list = load_templates()
            selected_template = st.selectbox(
                "템플릿", st.session_state.template_list, label_visibility="collapsed"
            )

            default_text = "" if selected_template == "(직접 입력)" else selected_template
            final_template = st.text_area(
                "댓글 내용 입력",
                value=default_text,
                height=150,
                help="{닉네임}, {제목} 치환 가능",
            )

            if st.button("💾 템플릿 저장", use_container_width=True):
                if final_template.strip():
                    save_new_template(final_template)
                    st.success("저장됨")
                    time.sleep(0.5)
                    st.rerun()

    with _col3:
        with st.container(border=True, key="commenter_settings_card_3", gap=None):
            render_settings_card_title("실행", icon="▶️")
            st.caption(f"메인 DB: {MAIN_DB_PATH}")
            if st.button("🌐 브라우저 열기", type="secondary", use_container_width=True):
                if not st.session_state.commenter:
                    st.session_state.commenter = NaverCafeCommenter(db_path=MAIN_DB_PATH, debug_mode=True)
                st.session_state.commenter.start_browser()
                st.success("브라우저 실행됨")

            if st.button("🚀 댓글 작성 시작", type="primary", use_container_width=True):
                if not st.session_state.commenter or not st.session_state.commenter.driver:
                    st.error("브라우저 미실행")
                elif (
                    "target_df" not in st.session_state
                    or st.session_state.target_df is None
                    or st.session_state.target_df.empty
                ):
                    st.error("타겟 없음")
                elif not final_template.strip():
                    st.error("내용 없음")
                else:
                    st.session_state.is_running = True

st.markdown("---")

# ==========================================
# 메인 화면 (데이터 확인 및 로그)
# ==========================================

# 1. 미리보기 영역
if final_template.strip():
    with st.expander("💬 댓글 미리보기", expanded=True):
        sample_nick = "홍길동"
        sample_title = "게시글 제목 예시"
        if st.session_state.target_df is not None and not st.session_state.target_df.empty:
            sample_nick = st.session_state.target_df.iloc[0]['nickname']
            sample_title = st.session_state.target_df.iloc[0]['title']
        
        preview_text = final_template.replace("{닉네임}", str(sample_nick)).replace("{제목}", str(sample_title))
        st.info(f"**To. {sample_nick}**: {preview_text}")

# 2. 타겟 목록 영역
st.subheader("📋 타겟 목록")
if st.session_state.target_df is not None and not st.session_state.target_df.empty:
    st.dataframe(
        st.session_state.target_df, 
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("게시글 링크"),
            "date": "작성일",
            "nickname": "작성자",
            "title": "제목"
        }
    )
else:
    st.info("👈 설정 영역에서 타겟을 검색하거나 불러와주세요.")

# 3. 실행 로직 (버튼 클릭 시 트리거된 상태 처리)
if st.session_state.get("is_running", False):
    st.markdown("---")
    st.subheader("🚀 작업 진행 중...")
    
    targets = st.session_state.target_df.to_dict('records')
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    log_msg(f"총 {len(targets)}개 글에 작업을 시작합니다.")
    
    for i, row in enumerate(targets):
        status_text.text(f"진행 중: {i+1}/{len(targets)} - {row['nickname']}님 글")
        
        log_msg(f"[{i+1}/{len(targets)}] '{row['title']}' ({row['nickname']}) 방문 중...")
        
        res = st.session_state.commenter.write_comment(
            article_url=row['url'],
            template=final_template,
            nickname=row['nickname'],
            title=row['title']
        )
        
        if res['status'] == 'success':
            log_msg(f"✅ 작성 성공")
        else:
            log_msg(f"❌ 실패: {res['message']}")
        
        progress_bar.progress((i + 1) / len(targets))
        
        # 휴식
        st.session_state.commenter.human_sleep(i + 1)
    
    st.session_state.is_running = False
    st.success("작업 완료!")
    st.balloons()

# 4. 로그 영역 (화면 표시 제거)
# st.markdown("---")
# with st.expander("📋 작업 로그 확인", expanded=True):
#     if st.session_state.comment_logs:
#         st.text_area("", "\n".join(reversed(st.session_state.comment_logs)), height=200)
#     else:
#         st.text("아직 로그가 없습니다.")
