"""
네이버 카페 크롤러 - Streamlit GUI 애플리케이션
로컬에서 실행하는 크롤링 도구
"""
import os
import sys
import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# .env 파일 로드
load_dotenv(project_root / ".env")

# 설정 파일 경로
CONFIG_FILE = project_root / "crawler_config.json"

from crawler import NaverCafeCrawler

# CSV 저장 함수 (간단한 버전)
def save_to_csv(results, output_dir="outputs"):
    """결과를 CSV로 저장"""
    import csv
    import os
    from datetime import datetime
    import orjson
    
    date_dir = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(output_dir, date_dir)
    os.makedirs(target_dir, exist_ok=True)
    
    csv_name = datetime.now().strftime("articles_%Y%m%d.csv")
    csv_path = os.path.join(target_dir, csv_name)
    
    fields = [
        "cafe_id", "article_id", "article_url", "title", "author_nickname",
        "posted_at", "content_text", "content_html", "images_base64_json",
        "comments_json", "scraped_at"
    ]
    
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not file_exists:
            writer.writeheader()
        
        for result in results:
            if "error" not in result:
                row = {
                    "cafe_id": result.get("cafe_id", ""),
                    "article_id": result.get("article_id", ""),
                    "article_url": result.get("article_url", ""),
                    "title": result.get("title", ""),
                    "author_nickname": result.get("author_nickname", ""),
                    "posted_at": result.get("posted_at") or "",
                    "content_text": result.get("content_text", ""),
                    "content_html": result.get("content_html", ""),
                    "images_base64_json": orjson.dumps(result.get("images_base64", [])).decode(),
                    "comments_json": orjson.dumps(result.get("comments", [])).decode(),
                    "scraped_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
                writer.writerow(row)
    
    return csv_path

# 페이지 설정
st.set_page_config(
    page_title="네이버 카페 크롤러",
    page_icon="☕",
    layout="wide"
)

# 제목
st.title("☕ 네이버 카페 크롤러")
st.markdown("---")

# 크롬 프로필 경로 자동 감지
def get_default_chrome_profile_path():
    r"""Windows에서 크롬 프로필 경로 자동 감지
    
    크롬의 --user-data-dir 옵션은 User Data 폴더의 부모 디렉토리(Chrome 폴더)를 지정해야 합니다.
    예: C:\Users\사용자명\AppData\Local\Google\Chrome
    프로필은 자동으로 Default를 사용합니다.
    """
    username = os.getenv('USERNAME') or os.getenv('USER')
    if username:
        # User Data 폴더의 부모 디렉토리 (Chrome 폴더)
        chrome_dir = rf"C:\Users\{username}\AppData\Local\Google\Chrome"
        user_data_dir = os.path.join(chrome_dir, "User Data")
        
        # User Data 폴더가 존재하는지 확인
        if os.path.exists(user_data_dir):
            # user-data-dir은 Chrome 폴더를 지정 (User Data의 부모)
            return chrome_dir
    return ""

# Supabase 클라이언트 초기화 함수
def init_supabase(url: str, key: str):
    """Supabase 클라이언트 초기화"""
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(url, key)
        return supabase
    except Exception as e:
        return None

# Supabase에 데이터 저장 (Upsert)
def save_to_supabase(supabase, table_name: str, results: list, cafe_name: str = "", keyword: str = "", status_callback=None):
    """결과를 Supabase에 Upsert (link 기준) - 실제 테이블 스키마에 맞춤"""
    if not supabase:
        return {"success": 0, "failed": len(results), "errors": ["Supabase 클라이언트가 초기화되지 않았습니다."]}
    
    import hashlib
    
    success_count = 0
    failed_count = 0
    errors = []
    
    for result in results:
        if "error" in result:
            failed_count += 1
            continue
        
        try:
            content = result.get("content_text", "")
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest() if content else ""
            
            # 1. 게시글 저장 (cafe_posts)
            post_data = {
                "link": result.get("article_url", ""),
                "cafe_name": cafe_name or result.get("cafe_id", ""),
                "keyword": keyword or "",
                "title": result.get("title", ""),
                "content": content,
                "author": result.get("author_nickname", ""),
                "date": result.get("posted_at", ""),
                "content_hash": content_hash,
                "vector_status": False # 기본값
            }
            
            # Upsert 실행
            post_response = supabase.table(table_name).upsert(
                post_data,
                on_conflict="link"
            ).execute()
            
            # 저장된 게시글의 ID 가져오기 (댓글 저장을 위해)
            post_id = None
            if post_response.data:
                post_id = post_response.data[0].get("id")
            
            # 2. 댓글 저장 (cafe_comments) - 댓글이 있는 경우
            comments = result.get("comments", [])
            if post_id and comments:
                comment_table = "cafe_comments"
                for comment in comments:
                    try:
                        c_content = comment.get("text", "")
                        c_hash = hashlib.md5(c_content.encode('utf-8')).hexdigest() if c_content else ""
                        
                        comment_data = {
                            "post_id": post_id,
                            "content": c_content,
                            "author": comment.get("nickname", ""),
                            "date": comment.get("created_at", ""),
                            "link": result.get("article_url", ""), # 원본 글 링크 참조
                            "content_hash": c_hash
                        }
                        supabase.table(comment_table).upsert(comment_data).execute()
                    except Exception as ce:
                        if status_callback:
                            status_callback(f"⚠️ 댓글 저장 실패: {str(ce)}")
            
            success_count += 1
            if status_callback:
                status_callback(f"✅ DB 저장 완료: {result.get('title', '')[:20]}... (댓글 {len(comments)}개)")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"DB 저장 실패 ({result.get('article_url', '')}): {str(e)}"
            errors.append(error_msg)
            if status_callback:
                status_callback(f"❌ {error_msg}")
    
    return {
        "success": success_count,
        "failed": failed_count,
        "total": len(results),
        "errors": errors
    }

# 설정 저장/불러오기 함수
def save_config(config: dict):
    """설정을 JSON 파일로 저장"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        return False

def load_config():
    """저장된 설정을 JSON 파일에서 불러오기"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        pass
    return {}

# 저장된 설정 불러오기
saved_config = load_config()

# 세션 상태 초기화
if 'crawler' not in st.session_state:
    st.session_state.crawler = None
if 'status_messages' not in st.session_state:
    st.session_state.status_messages = []
if 'results' not in st.session_state:
    st.session_state.results = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False

# 사이드바 - 설정
with st.sidebar:
    st.header("⚙️ 설정")
    
    # 크롬 프로필 경로
    default_profile = get_default_chrome_profile_path()
    saved_profile = saved_config.get('chrome_profile_path', default_profile)
    chrome_profile_path = st.text_input(
        "크롬 프로필 경로",
        value=saved_profile,
        help="크롬 브라우저의 Chrome 디렉토리 경로를 입력하세요 (User Data의 부모 폴더).\n예: C:\\Users\\사용자명\\AppData\\Local\\Google\\Chrome\n⚠️ User Data 폴더가 아닌 Chrome 폴더를 지정하세요!"
    )
    
    st.markdown("---")
    
    # 크롤링 모드 선택
    saved_mode = saved_config.get('crawl_mode', "게시판 수집")
    mode_options = ["게시판 수집", "작성자별 수집", "키워드 검색", "댓글만 수집"]
    mode_index = mode_options.index(saved_mode) if saved_mode in mode_options else 0
    crawl_mode = st.radio(
        "크롤링 모드",
        mode_options,
        index=mode_index,
        help="수집 방식을 선택하세요"
    )
    
    st.markdown("---")
    
    # 공통 설정
    cafe_url = st.text_input(
        "카페 URL",
        value=saved_config.get('cafe_url', ''),
        placeholder="https://cafe.naver.com/yourcafe",
        help="크롤링할 네이버 카페 URL을 입력하세요"
    )
    
    max_pages = st.number_input(
        "최대 페이지 수",
        min_value=1,
        max_value=100,
        value=saved_config.get('max_pages', 5),
        help="수집할 최대 페이지 수"
    )
    
    # 날짜 처리
    saved_cutoff = saved_config.get('cutoff_date')
    cutoff_date_value = None
    if saved_cutoff:
        try:
            cutoff_date_value = datetime.strptime(saved_cutoff, "%Y-%m-%d").date()
        except:
            cutoff_date_value = None
    
    cutoff_date = st.date_input(
        "수집 종료 날짜",
        value=cutoff_date_value,
        help="이 날짜 이전의 게시글은 수집하지 않습니다"
    )
    
    # 모드별 추가 설정
    board_mode = None
    board_url = None
    search_keyword = None
    author_nickname = None
    comment_author_nickname = None
    exclude_own_posts = True
    
    if crawl_mode == "게시판 수집":
        saved_board_mode = saved_config.get('board_mode', '전체 게시판')
        board_mode_index = 0 if saved_board_mode == "전체 게시판" else 1
        board_mode = st.radio(
            "게시판 선택",
            ["전체 게시판", "특정 게시판"],
            index=board_mode_index,
            help="전체 게시판을 수집할지, 특정 게시판만 수집할지 선택하세요"
        )
        
        if board_mode == "전체 게시판":
            board_url = None
            st.info("💡 카페의 모든 게시판을 수집합니다.")
        else:
            board_url = st.text_input(
                "게시판 URL",
                value=saved_config.get('board_url', ''),
                placeholder="https://cafe.naver.com/yourcafe/BoardList.nhn?clubid=...&menuid=...",
                help="수집할 게시판 URL을 입력하세요"
            )
    
    elif crawl_mode == "작성자별 수집":
        author_nickname = st.text_input(
            "작성자 닉네임",
            value=saved_config.get('author_nickname', ''),
            placeholder="작성자 닉네임을 입력하세요",
            help="특정 작성자의 모든 게시글을 수집합니다"
        )
    
    elif crawl_mode == "키워드 검색":
        search_keyword = st.text_input(
            "검색 키워드",
            value=saved_config.get('search_keyword', ''),
            placeholder="검색할 키워드를 입력하세요",
            help="카페 내에서 키워드로 검색하여 게시글을 수집합니다"
        )
    
    elif crawl_mode == "댓글만 수집":
        comment_author_nickname = st.text_input(
            "댓글 작성자 닉네임",
            value=saved_config.get('comment_author_nickname', ''),
            placeholder="댓글을 수집할 닉네임을 입력하세요",
            help="이 닉네임이 작성한 댓글을 수집합니다"
        )
        exclude_own_posts = st.checkbox(
            "내 게시글 제외",
            value=saved_config.get('exclude_own_posts', True),
            help="댓글 작성자와 게시글 작성자가 같으면 제외합니다"
        )
        st.info("💡 카페 전체를 순회하며 해당 닉네임의 댓글이 있는 게시글을 찾아 수집합니다.")
    
    
    st.markdown("---")
    
    # 댓글 필터링
    st.subheader("💬 댓글 필터링")
    st.caption("ℹ️ **수집된 게시글에 달린 댓글** 중에서 필터링합니다.")
    
    saved_include_nicks = saved_config.get('include_nicks', '')
    saved_exclude_nicks = saved_config.get('exclude_nicks', '')
    
    include_nicks_input = st.text_input(
        "포함할 닉네임 (쉼표로 구분)",
        value=saved_include_nicks,
        placeholder="멀린, 큐레이터",
        help="수집된 게시글의 댓글 중, 이 닉네임들이 작성한 댓글만 포함합니다"
    )
    exclude_nicks_input = st.text_input(
        "제외할 닉네임 (쉼표로 구분)",
        value=saved_exclude_nicks,
        placeholder="관리자",
        help="수집된 게시글의 댓글 중, 이 닉네임들이 작성한 댓글은 제외합니다"
    )
    
    include_nicks = [n.strip() for n in include_nicks_input.split(",") if n.strip()] if include_nicks_input else None
    exclude_nicks = [n.strip() for n in exclude_nicks_input.split(",") if n.strip()] if exclude_nicks_input else None
    
    st.markdown("---")
    
    # .env에서 Supabase 설정 자동 불러오기 (UI에 표시하지 않음)
    supabase_url = os.getenv('SUPABASE_URL', '')
    supabase_key = os.getenv('SUPABASE_KEY', '')
    table_name = os.getenv('SUPABASE_TABLE_NAME', 'cafe_posts')
    
    # 설정 저장 버튼
    col_save1, col_save2 = st.columns(2)
    with col_save1:
        if st.button("💾 설정 저장", use_container_width=True):
            config_to_save = {
                'chrome_profile_path': chrome_profile_path,
                'crawl_mode': crawl_mode,
                'cafe_url': cafe_url,
                'max_pages': max_pages,
                'cutoff_date': cutoff_date.strftime("%Y-%m-%d") if cutoff_date else None,
                'board_mode': board_mode if crawl_mode == "게시판 수집" else None,
                'board_url': board_url if crawl_mode == "게시판 수집" else None,
                'author_nickname': author_nickname if crawl_mode == "작성자별 수집" else None,
                'search_keyword': search_keyword if crawl_mode == "키워드 검색" else None,
                'comment_author_nickname': comment_author_nickname if crawl_mode == "댓글만 수집" else None,
                'exclude_own_posts': exclude_own_posts if crawl_mode == "댓글만 수집" else None,
                'include_nicks': include_nicks_input,
                'exclude_nicks': exclude_nicks_input,
            }
            if save_config(config_to_save):
                st.success("✅ 설정이 저장되었습니다!")
            else:
                st.error("❌ 설정 저장 실패")
    
    with col_save2:
        if st.button("🗑️ 설정 초기화", use_container_width=True):
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
            st.success("✅ 설정이 초기화되었습니다!")
            st.rerun()

# 메인 영역
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📊 크롤링 실행")
    
    # 2단계 실행 버튼 UI
    step_col1, step_col2 = st.columns(2)
    
    with step_col1:
        # 1단계 버튼
        if st.button("🌐 1단계: 브라우저 열기", use_container_width=True, help="크롬 브라우저를 먼저 띄웁니다. 실행 후 직접 로그인을 해주세요."):
            st.session_state.is_running = True
            st.session_state.status_messages = []
            
            # 크롤러 초기화 및 브라우저 시작
            try:
                if st.session_state.crawler:
                    st.session_state.crawler.close()
                
                from crawler import NaverCafeCrawler
                st.session_state.crawler = NaverCafeCrawler(chrome_profile_path=chrome_profile_path if chrome_profile_path else "")
                
                # 상태 콜백 설정
                def status_callback(message):
                    if 'status_messages' not in st.session_state:
                        st.session_state.status_messages = []
                    st.session_state.status_messages.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "message": message
                    })
                
                st.session_state.crawler.set_status_callback(status_callback)
                st.session_state.crawler.start_browser()
                
                st.success("✅ 브라우저가 실행되었습니다! 이제 네이버 로그인을 완료한 후 2단계를 클릭하세요.")
                st.session_state.is_running = False
            except Exception as e:
                st.error(f"❌ 브라우저 실행 실패: {e}")
                st.session_state.is_running = False

    with step_col2:
        # 2단계 버튼
        start_button = st.button("🚀 2단계: 크롤링 시작", type="primary", use_container_width=True, disabled=st.session_state.is_running)

    if start_button:
        if not st.session_state.crawler:
            st.error("❌ 1단계 '브라우저 열기'를 먼저 완료해 주세요.")
        elif not cafe_url:
            st.error("❌ 카페 URL을 입력하세요.")
        else:
            st.session_state.is_running = True
            # 결과 초기화 (누적하지 않으려면)
            st.session_state.results = []
            
            try:
                crawler = st.session_state.crawler
                
                # 상태 콜백 설정
                def status_callback(message):
                    if 'status_messages' not in st.session_state:
                        st.session_state.status_messages = []
                    
                    # 새로운 메시지 추가
                    new_msg = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "message": message
                    }
                    st.session_state.status_messages.append(new_msg)
                
                crawler.set_status_callback(status_callback)
                
                status_callback("🚀 크롤링 프로세스 시작...")
                
                # 모드별 입력 검증
                is_valid = True
                if crawl_mode == "게시판 수집" and board_mode == "특정 게시판" and not board_url:
                    st.error("❌ 게시판 URL을 입력하세요.")
                    is_valid = False
                elif crawl_mode == "작성자별 수집" and not author_nickname:
                    st.error("❌ 작성자 닉네임을 입력하세요.")
                    is_valid = False
                elif crawl_mode == "키워드 검색" and not search_keyword:
                    st.error("❌ 검색 키워드를 입력하세요.")
                    is_valid = False
                elif crawl_mode == "댓글만 수집" and not comment_author_nickname:
                    st.error("❌ 댓글 작성자 닉네임을 입력하세요.")
                    is_valid = False
                
                if not is_valid:
                    st.session_state.is_running = False
                    st.rerun()

                articles = []
                
                if crawl_mode == "게시판 수집":
                    cutoff = datetime.combine(cutoff_date, datetime.min.time()) if cutoff_date else None
                    
                    if board_mode == "전체 게시판":
                        # 전체 게시판 수집 (현재 페이지 우선)
                        boards = crawler.get_cafe_boards(cafe_url)
                        
                        if not boards:
                            status_callback("❌ 게시판을 찾을 수 없습니다.")
                            articles = []
                        else:
                            status_callback(f"📋 발견된 게시판: {len(boards)}개")
                            all_articles = []
                            
                            for i, board in enumerate(boards, 1):
                                status_callback(f"게시판 {i}/{len(boards)}: {board['menu_name']} 처리 중...")
                                board_articles = crawler.scrape_board_articles(board['board_url'], max_pages, cutoff)
                                all_articles.extend(board_articles)
                                
                                if i < len(boards):
                                    import random
                                    delay = random.uniform(3, 8)
                                    time.sleep(delay)  # 게시판 간 딜레이
                            
                            articles = all_articles
                    else:
                        # 특정 게시판 수집
                        articles = crawler.scrape_board_articles(board_url, max_pages, cutoff)
                
                elif crawl_mode == "작성자별 수집":
                    cutoff = datetime.combine(cutoff_date, datetime.min.time()) if cutoff_date else None
                    articles = crawler.get_articles_by_author(cafe_url, author_nickname, max_pages, cutoff)
                
                elif crawl_mode == "키워드 검색":
                    crawler.navigate_to_cafe(cafe_url)
                    cutoff = datetime.combine(cutoff_date, datetime.min.time()) if cutoff_date else None
                    articles = crawler.search_in_cafe(search_keyword, max_pages, cutoff)
                
                elif crawl_mode == "댓글만 수집":
                    cutoff = datetime.combine(cutoff_date, datetime.min.time()) if cutoff_date else None
                    articles = crawler.scrape_comments_only(
                        cafe_url, 
                        comment_author_nickname, 
                        exclude_own_posts, 
                        max_pages, 
                        cutoff
                    )
                
                # 게시글 상세 수집
                if articles:
                    article_urls = [a["article_url"] for a in articles]
                    # 댓글만 수집 모드의 경우, 댓글 필터링 적용
                    if crawl_mode == "댓글만 수집":
                        # 댓글 작성자 닉네임만 포함하도록 필터링
                        comment_filter = [comment_author_nickname] if comment_author_nickname else None
                        results = crawler.scrape_multiple_articles(article_urls, comment_filter, exclude_nicks)
                    else:
                        results = crawler.scrape_multiple_articles(article_urls, include_nicks, exclude_nicks)
                    
                    # CSV 저장
                    csv_path = save_to_csv(results, "outputs")
                    status_callback(f"💾 CSV 저장 완료: {csv_path}")
                    
                    # Supabase 저장 (10건 단위로 배치 처리)
                    db_stats = {"success": 0, "failed": 0, "total": 0}
                    if supabase_url and supabase_key and table_name:
                        supabase_client = init_supabase(supabase_url, supabase_key)
                        if supabase_client:
                            status_callback("🗄️ DB 저장 시작...")
                            
                            # 10건 단위로 배치 처리
                            batch_size = 10
                            for i in range(0, len(results), batch_size):
                                batch = results[i:i+batch_size]
                                batch_num = (i // batch_size) + 1
                                total_batches = (len(results) + batch_size - 1) // batch_size
                                
                                status_callback(f"📦 DB 배치 저장 중... ({batch_num}/{total_batches})")
                                # 카페 이름과 키워드 추출 (크롤링 모드에 따라)
                                current_cafe_name = cafe_url.split("/")[-1] if cafe_url else ""
                                current_keyword = search_keyword if crawl_mode == "키워드 검색" else ""
                                batch_result = save_to_supabase(supabase_client, table_name, batch, current_cafe_name, current_keyword, status_callback)
                                
                                db_stats["success"] += batch_result["success"]
                                db_stats["failed"] += batch_result["failed"]
                                db_stats["total"] += batch_result["total"]
                                
                                # 배치 간 딜레이
                                if i + batch_size < len(results):
                                    time.sleep(1)
                            
                            status_callback(f"🗄️ DB 업로드 완료: 성공 {db_stats['success']}/{db_stats['total']}건, 실패 {db_stats['failed']}건")
                        else:
                            status_callback("⚠️ DB 연결 실패. CSV만 저장되었습니다.")
                    else:
                        status_callback("ℹ️ DB 설정이 없어 CSV만 저장되었습니다.")
                    
                    st.session_state.results = results
                    success_msg = f"✅ 크롤링 완료: {len(results)}개 게시글 수집"
                    if db_stats["total"] > 0:
                        success_msg += f" | DB 저장: {db_stats['success']}/{db_stats['total']}건"
                    st.success(success_msg)
                
                crawler.close()
                st.session_state.crawler = None
                st.session_state.is_running = False
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")
                st.session_state.is_running = False
                if st.session_state.crawler:
                    st.session_state.crawler.close()
                    st.session_state.crawler = None
                st.rerun()
    
    # 중지 버튼
    if st.session_state.is_running:
        if st.button("⏹️ 중지"):
            if st.session_state.crawler:
                st.session_state.crawler.close()
                st.session_state.crawler = None
            st.session_state.is_running = False
            st.rerun()
    
    st.markdown("---")
    
    # 상태 모니터링
    st.subheader("📝 실시간 상태")
    status_container = st.container()
    
    with status_container:
        if st.session_state.status_messages:
            # 최근 50개 메시지만 표시
            recent_messages = st.session_state.status_messages[-50:]
            for msg in recent_messages:
                st.text(f"[{msg['time']}] {msg['message']}")
        else:
            st.info("크롤링을 시작하면 상태 메시지가 여기에 표시됩니다.")

with col2:
    st.header("📈 통계")
    
    if st.session_state.results:
        total = len(st.session_state.results)
        successful = len([r for r in st.session_state.results if "error" not in r])
        failed = total - successful
        
        st.metric("총 게시글", total)
        st.metric("성공", successful)
        st.metric("실패", failed)
    else:
        st.info("크롤링 결과가 없습니다.")

# 결과 표시
if st.session_state.results:
    st.markdown("---")
    st.header("📋 수집 결과")
    
    # DataFrame 생성
    df_data = []
    for result in st.session_state.results:
        if "error" not in result:
            df_data.append({
                "제목": result.get("title", "")[:50],
                "작성자": result.get("author_nickname", ""),
                "작성일": result.get("posted_at", ""),
                "URL": result.get("article_url", ""),
                "댓글 수": len(result.get("comments", [])),
                "이미지 수": len(result.get("images_base64", [])),
                "수집일시": result.get("scraped_at", "")
            })
    
    if df_data:
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, height=400)
        
        # CSV 다운로드
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 CSV 다운로드",
            data=csv,
            file_name=f"cafe_scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("표시할 결과가 없습니다.")

# 하단 정보
st.markdown("---")
st.caption("⚠️ 이 도구는 로컬에서만 실행됩니다. 네이버 카페 이용약관을 준수하여 사용하세요.")
