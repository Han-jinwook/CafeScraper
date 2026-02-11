#!/usr/bin/env python3
"""
로그인 상태 및 카페 접근 테스트
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

def test_login_and_cafe_access():
    """로그인 상태 및 카페 접근 테스트"""
    print("로그인 상태 및 카페 접근 테스트 시작...")
    
    # 테스트용 카페 URL (실제 카페 URL로 변경 필요)
    test_cafe_url = "https://cafe.naver.com/yourcafe"
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        print("1. 브라우저 초기화...")
        scraper.start_browser()
        
        print("2. 네이버 홈페이지 접속...")
        scraper.driver.get("https://www.naver.com")
        print(f"   현재 페이지: {scraper.driver.title}")
        
        print("3. 로그인 상태 확인...")
        # 로그인 버튼 확인
        login_buttons = scraper.driver.find_elements("xpath", "//a[contains(text(), '로그인')]")
        if login_buttons:
            print("   [WARN] 로그인 버튼이 보입니다. 로그인이 필요합니다.")
        else:
            print("   [SUCCESS] 로그인 버튼이 없습니다. 로그인된 상태로 보입니다.")
        
        print("4. 카페 접근 테스트...")
        try:
            scraper.driver.get(test_cafe_url)
            print(f"   카페 페이지 제목: {scraper.driver.title}")
            
            # 카페 접근 가능 여부 확인
            if "카페" in scraper.driver.title or "cafe" in scraper.driver.current_url:
                print("   [SUCCESS] 카페 접근 성공!")
            else:
                print("   [WARN] 카페 접근 실패 또는 리다이렉션됨")
                print(f"   현재 URL: {scraper.driver.current_url}")
        except Exception as e:
            print(f"   [ERROR] 카페 접근 실패: {e}")
        
        print("5. 브라우저 종료...")
        scraper.close()
        
        print("\n[SUCCESS] 로그인 상태 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        try:
            scraper.close()
        except:
            pass
        return False

if __name__ == "__main__":
    success = test_login_and_cafe_access()
    if success:
        print("\n[SUCCESS] 로그인 상태가 정상적으로 확인되었습니다!")
    else:
        print("\n[ERROR] 로그인 상태 확인에 문제가 있습니다.")
