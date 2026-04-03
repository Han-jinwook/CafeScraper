#!/usr/bin/env python3
"""
간단한 로그인 테스트 스크립트
사용법: python test_login.py
"""
import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

async def test_login():
    """테스트 로그인 기능"""
    print("🚀 네이버 로그인 테스트 시작...")
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        # 로그인 시도
        success = await scraper.ensure_logged_in()
        
        if success:
            print("✅ 로그인 성공! 쿠키가 저장되었습니다.")
            print(f"📁 세션 저장 위치: {sessions_dir.absolute()}")
            print(f"📁 스냅샷 저장 위치: {snapshots_dir.absolute()}")
        else:
            print("❌ 로그인 실패")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        await scraper.close()
        print("🔒 브라우저가 종료되었습니다.")

if __name__ == "__main__":
    asyncio.run(test_login())
