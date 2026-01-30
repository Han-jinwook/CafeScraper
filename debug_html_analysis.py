#!/usr/bin/env python3
"""
네이버 카페 HTML 구조 분석 도구
실제 페이지 구조를 분석하여 올바른 셀렉터를 찾습니다.
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json

def analyze_naver_cafe_structure():
    """네이버 카페 HTML 구조를 상세 분석"""
    
    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent 설정
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # WebDriver 초기화
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 자동화 감지 방지
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🔍 네이버 카페 HTML 구조 분석 시작...")
        
        # 테스트할 게시글 URL (실제 게시글)
        test_urls = [
            "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false",
            "https://cafe.naver.com/f-e/cafes/27870803/articles/66747?boardtype=L&menuid=185&referrerAllArticles=false",
            "https://cafe.naver.com/f-e/cafes/27870803/articles/66743?boardtype=L&menuid=185&referrerAllArticles=false"
        ]
        
        for i, url in enumerate(test_urls, 1):
            print(f"\n📄 게시글 {i} 분석: {url}")
            
            try:
                # 페이지 로드
                driver.get(url)
                time.sleep(5)  # 페이지 로딩 대기
                
                # 스크린샷 저장
                driver.save_screenshot(f"debug_article_{i}.png")
                
                # 페이지 소스 분석
                page_source = driver.page_source
                
                # BeautifulSoup으로 파싱
                soup = BeautifulSoup(page_source, 'html.parser')
                
                print(f"✅ 페이지 로드 완료: {url}")
                
                # 1. 제목 분석
                print("\n🔍 제목 분석:")
                analyze_title_structure(driver, soup, i)
                
                # 2. 내용 분석
                print("\n🔍 내용 분석:")
                analyze_content_structure(driver, soup, i)
                
                # 3. 작성자 분석
                print("\n🔍 작성자 분석:")
                analyze_author_structure(driver, soup, i)
                
                # 4. 댓글 분석
                print("\n🔍 댓글 분석:")
                analyze_comment_structure(driver, soup, i)
                
            except Exception as e:
                print(f"❌ 게시글 {i} 분석 실패: {e}")
                continue
        
        driver.quit()
        print("\n✅ HTML 구조 분석 완료")
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

def analyze_title_structure(driver, soup, article_num):
    """제목 구조 분석"""
    
    # 1. 모든 h 태그 찾기
    h_tags = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    print(f"   📋 발견된 h 태그: {len(h_tags)}개")
    
    for i, h_tag in enumerate(h_tags[:5]):  # 처음 5개만 출력
        text = h_tag.get_text().strip()
        classes = h_tag.get('class', [])
        if text:
            print(f"     h{i+1}: '{text[:50]}...' (클래스: {classes})")
    
    # 2. title 관련 클래스 찾기
    title_elements = soup.find_all(attrs={'class': lambda x: x and 'title' in ' '.join(x).lower()})
    print(f"   📋 title 관련 클래스: {len(title_elements)}개")
    
    for i, elem in enumerate(title_elements[:3]):
        text = elem.get_text().strip()
        classes = elem.get('class', [])
        if text:
            print(f"     title {i+1}: '{text[:50]}...' (클래스: {classes})")
    
    # 3. se- 관련 클래스 찾기 (네이버 에디터)
    se_elements = soup.find_all(attrs={'class': lambda x: x and any('se-' in cls for cls in x)})
    print(f"   📋 se- 관련 클래스: {len(se_elements)}개")
    
    for i, elem in enumerate(se_elements[:3]):
        text = elem.get_text().strip()
        classes = elem.get('class', [])
        if text:
            print(f"     se- {i+1}: '{text[:50]}...' (클래스: {classes})")
    
    # 4. 실제 게시글 제목이 있을 수 있는 영역들 확인
    print("   🔍 게시글 제목 후보 영역:")
    
    # 게시글 본문 영역 찾기
    content_areas = [
        '.se-main-container',
        '.se-component-content', 
        '.article_content',
        '.post_content',
        '.content',
        '[class*="article"]',
        '[class*="content"]'
    ]
    
    for selector in content_areas:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"     ✅ {selector}: {len(elements)}개 발견")
                for j, elem in enumerate(elements[:2]):
                    try:
                        text = elem.text.strip()
                        if text and len(text) > 10:  # 의미있는 텍스트만
                            print(f"       내용 {j+1}: '{text[:100]}...'")
                    except:
                        pass
        except:
            pass

def analyze_content_structure(driver, soup, article_num):
    """내용 구조 분석"""
    
    # 1. se- 관련 클래스들 (네이버 에디터)
    se_elements = soup.find_all(attrs={'class': lambda x: x and any('se-' in cls for cls in x)})
    print(f"   📋 se- 관련 요소: {len(se_elements)}개")
    
    # 2. 게시글 본문 영역들
    content_selectors = [
        '.se-main-container',
        '.se-component-content',
        '.article_content',
        '.post_content',
        '.content',
        '[class*="content"]',
        '[class*="article"]'
    ]
    
    for selector in content_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 발견")
                for i, elem in enumerate(elements[:2]):
                    try:
                        text = elem.text.strip()
                        if text and len(text) > 20:
                            print(f"     내용 {i+1}: '{text[:100]}...'")
                    except:
                        pass
        except:
            pass

def analyze_author_structure(driver, soup, article_num):
    """작성자 구조 분석"""
    
    # 작성자 관련 클래스들
    author_selectors = [
        '.nick',
        '.nickname',
        '.author',
        '.writer',
        '[class*="nick"]',
        '[class*="author"]',
        '[class*="writer"]'
    ]
    
    for selector in author_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 발견")
                for i, elem in enumerate(elements[:3]):
                    try:
                        text = elem.text.strip()
                        if text:
                            print(f"     작성자 {i+1}: '{text}'")
                    except:
                        pass
        except:
            pass

def analyze_comment_structure(driver, soup, article_num):
    """댓글 구조 분석"""
    
    # 댓글 관련 클래스들
    comment_selectors = [
        '.comment',
        '.reply',
        '[class*="comment"]',
        '[class*="reply"]'
    ]
    
    for selector in comment_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 발견")
        except:
            pass

if __name__ == "__main__":
    analyze_naver_cafe_structure()
