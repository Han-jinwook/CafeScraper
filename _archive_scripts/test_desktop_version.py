#!/usr/bin/env python3
"""
데스크톱 버전으로 강제 접근하여 스크래핑 테스트
"""

import sys
import os
import time
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

def test_desktop_version():
    """데스크톱 버전으로 강제 접근하여 테스트"""
    
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 브라우저 시작
        print("🔄 브라우저 시작 중...")
        scraper.start_browser()
        
        # 쿠키 로드
        scraper._load_cookies()
        
        # 데스크톱 버전으로 강제 접근
        desktop_url = "https://cafe.naver.com/joonggonara"
        print(f"🌐 데스크톱 버전 접속: {desktop_url}")
        
        # User-Agent를 데스크톱으로 설정
        scraper.driver.execute_script("Object.defineProperty(navigator, 'userAgent', {get: function () {return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';}})")
        
        scraper.driver.get(desktop_url)
        time.sleep(5)  # 기본 로딩 대기
        
        # JavaScript 로딩 대기 (더 긴 시간)
        print("⏳ JavaScript 로딩 대기 중... (60초)")
        time.sleep(60)
        
        # 현재 URL 확인
        current_url = scraper.driver.current_url
        print(f"📍 현재 URL: {current_url}")
        
        # 페이지 제목 확인
        page_title = scraper.driver.title
        print(f"📄 페이지 제목: {page_title}")
        
        # 스크린샷 저장
        scraper.driver.save_screenshot("debug_desktop_version.png")
        print("📸 스크린샷 저장: debug_desktop_version.png")
        
        # HTML 저장
        page_source = scraper.driver.page_source
        with open("debug_desktop_version.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("💾 HTML 저장: debug_desktop_version.html")
        
        # 게시글 링크 찾기
        print("\n🔍 게시글 링크 찾기...")
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
            time.sleep(5)  # 기본 로딩 대기
            
            # JavaScript 로딩 대기 (더 긴 시간)
            print("⏳ 게시글 JavaScript 로딩 대기 중... (60초)")
            time.sleep(60)
            
            # 현재 URL 확인
            current_url = scraper.driver.current_url
            print(f"📍 현재 URL: {current_url}")
            
            # 페이지 제목 확인
            page_title = scraper.driver.title
            print(f"📄 페이지 제목: {page_title}")
            
            # 스크린샷 저장
            scraper.driver.save_screenshot("debug_article_desktop.png")
            print("📸 스크린샷 저장: debug_article_desktop.png")
            
            # HTML 저장
            page_source = scraper.driver.page_source
            with open("debug_article_desktop.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            print("💾 HTML 저장: debug_article_desktop.html")
            
            # 업데이트된 스크래핑 로직 테스트
            print("\n🧪 업데이트된 스크래핑 로직 테스트:")
            
            # 제목 추출 테스트
            print("🔍 제목 추출 테스트:")
            title_selectors = [
                "h3.title",
                "h2.title", 
                "h1.title",
                ".title",
                ".se-title-text",
                ".se-fs-",
                ".se-component-content h1",
                ".se-component-content h2", 
                ".se-component-content h3",
                ".se-text-paragraph"
            ]
            
            title_found = False
            for selector in title_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.strip()
                            if text and len(text) > 5:
                                print(f"   ✅ {selector}: {text[:50]}...")
                                title_found = True
                                break
                        if title_found:
                            break
                except:
                    continue
            
            if not title_found:
                print("   ❌ 제목을 찾을 수 없음")
            
            # 내용 추출 테스트
            print("\n🔍 내용 추출 테스트:")
            content_selectors = [
                ".content",
                ".se-main-container",
                ".se-component-content",
                ".se-text-paragraph",
                ".se-text",
                ".se-component",
                ".article_content",
                ".post_content"
            ]
            
            content_found = False
            for selector in content_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.strip()
                            if text and len(text) > 10:
                                print(f"   ✅ {selector}: {text[:50]}...")
                                content_found = True
                                break
                        if content_found:
                            break
                except:
                    continue
            
            if not content_found:
                print("   ❌ 내용을 찾을 수 없음")
            
            # 작성자 추출 테스트
            print("\n🔍 작성자 추출 테스트:")
            author_selectors = [
                ".nick",
                ".nickname",
                ".author", 
                ".writer",
                "[class*='nick']",
                "[class*='author']",
                "[class*='writer']"
            ]
            
            author_found = False
            for selector in author_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.strip()
                            if text:
                                print(f"   ✅ {selector}: {text[:30]}...")
                                author_found = True
                                break
                        if author_found:
                            break
                except:
                    continue
            
            if not author_found:
                print("   ❌ 작성자를 찾을 수 없음")
            
            # 댓글 추출 테스트
            print("\n🔍 댓글 추출 테스트:")
            comment_selectors = [
                ".comment_area",
                ".LinkComment",
                ".comment",
                ".reply",
                "[class*='comment']",
                "[class*='reply']"
            ]
            
            comment_found = False
            for selector in comment_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        print(f"   ✅ {selector}: {len(elements)}개 발견")
                        comment_found = True
                        break
                except:
                    continue
            
            if not comment_found:
                print("   ❌ 댓글을 찾을 수 없음")
            
            print("\n✅ 테스트 완료!")
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
    test_desktop_version()
