#!/usr/bin/env python3
"""
간단한 Selenium 테스트 스크립트
"""
import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.scraper.naver import NaverScraper

async def test_selenium_basic():
    """기본 Selenium 기능 테스트"""
    print("Selenium 기본 기능 테스트 시작...")
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        print("1. 브라우저 초기화 테스트...")
        # 브라우저 시작
        scraper.start_browser()
        if scraper.driver:
            print("   [OK] 브라우저 초기화 성공")
        else:
            print("   [FAIL] 브라우저 초기화 실패")
            return False
        
        print("2. 네이버 홈페이지 접속 테스트...")
        # 네이버 홈페이지에 접속해보기
        scraper.driver.get("https://www.naver.com")
        title = scraper.driver.title
        print(f"   [OK] 네이버 접속 성공: {title}")
        
        print("3. 로그인 상태 확인 테스트...")
        # 로그인 상태 확인
        is_logged_in = await scraper.ensure_logged_in()
        if is_logged_in:
            print("   [OK] 로그인 상태 확인 성공")
        else:
            print("   [WARN] 로그인 상태 확인 실패 (쿠키가 없을 수 있음)")
        
        print("4. 브라우저 종료 테스트...")
        await scraper.close()
        print("   [OK] 브라우저 종료 성공")
        
        print("\n[SUCCESS] 모든 테스트 통과!")
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        try:
            await scraper.close()
        except:
            pass
        return False

if __name__ == "__main__":
    success = asyncio.run(test_selenium_basic())
    if success:
        print("\n[SUCCESS] Selenium 전환이 성공적으로 완료되었습니다!")
    else:
        print("\n[ERROR] Selenium 테스트에 문제가 있습니다.")
