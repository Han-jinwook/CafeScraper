#!/usr/bin/env python3
"""
네이버 카페 수동 검사 도구
브라우저를 열어서 실제 게시글 구조를 수동으로 확인합니다.
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def manual_inspection():
    """수동 검사를 위한 브라우저 열기"""
    
    # Chrome 옵션 설정 (헤드리스 모드 비활성화)
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent 설정
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 헤드리스 모드 비활성화 (브라우저 창이 보이도록)
    # chrome_options.add_argument("--headless")  # 이 줄을 주석 처리
    
    try:
        # WebDriver 초기화
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 자동화 감지 방지
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("🔍 네이버 카페 수동 검사를 위한 브라우저를 열었습니다.")
        print("📋 다음 단계를 따라주세요:")
        print("1. 브라우저에서 네이버 카페 게시글을 열어주세요")
        print("2. F12를 눌러 개발자 도구를 열어주세요")
        print("3. Elements 탭에서 게시글 제목과 내용의 HTML 구조를 확인해주세요")
        print("4. 확인이 완료되면 이 창에서 Enter를 눌러주세요")
        
        # 테스트할 게시글 URL
        test_url = "https://cafe.naver.com/f-e/cafes/27870803/articles/66575?boardtype=L&menuid=185&referrerAllArticles=false"
        
        print(f"\n📄 테스트 게시글: {test_url}")
        
        # 페이지 로드
        driver.get(test_url)
        time.sleep(3)
        
        print("\n✅ 브라우저가 열렸습니다. 개발자 도구로 HTML 구조를 확인해주세요.")
        print("   특히 다음 요소들을 찾아주세요:")
        print("   - 게시글 제목이 있는 HTML 요소")
        print("   - 게시글 내용이 있는 HTML 요소")
        print("   - 작성자 정보가 있는 HTML 요소")
        print("   - 댓글이 있는 HTML 요소")
        
        # 사용자 입력 대기
        input("\n확인 완료 후 Enter를 눌러주세요...")
        
        # 페이지 소스 저장
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        print("✅ 페이지 소스가 debug_page_source.html에 저장되었습니다.")
        
        driver.quit()
        print("✅ 브라우저가 닫혔습니다.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    manual_inspection()
