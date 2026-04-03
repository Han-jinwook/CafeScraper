#!/usr/bin/env python3
"""
로그인 상태 확인 및 JavaScript 로딩 대기 테스트
"""

import sys
import os
import time
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

def test_login_and_wait():
    """로그인 상태 확인 및 JavaScript 로딩 대기"""
    
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 브라우저 시작
        print("🔄 브라우저 시작 중...")
        scraper.start_browser()
        
        # 쿠키 로드
        scraper._load_cookies()
        
        # 네이버 메인 페이지로 이동하여 로그인 상태 확인
        print("🌐 네이버 메인 페이지 접속...")
        scraper.driver.get("https://www.naver.com")
        time.sleep(3)
        
        # 로그인 상태 확인
        print("🔍 로그인 상태 확인 중...")
        login_indicators = [
            len(scraper.driver.find_elements("xpath", "//a[contains(text(), '로그인')]")) == 0,
            len(scraper.driver.find_elements("xpath", "//a[contains(@href, 'nid.naver.com')]")) > 0,
            len(scraper.driver.find_elements("xpath", "//span[contains(@class, 'MyView-module__link_login___HpHMW')]")) > 0,
            len(scraper.driver.find_elements("xpath", "//a[contains(text(), '로그아웃')]")) > 0
        ]
        
        if any(login_indicators):
            print("✅ 로그인 상태 확인됨")
        else:
            print("❌ 로그인되지 않음")
            return
        
        # 접근 가능한 카페 찾기 (일반적인 공개 카페)
        test_cafes = [
            "https://cafe.naver.com/joonggonara",  # 중고나라
            "https://cafe.naver.com/steamindiegame",  # 스팀 인디게임
            "https://cafe.naver.com/steamindiegame/1",  # 스팀 인디게임 게시판
        ]
        
        for cafe_url in test_cafes:
            print(f"\n🌐 카페 접속 시도: {cafe_url}")
            try:
                scraper.driver.get(cafe_url)
                time.sleep(5)  # 페이지 로딩 대기
                
                # 페이지 제목 확인
                page_title = scraper.driver.title
                print(f"   페이지 제목: {page_title}")
                
                # 접근 가능한지 확인
                if "멤버가 아닙니다" in scraper.driver.page_source:
                    print("   ❌ 멤버가 아님")
                    continue
                elif "로그인" in page_title or "네이버 카페" in page_title:
                    print("   ✅ 접근 가능")
                    
                    # JavaScript 로딩 대기 (더 긴 시간)
                    print("   ⏳ JavaScript 로딩 대기 중... (30초)")
                    time.sleep(30)
                    
                    # 다시 페이지 소스 확인
                    page_source = scraper.driver.page_source
                    
                    # h 태그들 다시 확인
                    h_elements = scraper.driver.find_elements("css selector", "h1, h2, h3, h4, h5, h6")
                    print(f"   📄 h 태그 발견: {len(h_elements)}개")
                    
                    for i, elem in enumerate(h_elements[:5]):
                        try:
                            text = elem.text.strip()
                            if text:
                                print(f"      {i+1}. {text[:50]}...")
                        except:
                            pass
                    
                    # se- 클래스들 확인
                    se_elements = scraper.driver.find_elements("css selector", "[class*='se-']")
                    print(f"   📝 se- 클래스 발견: {len(se_elements)}개")
                    
                    # content 관련 클래스들 확인
                    content_elements = scraper.driver.find_elements("css selector", "[class*='content']")
                    print(f"   📄 content 클래스 발견: {len(content_elements)}개")
                    
                    if len(h_elements) > 0 or len(se_elements) > 0 or len(content_elements) > 0:
                        print("   ✅ 게시글 내용 발견!")
                        
                        # 스크린샷 저장
                        scraper.driver.save_screenshot(f"debug_successful_page_{cafe_url.split('/')[-1]}.png")
                        
                        # HTML 저장
                        with open(f"debug_successful_page_{cafe_url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
                            f.write(page_source)
                        
                        print(f"   📸 스크린샷 및 HTML 저장 완료")
                        break
                    else:
                        print("   ❌ 게시글 내용을 찾을 수 없음")
                        
            except Exception as e:
                print(f"   ❌ 오류: {e}")
                continue
        
        print("\n✅ 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            scraper.close()
        except:
            pass

if __name__ == "__main__":
    test_login_and_wait()
