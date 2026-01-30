#!/usr/bin/env python3
"""
간단한 스크래핑 테스트
이전 방식으로 되돌려서 테스트합니다.
"""

import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.scraper.naver import NaverScraper

def test_simple_scraping():
    """간단한 스크래핑 테스트"""
    print("🧪 간단한 스크래핑 테스트")
    print("=" * 50)
    
    # 스크래퍼 초기화
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 1. 브라우저 시작
        print("1️⃣ 브라우저 시작")
        scraper.start_browser()
        
        # 2. 쿠키 로드
        print("2️⃣ 쿠키 로드")
        scraper._load_cookies()
        
        # 3. 로그인 상태 확인
        print("3️⃣ 로그인 상태 확인")
        if not scraper._check_login_status():
            print("❌ 로그인 실패")
            return
        
        # 4. 카페 접속
        print("4️⃣ 카페 접속")
        cafe_url = "https://cafe.naver.com/sundreamd"
        scraper.driver.get(cafe_url)
        time.sleep(3)
        
        # 5. 게시판 목록 조회
        print("5️⃣ 게시판 목록 조회")
        boards = scraper.get_cafe_boards(cafe_url)
        print(f"✅ 게시판 {len(boards)}개 조회")
        
        # 6. ★가입인사 게시판 찾기
        target_board = None
        for board in boards:
            if board['menu_name'] == '★가입인사':
                target_board = board
                break
        
        if not target_board:
            print("❌ ★가입인사 게시판 없음")
            return
        
        print(f"✅ 대상 게시판: {target_board['menu_name']}")
        
        # 7. 게시판 스크래핑 (1페이지만)
        print("7️⃣ 게시판 스크래핑")
        board_results = scraper.scrape_board_articles(target_board['board_url'], max_pages=1)
        print(f"✅ 게시글 {len(board_results)}개 발견")
        
        if not board_results:
            print("❌ 게시글 없음")
            return
        
        # 8. 첫 번째 게시글 상세 스크래핑
        print("8️⃣ 첫 번째 게시글 상세 스크래핑")
        first_article = board_results[0]
        print(f"📄 제목: {first_article.get('title', 'N/A')}")
        print(f"🔗 URL: {first_article.get('article_url', 'N/A')}")
        
        try:
            detailed_result = scraper.scrape_article(first_article['article_url'])
            print("✅ 상세 스크래핑 성공")
            print(f"📝 내용 길이: {len(detailed_result.get('content_text', ''))}")
            print(f"💬 댓글 수: {len(detailed_result.get('comments', []))}")
            print(f"🖼️ 이미지 수: {len(detailed_result.get('images_base64', []))}")
            
        except Exception as e:
            print(f"❌ 상세 스크래핑 실패: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 50)
        print("🎉 간단한 스크래핑 테스트 완료")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 브라우저 종료
        if scraper.driver:
            scraper.close()
            print("🔒 브라우저 종료됨")

if __name__ == "__main__":
    test_simple_scraping()

