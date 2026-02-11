#!/usr/bin/env python3
"""
최종 스크래핑 테스트 - 업데이트된 셀렉터로 실제 스크래핑
"""

import sys
import os
import time
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

def test_final_scraping():
    """최종 스크래핑 테스트"""
    
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 브라우저 시작
        print("🔄 브라우저 시작 중...")
        scraper.start_browser()
        
        # 쿠키 로드
        scraper._load_cookies()
        
        # 중고나라 카페 접속
        print("🌐 중고나라 카페 접속...")
        scraper.driver.get("https://cafe.naver.com/joonggonara")
        time.sleep(5)
        
        # JavaScript 로딩 대기
        print("⏳ JavaScript 로딩 대기 중... (60초)")
        time.sleep(60)
        
        # 게시글 링크 찾기
        print("🔍 게시글 링크 찾기...")
        article_selectors = [
            "a[href*='ArticleRead']",
            "a[href*='ArticleRead.nhn']",
            ".article a",
            ".board_list a",
            "tr td a",
            "a[href*='cafe.naver.com']"
        ]
        
        article_links = []
        for selector in article_selectors:
            try:
                links = scraper.driver.find_elements("css selector", selector)
                if links:
                    article_links = links
                    print(f"   {selector}: {len(links)}개 발견")
                    break
            except:
                continue
        
        if article_links:
            print(f"✅ 게시글 링크 {len(article_links)}개 발견!")
            
            # 첫 번째 게시글 링크 클릭
            first_link = article_links[0]
            article_url = first_link.get_attribute("href")
            print(f"📄 첫 번째 게시글 접속: {article_url}")
            
            # 게시글 페이지로 이동
            scraper.driver.get(article_url)
            time.sleep(5)
            
            # JavaScript 로딩 대기
            print("⏳ 게시글 JavaScript 로딩 대기 중... (60초)")
            time.sleep(60)
            
            # 스크래핑 테스트
            print("\n🧪 스크래핑 테스트:")
            
            # 제목 추출
            print("🔍 제목 추출:")
            title_selectors = [
                "h3.title",
                "h2.title", 
                "h1.title",
                ".title"
            ]
            
            title = "제목을 찾을 수 없음"
            for selector in title_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.strip()
                            if text and len(text) > 5:
                                title = text
                                print(f"   ✅ {selector}: {title}")
                                break
                        if title != "제목을 찾을 수 없음":
                            break
                except:
                    continue
            
            if title == "제목을 찾을 수 없음":
                print("   ❌ 제목을 찾을 수 없음")
            
            # 내용 추출
            print("\n🔍 내용 추출:")
            content_selectors = [
                ".content",
                ".se-main-container",
                ".se-component-content",
                ".se-text-paragraph"
            ]
            
            content = "내용을 찾을 수 없음"
            for selector in content_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.strip()
                            if text and len(text) > 10:
                                content = text[:100] + "..." if len(text) > 100 else text
                                print(f"   ✅ {selector}: {content}")
                                break
                        if content != "내용을 찾을 수 없음":
                            break
                except:
                    continue
            
            if content == "내용을 찾을 수 없음":
                print("   ❌ 내용을 찾을 수 없음")
            
            # 작성자 추출
            print("\n🔍 작성자 추출:")
            author_selectors = [
                ".nick",
                ".nickname",
                ".author", 
                ".writer",
                "[class*='nick']",
                "[class*='author']",
                "[class*='writer']"
            ]
            
            author = "작성자를 찾을 수 없음"
            for selector in author_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.strip()
                            if text:
                                author = text
                                print(f"   ✅ {selector}: {author}")
                                break
                        if author != "작성자를 찾을 수 없음":
                            break
                except:
                    continue
            
            if author == "작성자를 찾을 수 없음":
                print("   ❌ 작성자를 찾을 수 없음")
            
            # 댓글 추출
            print("\n🔍 댓글 추출:")
            comment_selectors = [
                ".comment_area",
                ".LinkComment",
                ".comment",
                ".reply"
            ]
            
            comments = []
            for selector in comment_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        print(f"   ✅ {selector}: {len(elements)}개 발견")
                        comments = elements
                        break
                except:
                    continue
            
            if not comments:
                print("   ❌ 댓글을 찾을 수 없음")
            
            # 결과 요약
            print("\n📊 스크래핑 결과 요약:")
            print(f"   제목: {title}")
            print(f"   내용: {content[:50]}..." if len(content) > 50 else f"   내용: {content}")
            print(f"   작성자: {author}")
            print(f"   댓글: {len(comments)}개")
            
            # 성공률 계산
            success_count = 0
            if title != "제목을 찾을 수 없음":
                success_count += 1
            if content != "내용을 찾을 수 없음":
                success_count += 1
            if author != "작성자를 찾을 수 없음":
                success_count += 1
            if comments:
                success_count += 1
            
            success_rate = (success_count / 4) * 100
            print(f"\n🎯 성공률: {success_rate:.1f}% ({success_count}/4)")
            
            if success_rate >= 75:
                print("🎉 스크래핑 성공! 배치 테스트를 진행할 수 있습니다.")
            else:
                print("⚠️ 스크래핑 부분 성공. 추가 개선이 필요합니다.")
            
        else:
            print("❌ 게시글 링크를 찾을 수 없음")
        
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
    test_final_scraping()
