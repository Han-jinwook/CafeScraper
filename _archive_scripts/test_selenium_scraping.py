#!/usr/bin/env python3
"""
Selenium 기반 네이버 카페 스크래핑 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.products.scraper.naver import NaverScraper
import time

def test_selenium_scraping():
    """Selenium 기반 스크래핑 테스트"""
    print("🧪 Selenium 기반 네이버 카페 스크래핑 테스트 시작")
    print("=" * 60)
    
    try:
        # NaverScraper 인스턴스 생성
        scraper = NaverScraper("sessions", "snapshots")
        
        print("1️⃣ 브라우저 시작...")
        scraper.start_browser()
        print("✅ 브라우저 시작 성공")
        
        print("2️⃣ 로그인 확인...")
        is_logged_in = scraper.ensure_logged_in()
        if is_logged_in:
            print("✅ 로그인 상태 확인 완료")
        else:
            print("❌ 로그인 실패")
            return False
        
        print("3️⃣ 테스트용 카페 페이지 접속...")
        # 테스트용 카페 URL (실제 카페 URL로 변경 필요)
        test_cafe_url = "https://cafe.naver.com/steamindiegame"
        scraper.driver.get(test_cafe_url)
        time.sleep(3)
        
        print("4️⃣ 페이지 정보 확인...")
        title = scraper.driver.title
        current_url = scraper.driver.current_url
        print(f"📄 페이지 제목: {title}")
        print(f"🌐 현재 URL: {current_url}")
        
        print("5️⃣ 게시판 목록 조회 테스트...")
        try:
            boards = scraper.get_cafe_boards(test_cafe_url)
            print(f"✅ 게시판 {len(boards)}개 발견")
            for i, board in enumerate(boards[:3], 1):  # 처음 3개만 출력
                print(f"  {i}. {board['menu_name']} (ID: {board['menu_id']})")
        except Exception as e:
            print(f"⚠️ 게시판 조회 실패: {e}")
        
        print("6️⃣ 스크린샷 저장...")
        scraper.driver.save_screenshot("test_scraping_screenshot.png")
        print("✅ 스크린샷 저장 완료: test_scraping_screenshot.png")
        
        print("7️⃣ 브라우저 종료...")
        scraper.close()
        print("✅ 브라우저 종료 완료")
        
        print("=" * 60)
        print("🎉 Selenium 스크래핑 테스트 완료!")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        print(f"❌ 에러 타입: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_selenium_scraping()
    if success:
        print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
        print("🚀 이제 FastAPI 서버를 시작할 수 있습니다.")
    else:
        print("\n❌ 테스트가 실패했습니다.")
        print("🔧 에러 메시지를 확인하고 문제를 해결해주세요.")
