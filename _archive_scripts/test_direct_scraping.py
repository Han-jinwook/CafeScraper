#!/usr/bin/env python3
"""
직접 스크래핑 테스트
웹 UI 없이 직접 배치 크롤링을 테스트합니다.
"""

import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.products.scraper.naver import NaverScraper

def test_direct_scraping():
    """직접 스크래핑 테스트"""
    print("🧪 직접 스크래핑 테스트 시작")
    print("=" * 50)
    
    # 스크래퍼 초기화
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 1. 브라우저 시작
        print("1️⃣ 브라우저 시작")
        scraper.start_browser()
        print("✅ 브라우저 시작 성공")
        
        # 2. 쿠키 로드
        print("\n2️⃣ 쿠키 로드")
        scraper._load_cookies()
        print("✅ 쿠키 로드 완료")
        
        # 3. 로그인 상태 확인
        print("\n3️⃣ 로그인 상태 확인")
        login_status = scraper._check_login_status()
        if login_status:
            print("✅ 로그인 상태 확인 성공")
        else:
            print("❌ 로그인 상태 확인 실패")
            return
        
        # 4. 카페 게시판 목록 조회
        print("\n4️⃣ 카페 게시판 목록 조회")
        cafe_url = "https://cafe.naver.com/sundreamd"
        boards = scraper.get_cafe_boards(cafe_url)
        print(f"✅ 게시판 {len(boards)}개 조회 성공")
        
        # 5. 특정 게시판 스크래핑 (★가입인사)
        print("\n5️⃣ 특정 게시판 스크래핑")
        target_board = None
        for board in boards:
            if board['menu_name'] == '★가입인사':
                target_board = board
                break
        
        if not target_board:
            print("❌ ★가입인사 게시판을 찾을 수 없습니다")
            return
        
        print(f"✅ 대상 게시판: {target_board['menu_name']} (ID: {target_board['menu_id']})")
        
        # 6. 게시판 스크래핑 (최대 2페이지)
        print("\n6️⃣ 게시판 스크래핑")
        board_results = scraper.scrape_board_articles(target_board['board_url'], max_pages=2)
        print(f"✅ 게시판에서 {len(board_results)}개 게시글 발견")
        
        if not board_results:
            print("❌ 게시글이 없습니다")
            return
        
        # 7. 키워드 필터링 테스트
        print("\n7️⃣ 키워드 필터링 테스트")
        search_keywords = ["건선"]
        filtered_articles = []
        
        for article in board_results:
            title = article.get('title', '').lower()
            if any(keyword.lower() in title for keyword in search_keywords):
                filtered_articles.append(article)
                print(f"✅ 키워드 일치: {article.get('title', 'N/A')[:50]}...")
        
        print(f"✅ 키워드 필터링 결과: {len(filtered_articles)}개 게시글")
        
        if not filtered_articles:
            print("⚠️ '건선' 키워드가 포함된 게시글이 없습니다")
            print("🔍 전체 게시글 제목 확인:")
            for i, article in enumerate(board_results[:5], 1):
                print(f"   {i}. {article.get('title', 'N/A')}")
            return
        
        # 8. 상세 스크래핑 테스트 (최대 2개)
        print("\n8️⃣ 상세 스크래핑 테스트")
        test_articles = filtered_articles[:2]  # 최대 2개만 테스트
        
        for i, article in enumerate(test_articles, 1):
            print(f"\n📄 게시글 {i}/{len(test_articles)} 스크래핑")
            print(f"   제목: {article.get('title', 'N/A')}")
            print(f"   URL: {article.get('article_url', 'N/A')}")
            
            try:
                # 상세 스크래핑
                detailed_result = scraper.scrape_article(
                    article['article_url'],
                    include_nicks=None,
                    exclude_nicks=None
                )
                
                print(f"   ✅ 스크래핑 성공")
                print(f"   📝 내용 길이: {len(detailed_result.get('content_text', ''))}")
                print(f"   💬 댓글 수: {len(detailed_result.get('comments', []))}")
                print(f"   🖼️ 이미지 수: {len(detailed_result.get('images_base64', []))}")
                
            except Exception as e:
                print(f"   ❌ 스크래핑 실패: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 직접 스크래핑 테스트 완료")
        
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
    test_direct_scraping()

