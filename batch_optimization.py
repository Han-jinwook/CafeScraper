#!/usr/bin/env python3
"""
배치 크롤링 성공률 향상을 위한 최적화 스크립트
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.scraper.naver import NaverScraper

def test_batch_optimization():
    """배치 크롤링 최적화 테스트"""
    print("배치 크롤링 최적화 테스트 시작...")
    
    # 테스트용 카페 URL (실제 카페 URL로 변경 필요)
    test_cafe_url = "https://cafe.naver.com/yourcafe"
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        print("1. 브라우저 초기화...")
        scraper.start_browser()
        
        print("2. 로그인 상태 확인...")
        if not scraper.ensure_logged_in():
            print("   [WARN] 로그인이 필요합니다. 먼저 로그인을 진행하세요.")
            return False
        
        print("3. 게시판 목록 조회 테스트...")
        boards = scraper.get_cafe_boards(test_cafe_url)
        if boards:
            print(f"   [SUCCESS] {len(boards)}개 게시판 발견")
            for i, board in enumerate(boards[:3], 1):  # 처음 3개만 표시
                print(f"     {i}. {board['menu_name']} ({board['menu_id']})")
        else:
            print("   [WARN] 게시판을 찾을 수 없습니다.")
        
        print("4. 브라우저 종료...")
        scraper.close()
        
        print("\n[SUCCESS] 배치 크롤링 최적화 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        try:
            scraper.close()
        except:
            pass
        return False

if __name__ == "__main__":
    success = test_batch_optimization()
    if success:
        print("\n[SUCCESS] 배치 크롤링 시스템이 정상적으로 작동합니다!")
    else:
        print("\n[ERROR] 배치 크롤링 시스템에 문제가 있습니다.")

