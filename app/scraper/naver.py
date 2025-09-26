from __future__ import annotations
import asyncio
import json
import os
import time
import psutil
import base64
from pathlib import Path
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests

# 로깅 시스템 임포트
try:
    from app.utils.logger import scraping_logger
except ImportError:
    # 로깅 시스템이 없을 때 기본 로깅
    class DummyLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def debug(self, msg): print(f"DEBUG: {msg}")
        def log_scraping_start(self, url, total): self.info(f"🚀 스크래핑 시작: {url} (총 {total}개)")
        def log_scraping_progress(self, current, total, url): self.info(f"📄 [{current:3d}/{total:3d}] {url}")
        def log_scraping_success(self, url, title): self.info(f"✅ 성공: {title}")
        def log_scraping_error(self, url, error): self.error(f"❌ 실패: {url} - {error}")
        def log_scraping_complete(self, successful, failed, total): self.info(f"📊 완료: 성공 {successful}개, 실패 {failed}개")
        def log_performance(self, operation, duration, details=""): self.info(f"⏱️ {operation}: {duration:.2f}초")
        def log_memory_usage(self, operation, memory_mb): self.info(f"💾 {operation}: {memory_mb:.1f}MB")
        def log_antibot_measure(self, measure, details=""): self.info(f"🛡️ 안티봇 대응: {measure}")
    
    scraping_logger = DummyLogger()

class NaverScraper:
    """Naver Cafe scraper using Selenium WebDriver with manual login and cookie persistence."""

    def __init__(self, sessions_dir: str, snapshots_dir: str) -> None:
        self.sessions_dir = Path(sessions_dir)
        self.snapshots_dir = Path(snapshots_dir)
        self.sessions_dir.mkdir(exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)
        
        self.driver: Optional[webdriver.Chrome] = None
        self._cookie_file = self.sessions_dir / "naver_cookies.json"

    def start_browser(self) -> None:
        """Start Chrome browser with persistent context for cookie management."""
        if self.driver:
            print("✅ 브라우저가 이미 실행 중입니다.")
            return
        
        try:
            print("🔄 Selenium Chrome 브라우저 시작 중...")
            
            # Chrome 옵션 설정 (세션 안정성 강화)
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-field-trial-config")
            chrome_options.add_argument("--disable-back-forward-cache")
            chrome_options.add_argument("--disable-ipc-flooding-protection")
            # 세션 안정성 강화 옵션 추가
            chrome_options.add_argument("--disable-hang-monitor")
            chrome_options.add_argument("--disable-prompt-on-repost")
            chrome_options.add_argument("--disable-sync")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("--disable-permissions-api")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.cookies": 1,  # 쿠키 허용
                "profile.default_content_setting_values.javascript": 1,  # JavaScript 허용
                "profile.default_content_setting_values.plugins": 1,  # 플러그인 허용
                "profile.default_content_setting_values.media_stream": 2,  # 미디어 스트림 차단
                "profile.default_content_setting_values.geolocation": 2,  # 위치 정보 차단
                "profile.default_content_setting_values.camera": 2,  # 카메라 차단
                "profile.default_content_setting_values.microphone": 2  # 마이크 차단
            })
            
            # User-Agent 설정
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # 헤드리스 모드 (필요시 주석 해제)
            # chrome_options.add_argument("--headless")
            
            # WebDriver 초기화
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 자동화 감지 방지
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Selenium Chrome 브라우저 시작 완료")
            
        except Exception as e:
            print(f"❌ 브라우저 시작 실패: {e}")
            print(f"❌ 에러 타입: {type(e).__name__}")
            print(f"❌ 에러 상세: {str(e)}")
            raise Exception(f"브라우저 시작 실패: {str(e)}")

    def _load_cookies(self) -> None:
        """Load saved cookies from file with improved domain handling."""
        if self._cookie_file.exists() and self.driver:
            try:
                with open(self._cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                loaded_count = 0
                
                # 네이버 메인 페이지로 이동 후 쿠키 로드
                self.driver.get("https://www.naver.com")
                time.sleep(3)  # 페이지 로딩 대기 시간 증가
                
                for cookie in cookies:
                    try:
                        # 도메인 수정하여 로드 시도
                        original_domain = cookie.get('domain', '')
                        
                        # 쿠키 복사본 생성
                        cookie_copy = cookie.copy()
                        
                        # 도메인 처리 개선
                        if original_domain.startswith('.naver.com'):
                            # .naver.com 도메인 쿠키는 그대로 로드
                            self.driver.add_cookie(cookie_copy)
                            loaded_count += 1
                        elif original_domain.startswith('.cafe.naver.com'):
                            # .cafe.naver.com 도메인 쿠키는 .naver.com으로 변경하여 로드
                            cookie_copy['domain'] = '.naver.com'
                            self.driver.add_cookie(cookie_copy)
                            loaded_count += 1
                        elif original_domain.startswith('www.naver.com'):
                            # www.naver.com 도메인 쿠키는 .naver.com으로 변경
                            cookie_copy['domain'] = '.naver.com'
                            self.driver.add_cookie(cookie_copy)
                            loaded_count += 1
                        else:
                            # 기타 도메인 쿠키는 도메인을 제거하고 로드
                            if 'domain' in cookie_copy:
                                del cookie_copy['domain']
                            self.driver.add_cookie(cookie_copy)
                            loaded_count += 1
                            
                    except Exception as e:
                        print(f"⚠️ 쿠키 로드 실패: {cookie.get('name', 'unknown')} - {e}")
                        continue
                
                print(f"✅ Loaded {loaded_count} cookies from {self._cookie_file}")
                
                # 쿠키 로드 후 페이지 새로고침하여 세션 활성화
                self.driver.refresh()
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Failed to load cookies: {e}")

    def _save_cookies(self) -> None:
        """Save current cookies to file."""
        if self.driver:
            try:
                cookies = self.driver.get_cookies()
                # 쿠키 파일이 이미 존재하고 유효한 경우 덮어쓰지 않음
                if self._cookie_file.exists():
                    try:
                        with open(self._cookie_file, 'r', encoding='utf-8') as f:
                            existing_cookies = json.load(f)
                        if len(existing_cookies) > 0:
                            print(f"✅ 기존 쿠키 파일 유지 ({len(existing_cookies)}개 쿠키)")
                            return
                    except:
                        pass  # 기존 파일이 손상된 경우 새로 저장
                
                with open(self._cookie_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print(f"✅ Saved {len(cookies)} cookies to {self._cookie_file}")
            except Exception as e:
                print(f"⚠️ Failed to save cookies: {e}")

    def _check_login_status(self) -> bool:
        """로그인 상태만 확인 (재로그인 시도하지 않음)"""
        try:
            # 쿠키 파일이 있으면 로그인된 것으로 간주
            if self._cookie_file.exists():
                print("✅ 쿠키 파일 존재 - 로그인된 것으로 간주")
                return True
            
            # 네이버 메인 페이지로 이동
            self.driver.get("https://www.naver.com")
            time.sleep(3)
            
            # 여러 방법으로 로그인 상태 확인
            login_indicators = [
                # 로그인 버튼이 없으면 로그인된 상태
                len(self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그인')]")) == 0,
                # 사용자 프로필이 있으면 로그인된 상태
                len(self.driver.find_elements(By.XPATH, "//a[contains(@href, 'nid.naver.com')]")) > 0,
                # 닉네임이 표시되면 로그인된 상태
                len(self.driver.find_elements(By.XPATH, "//span[contains(@class, 'MyView-module__link_login___HpHMW')]")) > 0,
                # 로그아웃 버튼이 있으면 로그인된 상태
                len(self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그아웃')]")) > 0
            ]
            
            # 하나라도 True이면 로그인된 상태
            if any(login_indicators):
                print("✅ 로그인 상태 확인됨")
                return True
            else:
                print("❌ 로그인되지 않음")
                return False
        except Exception as e:
            print(f"❌ 로그인 상태 확인 실패: {e}")
            return False

    def manual_login(self) -> bool:
        """수동 로그인 프로세스 - 사용자가 브라우저에서 직접 로그인"""
        if not self.driver:
            self.start_browser()
        
        # 네이버 로그인 페이지로 이동
        print("🌐 네이버 로그인 페이지로 이동 중...")
        self.driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(3)
        
        print("🔐 브라우저에서 네이버에 로그인해주세요.")
        print("   로그인 완료 후 자동으로 감지됩니다...")
        
        # 자동 로그인 감지 (최대 5분 대기)
        max_wait_time = 120  # 2분
        check_interval = 3   # 3초마다 확인
        waited_time = 0
        
        while waited_time < max_wait_time:
            try:
                time.sleep(check_interval)
                waited_time += check_interval
                
                # 브라우저 창이 닫혔는지 확인
                try:
                    current_url = self.driver.current_url
                except Exception as e:
                    print(f"❌ 브라우저 창이 닫혔습니다: {e}")
                    print("🔐 브라우저에서 네이버에 로그인해주세요.")
                    print("   로그인 완료 후 자동으로 감지됩니다...")
                    # 브라우저 재시작
                    self.start_browser()
                    self.driver.get("https://nid.naver.com/nidlogin.login")
                    time.sleep(3)
                    continue
                
                # 로그인 성공 확인 (네이버 메인 페이지로 리다이렉트됨)
                if "naver.com" in current_url and "nidlogin" not in current_url:
                    self._save_cookies()
                    print("✅ 로그인 성공! 쿠키가 저장되었습니다.")
                    return True
                
                # 진행 상황 표시
                remaining_time = max_wait_time - waited_time
                print(f"⏳ 로그인 대기 중... ({remaining_time}초 남음)")
                
            except Exception as e:
                print(f"⚠️ 로그인 확인 중 오류: {e}")
                continue
        
        print("❌ 로그인 시간 초과. 다시 시도해주세요.")
        return False

    def ensure_logged_in(self) -> bool:
        """Ensure user is logged in to Naver. Returns True if successful."""
        if not self.driver:
            self.start_browser()
        
        # 브라우저 세션 유효성 확인
        try:
            current_url = self.driver.current_url
            if not current_url or current_url == "data:,":
                print("⚠️ 브라우저 세션이 끊어짐 - 재시작 중...")
                self.start_browser()
        except Exception as e:
            print(f"⚠️ 브라우저 세션 확인 실패: {e} - 재시작 중...")
            self.start_browser()
        
        # 쿠키 로드
        self._load_cookies()
        
        # 네이버 메인 페이지로 이동
        self.driver.get("https://www.naver.com")
        time.sleep(3)  # 로딩 대기 시간 증가
        
        # 로그인 상태 확인
        try:
            # 로그인 버튼이 없으면 로그인된 상태
            login_button = self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그인')]")
            if not login_button:
                print("✅ Already logged in to Naver")
                self._save_cookies()
                return True
            
            # 로그인 버튼이 있으면 로그인 필요
            print("🔐 Manual login required. Please log in to Naver in the browser window.")
            print("   The system will automatically detect when you're logged in...")
            
            # 자동 로그인 감지 (최대 5분 대기)
            max_wait_time = 120  # 2분
            check_interval = 3   # 3초마다 확인
            waited_time = 0
            
            while waited_time < max_wait_time:
                time.sleep(check_interval)
                waited_time += check_interval
                
                # 브라우저 세션 유효성 재확인
                try:
                    current_url = self.driver.current_url
                    if not current_url or current_url == "data:,":
                        print("⚠️ 브라우저 세션이 끊어짐 - 재시작 중...")
                        self.start_browser()
                        self._load_cookies()
                        self.driver.get("https://www.naver.com")
                        time.sleep(3)
                except Exception as e:
                    print(f"⚠️ 브라우저 세션 확인 실패: {e} - 재시작 중...")
                    self.start_browser()
                    self._load_cookies()
                    self.driver.get("https://www.naver.com")
                    time.sleep(3)
                
                # 페이지 새로고침 후 로그인 상태 확인
                self.driver.refresh()
                time.sleep(2)
                
                # 로그인 상태 재확인
                login_button_after = self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그인')]")
                if not login_button_after:
                    self._save_cookies()
                    print("✅ Login successful! Cookies saved.")
                    return True
                
                # 진행 상황 표시
                remaining_time = max_wait_time - waited_time
                print(f"⏳ Waiting for login... ({remaining_time}s remaining)")
            
            print("❌ Login timeout. Please try again.")
            return False
                
        except Exception as e:
            print(f"❌ Login check failed: {e}")
            return False

    def scrape_article(self, url: str, include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None, max_retries: int = 3):
        """Scrape a single article with comments and images."""
        # 로그인 상태 확인을 간소화 (이미 게시판 조회에서 확인됨)
        if not self.driver:
            raise Exception("Browser not started")
        
        for attempt in range(max_retries):
            try:
                print(f"📄 스크래핑 시도 {attempt + 1}/{max_retries}: {url}")
                
                # Navigate to article with retry logic
                self._navigate_with_retry(url, max_retries=2)
                
                # JavaScript 로딩 대기 (더 긴 시간)
                print("⏳ JavaScript 로딩 대기 중... (30초)")
                time.sleep(30)
                
                # Take snapshot for debugging
                # URL에서 안전한 디렉터리명 생성
                import re
                safe_name = re.sub(r'[^\w\-_.]', '_', url.split('/')[-1].split('?')[0])
                snapshot_dir = self.snapshots_dir / safe_name
                snapshot_dir.mkdir(exist_ok=True)
                self.driver.save_screenshot(str(snapshot_dir / f"page_attempt_{attempt + 1}.png"))
                
                # Extract article information
                article_data = self._extract_article_data(url)
                
                # Extract images and convert to base64
                images_base64 = self._extract_images()
                
                # Extract comments with filtering
                comments = self._extract_comments(include_nicks, exclude_nicks)
                
                # Combine all data
                result = {
                    **article_data,
                    "images_base64": images_base64,
                    "comments": comments,
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                print(f"✅ 스크래핑 성공: {article_data.get('title', 'N/A')}")
                return result
                
            except Exception as e:
                print(f"⚠️ 스크래핑 시도 {attempt + 1} 실패: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5초, 10초, 15초 대기
                    print(f"⏳ {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 최대 재시도 횟수 초과: {url}")
                    raise e

    def _extract_article_data(self, url: str) -> dict:
        """Extract basic article information."""
        try:
            # Extract cafe ID from URL
            cafe_id = url.split("cafe.naver.com/")[1].split("/")[0] if "cafe.naver.com" in url else "unknown"
            
            # Extract article ID from URL
            article_id = url.split("/")[-1] if "/" in url else "unknown"
            
            # 네이버 카페 최신 구조에 맞는 새로운 셀렉터 (2025년 업데이트)
            title_selectors = [
                # 1. 실제 발견된 셀렉터들 (우선순위)
                "h3.title",
                "h2.title", 
                "h1.title",
                ".title",
                # 2. 네이버 카페 최신 구조 (2024년 기준)
                ".se-title-text",
                ".se-fs-",
                ".se-component-content h1",
                ".se-component-content h2", 
                ".se-component-content h3",
                ".se-text-paragraph",
                # 3. 게시글 본문 영역 내 제목
                ".article_content h1",
                ".article_content h2",
                ".article_content h3",
                ".post_content h1",
                ".post_content h2",
                ".post_content h3",
                # 4. 일반적인 제목 셀렉터
                ".article_title",
                ".post_title",
                ".content_title",
                ".view_title",
                # 5. 네이버 카페 특화 셀렉터
                ".cafe-article-title",
                ".article-view-title",
                ".post-view-title",
                # 6. 최신 네이버 카페 구조
                ".Layout_content__pUOz1 h1",
                ".Layout_content__pUOz1 h2",
                ".Layout_content__pUOz1 h3",
                # 7. 완전히 새로운 접근 - 모든 h 태그에서 카페 제목 제외
                "h1:not([class*='Layout_cafe_name']):not([class*='Header'])",
                "h2:not([class*='Layout_cafe_name']):not([class*='Header'])",
                "h3:not([class*='Layout_cafe_name']):not([class*='Header'])",
                # 8. 게시글 제목이 있을 수 있는 특정 영역들
                "[class*='article'] h1",
                "[class*='article'] h2", 
                "[class*='article'] h3",
                "[class*='post'] h1",
                "[class*='post'] h2",
                "[class*='post'] h3",
                "[class*='content'] h1",
                "[class*='content'] h2",
                "[class*='content'] h3"
            ]
            
            title = self._safe_extract(title_selectors, default="제목을 찾을 수 없음")
            
            # 디버깅: 제목 추출 실패 시 페이지 구조 분석
            if title == "제목을 찾을 수 없음" or "비타민D자외선요법" in title:
                print("🔍 디버깅: 제목 추출 문제 분석 중...")
                try:
                    # 페이지 소스에서 가능한 제목 요소들 찾기
                    page_source = self.driver.page_source
                    
                    # h1, h2, h3 태그들 찾기
                    import re
                    h_tags = re.findall(r'<h[1-3][^>]*>([^<]+)</h[1-3]>', page_source)
                    if h_tags:
                        print(f"🔍 발견된 h 태그들: {h_tags[:5]}")  # 처음 5개만 출력
                    
                    # title 관련 클래스들 찾기
                    title_classes = re.findall(r'class="([^"]*title[^"]*)"', page_source)
                    if title_classes:
                        print(f"🔍 발견된 title 클래스들: {title_classes[:5]}")
                    
                    # se- 관련 클래스들 찾기
                    se_classes = re.findall(r'class="([^"]*se-[^"]*)"', page_source)
                    if se_classes:
                        print(f"🔍 발견된 se- 클래스들: {se_classes[:5]}")
                    
                    # 게시글 제목이 있을 수 있는 영역들 확인
                    print("🔍 게시글 제목 영역 확인 중...")
                    try:
                        # 게시글 본문 영역 내 제목 찾기
                        from selenium.webdriver.common.by import By
                        content_area = self.driver.find_elements(By.CSS_SELECTOR, ".article_content, .post_content, .se-main-container")
                        if content_area:
                            print(f"✅ 게시글 본문 영역 발견: {len(content_area)}개")
                            for i, area in enumerate(content_area[:2]):  # 처음 2개만 확인
                                try:
                                    titles_in_area = area.find_elements(By.CSS_SELECTOR, "h1, h2, h3, .title")
                                    if titles_in_area:
                                        print(f"   영역 {i+1} 내 제목 요소: {len(titles_in_area)}개")
                                        for j, title_elem in enumerate(titles_in_area[:3]):  # 처음 3개만 확인
                                            try:
                                                title_text = title_elem.text.strip()
                                                if title_text and "비타민D자외선요법" not in title_text:
                                                    print(f"     제목 {j+1}: {title_text[:50]}...")
                                            except:
                                                pass
                                except:
                                    pass
                        else:
                            print("❌ 게시글 본문 영역을 찾을 수 없음")
                        
                        # 완전히 새로운 접근 방식 - 모든 h 태그 확인
                        print("🔍 모든 h 태그 확인 중...")
                        all_h_tags = self.driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")
                        if all_h_tags:
                            print(f"✅ 전체 h 태그 발견: {len(all_h_tags)}개")
                            for i, h_tag in enumerate(all_h_tags[:10]):  # 처음 10개만 확인
                                try:
                                    h_text = h_tag.text.strip()
                                    h_class = h_tag.get_attribute("class") or ""
                                    if h_text and "비타민D자외선요법" not in h_text:
                                        print(f"   h 태그 {i+1}: {h_text[:50]}... (클래스: {h_class[:30]})")
                                except:
                                    pass
                        
                        # 게시글 제목이 있을 수 있는 특정 영역들 확인
                        print("🔍 게시글 제목 특화 영역 확인 중...")
                        title_areas = [
                            ".article_title",
                            ".post_title", 
                            ".content_title",
                            ".view_title",
                            ".se-title-text",
                            ".se-fs-",
                            ".cafe-article-title",
                            ".article-view-title",
                            ".post-view-title",
                            ".content-view-title"
                        ]
                        
                        for area_selector in title_areas:
                            try:
                                area_elements = self.driver.find_elements(By.CSS_SELECTOR, area_selector)
                                if area_elements:
                                    print(f"✅ {area_selector} 영역 발견: {len(area_elements)}개")
                                    for i, elem in enumerate(area_elements[:3]):
                                        try:
                                            elem_text = elem.text.strip()
                                            if elem_text and "비타민D자외선요법" not in elem_text:
                                                print(f"   {area_selector} {i+1}: {elem_text[:50]}...")
                                        except:
                                            pass
                            except:
                                pass
                        
                    except Exception as e:
                        print(f"❌ 게시글 제목 영역 확인 오류: {e}")
                        
                except Exception as e:
                    print(f"⚠️ 제목 디버깅 중 오류: {e}")
            
            # Try multiple selectors for author (updated for current Naver Cafe structure)
            author_selectors = [
                # 최신 네이버 카페 구조
                ".nick",
                ".nickname", 
                ".author",
                ".writer",
                ".user_nick",
                ".user_name",
                ".member_nick",
                ".member_name",
                # 네이버 카페 특화 셀렉터
                ".cafe-nick",
                ".cafe-author",
                ".article-author",
                ".post-author",
                # 일반적인 셀렉터
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
                ".article_info .nickname",
                # 추가 시도
                "span[class*='nick']",
                "div[class*='author']",
                "div[class*='writer']"
            ]
            
            author = self._safe_extract(author_selectors, default="작성자를 찾을 수 없음")
            
            # 네이버 카페 최신 구조에 맞는 내용 셀렉터 (2025년 업데이트)
            content_selectors = [
                # 1. 실제 발견된 셀렉터들 (우선순위)
                ".content",
                # 2. 네이버 에디터 최신 구조
                ".se-main-container",
                ".se-component-content",
                ".se-text-paragraph",
                ".se-text",
                ".se-component",
                # 3. 게시글 본문 영역
                ".article_content",
                ".post_content",
                ".article_text",
                ".board_text",
                ".article_body",
                # 4. 네이버 카페 특화 셀렉터
                ".cafe-content",
                ".cafe-article-content",
                ".article-view-content",
                ".view-content",
                ".content-view",
                # 5. 최신 네이버 카페 구조
                ".Layout_content__pUOz1",
                ".Layout_content__pUOz1 .se-main-container",
                ".Layout_content__pUOz1 .se-component-content",
                # 6. 일반적인 셀렉터
                "[data-testid='article-content']",
                "[class*='content']",
                "[class*='Content']",
                "[class*='text']",
                "[class*='Text']",
                # 7. se- 관련 모든 클래스
                "div[class*='se-']",
                "p[class*='se-']",
                "span[class*='se-']",
                # 8. 게시글 본문이 있을 수 있는 영역들
                "div[class*='article']",
                "div[class*='post']",
                "div[class*='content']"
            ]
            
            content_text = self._safe_extract(content_selectors, default="내용을 찾을 수 없음")
            content_html = self._safe_extract_html(content_selectors, default="<p>내용을 찾을 수 없음</p>")
            
            # 디버깅: 페이지 구조 확인
            if content_text == "내용을 찾을 수 없음":
                print("🔍 디버깅: 페이지 구조 분석 중...")
                try:
                    # 페이지 소스에서 가능한 셀렉터 찾기
                    page_source = self.driver.page_source
                    if "se-main-container" in page_source:
                        print("✅ se-main-container 발견됨")
                    if "article" in page_source.lower():
                        print("✅ article 관련 클래스 발견됨")
                    if "content" in page_source.lower():
                        print("✅ content 관련 클래스 발견됨")
                    
                    # 실제 존재하는 클래스들 찾기
                    import re
                    class_pattern = r'class="([^"]*)"'
                    classes = re.findall(class_pattern, page_source)
                    content_classes = [cls for cls in classes if any(keyword in cls.lower() for keyword in ['content', 'article', 'text', 'se-'])]
                    if content_classes:
                        print(f"🔍 발견된 클래스들: {content_classes[:10]}")  # 처음 10개만 출력
                except Exception as e:
                    print(f"⚠️ 디버깅 중 오류: {e}")
            
            # Try to extract date
            date_selectors = [
                ".date",
                ".time", 
                ".created_at",
                "[data-testid='created-date']",
                ".article_date",
                ".post_date",
                ".board_date",
                "[class*='date']",
                "[class*='Date']",
                "[class*='time']",
                "[class*='Time']",
                ".article_info .date",
                ".article_info .time",
                ".user_info .date",
                ".user_info .time"
            ]
            
            posted_at = self._safe_extract(date_selectors, default=None)
            if posted_at == "알 수 없음":
                posted_at = None
            
            return {
                "cafe_id": cafe_id,
                "article_id": article_id,
                "article_url": url,
                "title": title,
                "author_nickname": author,
                "posted_at": posted_at,
                "content_text": content_text,
                "content_html": content_html
            }
            
        except Exception as e:
            print(f"⚠️ Error extracting article data: {e}")
            return {
                "cafe_id": "unknown",
                "article_id": "unknown",
                "article_url": url,
                "title": "오류 발생",
                "author_nickname": "알 수 없음",
                "posted_at": None,
                "content_text": f"오류: {str(e)}",
                "content_html": f"<p>오류: {str(e)}</p>"
            }

    def _extract_images(self, max_images: int = 10, max_size_mb: float = 5.0) -> list:
        """Extract images and convert to base64 with memory optimization."""
        images = []
        try:
            # Find all images in the article
            image_elements = self.driver.find_elements(By.TAG_NAME, "img")
            
            # Limit number of images to prevent memory issues
            if len(image_elements) > max_images:
                print(f"⚠️ Too many images ({len(image_elements)}), limiting to {max_images}")
                image_elements = image_elements[:max_images]
            
            for i, img in enumerate(image_elements):
                try:
                    # Get image source
                    src = img.get_attribute("src")
                    if not src or src.startswith("data:"):
                        continue
                    
                    # Download image and convert to base64
                    response = requests.get(src, timeout=10)
                    if response.status_code == 200:
                        image_data = response.content
                        
                        # Check image size to prevent memory issues
                        size_mb = len(image_data) / (1024 * 1024)
                        if size_mb > max_size_mb:
                            print(f"⚠️ Image {i+1} too large ({size_mb:.1f}MB), skipping")
                            continue
                        
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        
                        # Determine MIME type
                        mime_type = "image/jpeg"
                        if src.lower().endswith('.png'):
                            mime_type = "image/png"
                        elif src.lower().endswith('.gif'):
                            mime_type = "image/gif"
                        
                        images.append({
                            "mime": mime_type,
                            "data": base64_data,
                            "filename": f"image_{i+1}.jpg",
                            "size_mb": round(size_mb, 2)
                        })
                        
                except Exception as e:
                    print(f"⚠️ Error processing image {i}: {e}")
                    continue
                    
        except Exception as e:
            print(f"⚠️ Error extracting images: {e}")
        
        return images

    def _extract_comments(self, include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None) -> list:
        """Extract comments with nickname filtering."""
        comments = []
        try:
            # Try multiple selectors for comments (updated for current Naver Cafe structure)
            comment_selectors = [
                # 1. 실제 발견된 셀렉터들 (우선순위)
                ".comment_area",
                ".LinkComment",
                # 2. 최신 네이버 카페 구조
                ".comment",
                ".reply", 
                ".comment_item",
                ".reply_item",
                ".cafe-comment",
                ".cafe-reply",
                ".article-comment",
                ".article-reply",
                # 3. 네이버 카페 특화 셀렉터
                ".comment-list .comment",
                ".comment-list .reply",
                ".reply-list .comment",
                ".reply-list .reply",
                ".comment-area .comment",
                ".comment-area .reply",
                ".reply-area .comment",
                ".reply-area .reply",
                # 4. 일반적인 셀렉터
                "[data-testid='comment']",
                "[class*='comment']",
                "[class*='Comment']",
                "[class*='reply']",
                "[class*='Reply']",
                # 5. 추가 시도
                "div[class*='comment']",
                "div[class*='reply']",
                "li[class*='comment']",
                "li[class*='reply']"
            ]
            
            comment_elements = []
            for selector in comment_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        comment_elements = elements
                        break
                except:
                    continue
            
            for comment_element in comment_elements:
                try:
                    # Extract comment text
                    text_element = comment_element.find_elements(By.CSS_SELECTOR, ".comment_text, .reply_text, .content")
                    text = text_element[0].text if text_element else "댓글 내용 없음"
                    
                    # Extract author
                    author_element = comment_element.find_elements(By.CSS_SELECTOR, ".nick, .nickname, .author")
                    author = author_element[0].text if author_element else "알 수 없음"
                    
                    # Extract date
                    date_element = comment_element.find_elements(By.CSS_SELECTOR, ".date, .time")
                    date = date_element[0].text if date_element else None
                    
                    # Apply nickname filtering
                    should_include = True
                    
                    if include_nicks and include_nicks:
                        should_include = any(nick in author for nick in include_nicks)
                    
                    if exclude_nicks and exclude_nicks:
                        should_include = should_include and not any(nick in author for nick in exclude_nicks)
                    
                    if should_include:
                        comments.append({
                            "comment_id": f"comment_{len(comments)+1}",
                            "nickname": author.strip() if author else "알 수 없음",
                            "text": text.strip() if text else "댓글 내용 없음",
                            "created_at": date.strip() if date else None
                        })
                        
                except Exception as e:
                    print(f"⚠️ Error processing comment: {e}")
                    continue
                    
        except Exception as e:
            print(f"⚠️ Error extracting comments: {e}")
        
        return comments

    def scrape_board_articles(self, board_url: str, max_pages: int = 5) -> list[dict]:
        """Scrape articles from a board page with pagination."""
        # 간단한 로그인 상태 확인
        if not self._cookie_file.exists():
            raise Exception("Login required but failed")
        
        articles = []
        page = 1
        total_articles = 0
        
        print(f"📊 게시판 스크래핑 시작: {board_url}")
        print(f"📄 최대 페이지: {max_pages}")
        print("=" * 50)
        
        while page <= max_pages:
            try:
                progress = f"[페이지 {page:2d}/{max_pages:2d}]"
                print(f"📄 {progress} 게시판 페이지 로딩 중...")
                
                # Navigate to board page
                page_url = f"{board_url}?page={page}" if "?" not in board_url else f"{board_url}&page={page}"
                self.driver.get(page_url)
                time.sleep(2)
                
                # Take snapshot for debugging
                snapshot_dir = self.snapshots_dir / f"board_page_{page}"
                snapshot_dir.mkdir(exist_ok=True)
                self.driver.save_screenshot(str(snapshot_dir / "page.png"))
                
                # Extract article links from current page
                page_articles = self._extract_article_links_from_board()
                
                if not page_articles:
                    print(f"📄 {progress} 게시글을 찾을 수 없음, 페이지네이션 중단")
                    break
                
                articles.extend(page_articles)
                total_articles += len(page_articles)
                print(f"✅ {progress} 완료 - 발견된 게시글: {len(page_articles)}개 (누적: {total_articles}개)")
                
                page += 1
                
                # Add delay to avoid being blocked
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ {progress} 오류: {e}")
                break
        
        print("=" * 50)
        print(f"📊 게시판 스크래핑 완료: 총 {total_articles}개 게시글 발견")
        return articles

    def _extract_article_links_from_board(self) -> list[dict]:
        """Extract article links and basic info from board page."""
        articles = []
        
        try:
            # Try multiple selectors for article links
            article_selectors = [
                "a[href*='/ArticleRead.nhn']",
                "a[href*='/ArticleRead']", 
                ".article",
                ".board_list a",
                ".list_item a",
                "tr td a"
            ]
            
            article_links = []
            for selector in article_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        article_links = links
                        print(f"✅ Found {len(links)} article links using selector: {selector}")
                        break
                except:
                    continue
            
            if not article_links:
                print("⚠️ No article links found on this page")
                return articles
            
            print(f"🔍 Processing {len(article_links)} links...")
            valid_links = 0
            
            for i, link in enumerate(article_links):
                try:
                    # Get article URL
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    
                    # Debug: Print first few links
                    if i < 5:
                        print(f"🔗 Link {i+1}: {href}")
                    
                    # Check for various article URL patterns
                    if not any(pattern in href for pattern in ["ArticleRead", "ArticleRead.nhn", "articleid", "clubid", "articles"]):
                        continue
                    
                    valid_links += 1
                    
                    # Make URL absolute
                    if href.startswith("/"):
                        href = f"https://cafe.naver.com{href}"
                    elif not href.startswith("http"):
                        href = f"https://cafe.naver.com/{href}"
                    
                    # Extract basic info from link text
                    title = link.text.strip() if link.text else "제목 없음"
                    
                    # Try to find author and date from parent elements
                    parent_row = link.find_element(By.XPATH, "ancestor::tr")
                    author = "알 수 없음"
                    date = None
                    
                    if parent_row:
                        # Try to find author in the same row
                        author_selectors = [".nick", ".nickname", ".author", "td:nth-child(2)", "td:nth-child(3)"]
                        for author_sel in author_selectors:
                            try:
                                author_elem = parent_row.find_elements(By.CSS_SELECTOR, author_sel)
                                if author_elem:
                                    author_text = author_elem[0].text
                                    if author_text and author_text.strip():
                                        author = author_text.strip()
                                        break
                            except:
                                continue
                        
                        # Try to find date in the same row
                        date_selectors = [".date", ".time", "td:last-child", "td:nth-last-child(2)"]
                        for date_sel in date_selectors:
                            try:
                                date_elem = parent_row.find_elements(By.CSS_SELECTOR, date_sel)
                                if date_elem:
                                    date_text = date_elem[0].text
                                    if date_text and date_text.strip():
                                        date = date_text.strip()
                                        break
                            except:
                                continue
                    
                    # Extract article ID from URL
                    article_id = href.split("/")[-1] if "/" in href else "unknown"
                    
                    articles.append({
                        "article_id": article_id,
                        "article_url": href,
                        "title": title,
                        "author_nickname": author,
                        "posted_at": date,
                        "scraped_at": None  # Will be filled when scraping full article
                    })
                    
                except Exception as e:
                    print(f"⚠️ Error processing article link: {e}")
                    continue
            
            print(f"✅ Found {valid_links} valid article links out of {len(article_links)} total links")
                    
        except Exception as e:
            print(f"⚠️ Error extracting article links: {e}")
        
        return articles

    def scrape_multiple_articles(self, article_urls: list[str], include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None, max_concurrent: int = 3) -> list[dict]:
        """Scrape multiple articles with progress tracking."""
        # 로그인 상태 확인을 간소화 (이미 게시판 조회에서 확인됨)
        if not self.driver:
            raise Exception("Browser not started")
        
        start_time = time.time()
        results = []
        total = len(article_urls)
        successful = 0
        failed = 0
        
        # 로깅 시작
        scraping_logger.log_scraping_start("다중 게시글", total)
        scraping_logger.log_performance("동시 처리 설정", 0, f"최대 {max_concurrent}개")
        
        print(f"🚀 다중 게시글 스크래핑 시작: {total}개 게시글")
        print("=" * 60)
        
        # Process articles sequentially (Selenium doesn't support true concurrency)
        for i, url in enumerate(article_urls, 1):
            try:
                progress = f"[{i:3d}/{total:3d}]"
                percentage = (i / total) * 100
                print(f"📄 {progress} ({percentage:5.1f}%) 스크래핑 중: {url}")
                
                # Scrape individual article
                article_data = self.scrape_article(url, include_nicks, exclude_nicks)
                results.append(article_data)
                successful += 1
                print(f"✅ {progress} 완료")
                
                # Add delay between requests
                if i < total:
                    delay = self._calculate_delay(i, total)
                    scraping_logger.log_antibot_measure("요청 간 대기", f"{delay}초")
                    time.sleep(delay)
                
            except Exception as e:
                print(f"❌ {progress} 실패: {e}")
                failed += 1
                results.append({
                    "article_url": url,
                    "title": "스크래핑 실패",
                    "error": str(e),
                    "scraped_at": None
                })
        
        print("=" * 60)
        print(f"📊 스크래핑 완료: 총 {total}개 중 성공 {successful}개, 실패 {failed}개")
        return results

    def _navigate_with_retry(self, url: str, max_retries: int = 3) -> None:
        """Navigate to URL with retry logic."""
        for attempt in range(max_retries):
            try:
                self.driver.get(url)
                time.sleep(3)  # Wait for page to load
                return
            except Exception as e:
                print(f"⚠️ 네비게이션 시도 {attempt + 1} 실패: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    raise e

    def _safe_extract(self, selectors: list[str], timeout: int = 2, default: str = "알 수 없음") -> str:
        """Safely extract text using multiple selectors."""
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if element and element.text.strip():
                    return element.text.strip()
            except:
                continue
        return default

    def _safe_extract_html(self, selectors: list[str], timeout: int = 2, default: str = "<p>알 수 없음</p>") -> str:
        """Safely extract HTML using multiple selectors."""
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if element and element.get_attribute("innerHTML").strip():
                    return element.get_attribute("innerHTML").strip()
            except:
                continue
        return default

    def _calculate_delay(self, current: int, total: int) -> float:
        """동적 지연 시간 계산 - 안티봇 대응"""
        import random
        
        # 기본 지연 시간 (2-5초)
        base_delay = random.uniform(2.0, 5.0)
        
        # 진행률에 따른 추가 지연 (후반부일수록 더 오래 대기)
        progress_factor = current / total
        additional_delay = progress_factor * 3.0  # 최대 3초 추가
        
        # 랜덤 요소 추가
        random_factor = random.uniform(0.5, 1.5)
        
        total_delay = (base_delay + additional_delay) * random_factor
        
        # 최대 10초로 제한
        return min(total_delay, 10.0)
    
    def _get_memory_usage(self) -> float:
        """현재 메모리 사용량 반환 (MB)"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # MB 단위
        except:
            return 0.0

    def get_cafe_boards(self, cafe_url: str) -> list[dict]:
        """카페의 게시판 목록 조회"""
        try:
            # 브라우저가 시작되지 않았으면 시작
            if not self.driver:
                print("🔄 브라우저 초기화 중...")
                self.start_browser()
            
            # 쿠키 로드
            self._load_cookies()
            
            # 쿠키가 있으면 로그인된 것으로 간주하고 카페 접속 시도
            if self._cookie_file.exists():
                print("✅ 저장된 쿠키를 사용하여 카페 접속을 시도합니다.")
            else:
                print("⚠️ 저장된 쿠키가 없습니다.")
                print("💡 해결 방법: 웹 UI에서 '로그인 시작' 버튼을 클릭하세요.")
                # 쿠키가 없어도 일단 시도해보기 (batch_scraping에서 이미 처리됨)
                print("🔄 쿠키 없이 카페 접속을 시도합니다.")
            
            # 카페 메인 페이지로 이동
            print(f"🌐 카페 페이지 이동: {cafe_url}")
            self.driver.get(cafe_url)
            time.sleep(3)
            
            # 게시판 목록 추출
            boards = self._extract_cafe_boards()
            
            scraping_logger.log_scraping_success(cafe_url, f"게시판 {len(boards)}개 조회")
            return boards
            
        except Exception as e:
            scraping_logger.log_scraping_error(cafe_url, str(e))
            raise e
    
    def _extract_cafe_boards(self) -> list[dict]:
        """카페 게시판 목록 추출"""
        boards = []
        
        try:
            # 게시판 링크 선택자들 (더 포괄적으로)
            board_selectors = [
                "a[href*='BoardList.nhn']",
                "a[href*='menuid=']",
                ".menu_list a",
                ".board_list a",
                "[class*='menu'] a",
                "[class*='board'] a",
                "a[href*='cafe.naver.com']",
                ".cafe_menu a",
                ".menu_item a"
            ]
            
            board_links = []
            for selector in board_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        board_links = links
                        print(f"✅ 게시판 링크 {len(links)}개 발견: {selector}")
                        break
                except:
                    continue
            
            if not board_links:
                print("⚠️ 게시판 링크를 찾을 수 없습니다")
                return boards
            
            print(f"🔍 발견된 링크들을 분석 중...")
            
            for i, link in enumerate(board_links):
                try:
                    href = link.get_attribute("href")
                    text = link.text.strip() if link.text else ""
                    
                    print(f"링크 {i+1}: {text} -> {href}")
                    
                    # 게시판 링크인지 확인 (더 유연한 조건)
                    if not href or not any(keyword in href.lower() for keyword in ['boardlist', 'menuid', 'cafe.naver.com']):
                        continue
                    
                    # 메뉴 ID 추출 (더 유연한 패턴)
                    import re
                    menuid_match = re.search(r'menuid=(\d+)', href)
                    if menuid_match:
                        menu_id = menuid_match.group(1)
                    else:
                        # menuid가 없으면 href에서 숫자 추출
                        numbers = re.findall(r'\d+', href)
                        menu_id = numbers[-1] if numbers else f"unknown_{i}"
                    
                    menu_name = text if text else f"게시판 {menu_id}"
                    
                    # URL 정규화
                    if href.startswith("/"):
                        href = f"https://cafe.naver.com{href}"
                    elif not href.startswith("http"):
                        href = f"https://cafe.naver.com/{href}"
                    
                    boards.append({
                        "menu_id": menu_id,
                        "menu_name": menu_name,
                        "board_url": href
                    })
                    
                    print(f"✅ 게시판 추가: {menu_name} (ID: {menu_id})")
                    
                except Exception as e:
                    print(f"⚠️ 게시판 링크 처리 오류: {e}")
                    continue
                    
        except Exception as e:
            print(f"⚠️ 게시판 목록 추출 오류: {e}")
        
        print(f"📊 총 {len(boards)}개 게시판 추출 완료")
        return boards
    
    def scrape_cafe(self, cafe_url: str, max_pages: int, all_boards: bool, selected_boards: list[str], include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None) -> list[dict]:
        """카페 전체 또는 특정 게시판 스크래핑"""
        # 로그인 상태 확인을 간소화 (이미 게시판 조회에서 확인됨)
        if not self.driver:
            raise Exception("Browser not started")
        
        start_time = time.time()
        all_results = []
        
        # 게시판 목록 조회
        boards = self.get_cafe_boards(cafe_url)
        
        if not boards:
            raise Exception("게시판을 찾을 수 없습니다")
        
        # 스크래핑할 게시판 필터링
        if all_boards:
            target_boards = boards
            scraping_logger.log_scraping_start("전체 게시판", len(target_boards))
        else:
            target_boards = [board for board in boards if board["menu_id"] in selected_boards]
            scraping_logger.log_scraping_start("선택된 게시판", len(target_boards))
        
        print(f"📊 스크래핑 대상 게시판: {len(target_boards)}개")
        
        # 각 게시판 스크래핑
        for i, board in enumerate(target_boards, 1):
            try:
                print(f"📄 게시판 {i}/{len(target_boards)}: {board['menu_name']}")
                scraping_logger.log_scraping_progress(i, len(target_boards), board['menu_name'])
                
                # 게시판 스크래핑
                board_results = self.scrape_board_articles(board["board_url"], max_pages)
                
                # 각 게시글 상세 스크래핑
                article_urls = [article["article_url"] for article in board_results]
                if article_urls:
                    detailed_results = self.scrape_multiple_articles(article_urls, include_nicks, exclude_nicks)
                    all_results.extend(detailed_results)
                
                print(f"✅ 게시판 {i}/{len(target_boards)} 완료: {len(article_urls)}개 게시글")
                
                # 게시판 간 지연
                if i < len(target_boards):
                    delay = self._calculate_delay(i, len(target_boards))
                    time.sleep(delay)
                
            except Exception as e:
                print(f"❌ 게시판 {i}/{len(target_boards)} 실패: {e}")
                scraping_logger.log_scraping_error(board["menu_name"], str(e))
                continue
        
        # 완료 로깅
        successful = len([r for r in all_results if "error" not in r])
        failed = len(all_results) - successful
        scraping_logger.log_scraping_complete(successful, failed, len(all_results))
        
        return all_results
    
    def batch_scraping(self, cafe_url: str, max_pages: int, all_boards: bool, selected_boards: list[str], search_keywords: list[str], post_authors: list[str], comment_authors: list[str], max_articles: int, image_processing: str, period: str, delay_between_requests: int) -> list[dict]:
        """배치 크롤링 - 키워드 검색 및 작성자 필터링 포함"""
        try:
            # 브라우저 세션 확인 및 재시작
            if not self.driver:
                print("🔄 브라우저 초기화 중...")
                self.start_browser()
            else:
                # 기존 브라우저 세션이 유효한지 확인
                try:
                    current_url = self.driver.current_url
                    if not current_url or current_url == "data:,":
                        print("⚠️ 브라우저 세션이 끊어짐 - 재시작 중...")
                        self.start_browser()
                except Exception as e:
                    print(f"⚠️ 브라우저 세션이 끊어짐: {e}")
                    print("🔄 브라우저 재시작 중...")
                    self.start_browser()

            # 쿠키 로드
            self._load_cookies()

            # 쿠키가 있으면 로그인된 것으로 간주하고 카페 접속 시도
            if self._cookie_file.exists():
                print("✅ 저장된 쿠키를 사용하여 카페 접속을 시도합니다.")
            else:
                print("⚠️ 저장된 쿠키가 없습니다.")
                print("💡 해결 방법: 웹 UI에서 '로그인 시작' 버튼을 클릭하세요.")
                raise Exception("Login required but failed")
        except Exception as e:
            print(f"❌ 배치 크롤링 초기화 실패: {e}")
            raise
        
        start_time = time.time()
        all_results = []
        collected_count = 0
        
        # 게시판 목록 조회
        boards = self.get_cafe_boards(cafe_url)
        
        if not boards:
            raise Exception("게시판을 찾을 수 없습니다")
        
        # 스크래핑할 게시판 필터링
        if all_boards:
            target_boards = boards
            scraping_logger.log_scraping_start("전체 게시판 배치 크롤링", len(target_boards))
        else:
            target_boards = [board for board in boards if board["menu_id"] in selected_boards]
            scraping_logger.log_scraping_start("선택된 게시판 배치 크롤링", len(target_boards))
        
        print(f"🔄 배치 크롤링 대상 게시판: {len(target_boards)}개")
        print(f"🔍 검색 키워드: {search_keywords}")
        print(f"👤 게시글 작성자 필터: {post_authors}")
        print(f"💬 댓글 작성자 필터: {comment_authors}")
        
        # 각 게시판 스크래핑
        for i, board in enumerate(target_boards, 1):
            if collected_count >= max_articles:
                print(f"📊 최대 수집 게시글 수({max_articles})에 도달하여 크롤링을 중단합니다.")
                break
                
            try:
                # 브라우저 세션 확인 및 재시작
                try:
                    current_url = self.driver.current_url
                    # URL이 유효한지 확인
                    if not current_url or current_url == "data:,":
                        raise Exception("Invalid browser session")
                except Exception as e:
                    print(f"⚠️ 브라우저 세션이 끊어짐: {e}")
                    print("🔄 브라우저 재시작 중...")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.start_browser()
                    self._load_cookies()
                    
                    # 카페 페이지로 다시 이동
                    try:
                        self.driver.get(cafe_url)
                        time.sleep(3)
                    except Exception as nav_e:
                        print(f"⚠️ 카페 페이지 재접속 실패: {nav_e}")
                        continue
                
                print(f"📄 게시판 {i}/{len(target_boards)}: {board['menu_name']}")
                scraping_logger.log_scraping_progress(i, len(target_boards), board['menu_name'])
                
                # 게시판 스크래핑
                board_results = self.scrape_board_articles(board["board_url"], max_pages)
                
                # 키워드 및 작성자 필터링
                filtered_articles = self._filter_articles(
                    board_results, 
                    search_keywords, 
                    post_authors, 
                    comment_authors,
                    period
                )
                
                # 각 게시글 상세 스크래핑
                article_urls = [article["article_url"] for article in filtered_articles]
                if article_urls:
                    # 남은 수집 가능한 게시글 수만큼만 처리
                    remaining_articles = max_articles - collected_count
                    if len(article_urls) > remaining_articles:
                        article_urls = article_urls[:remaining_articles]
                    
                    detailed_results = self.scrape_multiple_articles(article_urls, comment_authors, None)
                    all_results.extend(detailed_results)
                    collected_count += len(detailed_results)
                
                print(f"✅ 게시판 {i}/{len(target_boards)} 완료: {len(article_urls)}개 게시글 (누적: {collected_count}개)")
                
                # 게시판 간 지연
                if i < len(target_boards):
                    time.sleep(delay_between_requests)
                
            except Exception as e:
                print(f"❌ 게시판 {i}/{len(target_boards)} 실패: {e}")
                scraping_logger.log_scraping_error(board["menu_name"], str(e))
                continue
        
        # 완료 로깅
        successful = len([r for r in all_results if "error" not in r])
        failed = len(all_results) - successful
        scraping_logger.log_scraping_complete(successful, failed, len(all_results))
        
        return all_results
    
    def _filter_articles(self, articles: list[dict], search_keywords: list[str], post_authors: list[str], comment_authors: list[str], period: str) -> list[dict]:
        """게시글 필터링 - 키워드, 작성자, 기간"""
        filtered = []
        
        print(f"🔍 필터링 시작: {len(articles)}개 게시글 중에서")
        print(f"🔍 검색 키워드: {search_keywords}")
        print(f"🔍 작성자 필터: {post_authors}")
        
        for i, article in enumerate(articles):
            title = article.get('title', '').lower()
            author = article.get('author_nickname', '').lower()
            
            # 키워드 필터링
            if search_keywords:
                keyword_match = any(keyword.lower() in title for keyword in search_keywords)
                if not keyword_match:
                    print(f"❌ 키워드 불일치: {article.get('title', 'N/A')[:30]}...")
                    continue
                else:
                    print(f"✅ 키워드 일치: {article.get('title', 'N/A')[:30]}...")
            
            # 작성자 필터링
            if post_authors:
                author_match = any(author_nick.lower() in author for author_nick in post_authors)
                if not author_match:
                    print(f"❌ 작성자 불일치: {author}")
                    continue
                else:
                    print(f"✅ 작성자 일치: {author}")
            
            # 기간 필터링 (간단한 구현)
            if period != "all":
                # 실제 구현에서는 날짜 파싱 및 비교 필요
                pass
            
            filtered.append(article)
            print(f"✅ 필터 통과: {len(filtered)}번째 게시글")
            
            # 최대 게시글 수 제한 확인
            if len(filtered) >= 5:  # 5개로 제한
                print(f"🛑 최대 게시글 수(5개)에 도달하여 필터링 중단")
                break
        
        print(f"🔍 필터링 완료: {len(filtered)}개 게시글 선택")
        return filtered

    def close(self) -> None:
        """Close browser and save cookies."""
        if self.driver:
            self._save_cookies()
            self.driver.quit()
        print("🔒 Browser closed, cookies saved.")