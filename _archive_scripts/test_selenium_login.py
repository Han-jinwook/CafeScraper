#!/usr/bin/env python3
"""
Selenium 기반 네이버 로그인 테스트 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.products.scraper.naver import NaverScraper
import time

def test_selenium_login():
    """Selenium 기반 로그인 테스트"""
    print("🧪 Selenium 기반 네이버 로그인 테스트 시작")
    print("=" * 50)
    
    try:
        # NaverScraper 인스턴스 생성
        scraper = NaverScraper("sessions", "snapshots")
        
        print("1️⃣ 브라우저 시작 테스트...")
        scraper.start_browser()
        print("✅ 브라우저 시작 성공")
        
        print("2️⃣ 네이버 메인 페이지 접속 테스트...")
        scraper.driver.get("https://www.naver.com")
        time.sleep(3)
        print("✅ 네이버 메인 페이지 접속 성공")
        
        print("3️⃣ 페이지 제목 확인...")
        title = scraper.driver.title
        print(f"📄 페이지 제목: {title}")
        
        print("4️⃣ 로그인 상태 확인...")
        try:
            login_button = scraper.driver.find_elements("xpath", "//a[contains(text(), '로그인')]")
            if not login_button:
                print("✅ 이미 로그인된 상태입니다")
                is_logged_in = True
            else:
                print("🔐 로그인이 필요합니다")
                is_logged_in = False
        except Exception as e:
            print(f"⚠️ 로그인 상태 확인 중 오류: {e}")
            is_logged_in = False
        
        print("5️⃣ 스크린샷 저장...")
        scraper.driver.save_screenshot("test_login_screenshot.png")
        print("✅ 스크린샷 저장 완료: test_login_screenshot.png")
        
        print("6️⃣ 브라우저 종료...")
        scraper.close()
        print("✅ 브라우저 종료 완료")
        
        print("=" * 50)
        print("🎉 Selenium 로그인 테스트 완료!")
        print(f"📊 로그인 상태: {'로그인됨' if is_logged_in else '로그인 필요'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        print(f"❌ 에러 타입: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_selenium_login()
    if success:
        print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
        print("🚀 이제 실제 스크래핑 기능을 테스트할 수 있습니다.")
    else:
        print("\n❌ 테스트가 실패했습니다.")
        print("🔧 Selenium 설치나 Chrome 드라이버 설정을 확인해주세요.")
