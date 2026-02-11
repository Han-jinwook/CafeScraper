#!/usr/bin/env python3
"""
게시글 스크래핑 테스트 스크립트
사용법: python test_scrape.py
"""
import asyncio
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper
from app.utils.csv_writer import append_article_bundle_row

async def test_scrape_article():
    """테스트 게시글 스크래핑"""
    print("게시글 스크래핑 테스트 시작...")
    
    # 테스트할 게시글 URL 입력
    test_url = input("테스트할 네이버 카페 게시글 URL을 입력하세요: ").strip()
    if not test_url:
        print("URL이 입력되지 않았습니다.")
        return
    
    # 카페 ID 추출 (URL에서)
    try:
        cafe_id = test_url.split("cafe.naver.com/")[1].split("/")[0]
        print(f"카페 ID: {cafe_id}")
    except:
        cafe_id = "unknown"
        print("카페 ID를 자동으로 추출할 수 없습니다.")
    
    # 댓글 필터 설정
    include_nicks = input("포함할 닉네임 (쉼표로 구분, 엔터시 전체): ").strip()
    include_list = [nick.strip() for nick in include_nicks.split(",")] if include_nicks else None
    
    exclude_nicks = input("제외할 닉네임 (쉼표로 구분, 엔터시 없음): ").strip()
    exclude_list = [nick.strip() for nick in exclude_nicks.split(",")] if exclude_nicks else None
    
    print(f"댓글 필터 - 포함: {include_list}, 제외: {exclude_list}")
    
    # 디렉터리 설정
    sessions_dir = Path("sessions")
    snapshots_dir = Path("snapshots")
    outputs_dir = Path("outputs")
    
    scraper = NaverScraper(str(sessions_dir), str(snapshots_dir))
    
    try:
        # 로그인 확인
        print("로그인 상태 확인 중...")
        if not await scraper.ensure_logged_in():
            print("로그인이 필요합니다. 먼저 python test_login.py를 실행하세요.")
            return
        
        # 게시글 스크래핑
        print(f"게시글 스크래핑 중: {test_url}")
        
        # TODO: 실제 스크래핑 로직 구현
        # 실제 스크래핑 수행
        result = await scraper.scrape_article(
            test_url,
            include_list,
            exclude_list
        )
        
        # CSV 저장
        csv_path = append_article_bundle_row(outputs_dir, result)
        print(f"CSV 저장 완료: {csv_path}")
        
        # 결과 확인
        print("\n스크래핑 결과:")
        print(f"  - 카페 ID: {result['cafe_id']}")
        print(f"  - 제목: {result['title']}")
        print(f"  - 작성자: {result['author_nickname']}")
        print(f"  - 이미지 수: {len(result['images_base64'])}")
        print(f"  - 댓글 수: {len(result['comments'])}")
        
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        await scraper.close()
        print("브라우저가 종료되었습니다.")

if __name__ == "__main__":
    asyncio.run(test_scrape_article())
