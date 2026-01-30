#!/usr/bin/env python3
"""
간단한 로그인 프로세스 - 브라우저만 열어서 수동 로그인
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.scraper.naver import NaverScraper

def simple_login():
    """간단한 로그인 프로세스"""
    print("=" * 50)
    print("네이버 카페 스크래퍼 - 간단 로그인")
    print("=" * 50)
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        print("\n1. 브라우저 초기화 중...")
        scraper.start_browser()
        
        print("\n2. 네이버 로그인 페이지로 이동...")
        scraper.driver.get("https://nid.naver.com/nidlogin.login")
        print("   브라우저 창이 열렸습니다.")
        
        print("\n3. 로그인 안내:")
        print("   - 브라우저 창에서 네이버 아이디와 비밀번호를 입력하세요")
        print("   - 로그인 완료 후 브라우저 창을 닫지 마세요")
        print("   - 이 스크립트가 자동으로 로그인 상태를 확인합니다")
        
        print("\n4. 10초 후 자동으로 로그인 상태를 확인합니다...")
        import time
        for i in range(10, 0, -1):
            print(f"   {i}초 남음...")
            time.sleep(1)
        
        print("\n5. 로그인 상태 확인 중...")
        scraper.driver.get("https://www.naver.com")
        
        # 로그인 상태 확인
        login_buttons = scraper.driver.find_elements("xpath", "//a[contains(text(), '로그인')]")
        if not login_buttons:
            print("   [SUCCESS] 로그인 성공! 쿠키를 저장합니다...")
            scraper._save_cookies()
            
            # 카페 접근 테스트
            print("\n6. 카페 접근 테스트...")
            scraper.driver.get("https://cafe.naver.com")
            if "카페" in scraper.driver.title:
                print("   [SUCCESS] 카페 접근 가능!")
            else:
                print("   [WARN] 카페 접근에 문제가 있을 수 있습니다.")
            
            print("\n[SUCCESS] 로그인 프로세스 완료!")
            print("   이제 배치 크롤링을 사용할 수 있습니다.")
            return True
        else:
            print("   [ERROR] 로그인이 완료되지 않았습니다.")
            print("   브라우저에서 로그인을 완료한 후 다시 시도해주세요.")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] 로그인 프로세스 실패: {e}")
        return False
    finally:
        print("\n7. 브라우저 종료...")
        scraper.close()
        print("   [INFO] 브라우저가 종료되었습니다.")

if __name__ == "__main__":
    success = simple_login()
    if success:
        print("\n[SUCCESS] 로그인이 성공적으로 완료되었습니다!")
        print("   이제 웹 UI에서 배치 크롤링을 사용할 수 있습니다.")
    else:
        print("\n[ERROR] 로그인에 실패했습니다.")
        print("   다시 시도해주세요.")
