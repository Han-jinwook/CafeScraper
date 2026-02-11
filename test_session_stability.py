#!/usr/bin/env python3
"""
세션 안정성 테스트 스크립트
개선된 Selenium 코드의 세션 유지 기능을 테스트합니다.
"""

import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.products.scraper.naver import NaverScraper

def test_session_stability():
    """세션 안정성 테스트"""
    print("🧪 세션 안정성 테스트 시작")
    print("=" * 50)
    
    # 스크래퍼 초기화
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 1. 브라우저 시작 테스트
        print("1️⃣ 브라우저 시작 테스트")
        scraper.start_browser()
        print("✅ 브라우저 시작 성공")
        
        # 2. 쿠키 로드 테스트
        print("\n2️⃣ 쿠키 로드 테스트")
        scraper._load_cookies()
        print("✅ 쿠키 로드 완료")
        
        # 3. 로그인 상태 확인 테스트
        print("\n3️⃣ 로그인 상태 확인 테스트")
        login_status = scraper._check_login_status()
        if login_status:
            print("✅ 로그인 상태 확인 성공")
        else:
            print("⚠️ 로그인 상태 확인 실패 - 수동 로그인 필요")
        
        # 4. 네이버 메인 페이지 접속 테스트
        print("\n4️⃣ 네이버 메인 페이지 접속 테스트")
        scraper.driver.get("https://www.naver.com")
        time.sleep(3)
        current_url = scraper.driver.current_url
        print(f"✅ 현재 URL: {current_url}")
        
        # 5. 카페 페이지 접속 테스트
        print("\n5️⃣ 카페 페이지 접속 테스트")
        cafe_url = "https://cafe.naver.com/sundreamd"
        scraper.driver.get(cafe_url)
        time.sleep(3)
        cafe_url_current = scraper.driver.current_url
        print(f"✅ 카페 URL: {cafe_url_current}")
        
        # 6. 세션 유지 테스트 (여러 번 페이지 이동)
        print("\n6️⃣ 세션 유지 테스트")
        test_urls = [
            "https://www.naver.com",
            "https://cafe.naver.com/sundreamd",
            "https://www.naver.com",
            "https://cafe.naver.com/sundreamd"
        ]
        
        for i, url in enumerate(test_urls, 1):
            print(f"   {i}/4 페이지 이동: {url}")
            scraper.driver.get(url)
            time.sleep(2)
            
            # 세션 유효성 확인
            try:
                current_url = scraper.driver.current_url
                if current_url and current_url != "data:,":
                    print(f"   ✅ 세션 유지됨: {current_url}")
                else:
                    print(f"   ❌ 세션 끊어짐: {current_url}")
                    break
            except Exception as e:
                print(f"   ❌ 세션 확인 실패: {e}")
                break
        
        # 7. 게시판 목록 조회 테스트
        print("\n7️⃣ 게시판 목록 조회 테스트")
        try:
            boards = scraper.get_cafe_boards(cafe_url)
            print(f"✅ 게시판 {len(boards)}개 조회 성공")
        except Exception as e:
            print(f"❌ 게시판 조회 실패: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 세션 안정성 테스트 완료")
        
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
    test_session_stability()

