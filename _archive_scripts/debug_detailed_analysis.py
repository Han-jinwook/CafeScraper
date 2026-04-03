#!/usr/bin/env python3
"""
네이버 카페 상세 HTML 구조 분석
실제 게시글 제목과 내용의 위치를 찾습니다.
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

def detailed_analysis():
    """상세 HTML 구조 분석"""
    
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
        
        print("🔍 네이버 카페 상세 HTML 구조 분석 시작...")
        
        # 테스트할 게시글 URL
        test_url = "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false"
        
        print(f"📄 게시글 분석: {test_url}")
        
        # 페이지 로드
        driver.get(test_url)
        time.sleep(5)  # 페이지 로딩 대기
        
        # 스크린샷 저장
        driver.save_screenshot("debug_detailed_analysis.png")
        
        # 페이지 소스 분석
        page_source = driver.page_source
        
        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(page_source, 'html.parser')
        
        print(f"✅ 페이지 로드 완료")
        
        # 1. 모든 텍스트가 있는 요소들 찾기
        print("\n🔍 모든 텍스트 요소 분석:")
        find_all_text_elements(driver, soup)
        
        # 2. 게시글 제목이 있을 수 있는 영역들 상세 분석
        print("\n🔍 게시글 제목 상세 분석:")
        analyze_title_detailed(driver, soup)
        
        # 3. 게시글 내용이 있을 수 있는 영역들 상세 분석
        print("\n🔍 게시글 내용 상세 분석:")
        analyze_content_detailed(driver, soup)
        
        # 4. 페이지 구조 전체 분석
        print("\n🔍 페이지 구조 전체 분석:")
        analyze_page_structure(driver, soup)
        
        driver.quit()
        print("\n✅ 상세 HTML 구조 분석 완료")
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

def find_all_text_elements(driver, soup):
    """모든 텍스트 요소 찾기"""
    
    # 모든 div 요소에서 텍스트가 있는 것들 찾기
    all_divs = soup.find_all('div')
    text_elements = []
    
    for div in all_divs:
        text = div.get_text().strip()
        if text and len(text) > 10 and len(text) < 200:  # 의미있는 텍스트만
            classes = div.get('class', [])
            text_elements.append({
                'text': text,
                'classes': classes,
                'tag': div.name
            })
    
    print(f"   📋 텍스트가 있는 div 요소: {len(text_elements)}개")
    
    # 처음 10개만 출력
    for i, elem in enumerate(text_elements[:10]):
        classes_str = ' '.join(elem['classes']) if elem['classes'] else 'no-class'
        print(f"     {i+1}. '{elem['text'][:50]}...' (클래스: {classes_str})")

def analyze_title_detailed(driver, soup):
    """게시글 제목 상세 분석"""
    
    # 가능한 제목 셀렉터들
    title_selectors = [
        # 일반적인 제목 셀렉터
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        '.title', '.article-title', '.post-title',
        '.content-title', '.board-title',
        # 네이버 카페 특화
        '.cafe-title', '.article-title',
        # 클래스 패턴
        '[class*="title"]', '[class*="Title"]',
        '[class*="article"]', '[class*="Article"]',
        '[class*="post"]', '[class*="Post"]',
        # 최신 네이버 구조
        '.se-title', '.se-text',
        '[class*="se-"]'
    ]
    
    for selector in title_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 발견")
                for i, elem in enumerate(elements[:3]):
                    try:
                        text = elem.text.strip()
                        classes = elem.get_attribute('class') or ''
                        if text and len(text) > 5:
                            print(f"     {i+1}. '{text[:100]}...' (클래스: {classes})")
                    except:
                        pass
        except Exception as e:
            print(f"   ❌ {selector}: 오류 - {e}")

def analyze_content_detailed(driver, soup):
    """게시글 내용 상세 분석"""
    
    # 가능한 내용 셀렉터들
    content_selectors = [
        # 일반적인 내용 셀렉터
        '.content', '.article-content', '.post-content',
        '.text', '.article-text', '.post-text',
        # 네이버 카페 특화
        '.cafe-content', '.article-content',
        # 클래스 패턴
        '[class*="content"]', '[class*="Content"]',
        '[class*="text"]', '[class*="Text"]',
        '[class*="article"]', '[class*="Article"]',
        '[class*="post"]', '[class*="Post"]',
        # 최신 네이버 구조
        '.se-main-container', '.se-component-content',
        '.se-text-paragraph', '.se-text',
        '[class*="se-"]'
    ]
    
    for selector in content_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 발견")
                for i, elem in enumerate(elements[:2]):
                    try:
                        text = elem.text.strip()
                        classes = elem.get_attribute('class') or ''
                        if text and len(text) > 20:
                            print(f"     {i+1}. '{text[:200]}...' (클래스: {classes})")
                    except:
                        pass
        except Exception as e:
            print(f"   ❌ {selector}: 오류 - {e}")

def analyze_page_structure(driver, soup):
    """페이지 구조 전체 분석"""
    
    # 주요 컨테이너들 찾기
    main_containers = [
        'main', '.main', '#main',
        '.container', '.content', '.article',
        '.post', '.board', '.cafe',
        '[class*="Layout"]', '[class*="layout"]',
        '[class*="Content"]', '[class*="content"]'
    ]
    
    for selector in main_containers:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 발견")
                for i, elem in enumerate(elements[:2]):
                    try:
                        text = elem.text.strip()
                        classes = elem.get_attribute('class') or ''
                        if text and len(text) > 50:
                            print(f"     {i+1}. '{text[:100]}...' (클래스: {classes})")
                    except:
                        pass
        except Exception as e:
            print(f"   ❌ {selector}: 오류 - {e}")

if __name__ == "__main__":
    detailed_analysis()
