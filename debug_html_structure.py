#!/usr/bin/env python3
"""
네이버 카페 게시글 HTML 구조 분석 스크립트
실제 게시글 페이지의 HTML 구조를 파악하여 새로운 셀렉터를 찾습니다.
"""

import sys
import os
import time
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from app.products.scraper.naver import NaverScraper

def analyze_html_structure():
    """실제 게시글 페이지의 HTML 구조를 분석합니다."""
    
    # 스크래퍼 초기화
    scraper = NaverScraper("sessions", "snapshots")
    
    try:
        # 브라우저 시작
        print("🔄 브라우저 시작 중...")
        scraper.start_browser()
        
        # 쿠키 로드
        scraper._load_cookies()
        
        # 테스트할 게시글 URL (실제 네이버 카페 게시글)
        test_url = "https://cafe.naver.com/vitamind/1758864410"  # 실제 게시글 URL
        
        print(f"🌐 게시글 페이지 접속: {test_url}")
        scraper.driver.get(test_url)
        time.sleep(5)  # 페이지 로딩 대기
        
        # 스크린샷 저장
        scraper.driver.save_screenshot("debug_real_structure.png")
        print("📸 스크린샷 저장: debug_real_structure.png")
        
        # 페이지 소스 분석
        print("🔍 페이지 소스 분석 중...")
        page_source = scraper.driver.page_source
        
        # HTML 파일로 저장
        with open("debug_page_source_full.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("💾 전체 HTML 소스 저장: debug_page_source_full.html")
        
        # 제목 관련 요소들 찾기
        print("\n🔍 제목 관련 요소 분석:")
        title_elements = scraper.driver.find_elements("css selector", "h1, h2, h3, h4, h5, h6")
        print(f"   발견된 h 태그: {len(title_elements)}개")
        
        for i, elem in enumerate(title_elements[:10]):  # 처음 10개만 확인
            try:
                text = elem.text.strip()
                tag_name = elem.tag_name
                class_name = elem.get_attribute("class") or ""
                if text:
                    print(f"   {i+1}. <{tag_name}> {text[:50]}... (class: {class_name[:30]})")
            except Exception as e:
                print(f"   {i+1}. 오류: {e}")
        
        # se- 관련 클래스들 찾기
        print("\n🔍 se- 관련 클래스 분석:")
        se_elements = scraper.driver.find_elements("css selector", "[class*='se-']")
        print(f"   발견된 se- 클래스: {len(se_elements)}개")
        
        for i, elem in enumerate(se_elements[:10]):
            try:
                text = elem.text.strip()
                class_name = elem.get_attribute("class") or ""
                tag_name = elem.tag_name
                if text:
                    print(f"   {i+1}. <{tag_name}> {text[:50]}... (class: {class_name[:50]})")
            except Exception as e:
                print(f"   {i+1}. 오류: {e}")
        
        # content 관련 클래스들 찾기
        print("\n🔍 content 관련 클래스 분석:")
        content_elements = scraper.driver.find_elements("css selector", "[class*='content'], [class*='Content']")
        print(f"   발견된 content 클래스: {len(content_elements)}개")
        
        for i, elem in enumerate(content_elements[:10]):
            try:
                text = elem.text.strip()
                class_name = elem.get_attribute("class") or ""
                tag_name = elem.tag_name
                if text:
                    print(f"   {i+1}. <{tag_name}> {text[:50]}... (class: {class_name[:50]})")
            except Exception as e:
                print(f"   {i+1}. 오류: {e}")
        
        # article 관련 클래스들 찾기
        print("\n🔍 article 관련 클래스 분석:")
        article_elements = scraper.driver.find_elements("css selector", "[class*='article'], [class*='Article']")
        print(f"   발견된 article 클래스: {len(article_elements)}개")
        
        for i, elem in enumerate(article_elements[:10]):
            try:
                text = elem.text.strip()
                class_name = elem.get_attribute("class") or ""
                tag_name = elem.tag_name
                if text:
                    print(f"   {i+1}. <{tag_name}> {text[:50]}... (class: {class_name[:50]})")
            except Exception as e:
                print(f"   {i+1}. 오류: {e}")
        
        # 작성자 관련 요소들 찾기
        print("\n🔍 작성자 관련 요소 분석:")
        author_elements = scraper.driver.find_elements("css selector", "[class*='nick'], [class*='author'], [class*='writer']")
        print(f"   발견된 작성자 관련 요소: {len(author_elements)}개")
        
        for i, elem in enumerate(author_elements[:10]):
            try:
                text = elem.text.strip()
                class_name = elem.get_attribute("class") or ""
                tag_name = elem.tag_name
                if text:
                    print(f"   {i+1}. <{tag_name}> {text[:30]}... (class: {class_name[:30]})")
            except Exception as e:
                print(f"   {i+1}. 오류: {e}")
        
        # 댓글 관련 요소들 찾기
        print("\n🔍 댓글 관련 요소 분석:")
        comment_elements = scraper.driver.find_elements("css selector", "[class*='comment'], [class*='reply']")
        print(f"   발견된 댓글 관련 요소: {len(comment_elements)}개")
        
        for i, elem in enumerate(comment_elements[:10]):
            try:
                text = elem.text.strip()
                class_name = elem.get_attribute("class") or ""
                tag_name = elem.tag_name
                if text:
                    print(f"   {i+1}. <{tag_name}> {text[:30]}... (class: {class_name[:30]})")
            except Exception as e:
                print(f"   {i+1}. 오류: {e}")
        
        # 모든 클래스 이름 수집
        print("\n🔍 모든 클래스 이름 수집:")
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
        keywords = ['title', 'content', 'article', 'post', 'author', 'nick', 'comment', 'reply', 'se-']
        
        for class_name in all_classes:
            if any(keyword in class_name.lower() for keyword in keywords):
                relevant_classes.append(class_name)
        
        print(f"   관련 클래스 {len(relevant_classes)}개 발견:")
        for i, class_name in enumerate(sorted(relevant_classes)[:20]):  # 처음 20개만 출력
            print(f"   {i+1}. {class_name}")
        
        print("\n✅ HTML 구조 분석 완료!")
        print("📁 생성된 파일들:")
        print("   - debug_real_structure.png (스크린샷)")
        print("   - debug_page_source_full.html (전체 HTML)")
        
    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 브라우저 종료
        try:
            scraper.close()
        except:
            pass

if __name__ == "__main__":
    analyze_html_structure()
