#!/usr/bin/env python3
"""
네이버 카페 대안적 접근법
JavaScript 로딩 문제를 우회하는 새로운 방법을 시도합니다.
"""

import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json

def alternative_approach():
    """대안적 접근법으로 네이버 카페 데이터 추출"""
    
    print("🔍 네이버 카페 대안적 접근법 시작...")
    
    # 1. API 기반 접근 시도
    print("\n1️⃣ API 기반 접근 시도:")
    try_api_approach()
    
    # 2. 네트워크 요청 분석
    print("\n2️⃣ 네트워크 요청 분석:")
    analyze_network_requests()
    
    # 3. 완전히 다른 셀렉터 시도
    print("\n3️⃣ 완전히 다른 셀렉터 시도:")
    try_different_selectors()

def try_api_approach():
    """API 기반 접근 시도"""
    
    # 네이버 카페 API 엔드포인트 시도
    api_urls = [
        "https://cafe.naver.com/api/cafe/27870803/articles/66575",
        "https://cafe.naver.com/f-e/cafes/27870803/articles/66575.json",
        "https://cafe.naver.com/api/articles/66575",
        "https://cafe.naver.com/api/cafe/articles/66575"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Referer': 'https://cafe.naver.com/sundreamd'
    }
    
    for url in api_urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"   ✅ API 성공: {url}")
                try:
                    data = response.json()
                    print(f"   📊 데이터: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
                    return data
                except:
                    print(f"   📊 텍스트 데이터: {response.text[:200]}...")
            else:
                print(f"   ❌ API 실패: {url} (상태: {response.status_code})")
        except Exception as e:
            print(f"   ❌ API 오류: {url} - {e}")
    
    print("   ❌ 모든 API 접근 실패")

def analyze_network_requests():
    """네트워크 요청 분석"""
    
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
        
        # 네트워크 로그 활성화
        driver.execute_cdp_cmd('Network.enable', {})
        
        # 페이지 로드
        test_url = "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false"
        driver.get(test_url)
        
        print("   ⏳ 네트워크 요청 분석 중...")
        time.sleep(10)  # 네트워크 요청 대기
        
        # 네트워크 로그 가져오기
        logs = driver.get_log('performance')
        
        print(f"   📊 네트워크 요청: {len(logs)}개")
        
        # JSON 응답 찾기
        json_responses = []
        for log in logs:
            try:
                message = json.loads(log['message'])
                if message['message']['method'] == 'Network.responseReceived':
                    response = message['message']['params']['response']
                    if 'application/json' in response.get('mimeType', ''):
                        json_responses.append(response['url'])
                        print(f"   ✅ JSON 응답 발견: {response['url']}")
            except:
                pass
        
        if json_responses:
            print(f"   📊 발견된 JSON 응답: {len(json_responses)}개")
            for url in json_responses[:5]:  # 처음 5개만 출력
                print(f"     - {url}")
        else:
            print("   ❌ JSON 응답을 찾을 수 없음")
        
        driver.quit()
        
    except Exception as e:
        print(f"   ❌ 네트워크 분석 실패: {e}")

def try_different_selectors():
    """완전히 다른 셀렉터 시도"""
    
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
        
        # 페이지 로드
        test_url = "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false"
        driver.get(test_url)
        
        print("   ⏳ 페이지 로딩 대기...")
        time.sleep(15)  # 충분한 대기
        
        # 완전히 새로운 셀렉터 시도
        new_selectors = [
            # 1. 모든 텍스트 요소에서 의미있는 것 찾기
            "*[class*='title']",
            "*[class*='Title']",
            "*[class*='content']",
            "*[class*='Content']",
            "*[class*='article']",
            "*[class*='Article']",
            "*[class*='post']",
            "*[class*='Post']",
            "*[class*='text']",
            "*[class*='Text']",
            # 2. 특정 속성으로 찾기
            "*[data-title]",
            "*[data-content]",
            "*[data-article]",
            "*[data-post]",
            # 3. ID로 찾기
            "*[id*='title']",
            "*[id*='content']",
            "*[id*='article']",
            "*[id*='post']",
            # 4. 모든 div에서 텍스트가 있는 것
            "div:not([class*='gnb']):not([class*='Layout_cafe']):not([class*='Header'])",
            "span:not([class*='gnb']):not([class*='Layout_cafe']):not([class*='Header'])",
            "p:not([class*='gnb']):not([class*='Layout_cafe']):not([class*='Header'])"
        ]
        
        for selector in new_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"   ✅ {selector}: {len(elements)}개 발견")
                    for i, elem in enumerate(elements[:3]):  # 처음 3개만 확인
                        try:
                            text = elem.text.strip()
                            if text and len(text) > 5 and len(text) < 200:
                                print(f"     {i+1}. '{text[:100]}...'")
                        except:
                            pass
            except:
                continue
        
        driver.quit()
        
    except Exception as e:
        print(f"   ❌ 셀렉터 시도 실패: {e}")

if __name__ == "__main__":
    alternative_approach()
