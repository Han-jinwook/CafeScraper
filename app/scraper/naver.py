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
        def log_scraping_start(self, url, total): self.info(f"[INFO] 스크래핑 시작: {url} (총 {total}개)")
        def log_scraping_progress(self, current, total, url): self.info(f"[INFO] [{current:3d}/{total:3d}] {url}")
        def log_scraping_success(self, url, title): self.info(f"[SUCCESS] 성공: {title}")
        def log_scraping_error(self, url, error): self.error(f"[ERROR] 실패: {url} - {error}")
        def log_scraping_complete(self, successful, failed, total): self.info(f"[INFO] 완료: 성공 {successful}개, 실패 {failed}개")
        def log_performance(self, operation, duration, details=""): self.info(f"[INFO] {operation}: {duration:.2f}초")
        def log_memory_usage(self, operation, memory_mb): self.info(f"[INFO] {operation}: {memory_mb:.1f}MB")
        def log_antibot_measure(self, measure, details=""): self.info(f"[INFO] 안티봇 대응: {measure}")
    
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
            print("[INFO] 브라우저가 이미 실행 중입니다.")
            return
        
        try:
            print("[INFO] Selenium Chrome 브라우저 시작 중...")
            
            # Chrome 옵션 설정
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
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2
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
            
            print("[SUCCESS] Selenium Chrome 브라우저 시작 완료")
            
        except Exception as e:
            print(f"[ERROR] 브라우저 시작 실패: {e}")
            print(f"[ERROR] 에러 타입: {type(e).__name__}")
            print(f"[ERROR] 에러 상세: {str(e)}")
            raise Exception(f"브라우저 시작 실패: {str(e)}")

    def _load_cookies(self) -> None:
        """Load saved cookies from file."""
        if self._cookie_file.exists() and self.driver:
            try:
                with open(self._cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                # 네이버 메인 페이지로 이동 후 쿠키 로드
                self.driver.get("https://www.naver.com")
                time.sleep(2)  # 페이지 로딩 대기
                
                loaded_count = 0
                for cookie in cookies:
                    try:
                        # 쿠키 도메인 문제 해결을 위한 수정
                        if 'domain' in cookie:
                            # 도메인이 .naver.com인 경우 www.naver.com으로 변경
                            if cookie['domain'] == '.naver.com':
                                cookie['domain'] = 'www.naver.com'
                        
                        self.driver.add_cookie(cookie)
                        loaded_count += 1
                    except Exception as e:
                        # 쿠키 로드 실패는 무시하고 계속 진행
                        continue
                
                print(f"[SUCCESS] Loaded {loaded_count}/{len(cookies)} cookies from {self._cookie_file}")
                
                # 쿠키 로드 후 페이지 새로고침
                self.driver.refresh()
                time.sleep(2)
                
            except Exception as e:
                print(f"[WARN] Failed to load cookies: {e}")

    def _save_cookies(self) -> None:
        """Save current cookies to file."""
        if self.driver:
            try:
                cookies = self.driver.get_cookies()
                with open(self._cookie_file, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print(f"[SUCCESS] Saved {len(cookies)} cookies to {self._cookie_file}")
            except Exception as e:
                print(f"[WARN] Failed to save cookies: {e}")

    def ensure_logged_in(self) -> bool:
        """Ensure user is logged in to Naver. Returns True if successful."""
        if not self.driver:
            self.start_browser()
        
        # 쿠키 로드
        self._load_cookies()
        
        # 네이버 메인 페이지로 이동
        self.driver.get("https://www.naver.com")
        time.sleep(2)
        
        # 로그인 상태 확인
        try:
            # 로그인 버튼이 없으면 로그인된 상태
            login_button = self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그인')]")
            if not login_button:
                print("[SUCCESS] Already logged in to Naver")
                self._save_cookies()
                return True
            
            # 로그인 버튼이 있어도 카페 접근 가능한지 확인
            print("[INFO] 네이버 홈에서 로그인 버튼이 보이지만, 카페 접근 가능 여부를 확인합니다...")
            
            # 카페 접근 테스트 (실제 카페 URL이 필요)
            # 임시로 네이버 카페 메인 페이지로 이동해서 확인
            try:
                self.driver.get("https://cafe.naver.com")
                time.sleep(3)
                
                # 카페 페이지에서 로그인 상태 확인
                cafe_login_buttons = self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그인')]")
                if not cafe_login_buttons:
                    print("[SUCCESS] 카페 접근 가능 - 로그인 상태 확인됨")
                    self._save_cookies()
                    return True
                else:
                    print("[WARN] 카페에서도 로그인이 필요합니다")
            except Exception as e:
                print(f"[WARN] 카페 접근 테스트 실패: {e}")
                # 카페 접근이 실패해도 네이버 홈에서 로그인 버튼이 없으면 로그인된 것으로 간주
                if not login_button:
                    print("[SUCCESS] 네이버 홈에서 로그인 상태 확인됨")
                    self._save_cookies()
                    return True
            
            # 로그인 버튼이 있으면 로그인 필요
            print("[INFO] Manual login required. Please log in to Naver in the browser window.")
            print("   The system will automatically detect when you're logged in...")
            
            # 자동 로그인 감지 (최대 5분 대기)
            max_wait_time = 300  # 5분
            check_interval = 3   # 3초마다 확인
            waited_time = 0
            
            while waited_time < max_wait_time:
                time.sleep(check_interval)
                waited_time += check_interval
                
                # 페이지 새로고침 후 로그인 상태 확인
                self.driver.refresh()
                time.sleep(2)
                
                # 로그인 상태 재확인
                login_button_after = self.driver.find_elements(By.XPATH, "//a[contains(text(), '로그인')]")
                if not login_button_after:
                    self._save_cookies()
                    print("[SUCCESS] Login successful! Cookies saved.")
                    return True
                
                # 진행 상황 표시
                remaining_time = max_wait_time - waited_time
                print(f"[INFO] Waiting for login... ({remaining_time}s remaining)")
            
            print("[ERROR] Login timeout. Please try again.")
            return False
                
        except Exception as e:
            print(f"[ERROR] Login check failed: {e}")
            return False

    def scrape_article(self, url: str, include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None, max_retries: int = 3):
        """Scrape a single article with comments and images."""
        if not self.ensure_logged_in():
            raise Exception("Login required but failed")
        
        for attempt in range(max_retries):
            try:
                print(f"[INFO] 스크래핑 시도 {attempt + 1}/{max_retries}: {url}")
                
                # Navigate to article with retry logic
                self._navigate_with_retry(url, max_retries=2)
                
                # Take snapshot for debugging
                snapshot_dir = self.snapshots_dir / Path(url).stem
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
                
                print(f"[SUCCESS] 스크래핑 성공: {article_data.get('title', 'N/A')}")
                return result
                
            except Exception as e:
                print(f"[WARN] 스크래핑 시도 {attempt + 1} 실패: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 5초, 10초, 15초 대기
                    print(f"⏳ {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    print(f"[ERROR] 최대 재시도 횟수 초과: {url}")
                    raise e

    def _extract_article_data(self, url: str) -> dict:
        """Extract basic article information."""
        try:
            # Extract cafe ID from URL
            cafe_id = url.split("cafe.naver.com/")[1].split("/")[0] if "cafe.naver.com" in url else "unknown"
            
            # Extract article ID from URL
            article_id = url.split("/")[-1] if "/" in url else "unknown"
            
            # Try multiple selectors for title
            title_selectors = [
                ".title_text",
                ".se-title-text", 
                ".se-fs-",
                "h3.title",
                ".article_title",
                "[data-testid='article-title']",
                ".board_title",
                ".article_title_text",
                ".se-text-paragraph",
                "h1", "h2", "h3",
                ".title",
                "[class*='title']",
                "[class*='Title']"
            ]
            
            title = self._safe_extract(title_selectors, default="제목을 찾을 수 없음")
            
            # Try multiple selectors for author
            author_selectors = [
                ".nick",
                ".nickname", 
                ".author",
                ".writer",
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
            
            author = self._safe_extract(author_selectors, default="작성자를 찾을 수 없음")
            
            # Try multiple selectors for content
            content_selectors = [
                ".se-main-container",
                ".se-component-content", 
                ".article_content",
                ".content",
                "[data-testid='article-content']",
                ".se-text-paragraph",
                ".article_text",
                ".board_text",
                ".post_content",
                ".article_body",
                "[class*='content']",
                "[class*='Content']",
                "[class*='text']",
                "[class*='Text']",
                ".se-text",
                ".se-component"
            ]
            
            content_text = self._safe_extract(content_selectors, default="내용을 찾을 수 없음")
            content_html = self._safe_extract_html(content_selectors, default="<p>내용을 찾을 수 없음</p>")
            
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
            print(f"[WARN] Error extracting article data: {e}")
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
                print(f"[WARN] Too many images ({len(image_elements)}), limiting to {max_images}")
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
                            print(f"[WARN] Image {i+1} too large ({size_mb:.1f}MB), skipping")
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
                    print(f"[WARN] Error processing image {i}: {e}")
                    continue
                    
        except Exception as e:
            print(f"[WARN] Error extracting images: {e}")
        
        return images

    def _extract_comments(self, include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None) -> list:
        """Extract comments with nickname filtering."""
        comments = []
        try:
            # Try multiple selectors for comments
            comment_selectors = [
                ".comment",
                ".reply", 
                ".comment_item",
                "[data-testid='comment']",
                ".comment_list .comment",
                ".comment_list .reply",
                ".reply_list .comment",
                ".reply_list .reply",
                "[class*='comment']",
                "[class*='Comment']",
                "[class*='reply']",
                "[class*='Reply']",
                ".comment_area .comment",
                ".comment_area .reply",
                ".reply_area .comment",
                ".reply_area .reply"
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
                    print(f"[WARN] Error processing comment: {e}")
                    continue
                    
        except Exception as e:
            print(f"[WARN] Error extracting comments: {e}")
        
        return comments

    def scrape_board_articles(self, board_url: str, max_pages: int = 5) -> list[dict]:
        """Scrape articles from a board page with pagination."""
        if not self.ensure_logged_in():
            raise Exception("Login required but failed")
        
        articles = []
        page = 1
        total_articles = 0
        
        print(f"[INFO] 게시판 스크래핑 시작: {board_url}")
        print(f"[INFO] 최대 페이지: {max_pages}")
        print("=" * 50)
        
        while page <= max_pages:
            try:
                progress = f"[페이지 {page:2d}/{max_pages:2d}]"
                print(f"[INFO] {progress} 게시판 페이지 로딩 중...")
                
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
                    print(f"[WARN] {progress} 게시글을 찾을 수 없음, 페이지네이션 중단")
                    break
                
                articles.extend(page_articles)
                total_articles += len(page_articles)
                print(f"[SUCCESS] {progress} 완료 - 발견된 게시글: {len(page_articles)}개 (누적: {total_articles}개)")
                
                page += 1
                
                # Add delay to avoid being blocked
                time.sleep(2)
                
            except Exception as e:
                print(f"[WARN] {progress} 오류: {e}")
                break
        
        print("=" * 50)
        print(f"[INFO] 게시판 스크래핑 완료: 총 {total_articles}개 게시글 발견")
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
                        print(f"[SUCCESS] Found {len(links)} article links using selector: {selector}")
                        break
                except:
                    continue
            
            if not article_links:
                print("[WARN] No article links found on this page")
                return articles
            
            for link in article_links:
                try:
                    # Get article URL
                    href = link.get_attribute("href")
                    if not href or "ArticleRead" not in href:
                        continue
                    
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
                    print(f"[WARN] Error processing article link: {e}")
                    continue
                    
        except Exception as e:
            print(f"[WARN] Error extracting article links: {e}")
        
        return articles

    def scrape_multiple_articles(self, article_urls: list[str], include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None, max_concurrent: int = 3) -> list[dict]:
        """Scrape multiple articles with progress tracking."""
        if not self.ensure_logged_in():
            raise Exception("Login required but failed")
        
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
                print(f"[INFO] {progress} ({percentage:5.1f}%) 스크래핑 중: {url}")
                
                # Scrape individual article
                article_data = self.scrape_article(url, include_nicks, exclude_nicks)
                results.append(article_data)
                successful += 1
                print(f"[SUCCESS] {progress} 완료")
                
                # Add delay between requests
                if i < total:
                    delay = self._calculate_delay(i, total)
                    scraping_logger.log_antibot_measure("요청 간 대기", f"{delay}초")
                    time.sleep(delay)
                
            except Exception as e:
                print(f"[ERROR] {progress} 실패: {e}")
                failed += 1
                results.append({
                    "article_url": url,
                    "title": "스크래핑 실패",
                    "error": str(e),
                    "scraped_at": None
                })
        
        print("=" * 60)
        print(f"[INFO] 스크래핑 완료: 총 {total}개 중 성공 {successful}개, 실패 {failed}개")
        return results

    def _navigate_with_retry(self, url: str, max_retries: int = 3) -> None:
        """Navigate to URL with retry logic."""
        for attempt in range(max_retries):
            try:
                self.driver.get(url)
                time.sleep(3)  # Wait for page to load
                return
            except Exception as e:
                print(f"[WARN] 네비게이션 시도 {attempt + 1} 실패: {e}")
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
                print("[INFO] 브라우저 초기화 중...")
                self.start_browser()
            
            # 로그인 확인
            if not self.ensure_logged_in():
                raise Exception("Login required but failed")
            
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
            # 게시판 링크 선택자들
            board_selectors = [
                "a[href*='BoardList.nhn']",
                "a[href*='menuid=']",
                ".menu_list a",
                ".board_list a",
                "[class*='menu'] a",
                "[class*='board'] a"
            ]
            
            board_links = []
            for selector in board_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        board_links = links
                        print(f"[SUCCESS] 게시판 링크 {len(links)}개 발견: {selector}")
                        break
                except:
                    continue
            
            if not board_links:
                print("[WARN] 게시판 링크를 찾을 수 없습니다")
                return boards
            
            for link in board_links:
                try:
                    href = link.get_attribute("href")
                    if not href or "BoardList" not in href:
                        continue
                    
                    # 메뉴 ID 추출
                    import re
                    menuid_match = re.search(r'menuid=(\d+)', href)
                    if not menuid_match:
                        continue
                    
                    menu_id = menuid_match.group(1)
                    menu_name = link.text.strip() if link.text else f"게시판 {menu_id}"
                    
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
                    
                except Exception as e:
                    print(f"[WARN] 게시판 링크 처리 오류: {e}")
                    continue
                    
        except Exception as e:
            print(f"[WARN] 게시판 목록 추출 오류: {e}")
        
        return boards
    
    def scrape_cafe(self, cafe_url: str, max_pages: int, all_boards: bool, selected_boards: list[str], include_nicks: list[str] | None = None, exclude_nicks: list[str] | None = None) -> list[dict]:
        """카페 전체 또는 특정 게시판 스크래핑"""
        if not self.ensure_logged_in():
            raise Exception("Login required but failed")
        
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
        
        print(f"[INFO] 스크래핑 대상 게시판: {len(target_boards)}개")
        
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
                
                print(f"[SUCCESS] 게시판 {i}/{len(target_boards)} 완료: {len(article_urls)}개 게시글")
                
                # 게시판 간 지연
                if i < len(target_boards):
                    delay = self._calculate_delay(i, len(target_boards))
                    time.sleep(delay)
                
            except Exception as e:
                print(f"[ERROR] 게시판 {i}/{len(target_boards)} 실패: {e}")
                scraping_logger.log_scraping_error(board["menu_name"], str(e))
                continue
        
        # 완료 로깅
        successful = len([r for r in all_results if "error" not in r])
        failed = len(all_results) - successful
        scraping_logger.log_scraping_complete(successful, failed, len(all_results))
        
        return all_results
    
    def batch_scraping(self, cafe_url: str, max_pages: int, all_boards: bool, selected_boards: list[str], search_keywords: list[str], post_authors: list[str], comment_authors: list[str], max_articles: int, image_processing: str, period: str, delay_between_requests: int) -> list[dict]:
        """배치 크롤링 - 키워드 검색 및 작성자 필터링 포함"""
        if not self.ensure_logged_in():
            raise Exception("Login required but failed")
        
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
        
        print(f"[INFO] 배치 크롤링 대상 게시판: {len(target_boards)}개")
        print(f"[INFO] 검색 키워드: {search_keywords}")
        print(f"[INFO] 게시글 작성자 필터: {post_authors}")
        print(f"[INFO] 댓글 작성자 필터: {comment_authors}")
        
        # 각 게시판 스크래핑
        for i, board in enumerate(target_boards, 1):
            if collected_count >= max_articles:
                print(f"[INFO] 최대 수집 게시글 수({max_articles})에 도달하여 크롤링을 중단합니다.")
                break
                
            try:
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
                
                print(f"[SUCCESS] 게시판 {i}/{len(target_boards)} 완료: {len(article_urls)}개 게시글 (누적: {collected_count}개)")
                
                # 게시판 간 지연
                if i < len(target_boards):
                    time.sleep(delay_between_requests)
                
            except Exception as e:
                print(f"[ERROR] 게시판 {i}/{len(target_boards)} 실패: {e}")
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
        
        for article in articles:
            # 키워드 필터링
            if search_keywords:
                title = article.get('title', '').lower()
                content = article.get('content_text', '').lower()
                
                keyword_match = any(keyword.lower() in title or keyword.lower() in content 
                                  for keyword in search_keywords)
                if not keyword_match:
                    continue
            
            # 작성자 필터링
            if post_authors:
                author = article.get('author_nickname', '').lower()
                author_match = any(author_nick.lower() in author for author_nick in post_authors)
                if not author_match:
                    continue
            
            # 기간 필터링 (간단한 구현)
            if period != "all":
                # 실제 구현에서는 날짜 파싱 및 비교 필요
                pass
            
            filtered.append(article)
        
        return filtered

    def close(self) -> None:
        """Close browser and save cookies."""
        if self.driver:
            self._save_cookies()
            self.driver.quit()
        print("[INFO] Browser closed, cookies saved.")