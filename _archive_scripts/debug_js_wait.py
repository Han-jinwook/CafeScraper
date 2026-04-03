#!/usr/bin/env python3
"""
네이버 카페 JavaScript 로딩 대기 및 실제 데이터 추출
JavaScript로 동적 로딩되는 내용을 기다려서 추출합니다.
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def extract_with_js_wait():
    """JavaScript 로딩 대기 후 실제 데이터 추출"""
    
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
        
        print("🔍 JavaScript 로딩 대기 후 실제 데이터 추출 시작...")
        
        # 테스트할 게시글 URL
        test_url = "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false"
        
        print(f"📄 분석 대상: {test_url}")
        
        # 페이지 로드
        driver.get(test_url)
        print("⏳ 페이지 로딩 중...")
        
        # JavaScript 로딩 대기 (최대 30초)
        wait = WebDriverWait(driver, 30)
        
        print("⏳ JavaScript 로딩 대기 중...")
        time.sleep(10)  # 기본 대기
        
        # 1. 제목 추출 시도
        print("\n🔍 제목 추출 시도:")
        title = extract_title_with_wait(driver, wait)
        print(f"   결과: '{title}'")
        
        # 2. 내용 추출 시도
        print("\n🔍 내용 추출 시도:")
        content = extract_content_with_wait(driver, wait)
        print(f"   결과: '{content[:100]}...' (길이: {len(content)})")
        
        # 3. 작성자 추출 시도
        print("\n🔍 작성자 추출 시도:")
        author = extract_author_with_wait(driver, wait)
        print(f"   결과: '{author}'")
        
        # 4. 댓글 추출 시도
        print("\n🔍 댓글 추출 시도:")
        comments = extract_comments_with_wait(driver, wait)
        print(f"   결과: {len(comments)}개 댓글")
        
        # 5. 페이지 소스 저장 (JavaScript 로딩 후)
        page_source = driver.page_source
        with open("debug_js_loaded_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("\n✅ JavaScript 로딩 후 페이지 소스 저장: debug_js_loaded_source.html")
        
        driver.quit()
        print("\n✅ JavaScript 로딩 대기 분석 완료")
        
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

def extract_title_with_wait(driver, wait):
    """JavaScript 로딩 대기 후 제목 추출"""
    
    # 가능한 제목 셀렉터들
    title_selectors = [
        # 네이버 카페 최신 구조
        ".se-title-text",
        ".se-fs-",
        ".se-component-content h1",
        ".se-component-content h2",
        ".se-component-content h3",
        # 일반적인 제목 셀렉터
        ".article_title",
        ".post_title",
        ".content_title",
        ".view_title",
        "h1.title",
        "h2.title",
        "h3.title",
        # 네이버 카페 특화
        ".cafe-article-title",
        ".article-view-title",
        ".post-view-title",
        # 최신 구조
        ".Layout_content__pUOz1 h1",
        ".Layout_content__pUOz1 h2",
        ".Layout_content__pUOz1 h3",
        # 모든 h 태그에서 카페 제목 제외
        "h1:not([class*='Layout_cafe_name']):not([class*='Header'])",
        "h2:not([class*='Layout_cafe_name']):not([class*='Header'])",
        "h3:not([class*='Layout_cafe_name']):not([class*='Header'])"
    ]
    
    for selector in title_selectors:
        try:
            # 요소가 로딩될 때까지 대기
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if element and element.text.strip():
                text = element.text.strip()
                if text and "비타민D자외선요법" not in text:  # 카페 제목 제외
                    print(f"   ✅ {selector}: '{text[:50]}...'")
                    return text
        except:
            continue
    
    return "제목을 찾을 수 없음"

def extract_content_with_wait(driver, wait):
    """JavaScript 로딩 대기 후 내용 추출"""
    
    # 가능한 내용 셀렉터들
    content_selectors = [
        # 네이버 에디터 구조
        ".se-main-container",
        ".se-component-content",
        ".se-text-paragraph",
        ".se-text",
        ".se-component",
        # 게시글 본문 영역
        ".article_content",
        ".post_content",
        ".content",
        ".article_text",
        ".board_text",
        ".article_body",
        # 네이버 카페 특화
        ".cafe-content",
        ".cafe-article-content",
        ".article-view-content",
        ".view-content",
        ".content-view",
        # 최신 구조
        ".Layout_content__pUOz1",
        ".Layout_content__pUOz1 .se-main-container",
        ".Layout_content__pUOz1 .se-component-content",
        # se- 관련 모든 클래스
        "div[class*='se-']",
        "p[class*='se-']",
        "span[class*='se-']"
    ]
    
    for selector in content_selectors:
        try:
            # 요소가 로딩될 때까지 대기
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if element and element.text.strip():
                text = element.text.strip()
                if text and len(text) > 20:  # 의미있는 내용만
                    print(f"   ✅ {selector}: '{text[:100]}...' (길이: {len(text)})")
                    return text
        except:
            continue
    
    return "내용을 찾을 수 없음"

def extract_author_with_wait(driver, wait):
    """JavaScript 로딩 대기 후 작성자 추출"""
    
    # 가능한 작성자 셀렉터들
    author_selectors = [
        ".nick",
        ".nickname",
        ".author",
        ".writer",
        ".user_nick",
        ".user_name",
        ".member_nick",
        ".member_name",
        ".cafe-nick",
        ".cafe-author",
        ".article-author",
        ".post-author",
        "[data-testid='author']",
        ".se-fs-",
        ".nickname_text",
        ".author_name",
        ".writer_name",
        "[class*='nick']",
        "[class*='author']",
        "[class*='writer']",
        ".user_info .nick",
        ".user_info .nickname",
        ".article_info .nick",
        ".article_info .nickname"
    ]
    
    for selector in author_selectors:
        try:
            # 요소가 로딩될 때까지 대기
            element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if element and element.text.strip():
                text = element.text.strip()
                if text and len(text) < 50:  # 작성자명은 보통 짧음
                    print(f"   ✅ {selector}: '{text}'")
                    return text
        except:
            continue
    
    return "작성자를 찾을 수 없음"

def extract_comments_with_wait(driver, wait):
    """JavaScript 로딩 대기 후 댓글 추출"""
    
    # 가능한 댓글 셀렉터들
    comment_selectors = [
        ".comment",
        ".reply",
        ".comment_item",
        ".reply_item",
        ".cafe-comment",
        ".cafe-reply",
        ".article-comment",
        ".article-reply",
        ".comment-list .comment",
        ".comment-list .reply",
        ".reply-list .comment",
        ".reply-list .reply",
        ".comment-area .comment",
        ".comment-area .reply",
        ".reply-area .comment",
        ".reply-area .reply",
        "[data-testid='comment']",
        "[class*='comment']",
        "[class*='Comment']",
        "[class*='reply']",
        "[class*='Reply']"
    ]
    
    comments = []
    for selector in comment_selectors:
        try:
            # 요소들이 로딩될 때까지 대기
            elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
            if elements:
                print(f"   ✅ {selector}: {len(elements)}개 댓글 발견")
                for i, elem in enumerate(elements[:5]):  # 처음 5개만
                    try:
                        text = elem.text.strip()
                        if text:
                            comments.append({
                                'comment_id': f"comment_{i+1}",
                                'text': text[:100] + "..." if len(text) > 100 else text
                            })
                    except:
                        pass
                break
        except:
            continue
    
    return comments

if __name__ == "__main__":
    extract_with_js_wait()
