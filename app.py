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
from crawler import NaverCafeCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, get_logs_dir, get_project_root, resolve_db_path

# 페이지 설정
st.set_page_config(page_title="Project DAYBREAK - Cafe Scraper", layout="wide")

# 커스텀 CSS: 드롭다운 화살표 커서 스타일 개선
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

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

# 설정 로드 및 DB 경로 확정 (환경변수/설정값/기본값)
config = load_config()
DB_PATH = str(resolve_db_path(config.get("db_path")))

# 기존 DB가 있어도 CREATE TABLE IF NOT EXISTS는 안전하므로 항상 보장
init_db(DB_PATH)

def save_to_sqlite(post_data: dict, comments: list):
    """SQLite에 게시글 및 댓글 저장 (timeout 및 재시도 추가)"""
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            # timeout 30초로 증가 (잠금 해제 대기)
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()
            
            # 1. 게시글 저장 (Upsert)
            cursor.execute('''
                INSERT OR REPLACE INTO posts (post_id, member_id, nickname, title, content, date, board_name, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (post_data['post_id'], post_data.get('member_id', 'unknown'), post_data['nickname'], 
                  post_data['title'], post_data['content'], post_data['date'], 
                  post_data.get('board_name', ''), post_data['url']))
            
            # 2. 댓글 저장 (is_target: 본문 작성자 또는 운영자 댓글만)
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

# UI 구성
st.title("🌅 Project DAYBREAK: 네이버 카페 전략 크롤러")
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
with col_nav1:
    if st.button("📚 논문 수집", use_container_width=True):
        _go_to_papers_page()
with col_nav2:
    # page_link는 특정 환경에서 KeyError(url_pathname)로 앱을 죽여서 기본 사용은 보류
    st.caption("페이지 목록이 안 보이면 Streamlit 재시작이 필요할 수 있습니다.")
st.markdown("---")

# 실시간 로그 출력을 위한 placeholder (사이드바 아래 또는 메인에 배치)
log_placeholder = st.empty()

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
    try:
        log_placeholder.markdown("### 📋 실시간 로그")
        # 최근 20개 로그만 표시
        recent_logs = "\n\n".join(reversed(st.session_state.status_messages[-20:]))
        log_placeholder.text_area("", recent_logs, height=300, label_visibility="collapsed", disabled=True)
    except:
        pass  # UI 에러 무시

with st.sidebar:
    st.header("⚙️ 설정")
    admin_nicks = st.text_area("운영자 닉네임 (쉼표로 구분)", value=config.get("admin_nicks", "마법사멀린, 멀린스타크, 멀린"))

    st.subheader("🚫 제외 게시판")
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
        height=180,
    )
    
    st.subheader("📅 수집 기간")
    st.info("💡 11년치 수집 시 1년 단위로 끊어서 진행하는 것을 권장합니다.")
    
    default_start = datetime.now() - timedelta(days=365)
    if "start_date" in config:
        try: default_start = datetime.strptime(config["start_date"], "%Y-%m-%d")
        except: pass
        
    default_end = datetime.now()
    if "end_date" in config:
        try: default_end = datetime.strptime(config["end_date"], "%Y-%m-%d")
        except: pass

    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", default_start)
    end_date = col2.date_input("종료일", default_end)
    
    cafe_url = st.text_input("카페 URL", value=config.get("cafe_url", "https://cafe.naver.com/sundreamd"))
    board_url = st.text_input("게시판 URL (전체글보기 권장)", value=config.get("board_url", "https://cafe.naver.com/f-e/cafes/27870803/menus/0"))
    
    st.markdown("---")
    st.session_state.debug_mode = st.checkbox("🐞 디버그 모드 (상세 로그)", value=st.session_state.debug_mode)
    if st.session_state.debug_mode:
        st.info("디버그 모드: 각 게시글 분석 과정을 상세히 표시합니다 (속도 저하)")

    st.subheader("💾 DB 경로 (옵션)")
    db_path_override = st.text_input(
        "외부 DB 절대경로를 지정할 수 있어요 (비워두면 이 프로젝트 폴더의 cafe_data.db 사용)",
        value=str(config.get("db_path", "")),
        placeholder=r"D:\OtherProject\data\cafe_data.db",
    )
    st.caption("우선순위: 환경변수 `CAFESCRAPER_DB_PATH` > 여기 입력한 경로 > 기본값")

    if st.button("💾 설정 저장", use_container_width=True):
        new_config = {
            "admin_nicks": admin_nicks,
            "exclude_boards": exclude_boards_text,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "cafe_url": cafe_url,
            "board_url": board_url,
            "db_path": db_path_override.strip(),
        }
        save_config(new_config)
        st.success("✅ 설정이 로컬에 저장되었습니다! (DB 경로를 바꿨다면 앱이 자동으로 재시작됩니다)")
        st.rerun()
    
    # 로컬 DB 경로 및 통계
    st.markdown("---")
    st.subheader("💾 데이터베이스")
    db_full_path = os.path.abspath(DB_PATH)
    
    # DB 통계 실시간 표시
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        post_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM posts", conn)['cnt'][0]
        comment_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM comments", conn)['cnt'][0]
        conn.close()
        
        col_stat1, col_stat2 = st.columns(2)
        col_stat1.metric("📝 게시글", f"{post_count:,}개")
        col_stat2.metric("💬 댓글", f"{comment_count:,}개")
    except:
        st.info("DB가 아직 초기화되지 않았습니다.")
    
    st.caption(f"경로: {db_full_path}")
    
    col_db1, col_db2 = st.columns(2)
    with col_db1:
        if st.button("📂 폴더 열기", use_container_width=True):
            try:
                # 폴더를 열고 DB 파일을 선택 상태로 표시
                import subprocess
                subprocess.run(['explorer', '/select,', db_full_path])
                st.success("✅ 폴더를 열었습니다!")
            except Exception as e:
                st.error(f"폴더 열기 실패: {e}")
    
    with col_db2:
        # DB 뷰어 다운로드 링크
        st.link_button("📥 DB Browser 다운로드", "https://sqlitebrowser.org/dl/", use_container_width=True)
    
    # 로그 파일 보기
    st.markdown("---")
    st.subheader("📋 로그 파일")
    log_dir = str(get_logs_dir())
    log_file_today = os.path.join(log_dir, f"crawler_{datetime.now().strftime('%Y%m%d')}.log")
    
    if os.path.exists(log_file_today):
        st.caption(f"오늘 로그: {log_file_today}")
        if st.button("📂 로그 폴더 열기", use_container_width=True):
            try:
                import subprocess
                subprocess.run(['explorer', log_dir])
                st.success("✅ 로그 폴더를 열었습니다!")
            except Exception as e:
                st.error(f"폴더 열기 실패: {e}")
    else:
        st.info("아직 로그가 없습니다.")

# 메인 화면
step_col1, step_col2 = st.columns(2)

with step_col1:
    if st.button("1단계: 브라우저 열기", use_container_width=True):
        if not st.session_state.crawler:
            # 수동 로그인 모드
            st.session_state.crawler = NaverCafeCrawler("", debug_mode=st.session_state.debug_mode)
            st.session_state.crawler.set_status_callback(update_logs)
        st.session_state.crawler.start_browser()
        update_logs()

with step_col2:
    if st.button("2단계: 크롤링 시작", type="primary", use_container_width=True):
        if not st.session_state.crawler or not st.session_state.crawler.driver:
            st.error("먼저 브라우저를 열어주세요.")
        else:
            admin_list = [n.strip() for n in admin_nicks.split(",") if n.strip()]
            st.session_state.crawler.admin_nickname = admin_list[0] if admin_list else "멀린"
            
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            
            # 1단계: 리스트 수집
            update_logs("🔍 1단계: 대상 게시글 목록 확보 시작...")
            exclude_boards = [x.strip() for x in (exclude_boards_text or "").splitlines() if x.strip()]
            articles = st.session_state.crawler.scrape_board_list(board_url, start_dt, end_dt, exclude_boards=exclude_boards)
            
            if articles:
                update_logs(f"✅ 총 {len(articles)}개의 대상 게시글을 찾았습니다.")
                
                # 중복 체크
                conn = sqlite3.connect(DB_PATH, timeout=30.0)
                existing_ids = pd.read_sql_query("SELECT post_id FROM posts", conn)['post_id'].tolist()
                conn.close()
                
                # 2단계: 상세 수집
                update_logs("🚀 2단계: 본문 및 댓글 상세 수집 시작...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                skip_count = 0
                error_count = 0
                
                for i, art in enumerate(articles):
                    try:
                        if art['post_id'] in existing_ids:
                            skip_count += 1
                            progress_bar.progress((i + 1) / len(articles))
                            continue
                            
                        status_text.text(f"📄 수집 중: {art['title'][:40]}...")
                        update_logs(f"📄 '{art['title'][:20]}...' 수집 중 ({i+1}/{len(articles)})")
                        
                        # 상세 수집 (에러 방어)
                        try:
                            detail = st.session_state.crawler.scrape_article_detail(art['url'], art['member_id'], admin_list)
                            art['content'] = detail['content']
                            # 상세에서 API/레이어로 보강된 작성자 ID 반영
                            if detail.get("member_id") and detail.get("member_id") != "unknown":
                                art["member_id"] = detail["member_id"]
                            # 게시글 리스트에서 닉네임 unknown인 경우, 상세(API) 닉네임으로 보강
                            if (not art.get("nickname") or art.get("nickname") == "unknown") and detail.get("nickname") and detail.get("nickname") != "unknown":
                                art["nickname"] = detail["nickname"]
                            # 게시판 이름 보강
                            if (not art.get("board_name")) and detail.get("board_name"):
                                art["board_name"] = detail["board_name"]
                            
                            save_to_sqlite(art, detail['comments'])
                            update_logs(f"✅ '{art['title'][:20]}...' 저장 완료")
                        except Exception as detail_error:
                            error_count += 1
                            update_logs(f"⚠️ '{art['title'][:20]}...' 수집 실패: {detail_error}")
                            # 실패해도 계속 진행
                        
                        progress_bar.progress((i + 1) / len(articles))
                        
                        # IP 차단 방지: 게시글 간 충분한 대기 시간
                        delay = random.uniform(3, 7)
                        time.sleep(delay)
                        
                    except Exception as loop_error:
                        error_count += 1
                        update_logs(f"❌ 항목 {i+1} 처리 중 오류: {loop_error}")
                        progress_bar.progress((i + 1) / len(articles))
                        continue
                
                # 최종 결과 표시
                if skip_count > 0:
                    update_logs(f"💡 기존 수집분 {skip_count}개를 건너뛰었습니다.")
                if error_count > 0:
                    update_logs(f"⚠️ {error_count}개 항목 수집 실패 (나머지는 정상 처리)")
                
                success_count = len(articles) - skip_count - error_count
                if success_count > 0:
                    st.balloons()
                    update_logs(f"✨ {success_count}개 게시글 수집 완료!")
                
                status_text.text(f"✅ 작업 완료 (성공: {success_count}, 스킵: {skip_count}, 실패: {error_count})")
            else:
                update_logs("⚠️ 수집된 게시글이 없습니다. 기간이나 URL을 확인해 주세요.")

# 초기 로그 표시
update_logs()

# DB 관리 UI (데이터 조회 및 삭제)
st.markdown("---")
st.header("📊 데이터 관리")

if "posts_editor_refresh" not in st.session_state:
    st.session_state.posts_editor_refresh = 0
if "comments_editor_refresh" not in st.session_state:
    st.session_state.comments_editor_refresh = 0

tab1, tab2 = st.tabs(["📝 게시글 관리", "💬 댓글 관리"])

with tab1:
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        df_posts = pd.read_sql_query("SELECT post_id, member_id, nickname, title, content, date, url FROM posts ORDER BY date DESC LIMIT 100", conn)
        
        if not df_posts.empty:
            st.write(f"**총 {len(df_posts)}개 게시글** (최근 100개 표시)")
            
            # 선택된 게시글 저장
            if "selected_posts" not in st.session_state:
                st.session_state.selected_posts = []
            
            # 데이터 에디터 (체크박스 포함)
            df_display = df_posts.copy()
            df_display.insert(0, "선택", False)
            
            # content는 미리보기로 (100자만)
            df_display['본문미리보기'] = df_display['content'].apply(lambda x: str(x)[:100] + '...' if x and len(str(x)) > 100 else str(x))
            df_display = df_display.drop(columns=['content'])  # 전체 본문은 숨김
            
            # 이전 선택 복원
            for idx, post_id in enumerate(df_display['post_id']):
                if post_id in st.session_state.selected_posts:
                    df_display.at[idx, "선택"] = True
            
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "선택": st.column_config.CheckboxColumn("선택", default=False),
                    "post_id": "게시글 ID",
                    "member_id": "작성자 ID",
                    "nickname": "닉네임",
                    "title": st.column_config.TextColumn("제목", width="medium"),
                    "본문미리보기": st.column_config.TextColumn("본문 미리보기", width="large"),
                    "date": "작성일",
                    "url": st.column_config.LinkColumn("URL")
                },
                hide_index=True,
                use_container_width=True,
                disabled=["post_id", "member_id", "nickname", "title", "본문미리보기", "date", "url"],
                key=f"posts_editor_{st.session_state.posts_editor_refresh}"
            )
            
            # 선택된 항목 업데이트
            st.session_state.selected_posts = edited_df[edited_df["선택"] == True]['post_id'].tolist()
            
            # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
            st.markdown("---")
            col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
            with col_action1:
                if st.button("☑️ 전체 선택", use_container_width=True, key="select_all_posts"):
                    st.session_state.selected_posts = df_posts['post_id'].tolist()
                    st.session_state.posts_editor_refresh += 1
                    st.rerun()
            
            with col_action2:
                if st.button("⬜ 전체 해제", use_container_width=True, key="deselect_all_posts"):
                    st.session_state.selected_posts = []
                    st.session_state.posts_editor_refresh += 1
                    st.rerun()
            
            with col_action3:
                # 삭제 버튼 (선택된 항목이 있을 때만 활성화)
                if st.session_state.selected_posts:
                    if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_posts)})", type="primary", use_container_width=True, key="delete_posts"):
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
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")
                else:
                    st.button("🗑️ 선택 항목 삭제", disabled=True, use_container_width=True, key="delete_posts_disabled")
            
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
                
                col_d1, col_d2, col_d3 = st.columns([1, 1, 2])
                col_d1.metric("작성자 ID", post_detail['member_id'])
                col_d2.metric("닉네임", post_detail['nickname'])
                col_d3.metric("작성일", post_detail['date'])
                
                st.markdown(f"**제목:** {post_detail['title']}")
                st.markdown(f"**URL:** {post_detail['url']}")
                st.markdown("**본문:**")
                st.text_area("", post_detail['content'], height=300, disabled=True, label_visibility="collapsed")
                
                # 해당 게시글의 댓글 조회
                df_post_comments = pd.read_sql_query(f"SELECT * FROM comments WHERE post_id = '{selected_post_id}'", conn)
                if not df_post_comments.empty:
                    st.markdown(f"**💬 댓글 ({len(df_post_comments)}개)**")
                    st.dataframe(df_post_comments, use_container_width=True, hide_index=True)
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
            LIMIT 100
        """, conn)
        
        if not df_comments.empty:
            st.write(f"**총 {len(df_comments)}개 댓글** (최근 100개 표시)")
            
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
                use_container_width=True,
                disabled=["comment_id", "post_id", "writer_id", "nickname", "content", "is_target", "post_title"],
                key=f"comments_editor_{st.session_state.comments_editor_refresh}"
            )
            
            st.session_state.selected_comments = edited_comments[edited_comments["선택"] == True]['comment_id'].tolist()
            
            # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
            st.markdown("---")
            col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
            with col_action1:
                if st.button("☑️ 전체 선택", use_container_width=True, key="select_all_comments"):
                    st.session_state.selected_comments = df_comments['comment_id'].tolist()
                    st.session_state.comments_editor_refresh += 1
                    st.rerun()
            
            with col_action2:
                if st.button("⬜ 전체 해제", use_container_width=True, key="deselect_all_comments"):
                    st.session_state.selected_comments = []
                    st.session_state.comments_editor_refresh += 1
                    st.rerun()
            
            with col_action3:
                if st.session_state.selected_comments:
                    if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_comments)})", type="primary", use_container_width=True, key="delete_comments"):
                        try:
                            cursor = conn.cursor()
                            for comment_id in st.session_state.selected_comments:
                                cursor.execute("DELETE FROM comments WHERE comment_id = ?", (comment_id,))
                            conn.commit()
                            st.success(f"✅ {len(st.session_state.selected_comments)}개 댓글이 삭제되었습니다!")
                            st.session_state.selected_comments = []
                            st.session_state.comments_editor_refresh += 1
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")
                else:
                    st.button("🗑️ 선택 항목 삭제", disabled=True, use_container_width=True, key="delete_comments_disabled")
        else:
            st.info("수집된 댓글이 없습니다.")
        
        conn.close()
    except Exception as e:
        st.error(f"DB 조회 중 오류: {e}")
