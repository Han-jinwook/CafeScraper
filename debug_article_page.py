#!/usr/bin/env python3
"""
실제 게시글 페이지에서 HTML 구조 분석
"""

import sys
import os
import time
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from app.scraper.naver import NaverScraper

def analyze_article_page():
    """실제 게시글 페이지 분석"""
    
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 브라우저 시작
        print("🔄 브라우저 시작 중...")
        scraper.start_browser()
        
        # 쿠키 로드
        scraper._load_cookies()
        
        # 중고나라 카페의 실제 게시글 페이지 접근
        print("🌐 중고나라 카페 접속...")
        scraper.driver.get("https://cafe.naver.com/joonggonara")
        time.sleep(5)
        
        # 게시글 링크 찾기
        print("🔍 게시글 링크 찾기...")
        article_links = scraper.driver.find_elements("css selector", "a[href*='ArticleRead']")
        print(f"   발견된 게시글 링크: {len(article_links)}개")
        
        if article_links:
            # 첫 번째 게시글 링크 클릭
            first_link = article_links[0]
            article_url = first_link.get_attribute("href")
            print(f"📄 첫 번째 게시글 접속: {article_url}")
            
            scraper.driver.get(article_url)
            time.sleep(5)  # 기본 로딩 대기
            
            # JavaScript 로딩 대기 (더 긴 시간)
            print("⏳ JavaScript 로딩 대기 중... (30초)")
            time.sleep(30)
            
            # 스크린샷 저장
            scraper.driver.save_screenshot("debug_article_page.png")
            print("📸 스크린샷 저장: debug_article_page.png")
            
            # HTML 저장
            page_source = scraper.driver.page_source
            with open("debug_article_page.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            print("💾 HTML 저장: debug_article_page.html")
            
            # 제목 분석
            print("\n🔍 제목 분석:")
            h_elements = scraper.driver.find_elements("css selector", "h1, h2, h3, h4, h5, h6")
            print(f"   h 태그: {len(h_elements)}개")
            
            for i, elem in enumerate(h_elements[:10]):
                try:
                    text = elem.text.strip()
                    tag_name = elem.tag_name
                    class_name = elem.get_attribute("class") or ""
                    if text and len(text) > 5:  # 의미있는 텍스트만
                        print(f"   {i+1}. <{tag_name}> {text[:50]}... (class: {class_name[:30]})")
                except:
                    pass
            
            # 내용 분석
            print("\n🔍 내용 분석:")
            content_selectors = [
                ".se-main-container",
                ".se-component-content", 
                ".se-text-paragraph",
                ".article_content",
                ".post_content",
                ".content",
                "[class*='content']",
                "[class*='article']",
                "[class*='post']"
            ]
            
            for selector in content_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        print(f"   {selector}: {len(elements)}개 발견")
                        for i, elem in enumerate(elements[:3]):
                            try:
                                text = elem.text.strip()
                                if text and len(text) > 10:
                                    print(f"      {i+1}. {text[:50]}...")
                            except:
                                pass
                except:
                    pass
            
            # 작성자 분석
            print("\n🔍 작성자 분석:")
            author_selectors = [
                ".nick",
                ".nickname",
                ".author", 
                ".writer",
                "[class*='nick']",
                "[class*='author']",
                "[class*='writer']"
            ]
            
            for selector in author_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        print(f"   {selector}: {len(elements)}개 발견")
                        for i, elem in enumerate(elements[:3]):
                            try:
                                text = elem.text.strip()
                                if text:
                                    print(f"      {i+1}. {text[:30]}...")
                            except:
                                pass
                except:
                    pass
            
            # 댓글 분석
            print("\n🔍 댓글 분석:")
            comment_selectors = [
                ".comment",
                ".reply",
                "[class*='comment']",
                "[class*='reply']"
            ]
            
            for selector in comment_selectors:
                try:
                    elements = scraper.driver.find_elements("css selector", selector)
                    if elements:
                        print(f"   {selector}: {len(elements)}개 발견")
                        for i, elem in enumerate(elements[:3]):
                            try:
                                text = elem.text.strip()
                                if text and len(text) > 5:
                                    print(f"      {i+1}. {text[:30]}...")
                            except:
                                pass
                except:
                    pass
            
            # 모든 클래스 이름 수집
            print("\n🔍 모든 클래스 분석:")
            all_elements = scraper.driver.find_elements("css selector", "*")
            all_classes = set()
            
            for elem in all_elements:
                try:
                    class_name = elem.get_attribute("class")
                    if class_name:
                        all_classes.update(class_name.split())
                except:
                    continue
            
            # 관련 키워드가 포함된 클래스들만 필터링
            relevant_classes = []
            keywords = ['title', 'content', 'article', 'post', 'author', 'nick', 'comment', 'reply', 'se-', 'text']
            
            for class_name in all_classes:
                if any(keyword in class_name.lower() for keyword in keywords):
                    relevant_classes.append(class_name)
            
            print(f"   관련 클래스 {len(relevant_classes)}개 발견:")
            for i, class_name in enumerate(sorted(relevant_classes)[:30]):  # 처음 30개만 출력
                print(f"   {i+1}. {class_name}")
        
        print("\n✅ 게시글 페이지 분석 완료!")
        
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            scraper.close()
        except:
            pass

if __name__ == "__main__":
    analyze_article_page()
