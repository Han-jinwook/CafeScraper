#!/usr/bin/env python3
"""
네이버 카페 게시판 스크래핑 테스트 스크립트
"""

import asyncio
import json
import requests
from typing import Optional

# API 서버 설정
API_BASE_URL = "http://localhost:8000"

def test_board_scraping():
    """게시판 스크래핑 테스트"""
    print("🧪 게시판 스크래핑 테스트 시작")
    
    # 테스트할 게시판 URL (실제 카페 URL로 변경 필요)
    # 실제 카페 URL을 사용하거나, 로그인 테스트만 진행
    board_url = "https://cafe.naver.com/yourcafe/BoardList.nhn?clubid=12345678&menuid=1"
    
    print("⚠️  실제 카페 URL이 필요합니다. 로그인 테스트만 진행합니다.")
    return
    
    payload = {
        "board_url": board_url,
        "max_pages": 2,  # 처음에는 2페이지만 테스트
        "comment_filter": {
            "include": None,
            "exclude": None
        }
    }
    
    try:
        print(f"📄 게시판 스크래핑 요청: {board_url}")
        response = requests.post(f"{API_BASE_URL}/scrape/board", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 성공: {result['message']}")
            print(f"📊 발견된 게시글: {result['articles_found']}")
            print(f"📊 스크래핑된 게시글: {result['articles_scraped']}")
            print(f"💾 저장된 CSV 파일: {len(result['saved_csvs'])}개")
            
            # 첫 번째 결과 미리보기
            if result['results']:
                first_article = result['results'][0]
                print(f"\n📄 첫 번째 게시글 미리보기:")
                print(f"   제목: {first_article.get('title', 'N/A')}")
                print(f"   작성자: {first_article.get('author_nickname', 'N/A')}")
                print(f"   URL: {first_article.get('article_url', 'N/A')}")
                print(f"   이미지 수: {len(first_article.get('images_base64', []))}")
                print(f"   댓글 수: {len(first_article.get('comments', []))}")
        else:
            print(f"❌ 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def test_multiple_articles():
    """여러 게시글 스크래핑 테스트"""
    print("\n🧪 여러 게시글 스크래핑 테스트 시작")
    
    # 테스트할 게시글 URL들 (실제 URL로 변경 필요)
    article_urls = [
        "https://cafe.naver.com/yourcafe/ArticleRead.nhn?clubid=12345678&articleid=123456",
        "https://cafe.naver.com/yourcafe/ArticleRead.nhn?clubid=12345678&articleid=123457",
    ]
    
    print("⚠️  실제 게시글 URL이 필요합니다. 로그인 테스트만 진행합니다.")
    return
    
    payload = {
        "article_urls": article_urls,
        "comment_filter": {
            "include": None,
            "exclude": None
        }
    }
    
    try:
        print(f"📄 여러 게시글 스크래핑 요청: {len(article_urls)}개")
        response = requests.post(f"{API_BASE_URL}/scrape/multiple", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 성공: {result['message']}")
            print(f"💾 저장된 CSV 파일: {len(result['saved_csvs'])}개")
            
            # 결과 미리보기
            for i, article in enumerate(result['results'], 1):
                print(f"\n📄 게시글 {i}:")
                print(f"   제목: {article.get('title', 'N/A')}")
                print(f"   작성자: {article.get('author_nickname', 'N/A')}")
                print(f"   이미지 수: {len(article.get('images_base64', []))}")
                print(f"   댓글 수: {len(article.get('comments', []))}")
        else:
            print(f"❌ 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def test_health():
    """API 서버 상태 확인"""
    print("🏥 API 서버 상태 확인")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API 서버 정상 작동")
            return True
        else:
            print(f"❌ API 서버 오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API 서버 연결 실패: {e}")
        return False

def test_login():
    """로그인 테스트"""
    print("🔐 로그인 테스트 시작")
    
    try:
        response = requests.post(f"{API_BASE_URL}/login/start")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 로그인 성공: {result['message']}")
            return True
        else:
            print(f"❌ 로그인 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 로그인 오류: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 네이버 카페 게시판 스크래핑 테스트")
    print("=" * 50)
    
    # API 서버 상태 확인
    if not test_health():
        print("\n❌ API 서버가 실행되지 않았습니다.")
        print("   다음 명령어로 서버를 시작하세요:")
        print("   uvicorn app.main:app --reload")
        return
    
    print("\n" + "=" * 50)
    
    # 로그인 테스트
    print("🔐 로그인 테스트 (브라우저가 열립니다)")
    print("   브라우저에서 네이버에 로그인한 후 터미널에서 Enter를 누르세요.")
    if test_login():
        print("✅ 로그인 성공! 이제 실제 카페 URL로 스크래핑을 테스트할 수 있습니다.")
    else:
        print("❌ 로그인 실패. 쿠키 파일을 확인하세요.")
    
    print("\n" + "=" * 50)
    
    # 게시판 스크래핑 테스트
    test_board_scraping()
    
    print("\n" + "=" * 50)
    
    # 여러 게시글 스크래핑 테스트
    test_multiple_articles()
    
    print("\n" + "=" * 50)
    print("🎉 테스트 완료!")
    print("\n💡 실제 스크래핑을 테스트하려면:")
    print("   1. test_board_scraping.py에서 실제 카페 URL로 변경")
    print("   2. test_multiple_articles()에서 실제 게시글 URL로 변경")

if __name__ == "__main__":
    main()
