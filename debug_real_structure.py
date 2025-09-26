#!/usr/bin/env python3
"""
네이버 카페 실제 HTML 구조 완전 분석
실제 게시글 페이지의 정확한 구조를 파악합니다.
"""

import os
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def analyze_real_structure():
    """실제 네이버 카페 게시글 구조 완전 분석"""
    
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
        
        print("🔍 네이버 카페 실제 HTML 구조 완전 분석 시작...")
        
        # 테스트할 게시글 URL
        test_url = "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false"
        
        print(f"📄 분석 대상: {test_url}")
        
        # 페이지 로드
        driver.get(test_url)
        time.sleep(8)  # 충분한 로딩 대기
        
        # 스크린샷 저장
        driver.save_screenshot("debug_real_structure.png")
        
        # 페이지 소스 저장
        page_source = driver.page_source
        with open("debug_page_source_full.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        
        print("✅ 페이지 소스 저장 완료: debug_page_source_full.html")
        
        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # 1. 모든 텍스트 요소 완전 분석
        print("\n🔍 모든 텍스트 요소 완전 분석:")
        analyze_all_text_elements(driver, soup)
        
        # 2. 실제 게시글 제목 찾기
        print("\n🔍 실제 게시글 제목 찾기:")
        find_real_title(driver, soup)
        
        # 3. 실제 게시글 내용 찾기
        print("\n🔍 실제 게시글 내용 찾기:")
        find_real_content(driver, soup)
        
        # 4. 실제 작성자 찾기
        print("\n🔍 실제 작성자 찾기:")
        find_real_author(driver, soup)
        
        # 5. 페이지 구조 완전 분석
        print("\n🔍 페이지 구조 완전 분석:")
        analyze_complete_structure(driver, soup)
        
        driver.quit()
        print("\n✅ 완전 분석 완료")
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

def analyze_all_text_elements(driver, soup):
    """모든 텍스트 요소 완전 분석"""
    
    # 모든 요소에서 텍스트 추출
    all_elements = soup.find_all(['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'article', 'section'])
    
    text_elements = []
    for elem in all_elements:
        text = elem.get_text().strip()
        if text and len(text) > 5 and len(text) < 500:  # 의미있는 텍스트만
            classes = elem.get('class', [])
            text_elements.append({
                'text': text,
                'classes': classes,
                'tag': elem.name,
                'id': elem.get('id', '')
            })
    
    print(f"   📋 텍스트가 있는 요소: {len(text_elements)}개")
    
    # 처음 20개 출력
    for i, elem in enumerate(text_elements[:20]):
        classes_str = ' '.join(elem['classes']) if elem['classes'] else 'no-class'
        id_str = elem['id'] if elem['id'] else 'no-id'
        print(f"     {i+1}. [{elem['tag']}] '{elem['text'][:100]}...' (클래스: {classes_str}, ID: {id_str})")

def find_real_title(driver, soup):
    """실제 게시글 제목 찾기"""
    
    # 가능한 모든 제목 셀렉터 시도
    title_candidates = []
    
    # 1. 모든 h 태그 확인
    h_tags = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    for h in h_tags:
        text = h.get_text().strip()
        if text and "비타민D자외선요법" not in text:  # 카페 제목 제외
            title_candidates.append({
                'text': text,
                'tag': h.name,
                'classes': h.get('class', []),
                'selector': h.name
            })
    
    # 2. title 관련 클래스 확인
    title_elements = soup.find_all(attrs={'class': lambda x: x and any('title' in cls.lower() for cls in x)})
    for elem in title_elements:
        text = elem.get_text().strip()
        if text and "비타민D자외선요법" not in text:
            title_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    # 3. se- 관련 클래스 확인
    se_elements = soup.find_all(attrs={'class': lambda x: x and any('se-' in cls for cls in x)})
    for elem in se_elements:
        text = elem.get_text().strip()
        if text and "비타민D자외선요법" not in text:
            title_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    print(f"   📋 제목 후보: {len(title_candidates)}개")
    for i, candidate in enumerate(title_candidates[:10]):
        classes_str = ' '.join(candidate['classes']) if candidate['classes'] else 'no-class'
        print(f"     {i+1}. '{candidate['text'][:100]}...' (태그: {candidate['tag']}, 클래스: {classes_str})")

def find_real_content(driver, soup):
    """실제 게시글 내용 찾기"""
    
    # 가능한 모든 내용 셀렉터 시도
    content_candidates = []
    
    # 1. se- 관련 클래스 확인
    se_elements = soup.find_all(attrs={'class': lambda x: x and any('se-' in cls for cls in x)})
    for elem in se_elements:
        text = elem.get_text().strip()
        if text and len(text) > 20:  # 의미있는 내용만
            content_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    # 2. content 관련 클래스 확인
    content_elements = soup.find_all(attrs={'class': lambda x: x and any('content' in cls.lower() for cls in x)})
    for elem in content_elements:
        text = elem.get_text().strip()
        if text and len(text) > 20:
            content_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    # 3. article 관련 클래스 확인
    article_elements = soup.find_all(attrs={'class': lambda x: x and any('article' in cls.lower() for cls in x)})
    for elem in article_elements:
        text = elem.get_text().strip()
        if text and len(text) > 20:
            content_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    print(f"   📋 내용 후보: {len(content_candidates)}개")
    for i, candidate in enumerate(content_candidates[:10]):
        classes_str = ' '.join(candidate['classes']) if candidate['classes'] else 'no-class'
        print(f"     {i+1}. '{candidate['text'][:200]}...' (태그: {candidate['tag']}, 클래스: {classes_str})")

def find_real_author(driver, soup):
    """실제 작성자 찾기"""
    
    # 가능한 모든 작성자 셀렉터 시도
    author_candidates = []
    
    # 1. nick 관련 클래스 확인
    nick_elements = soup.find_all(attrs={'class': lambda x: x and any('nick' in cls.lower() for cls in x)})
    for elem in nick_elements:
        text = elem.get_text().strip()
        if text and len(text) < 50:  # 작성자명은 보통 짧음
            author_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    # 2. author 관련 클래스 확인
    author_elements = soup.find_all(attrs={'class': lambda x: x and any('author' in cls.lower() for cls in x)})
    for elem in author_elements:
        text = elem.get_text().strip()
        if text and len(text) < 50:
            author_candidates.append({
                'text': text,
                'tag': elem.name,
                'classes': elem.get('class', []),
                'selector': f".{'.'.join(elem.get('class', []))}"
            })
    
    print(f"   📋 작성자 후보: {len(author_candidates)}개")
    for i, candidate in enumerate(author_candidates[:10]):
        classes_str = ' '.join(candidate['classes']) if candidate['classes'] else 'no-class'
        print(f"     {i+1}. '{candidate['text']}' (태그: {candidate['tag']}, 클래스: {classes_str})")

def analyze_complete_structure(driver, soup):
    """페이지 구조 완전 분석"""
    
    # 주요 컨테이너들 찾기
    main_containers = [
        'main', '.main', '#main',
        '.container', '.content', '.article',
        '.post', '.board', '.cafe',
        '[class*="Layout"]', '[class*="layout"]',
        '[class*="Content"]', '[class*="content"]',
        '[class*="Article"]', '[class*="article"]'
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
    analyze_real_structure()
