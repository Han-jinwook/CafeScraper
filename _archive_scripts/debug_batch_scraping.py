#!/usr/bin/env python3
"""
배치 크롤링 디버깅 스크립트
웹 UI와 동일한 방식으로 배치 크롤링을 테스트합니다.
"""

import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.scraper.naver import NaverScraper

def debug_batch_scraping():
    """배치 크롤링 디버깅"""
    print("🔍 배치 크롤링 디버깅 시작")
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
        
        # 3. 배치 크롤링 파라미터 설정
        cafe_url = "https://cafe.naver.com/sundreamd"
        max_pages = 1
        all_boards = False
        selected_boards = ["185"]  # ★가입인사
        search_keywords = ["건선"]
        post_authors = []
        comment_authors = []
        max_articles = 5
        image_processing = "base64"
        period = "all"
        delay_between_requests = 3
        
        print("3️⃣ 배치 크롤링 파라미터")
        print(f"   카페 URL: {cafe_url}")
        print(f"   최대 페이지: {max_pages}")
        print(f"   전체 게시판: {all_boards}")
        print(f"   선택된 게시판: {selected_boards}")
        print(f"   검색 키워드: {search_keywords}")
        print(f"   최대 게시글: {max_articles}")
        
        # 4. 배치 크롤링 실행
        print("\n4️⃣ 배치 크롤링 실행")
        results = scraper.batch_scraping(
            cafe_url=cafe_url,
            max_pages=max_pages,
            all_boards=all_boards,
            selected_boards=selected_boards,
            search_keywords=search_keywords,
            post_authors=post_authors,
            comment_authors=comment_authors,
            max_articles=max_articles,
            image_processing=image_processing,
            period=period,
            delay_between_requests=delay_between_requests
        )
        
        print(f"\n5️⃣ 결과 분석")
        print(f"   총 결과 수: {len(results)}")
        
        if results:
            print("✅ 스크래핑 성공!")
            for i, result in enumerate(results[:3], 1):  # 처음 3개만 출력
                print(f"   {i}. {result.get('title', 'N/A')[:50]}...")
        else:
            print("❌ 스크래핑 실패 - 결과가 없습니다")
        
        print("\n" + "=" * 50)
        print("🎉 배치 크롤링 디버깅 완료")
        
    except Exception as e:
        print(f"❌ 디버깅 실패: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 브라우저 종료
        if scraper.driver:
            scraper.close()
            print("🔒 브라우저 종료됨")

if __name__ == "__main__":
    debug_batch_scraping()

