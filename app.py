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
from app.products.scraper.crawler import NaverCafeCrawler
from app.utils.sqlite_db import init_db
from app.utils.paths import get_config_path, get_logs_dir, get_project_root, resolve_db_path
import shutil

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

config = load_config()
# DB 경로는 설정/환경변수로 변경 가능
DB_PATH = str(resolve_db_path(config.get("db_path")))

# 기존 DB가 있어도 CREATE TABLE IF NOT EXISTS는 안전하므로 항상 보장
init_db(DB_PATH)

def save_to_sqlite(post_data: dict, comments: list, replace_comments: bool = True):
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
                INSERT OR REPLACE INTO posts (
                    post_id, member_id, nickname, title, content, date, board_name, category, view_count, like_count, url, member_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_data['post_id'],
                post_data.get('member_id', 'unknown'),
                post_data['nickname'],
                post_data['title'],
                post_data['content'],
                post_data['date'],
                post_data.get('board_name', ''),
                post_data.get('category', ''),
                int(post_data.get('view_count', 0) or 0),
                int(post_data.get('like_count', 0) or 0),
                post_data['url'],
                post_data.get('member_level', ''),
            ))
            
            # 2. 댓글 저장 (재실행/업데이트 시 중복 방지 옵션)
            if replace_comments:
                cursor.execute("DELETE FROM comments WHERE post_id = ?", (post_data["post_id"],))
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
# with col_nav1:
#     if st.button("📚 논문 수집", width="stretch"):
#         _go_to_papers_page()
# with col_nav2:
    # page_link는 특정 환경에서 KeyError(url_pathname)로 앱을 죽여서 기본 사용은 보류
    # st.caption("페이지 목록이 안 보이면 Streamlit 재시작이 필요할 수 있습니다.")
# st.markdown("---")

st.markdown("""
<style>
    /* 로그 영역 스타일 개선 - 박스 제거 및 폰트 조정 */
    textarea[disabled] {
        background-color: transparent !important;
        border: none !important;
        color: #666 !important;
        font-family: monospace;
        font-size: 0.9em;
        padding: 0 !important;
        resize: none;
    }
</style>
""", unsafe_allow_html=True)

# 실시간 로그 출력을 위한 placeholder (사이드바 아래 또는 메인에 배치)
# log_placeholder = st.empty()

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
    # try:
    #     # 최근 20개 로그만 표시 - 제목 없이 깔끔하게 텍스트만
    #     recent_logs = "\n".join(reversed(st.session_state.status_messages[-20:]))
    #     log_placeholder.text_area("", recent_logs, height=300, label_visibility="collapsed", disabled=True)
    # except:
    #     pass  # UI 에러 무시

with st.sidebar:
    st.header("⚙️ 수집 설정")

    cafe_url = st.text_input("카페 URL", value=config.get("cafe_url", "https://cafe.naver.com/sundreamd"))
    board_url = st.text_input("게시판 URL (전체글보기 권장)", value=config.get("board_url", "https://cafe.naver.com/f-e/cafes/27870803/menus/0"))

    st.subheader("📅 수집 기간")
    default_start = datetime.now() - timedelta(days=365)
    if "start_date" in config:
        try:
            default_start = datetime.strptime(config["start_date"], "%Y-%m-%d")
        except:
            pass

    default_end = datetime.now()
    if "end_date" in config:
        try:
            default_end = datetime.strptime(config["end_date"], "%Y-%m-%d")
        except:
            pass

    col1, col2 = st.columns(2)
    start_date = col1.date_input("시작일", default_start)
    end_date = col2.date_input("종료일", default_end)

    with st.expander("🚫 제외 게시판 / 운영자 닉네임", expanded=False):
        admin_nicks = st.text_area(
            "운영자 닉네임 (쉼표로 구분)",
            value=config.get("admin_nicks", "마법사멀린, 멀린스타크, 멀린"),
        )
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
            height=160,
        )

    with st.expander("고급 옵션", expanded=False):
        st.session_state.debug_mode = st.checkbox("디버그 모드(상세 로그)", value=st.session_state.debug_mode)
        level_backfill = st.checkbox(
            "기존 글 등급 보강(member_level만)",
            value=bool(config.get("level_backfill", config.get("meta_backfill", False))),
        )

    st.markdown("---")
    if st.button("💾 설정 저장", width="stretch"):
        new_config = {
            "admin_nicks": admin_nicks,
            "exclude_boards": exclude_boards_text,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "cafe_url": cafe_url,
            "board_url": board_url,
            "level_backfill": bool(level_backfill),
            # 하위 호환: 기존 키를 읽는 코드가 있어도 동일 동작하도록 동기화
            "meta_backfill": bool(level_backfill),
            "db_path": str(config.get("db_path", "") or "").strip(),
        }
        save_config(new_config)
        st.success("✅ 설정이 저장되었습니다.")

    st.markdown("---")
    st.header("💾 데이터/DB")
    db_full_path = os.path.abspath(DB_PATH)
    exists = os.path.exists(db_full_path)
    try:
        size_mb = os.path.getsize(db_full_path) / (1024 * 1024) if exists else 0.0
        mtime = datetime.fromtimestamp(os.path.getmtime(db_full_path)).strftime("%Y-%m-%d %H:%M:%S") if exists else "-"
    except:
        size_mb, mtime = 0.0, "-"
    st.caption(f"경로: `{db_full_path}`")
    st.caption(f"파일: {'존재함' if exists else '없음'} · 크기: {size_mb:.2f}MB · 수정: {mtime}")

    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        post_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM posts", conn)['cnt'][0]
        comment_count = pd.read_sql_query("SELECT COUNT(*) as cnt FROM comments", conn)['cnt'][0]
        last_post_date = pd.read_sql_query("SELECT MAX(date) as d FROM posts", conn)["d"][0]
        last_created_at = pd.read_sql_query("SELECT MAX(created_at) as t FROM posts", conn)["t"][0]
        conn.close()
        col_stat1, col_stat2 = st.columns(2)
        col_stat1.metric("게시글", f"{int(post_count):,}")
        col_stat2.metric("댓글", f"{int(comment_count):,}")
        st.caption(f"최신 게시글 날짜: `{str(last_post_date) if last_post_date else '-'}`")
        st.caption(f"마지막 저장시각: `{str(last_created_at) if last_created_at else '-'}`")
    except:
        st.info("DB 통계를 읽을 수 없습니다.")

    col_db1, col_db2 = st.columns(2)
    with col_db1:
        if st.button("폴더 열기", width="stretch", key="open_db_folder"):
            try:
                import subprocess
                subprocess.run(['explorer', '/select,', db_full_path])
            except Exception as e:
                st.error(f"폴더 열기 실패: {e}")
    with col_db2:
        log_dir = str(get_logs_dir())
        if st.button("로그 폴더", width="stretch", key="open_log_folder"):
            try:
                import subprocess
                subprocess.run(['explorer', log_dir])
            except Exception as e:
                st.error(f"폴더 열기 실패: {e}")

    with st.expander("DB 위치 변경", expanded=False):
        db_path_override = st.text_input(
            "DB 파일 절대경로 (예: D:\\CafeBreaker\\cafe_data.db)",
            value=str(config.get("db_path", "") or ""),
            placeholder=r"D:\CafeBreaker\cafe_data.db",
            key="db_path_override_input",
        )
        st.caption("우선순위: 환경변수 `CAFESCRAPER_DB_PATH` > 여기 입력한 경로 > 기본값")
        st.caption(f"현재 입력값: `{(db_path_override or '').strip() or '(비어있음)'}`")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("경로 저장(파일 이동 없음)", width="stretch", key="apply_db_path_only"):
                target = (db_path_override or "").strip()
                if not target:
                    st.error("대상 DB 경로가 비어 있습니다.")
                else:
                    config["db_path"] = target
                    save_config(config)
                    st.success("✅ 저장 완료. 앱을 새로고침하세요.")
        with c2:
            if st.button("현재 DB 복사 + 전환", width="stretch", key="copy_db_and_apply"):
                target = (db_path_override or "").strip()
                if not target:
                    st.error("대상 DB 경로가 비어 있습니다.")
                else:
                    try:
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        shutil.copy2(db_full_path, target)
                        config["db_path"] = target
                        save_config(config)
                        st.success("✅ 복사/전환 완료. 앱을 새로고침하세요.")
                    except Exception as e:
                        st.error(f"복사/전환 실패: {e}")

# 메인 화면
step_col1, step_col2 = st.columns(2)

with step_col1:
    if st.button("1단계: 브라우저 열기", width="stretch"):
        if not st.session_state.crawler:
            # 수동 로그인 모드
            st.session_state.crawler = NaverCafeCrawler("", debug_mode=st.session_state.debug_mode)
            st.session_state.crawler.set_status_callback(update_logs)
        st.session_state.crawler.start_browser()
        update_logs()

with step_col2:
    if st.button("2단계: 크롤링 시작", type="primary", width="stretch"):
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
                # 과거 설정키(update_existing/meta_only) 호환:
                # - 기존: update_existing=True & meta_only=True => 기존글 보강 모드
                legacy_backfill = bool(config.get("update_existing", False)) and bool(config.get("meta_only", True))
                level_backfill_mode = (
                    bool(config.get("level_backfill", False))
                    or bool(config.get("meta_backfill", False))
                    or legacy_backfill
                )
                
                # 2단계: 상세 수집
                update_logs("🚀 2단계: 본문 및 댓글 상세 수집 시작...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                skip_count = 0
                error_count = 0
                updated_level_count = 0
                
                for i, art in enumerate(articles):
                    try:
                        # 30개마다 60초 휴식 (장시간 수집 시 차단 방지)
                        if i > 0 and i % 30 == 0:
                            update_logs(f"☕ 네이버 차단 방지를 위해 1분간 휴식합니다... ({i}/{len(articles)})")
                            time.sleep(60)

                        exists = art['post_id'] in existing_ids
                        if (not level_backfill_mode) and exists:
                            skip_count += 1
                            progress_bar.progress((i + 1) / len(articles))
                            continue

                        # ✅ 등급만 업데이트 모드: 기존 글은 본문/댓글 저장 없이 member_level만 보강
                        if exists and level_backfill_mode:
                            status_text.text(f"🏷️ 등급 보강 중: {art['title'][:40]}...")
                            update_logs(f"🏷️ 등급 보강: '{art['title'][:20]}...' ({i+1}/{len(articles)})")
                            try:
                                meta = st.session_state.crawler.get_article_meta(art["url"])
                                lvl = str(meta.get("member_level", "") or "").strip()

                                # API에서 비어있으면 상세 1회 폴백 (등급 추출 성공률 향상)
                                if not lvl:
                                    detail = st.session_state.crawler.scrape_article_detail(
                                        art["url"],
                                        art.get("member_id", "unknown"),
                                        admin_list
                                    )
                                    lvl = str(detail.get("member_level", "") or "").strip()

                                conn_u = sqlite3.connect(DB_PATH, timeout=30.0)
                                cur_u = conn_u.cursor()
                                if lvl:
                                    cur_u.execute(
                                        "UPDATE posts SET member_level = ? WHERE post_id = ?",
                                        (lvl, art["post_id"]),
                                    )
                                    updated_level_count += 1
                                conn_u.commit()
                                conn_u.close()
                            except Exception as meta_err:
                                error_count += 1
                                update_logs(f"⚠️ 등급 보강 실패: {meta_err}")

                            progress_bar.progress((i + 1) / len(articles))
                            # 등급 보강 모드는 상대적으로 가볍게
                            time.sleep(random.uniform(1.0, 2.5))
                            continue
                            
                        status_text.text(f"📄 수집 중: {art['title'][:40]}...")
                        update_logs(f"📄 '{art['title'][:20]}...' 수집 중 ({i+1}/{len(articles)})")
                        
                        # 상세 수집 (에러 방어)
                        try:
                            detail = st.session_state.crawler.scrape_article_detail(art['url'], art['member_id'], admin_list)
                            art['content'] = detail['content']
                            # 게시글 메타(조회수/좋아요/카테고리)
                            if detail.get("category"):
                                art["category"] = detail.get("category", "")
                            if detail.get("view_count") is not None:
                                art["view_count"] = detail.get("view_count", 0)
                            if detail.get("like_count") is not None:
                                art["like_count"] = detail.get("like_count", 0)
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
                if updated_level_count > 0:
                    update_logs(f"🏷️ 등급 보강 완료: {updated_level_count}개")
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
        post_show_limit = st.selectbox("표시 건수", options=[100, 500, 2000, 10000, "전체"], index=0, key="posts_show_limit")
        post_limit_sql = None if post_show_limit == "전체" else int(post_show_limit)
        df_posts = pd.read_sql_query(
            (
                "SELECT post_id, member_id, nickname, member_level, title, content, date, board_name, view_count, like_count, url "
                "FROM posts ORDER BY date DESC"
                + (f" LIMIT {post_limit_sql}" if post_limit_sql else "")
            ),
            conn,
        )
        
        if not df_posts.empty:
            st.write(f"**표시: {len(df_posts):,}개 게시글**")
            
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
                    "member_level": "등급",
                    "board_name": "게시판",
                    "view_count": "조회수",
                    "like_count": "좋아요",
                    "title": st.column_config.TextColumn("제목", width="medium"),
                    "본문미리보기": st.column_config.TextColumn("본문 미리보기", width="large"),
                    "date": "작성일",
                    "url": st.column_config.LinkColumn("URL")
                },
                hide_index=True,
                width="stretch",
                disabled=[
                    "post_id",
                    "member_id",
                    "nickname",
                    "member_level",
                    "board_name",
                    "view_count",
                    "like_count",
                    "title",
                    "본문미리보기",
                    "date",
                    "url",
                ],
                key=f"posts_editor_{st.session_state.posts_editor_refresh}"
            )
            
            # 선택된 항목 업데이트
            st.session_state.selected_posts = edited_df[edited_df["선택"] == True]['post_id'].tolist()
            
            # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
            st.markdown("---")
            col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
            with col_action1:
                if st.button("☑️ 전체 선택", width="stretch", key="select_all_posts"):
                    st.session_state.selected_posts = df_posts['post_id'].tolist()
                    st.session_state.posts_editor_refresh += 1
                    st.rerun()
            
            with col_action2:
                if st.button("⬜ 전체 해제", width="stretch", key="deselect_all_posts"):
                    st.session_state.selected_posts = []
                    st.session_state.posts_editor_refresh += 1
                    st.rerun()
            
            with col_action3:
                # 삭제 버튼 (선택된 항목이 있을 때만 활성화)
                if st.session_state.selected_posts:
                    if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_posts)})", type="primary", width="stretch", key="delete_posts"):
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
                    st.button("🗑️ 선택 항목 삭제", disabled=True, width="stretch", key="delete_posts_disabled")
            
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
                
                col_d1, col_d2, col_d3, col_d4 = st.columns([1, 1, 1, 1])
                col_d1.metric("작성자 ID", post_detail['member_id'])
                col_d2.metric("닉네임", post_detail['nickname'])
                col_d3.metric("등급", post_detail.get('member_level', ''))
                col_d4.metric("작성일", post_detail['date'])
                
                st.markdown(f"**제목:** {post_detail['title']}")
                st.markdown(f"**URL:** {post_detail['url']}")
                st.markdown("**본문:**")
                st.text_area("", post_detail['content'], height=300, disabled=True, label_visibility="collapsed")
                
                # 해당 게시글의 댓글 조회
                df_post_comments = pd.read_sql_query(f"SELECT * FROM comments WHERE post_id = '{selected_post_id}'", conn)
                if not df_post_comments.empty:
                    st.markdown(f"**💬 댓글 ({len(df_post_comments)}개)**")
                    st.dataframe(df_post_comments, width="stretch", hide_index=True)
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
        comment_show_limit = st.selectbox("표시 건수", options=[100, 500, 2000, 10000, "전체"], index=0, key="comments_show_limit")
        comment_limit_sql = None if comment_show_limit == "전체" else int(comment_show_limit)
        df_comments = pd.read_sql_query("""
            SELECT c.comment_id, c.post_id, c.writer_id, c.nickname, c.content, c.is_target, p.title as post_title
            FROM comments c
            LEFT JOIN posts p ON c.post_id = p.post_id
            ORDER BY c.comment_id DESC
        """ + (f"\nLIMIT {comment_limit_sql}\n" if comment_limit_sql else ""), conn)
        
        if not df_comments.empty:
            st.write(f"**표시: {len(df_comments):,}개 댓글**")
            
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
                width="stretch",
                disabled=["comment_id", "post_id", "writer_id", "nickname", "content", "is_target", "post_title"],
                key=f"comments_editor_{st.session_state.comments_editor_refresh}"
            )
            
            st.session_state.selected_comments = edited_comments[edited_comments["선택"] == True]['comment_id'].tolist()
            
            # 전체 선택/해제/삭제 버튼 (테이블 아래에 배치)
            st.markdown("---")
            col_action1, col_action2, col_action3 = st.columns([1, 1, 1])
            
            with col_action1:
                if st.button("☑️ 전체 선택", width="stretch", key="select_all_comments"):
                    st.session_state.selected_comments = df_comments['comment_id'].tolist()
                    st.session_state.comments_editor_refresh += 1
                    st.rerun()
            
            with col_action2:
                if st.button("⬜ 전체 해제", width="stretch", key="deselect_all_comments"):
                    st.session_state.selected_comments = []
                    st.session_state.comments_editor_refresh += 1
                    st.rerun()
            
            with col_action3:
                if st.session_state.selected_comments:
                    if st.button(f"🗑️ 선택 항목 삭제 ({len(st.session_state.selected_comments)})", type="primary", width="stretch", key="delete_comments"):
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
                    st.button("🗑️ 선택 항목 삭제", disabled=True, width="stretch", key="delete_comments_disabled")
        else:
            st.info("수집된 댓글이 없습니다.")
        
        conn.close()
    except Exception as e:
        st.error(f"DB 조회 중 오류: {e}")
