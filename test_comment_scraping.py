#!/usr/bin/env python3
"""
댓글 긁어오기 기능 테스트
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

def test_comment_scraping():
    """댓글 긁어오기 기능 테스트"""
    print("=" * 60)
    print("댓글 긁어오기 기능 테스트")
    print("=" * 60)
    
    # 테스트할 게시글 URL (실제 카페 게시글 URL로 변경 필요)
    test_article_url = "https://cafe.naver.com/yourcafe/ArticleRead.nhn?clubid=12345678&articleid=123456"
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        print("\n1. 브라우저 초기화...")
        scraper.start_browser()
        
        print("\n2. 로그인 상태 확인...")
        if not scraper.ensure_logged_in():
            print("   [WARN] 로그인이 필요합니다. 웹 UI에서 먼저 로그인하세요.")
            print("   http://127.0.0.1:8001 에서 '로그인 시작' 버튼을 클릭하세요.")
            return False
        
        print("\n3. 테스트 게시글 접근...")
        print(f"   URL: {test_article_url}")
        
        # 게시글 페이지로 이동
        scraper.driver.get(test_article_url)
        time.sleep(3)  # 페이지 로딩 대기
        
        print(f"   페이지 제목: {scraper.driver.title}")
        
        print("\n4. 댓글 추출 테스트...")
        
        # 댓글 추출 (필터 없이)
        comments = scraper._extract_comments()
        print(f"   [INFO] 추출된 댓글 수: {len(comments)}개")
        
        if comments:
            print("\n5. 댓글 내용 확인:")
            for i, comment in enumerate(comments[:3], 1):  # 처음 3개만 표시
                author = comment.get('author_nickname', '알 수 없음')
                content = comment.get('content', '내용 없음')[:50]  # 50자까지만
                date = comment.get('date', '날짜 없음')
                print(f"   {i}. [{author}] {content}... ({date})")
            
            print(f"\n   [SUCCESS] 댓글 추출 성공! 총 {len(comments)}개 댓글 발견")
        else:
            print("   [WARN] 댓글을 찾을 수 없습니다.")
            print("   - 게시글에 댓글이 없을 수 있습니다.")
            print("   - 댓글 셀렉터가 변경되었을 수 있습니다.")
            print("   - 로그인이 필요할 수 있습니다.")
        
        print("\n6. 댓글 필터링 테스트...")
        # 특정 닉네임 포함 댓글만 추출
        test_nickname = "테스트"
        filtered_comments = scraper._extract_comments(include_nicks=[test_nickname])
        print(f"   '{test_nickname}' 포함 댓글: {len(filtered_comments)}개")
        
        print("\n[SUCCESS] 댓글 긁어오기 테스트 완료!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 댓글 긁어오기 테스트 실패: {e}")
        return False
    finally:
        print("\n7. 브라우저 종료...")
        scraper.close()
        print("   [INFO] 브라우저가 종료되었습니다.")

if __name__ == "__main__":
    success = test_comment_scraping()
    if success:
        print("\n[SUCCESS] 댓글 긁어오기 기능이 정상적으로 작동합니다!")
        print("   이제 배치 크롤링에서 댓글도 함께 수집할 수 있습니다.")
    else:
        print("\n[ERROR] 댓글 긁어오기에 문제가 있습니다.")
        print("   로그인 상태를 확인하거나 게시글 URL을 확인해주세요.")
