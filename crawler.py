"""
네이버 카페 크롤러 - 로컬 GUI 애플리케이션용
Selenium을 사용하여 로컬 크롬 브라우저를 제어
"""
import os
import time
import random
import json
import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
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

# 크롬 프로필 경로 (사용자가 설정)
CHROME_PROFILE_PATH = ""  # 예: r"C:\Users\사용자명\AppData\Local\Google\Chrome\User Data"


class NaverCafeCrawler:
    """네이버 카페 크롤러 - 로컬 크롬 프로필 사용"""
    
    def __init__(self, chrome_profile_path: str = "", output_dir: str = "outputs"):
        """
        Args:
            chrome_profile_path: 크롬 프로필 경로 (user-data-dir)
            output_dir: 결과 저장 디렉토리
        """
        self.chrome_profile_path = chrome_profile_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.driver: Optional[webdriver.Chrome] = None
        self.status_callback = None  # Streamlit 상태 업데이트용 콜백
        
    def set_status_callback(self, callback):
        """상태 업데이트 콜백 함수 설정"""
        self.status_callback = callback
    
    def _update_status(self, message: str):
        """상태 메시지 업데이트"""
        if self.status_callback:
            self.status_callback(message)
        else:
            print(f"[INFO] {message}")
    
    def start_browser(self) -> None:
        """크롬 브라우저 시작 (헤드리스 모드 없음, 로컬 프로필 사용)"""
        if self.driver:
            self._update_status("브라우저가 이미 실행 중입니다.")
            return
        
        try:
            self._update_status("크롬 브라우저 시작 중...")
            
            chrome_options = Options()
            
            # 로컬 크롬 프로필 사용
            # 주의: 크롬이 이미 실행 중이면 프로필을 사용할 수 없습니다
            # --user-data-dir은 Chrome 폴더를 지정해야 합니다 (User Data의 부모)
            if self.chrome_profile_path and os.path.exists(self.chrome_profile_path):
                # 프로필 경로를 직접 사용 (크롬이 종료된 상태여야 함)
                # 경로가 User Data 폴더인지 확인하고, 그렇다면 부모 디렉토리로 변경
                profile_path = self.chrome_profile_path
                if profile_path.endswith("User Data") or os.path.basename(profile_path) == "User Data":
                    # User Data 폴더가 지정된 경우, 부모 디렉토리(Chrome 폴더)로 변경
                    profile_path = os.path.dirname(profile_path)
                    self._update_status(f"⚠️ User Data 폴더 대신 Chrome 폴더를 사용합니다: {profile_path}")
                
                chrome_options.add_argument(f"--user-data-dir={profile_path}")
                self._update_status(f"크롬 프로필 사용: {profile_path}")
                self._update_status("⚠️ 크롬이 이미 실행 중이면 프로필을 사용할 수 없습니다.")
                self._update_status("💡 크롬을 완전히 종료(Ctrl+Shift+Q 또는 작업 관리자에서 종료)한 후 다시 시도하세요.")
            else:
                # 프로필 경로가 없으면 기본 프로필 사용 (임시 프로필)
                import tempfile
                temp_profile = tempfile.mkdtemp(prefix="chrome_temp_")
                chrome_options.add_argument(f"--user-data-dir={temp_profile}")
                self._update_status(f"임시 프로필 사용: {temp_profile}")
                self._update_status("⚠️ 로그인 정보는 저장되지 않습니다. 크롬 프로필 경로를 설정하세요.")
            
            # 헤드리스 모드 제거 (브라우저가 보이게) - 명시적으로 설정
            # chrome_options.add_argument("--headless")  # 절대 사용하지 않음
            
            # 기본 옵션 (강화된 Stealth 설정)
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-extensions")
            
            # 자동화 표시 제거
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # 가속 및 로그 끄기
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")
            
            # User-Agent 설정 (최신 Chrome 버전)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
            
            # 창 크기 설정
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self._update_status("WebDriver 초기화 중...")
            self._update_status("ChromeDriver 다운로드/확인 중... (처음 실행 시 시간이 걸릴 수 있습니다)")
            
            # WebDriver 초기화
            try:
                # ChromeDriverManager에 타임아웃 설정
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("ChromeDriver 설치 시간 초과")
                
                # ChromeDriver 경로 확인
                self._update_status("ChromeDriver 경로 확인 중...")
                try:
                    import time as time_module
                    start_time = time_module.time()
                    driver_path = ChromeDriverManager().install()
                    elapsed = time_module.time() - start_time
                    self._update_status(f"✅ ChromeDriver 경로: {driver_path}")
                    self._update_status(f"⏱️ ChromeDriver 확인 시간: {elapsed:.2f}초")
                except Exception as driver_mgr_error:
                    error_msg = str(driver_mgr_error)
                    self._update_status(f"❌ ChromeDriverManager 오류: {error_msg}")
                    import traceback
                    self._update_status(f"상세 오류:\n{traceback.format_exc()}")
                    self._update_status("💡 ChromeDriver를 수동으로 설치하거나 인터넷 연결을 확인하세요.")
                    raise
                
                service = Service(driver_path)
                self._update_status("Chrome WebDriver 인스턴스 생성 중...")
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self._update_status("✅ Chrome WebDriver 인스턴스 생성 완료")
                
                # 페이지 로드 타임아웃 설정 (무한 대기 방지)
                self.driver.set_page_load_timeout(20)  # 20초 타임아웃
                self.driver.implicitly_wait(5)  # 요소 찾기 대기 시간 5초
                
                # 창 최대화
                try:
                    self.driver.maximize_window()
                except:
                    pass
                
                # 자동화 감지 방지 (강화)
                self.driver.execute_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
                    window.chrome = {runtime: {}};
                """)
                
                # 초기 페이지 로드
                self.driver.get("about:blank")
                
                # 브라우저 정보 확인
                try:
                    window_handles = self.driver.window_handles
                    # 카페 URL이 있으면 바로 이동
                    if self.chrome_profile_path: # 프로필이 있으면 이미 로그인 상태일 수 있음
                         self.driver.get("https://cafe.naver.com")
                    else:
                         self.driver.get("https://nid.naver.com/nidlogin.login") # 프로필 없으면 로그인 페이지로
                    
                    current_url = self.driver.current_url
                    self._update_status(f"✅ 크롬 브라우저 시작 완료")
                    self._update_status(f"현재 URL: {current_url}")
                    self._update_status(f"💡 브라우저에서 로그인을 완료한 후 2단계를 진행하세요.")
                except Exception as info_error:
                    self._update_status(f"✅ 크롬 브라우저 시작 완료 (정보 확인 실패: {info_error})")
                
            except Exception as driver_error:
                error_msg = str(driver_error)
                self._update_status(f"❌ WebDriver 초기화 실패: {error_msg}")
                
                # 일반적인 오류 해결 방법 안내
                if "user data directory" in error_msg.lower() or "profile" in error_msg.lower() or "lock" in error_msg.lower():
                    self._update_status("💡 해결 방법:")
                    self._update_status("   1. 모든 크롬 창을 완전히 종료하세요 (작업 관리자에서 chrome.exe 프로세스 확인)")
                    self._update_status("   2. 크롬 프로필 경로를 비워두고 다시 시도하세요")
                elif "chrome" in error_msg.lower() and ("not found" in error_msg.lower() or "path" in error_msg.lower()):
                    self._update_status("💡 해결 방법: Chrome 브라우저가 설치되어 있는지 확인하세요.")
                else:
                    import traceback
                    self._update_status(f"상세 오류:\n{traceback.format_exc()}")
                
                raise
            
        except Exception as e:
            error_msg = str(e)
            self._update_status(f"❌ 브라우저 시작 실패: {error_msg}")
            raise
    
    def _switch_to_cafe_iframe(self) -> bool:
        """네이버 카페 iframe으로 전환 (강화된 버전)"""
        try:
            # 먼저 default_content로 전환
            self.driver.switch_to.default_content()
            
            # iframe이 이미 없는 새로운 형식인지 확인
            current_url = self.driver.current_url
            if "/ca-fe/web/cafes/" in current_url:
                self._update_status("ℹ️ 새로운 형식 페이지 (iframe 없음)")
                return True

            # iframe 찾기 시도 (최대 10초 대기)
            iframe_selectors = [
                "iframe#cafe_main",
                "iframe[name='cafe_main']",
                "iframe[src*='BoardList']",
                "iframe[src*='ArticleRead']",
                "iframe[src*='cafe']"
            ]
            
            start_time = time.time()
            while time.time() - start_time < 10:
                for selector in iframe_selectors:
                    try:
                        iframes = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if iframes:
                            iframe = iframes[0]
                            # iframe이 로드되었는지 확인 (src가 비어있지 않은지)
                            src = iframe.get_attribute("src")
                            if src and "about:blank" not in src:
                                self.driver.switch_to.frame(iframe)
                                self._update_status(f"✅ iframe 전환 성공: {selector}")
                                return True
                    except:
                        continue
                time.sleep(1)
            
            # 만약 BoardList.nhn URL인데 iframe을 못 찾았다면 오류일 가능성이 높음
            if "BoardList.nhn" in current_url or "ArticleRead.nhn" in current_url:
                self._update_status("⚠️ iframe을 찾을 수 없습니다 (기존 형식 페이지)")
                return False
                
            self._update_status("ℹ️ iframe 없음 (메인 프레임 사용)")
            return True
            
        except Exception as e:
            self._update_status(f"⚠️ iframe 전환 중 오류: {e}")
            return False
    
    def _switch_to_default_content(self):
        """기본 콘텐츠로 전환"""
        try:
            self.driver.switch_to.default_content()
        except:
            pass
    
    def _wait_for_page_load(self, timeout: int = 10):
        """페이지 로딩 완료 대기 (타임아웃 적용)"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except:
            # 타임아웃 발생 시에도 계속 진행 (일부 페이지는 완전히 로드되지 않을 수 있음)
            return False
    
    def _is_error_page(self) -> bool:
        """오류 페이지인지 확인 (Naver 'Sorry' 페이지 포함)"""
        try:
            # 페이지 제목 확인
            title = self.driver.title.lower()
            if "잠시 후" in title or "연결할 수 없" in title or "error" in title or "오류" in title or "sorry" in title:
                return True
            
            # 페이지 소스 확인 (더 구체적인 키워드)
            page_source = self.driver.page_source.lower()
            error_keywords = [
                "잠시 후 다시 확인해주세요",
                "지금 이 서비스와 연결할 수 없습니다",
                "문제를 해결하기 위해 열심히 노력하고 있습니다",
                "sorry",
                "service unavailable",
                "접속이 제한되었습니다",
                "비정상적인 접근",
                "captcha"
            ]
            if any(keyword in page_source for keyword in error_keywords):
                return True
            
            # 특정 이미지나 요소로 확인 (나타난 고양이/강아지 이미지 등)
            if "illustration by" in page_source:
                return True
                
            return False
        except:
            return False
    
    def _random_delay(self, min_sec: float = 3.0, max_sec: float = 10.0):
        """랜덤 딜레이 (사람처럼 불규칙하게)"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """날짜 문자열을 datetime 객체로 변환"""
        if not date_str:
            return None
        
        try:
            # 다양한 날짜 형식 처리
            # "2024.01.01", "2024-01-01", "1일 전", "2시간 전" 등
            date_str = date_str.strip()
            
            # 상대 시간 처리 ("1일 전", "2시간 전" 등)
            if "전" in date_str or "ago" in date_str.lower():
                # 간단한 처리: 상대 시간은 현재 시간으로 간주
                return datetime.now()
            
            # "YYYY.MM.DD" 형식
            if re.match(r'\d{4}\.\d{2}\.\d{2}', date_str):
                return datetime.strptime(date_str, "%Y.%m.%d")
            
            # "YYYY-MM-DD" 형식
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return datetime.strptime(date_str, "%Y-%m-%d")
            
            # "YYYY/MM/DD" 형식
            if re.match(r'\d{4}/\d{2}/\d{2}', date_str):
                return datetime.strptime(date_str, "%Y/%m/%d")
            
            # 기타 형식 시도
            for fmt in ["%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            
            return None
            
        except Exception as e:
            self._update_status(f"⚠️ 날짜 파싱 실패: {date_str} - {e}")
            return None
    
    def _is_date_before_cutoff(self, date_str: str, cutoff_date: Optional[datetime]) -> bool:
        """날짜가 종료 날짜 이전인지 확인"""
        if not cutoff_date:
            return False
        
        parsed_date = self._parse_date(date_str)
        if not parsed_date:
            return False
        
        return parsed_date < cutoff_date
    
    def navigate_to_cafe(self, cafe_url: str):
        """카페 페이지로 이동 및 iframe 전환"""
        self._update_status(f"카페 페이지 이동: {cafe_url}")
        
        # 페이지 로드 (타임아웃 적용)
        self._switch_to_default_content()
        
        try:
            # 페이지 로드 시작
            self.driver.set_page_load_timeout(15)  # 페이지 로드 타임아웃 15초
            self.driver.get(cafe_url)
            
            # 페이지 로딩 완료 대기
            load_success = self._wait_for_page_load(timeout=10)
            if not load_success:
                self._update_status("⚠️ 페이지 로드 타임아웃 (계속 진행)")
            
            time.sleep(2)
            
            # 오류 페이지 확인
            if self._is_error_page():
                self._update_status("❌ 오류 페이지가 표시됩니다. 네이버 서버 문제일 수 있습니다.")
                raise Exception("네이버 서비스 오류 페이지가 표시됩니다.")
                
        except Exception as load_error:
            error_msg = str(load_error)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                self._update_status("⚠️ 페이지 로드 타임아웃")
            elif "오류 페이지" in error_msg:
                raise  # 오류 페이지는 재시도하지 않고 즉시 실패
            else:
                self._update_status(f"⚠️ 페이지 로드 실패: {error_msg}")
            raise
        
        self._random_delay(2, 4)
        
        # iframe 전환
        self._switch_to_cafe_iframe()
        self._random_delay(1, 2)
    
    def search_in_cafe(self, keyword: str, max_pages: int = 5, cutoff_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """카페 내 검색 수행"""
        self._update_status(f"카페 내 검색: '{keyword}'")
        
        try:
            # 기본 콘텐츠로 전환 (iframe 밖에서 검색창 찾기)
            self._switch_to_default_content()
            
            # 검색창 찾기 (여러 위치 시도)
            search_selectors = [
                "input[name='query']",
                "input[type='text'][placeholder*='검색']",
                "input.search_input",
                "#searchKeyword",
                ".search_input",
                "input[class*='search']",
                "#topLayerQuery",
                "input[placeholder*='검색']"
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if search_input.is_displayed():
                        self._update_status(f"✅ 검색창 발견: {selector}")
                        break
                except:
                    continue
            
            if not search_input:
                self._update_status("❌ 검색창을 찾을 수 없습니다. 페이지 구조를 확인하세요.")
                return []
            
            # 검색어 입력
            search_input.clear()
            search_input.send_keys(keyword)
            self._random_delay(0.5, 1.5)
            
            # 검색 버튼 클릭 또는 Enter 키
            search_button_selectors = [
                "button[type='submit']",
                ".btn_search",
                "button.search",
                "input[type='submit']",
                ".search_btn",
                "button[class*='search']"
            ]
            
            clicked = False
            for selector in search_button_selectors:
                try:
                    search_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if search_button.is_displayed():
                        search_button.click()
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                # 버튼을 찾지 못하면 Enter 키 시도
                from selenium.webdriver.common.keys import Keys
                search_input.send_keys(Keys.RETURN)
            
            self._random_delay(3, 6)
            
            # 검색 결과 페이지에서 게시글 리스트 수집
            all_articles = []
            
            for page in range(1, max_pages + 1):
                try:
                    self._update_status(f"검색 결과 페이지 {page}/{max_pages} 처리 중...")
                    
                    # iframe 전환 시도
                    self._switch_to_cafe_iframe()
                    self._random_delay(1, 2)
                    
                    # 게시글 리스트 추출
                    page_articles = self._extract_article_links_from_board()
                    
                    if not page_articles:
                        self._update_status(f"페이지 {page}에서 게시글을 찾을 수 없습니다.")
                        break
                    
                    # 날짜 필터링
                    if cutoff_date:
                        filtered_articles = []
                        should_stop = False
                        for article in page_articles:
                            posted_at = article.get('posted_at')
                            if posted_at and self._is_date_before_cutoff(posted_at, cutoff_date):
                                should_stop = True
                                break
                            filtered_articles.append(article)
                        
                        all_articles.extend(filtered_articles)
                        if should_stop:
                            self._update_status(f"종료 날짜 이전 게시글 발견. 수집 중단.")
                            break
                    else:
                        all_articles.extend(page_articles)
                    
                    self._update_status(f"페이지 {page} 완료: {len(page_articles)}개 게시글 (누적: {len(all_articles)}개)")
                    
                    # 다음 페이지로 이동
                    if page < max_pages:
                        try:
                            next_button_selectors = [
                                "a[href*='page=']",
                                ".paging a:last-child",
                                ".next",
                                "a.next"
                            ]
                            
                            for selector in next_button_selectors:
                                try:
                                    next_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                    for btn in next_buttons:
                                        if "다음" in btn.text or ">" in btn.text or "next" in btn.text.lower():
                                            btn.click()
                                            self._random_delay(2, 4)
                                            break
                                except:
                                    continue
                        except:
                            break
                    
                    self._random_delay(3, 8)
                    
                except Exception as e:
                    self._update_status(f"⚠️ 페이지 {page} 처리 실패: {e}")
                    break
            
            self._update_status(f"검색 결과: {len(all_articles)}개 게시글 발견")
            return all_articles
            
        except Exception as e:
            self._update_status(f"❌ 검색 실패: {e}")
            import traceback
            self._update_status(f"상세 오류: {traceback.format_exc()}")
            return []
    
    def get_articles_by_author(self, cafe_url: str, author_nickname: str, max_pages: int = 10, cutoff_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """특정 작성자의 모든 게시글 수집"""
        self._update_status(f"작성자 '{author_nickname}'의 게시글 수집 시작")
        
        articles = []
        self.navigate_to_cafe(cafe_url)
        
        # 게시판 목록 조회
        board_urls = self._get_cafe_board_urls()
        
        if not board_urls:
            self._update_status("⚠️ 게시판을 찾을 수 없습니다.")
            return articles
        
        self._update_status(f"발견된 게시판: {len(board_urls)}개")
        
        for board_idx, board_url in enumerate(board_urls[:max_pages], 1):
            if len(articles) >= 100:  # 최대 100개로 제한
                break
            
            self._update_status(f"게시판 {board_idx}/{min(len(board_urls), max_pages)}: {board_url}")
            
            # 게시판 페이지별 순회
            for page in range(1, max_pages + 1):
                try:
                    if "?" in board_url:
                        page_url = f"{board_url}&page={page}"
                    else:
                        page_url = f"{board_url}?page={page}"
                    
                    self._switch_to_default_content()
                    self.driver.get(page_url)
                    self._switch_to_cafe_iframe()
                    self._random_delay(2, 4)
                    
                    page_articles = self._extract_article_links_from_board()
                    
                    if not page_articles:
                        break  # 더 이상 게시글이 없으면 다음 게시판으로
                    
                    # 작성자 필터링 (공백 및 부분 일치 대응)
                    target_nick = author_nickname.strip().lower()
                    filtered = [
                        a for a in page_articles 
                        if target_nick in a.get('author_nickname', '').strip().lower() or 
                           a.get('author_nickname', '').strip().lower() in target_nick
                    ]
                    
                    # 날짜 필터링
                    if cutoff_date:
                        date_filtered = []
                        should_stop = False
                        for article in filtered:
                            posted_at = article.get('posted_at')
                            if posted_at and self._is_date_before_cutoff(posted_at, cutoff_date):
                                should_stop = True
                                break
                            date_filtered.append(article)
                        
                        articles.extend(date_filtered)
                        if should_stop:
                            self._update_status(f"종료 날짜 이전 게시글 발견. 수집 중단.")
                            break
                    else:
                        articles.extend(filtered)
                    
                    self._update_status(f"  페이지 {page}: {len(filtered)}개 게시글 발견 (누적: {len(articles)}개)")
                    
                    if len(articles) >= 100:
                        break
                    
                    self._random_delay(3, 8)
                    
                except Exception as e:
                    self._update_status(f"⚠️ 페이지 {page} 처리 실패: {e}")
                    break
        
        self._update_status(f"작성자 '{author_nickname}' 게시글: {len(articles)}개 발견")
        return articles
    
    def get_cafe_boards(self, cafe_url: str) -> List[Dict[str, Any]]:
        """카페 게시판 목록 조회 (SPA 및 iframe 방식 모두 지원)"""
        boards = []
        try:
            self._update_status(f"카페 메인으로 이동하여 게시판 목록을 가져옵니다: {cafe_url}")
            self.driver.get(cafe_url)
            time.sleep(3)
            
            # 1. iframe 전환 시도 (기존 방식)
            self._switch_to_cafe_iframe()
            
            # 2. 게시판 링크 찾기 (왼쪽 메뉴 영역 집중 탐색)
            # SPA 방식과 iframe 방식의 모든 메뉴 선택자 포함
            menu_selectors = [
                "#groupArea a[href*='menuid=']",
                "#menuLinka[href*='menuid=']",
                ".cafe-menu-list a[href*='menuid=']",
                "a[href*='ArticleList.nhn?search.clubid=']",
                "a[href*='/menus/']",
                ".menu_name a",
                "a.item" # 추가
            ]
            
            found_links = []
            for selector in menu_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for l in links:
                        if l not in found_links:
                            found_links.append(l)
                except: continue
            
            # 만약 위 선택자로 못 찾았다면 전체 <a> 태그 중 menuid 포함된 것 찾기
            if not found_links:
                all_a = self.driver.find_elements(By.TAG_NAME, "a")
                found_links = [a for a in all_a if "menuid=" in (a.get_attribute("href") or "")]

            self._update_status(f"✅ 메뉴 영역에서 {len(found_links)}개 링크 발견")
            
            seen_menu_ids = set()
            for link in found_links:
                try:
                    href = link.get_attribute("href")
                    name = link.text.strip() or link.get_attribute("innerText").strip()
                    
                    if not href or not name or any(p in href for p in ["javascript", "#", "mailto"]):
                        continue
                        
                    menu_id = None
                    if "menuid=" in href:
                        match = re.search(r'menuid=(\d+)', href)
                        if match: menu_id = match.group(1)
                    elif "/menus/" in href:
                        match = re.search(r'/menus/(\d+)', href)
                        if match: menu_id = match.group(1)
                        
                    if menu_id and menu_id not in seen_menu_ids:
                        # 게시판 성격이 아닌 메뉴(전체글보기, 공지사항 등) 제외 필터링 (필요시)
                        seen_menu_ids.add(menu_id)
                        
                        # URL 정규화
                        if href.startswith("/"):
                            href = f"https://cafe.naver.com{href}"
                        
                        boards.append({
                            "menu_id": menu_id,
                            "menu_name": name,
                            "board_url": href
                        })
                        self._update_status(f"✅ 게시판 발견: {name} (ID: {menu_id})")
                except:
                    continue
            
            self._update_status(f"✅ 총 {len(boards)}개의 게시판 목록을 확보했습니다.")
            
            # 3. 만약 게시판을 하나도 못 찾았다면, 현재 URL이라도 추가 (최후의 수단)
            if not boards:
                current_url = self.driver.current_url
                if "menuid=" in current_url or "/menus/" in current_url:
                    boards.append({
                        "menu_id": "current",
                        "menu_name": "현재 게시판",
                        "board_url": current_url
                    })
                    self._update_status("⚠️ 메뉴를 찾지 못해 현재 페이지를 수집 대상으로 설정합니다.")

            return boards
        except Exception as e:
            self._update_status(f"⚠️ 게시판 목록 조회 실패: {e}")
            return []
            
            # 3. 게시판 링크 찾기 (더 포괄적인 선택자)
            board_selectors = [
                "a[href*='menuid=']",
                "a[href*='/menus/']",
                ".menu_list a",
                ".board_list a",
                "[class*='menu'] a"
            ]
            
            found_links = []
            for selector in board_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for l in links:
                        if l not in found_links:
                            found_links.append(l)
                except: continue
            
            self._update_status(f"✅ 후보 링크 {len(found_links)}개 발견")
            
            seen_menu_ids = set()
            for link in found_links:
                try:
                    href = link.get_attribute("href")
                    name = link.text.strip()
                    
                    if not href or not name or any(p in href for p in ["javascript", "#", "mailto"]):
                        continue
                        
                    menu_id = None
                    if "menuid=" in href:
                        match = re.search(r'menuid=(\d+)', href)
                        if match: menu_id = match.group(1)
                    elif "/menus/" in href:
                        match = re.search(r'/menus/(\d+)', href)
                        if match: menu_id = match.group(1)
                        
                    if menu_id and menu_id not in seen_menu_ids:
                        seen_menu_ids.add(menu_id)
                        
                        # URL 정규화
                        if href.startswith("/"):
                            href = f"https://cafe.naver.com{href}"
                        elif not href.startswith("http"):
                            href = f"https://cafe.naver.com/{href}"
                            
                        boards.append({
                            "menu_id": menu_id,
                            "menu_name": name,
                            "board_url": href
                        })
                        self._update_status(f"✅ 게시판 추가: {name} (ID: {menu_id})")
                except:
                    continue
            
            self._update_status(f"✅ 게시판 목록 조회 완료: {len(boards)}개")
            return boards
        except Exception as e:
            self._update_status(f"⚠️ 게시판 목록 조회 실패: {e}")
            return []
    
    def _get_cafe_board_urls(self) -> List[str]:
        """카페 게시판 URL 목록 조회 (레거시 메서드)"""
        boards = self.get_cafe_boards(self.driver.current_url if self.driver else "")
        return [board["board_url"] for board in boards]
    
    def scrape_board_articles(self, board_url: str, max_pages: int = 5, cutoff_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """게시판에서 게시글 리스트 수집 (날짜 필터링 포함)"""
        articles = []
        page = 1
        
        self._update_status(f"게시판 스크래핑 시작: {board_url}")
        
        while page <= max_pages:
            try:
                self._update_status(f"페이지 {page}/{max_pages} 처리 중...")
                
                # 페이지 URL 구성
                if "/ca-fe/web/" in board_url:
                    sep = "&" if "?" in board_url else "?"
                    page_url = f"{board_url}{sep}page={page}"
                else:
                    sep = "&" if "?" in board_url else "?"
                    page_url = f"{board_url}{sep}page={page}"
                
                # 페이지 이동
                if self.driver.current_url != page_url:
                    self._switch_to_default_content()
                    self.driver.get(page_url)
                
                # 페이지 로딩 및 iframe 전환 대기
                time.sleep(2)
                self._switch_to_cafe_iframe()
                
                # 게시글 목록이 나타날 때까지 대기 (최대 10초)
                wait_selectors = [
                    "form[name='ArticleList']", 
                    "div.article-board", 
                    "table.board-list",
                    ".article_list",
                    "div[class*='ArticleItem']"
                ]
                
                found_list = False
                for selector in wait_selectors:
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        found_list = True
                        break
                    except: continue
                
                if not found_list:
                    self._update_status("⚠️ 게시글 목록 요소를 찾을 수 없습니다. 계속 진행 시도...")

                # 게시글 리스트 추출
                page_articles = self._extract_article_links_from_board()
                
                if not page_articles:
                    # 디버깅용: 왜 못 찾았는지 샘플 링크 출력
                    try:
                        all_a = self.driver.find_elements(By.TAG_NAME, "a")
                        sample_hrefs = [a.get_attribute("href") for a in all_a[:10] if a.get_attribute("href")]
                        self._update_status(f"⚠️ 페이지 {page}에서 게시글 추출 실패. 발견된 링크 샘플: {sample_hrefs}")
                    except: pass
                    
                    self._update_status(f"페이지 {page}에서 게시글을 찾을 수 없습니다. 다음 단계 진행.")
                    page += 1 # 무한 루프 방지를 위해 다음 페이지로
                    continue
                
                # 날짜 필터링
                if cutoff_date:
                    filtered_articles = []
                    should_stop = False
                    
                    for article in page_articles:
                        posted_at = article.get('posted_at')
                        if posted_at and self._is_date_before_cutoff(posted_at, cutoff_date):
                            should_stop = True
                            break
                        filtered_articles.append(article)
                    
                    articles.extend(filtered_articles)
                    
                    if should_stop:
                        self._update_status(f"종료 날짜({cutoff_date.strftime('%Y-%m-%d')}) 이전 게시글 발견. 수집 중단.")
                        break
                else:
                    articles.extend(page_articles)
                
                self._update_status(f"페이지 {page} 완료: {len(page_articles)}개 게시글 (누적: {len(articles)}개)")
                
                page += 1
                # 페이지 간 딜레이 증가 (오류 방지)
                self._random_delay(5, 15)  # 5-15초 랜덤 딜레이
                
            except Exception as e:
                self._update_status(f"⚠️ 페이지 {page} 처리 실패: {e}")
                break
        
        self._update_status(f"게시판 스크래핑 완료: 총 {len(articles)}개 게시글")
        return articles
    
    def _extract_article_links_from_board(self) -> List[Dict[str, Any]]:
        """게시판 페이지에서 게시글 링크 추출 (강화된 버전)"""
        articles = []
        
        try:
            current_url = self.driver.current_url
            self._update_status(f"현재 페이지 분석 중: {current_url}")
            
            # 새로운 형식의 페이지인 경우 스크롤 및 대기
            if "/ca-fe/web/cafes/" in current_url:
                self._update_status("ℹ️ 새로운 형식 페이지 분석 중...")
                # 여러 번 스크롤하여 동적 콘텐츠 로드
                for _ in range(2):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(0.5)
            
            # 게시글 링크 선택자 (더 구체적이고 포괄적으로)
            article_selectors = [
                # 기존 형식 (iframe 내부 테이블)
                "a.article",
                "a[href*='ArticleRead.nhn?articleid=']",
                "a[href*='ArticleRead.nhn'][href*='articleid=']",
                "td.td_article a.article",
                "div.board-list td.td_article a",
                
                # 새로운 형식 (SPA)
                "a[href*='/articles/']",
                "a[class*='article']",
                "a[class*='post']",
                ".article_item a",
                ".article_list a",
                "div[class*='ArticleItem'] a",
                "div[class*='article_'] a", # 추가
                "a[class*='tit']", # 추가 (제목 링크)
                
                # 공통/기타
                "tr td a[href*='articleid']",
                "li a[href*='articleid']",
                "a.aaa", # 네이버 카페 특정 클래스
                "a[href*='/vpqtnl/']" # 카페 ID가 포함된 모든 링크 (최후의 수단)
            ]
            
            found_links = []
            for selector in article_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        href = el.get_attribute("href")
                        if href and href not in [l.get_attribute("href") for l in found_links]:
                            # 광고나 공지사항 제외 필터링 (필요시)
                            found_links.append(el)
                except:
                    continue
            
            if not found_links:
                # 최후의 수단: 모든 <a> 태그 중 articleid가 포함된 것 찾기
                all_a = self.driver.find_elements(By.TAG_NAME, "a")
                for a in all_a:
                    try:
                        href = a.get_attribute("href")
                        if href and ("articleid=" in href or "/articles/" in href):
                            if href not in [l.get_attribute("href") for l in found_links]:
                                found_links.append(a)
                    except:
                        continue

            self._update_status(f"✅ 후보 링크 {len(found_links)}개 발견")
            if found_links:
                sample_hrefs = [l.get_attribute("href") for l in found_links[:3]]
                self._update_status(f"ℹ️ 링크 샘플: {sample_hrefs}")
            
            for link in found_links:
                try:
                    href = link.get_attribute("href")
                    if not href: continue
                    
                    # 1. 공지사항 제외 로직 강화
                    try:
                        # 부모 행(tr)을 찾아서 공지사항인지 확인
                        parent_tr = link.find_element(By.XPATH, "ancestor::tr")
                        tr_class = parent_tr.get_attribute("class") or ""
                        tr_text = parent_tr.text
                        
                        # '공지', '필독' 단어가 포함되어 있거나 클래스명이 notice인 경우 제외
                        if "notice" in tr_class.lower() or "공지" in tr_text[:10] or "필독" in tr_text[:10]:
                            continue
                    except:
                        # tr 구조가 아닌 경우(SPA) 클래스명으로 판단
                        link_class = link.get_attribute("class") or ""
                        if "notice" in link_class.lower():
                            continue

                    # 2. 메뉴/카페 설정 등 불필요한 링크 제외
                    is_potential_article = ("/articles/" in href or "articleid=" in href or re.search(r'/\d+(?:\?|#|$)', href))
                    if any(p in href for p in ["/menus/", "/cafes/", "javascript:", "#", "MyCafeIntro", "BoardList.nhn"]):
                        if not is_potential_article:
                            continue
                        
                    # 제목 추출
                    title = link.text.strip()
                    if not title:
                        try:
                            title = self.driver.execute_script("return arguments[0].innerText;", link).strip()
                        except:
                            title = "제목 없음"
                    
                    # 작성자 및 날짜 추출
                    author = "알 수 없음"
                    date = "알 수 없음"
                    
                    try:
                        parent = None
                        for p_tag in ["tr", "li", "div[class*='item']", "div[class*='ArticleItem']"]:
                            try:
                                parent = link.find_element(By.XPATH, f"ancestor::{p_tag}")
                                if parent: break
                            except: continue
                            
                        if parent:
                            author_selectors = [".nick", ".nickname", ".author", "[class*='writer']", "[class*='nick']", ".m-tcol-c", ".p-nick"]
                            for selector in author_selectors:
                                try:
                                    els = parent.find_elements(By.CSS_SELECTOR, selector)
                                    if els and els[0].text.strip():
                                        author = els[0].text.strip()
                                        break
                                except: continue
                            
                            date_selectors = [".date", ".time", "[class*='date']", "[class*='time']", "td.td_date", "span.date"]
                            for selector in date_selectors:
                                try:
                                    els = parent.find_elements(By.CSS_SELECTOR, selector)
                                    if els and els[0].text.strip():
                                        date = els[0].text.strip()
                                        break
                                except: continue
                    except: pass
                    
                    # 게시글 ID 추출 로직 강화
                    article_id = "unknown"
                    
                    # 1. data-article-id 속성 확인
                    try:
                        article_id = link.get_attribute("data-article-id")
                    except: pass
                    
                    if not article_id or article_id == "unknown":
                        # 2. href에서 추출
                        if "articleid=" in href:
                            match = re.search(r'articleid=(\d+)', href)
                            if match: article_id = match.group(1)
                        elif "/articles/" in href:
                            parts = href.split("/articles/")
                            if len(parts) > 1:
                                article_id = parts[1].split("?")[0].split("/")[0]
                        else:
                            # 3. 최후의 수단: URL의 마지막 부분이 숫자인지 확인 (예: /vpqtnl/123)
                            match = re.search(r'/(\d+)(?:\?|#|$)', href)
                            if match:
                                article_id = match.group(1)
                    
                    if not article_id or article_id == "unknown" or not str(article_id).isdigit():
                        continue

                    articles.append({
                        "article_id": article_id,
                        "article_url": href,
                        "title": title,
                        "author_nickname": author,
                        "posted_at": date,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                except:
                    continue
                    
            # 중복 제거
            seen_ids = set()
            unique_articles = []
            for a in articles:
                if a["article_id"] not in seen_ids:
                    unique_articles.append(a)
                    seen_ids.add(a["article_id"])
            
            self._update_status(f"✅ 최종 게시글 {len(unique_articles)}개 추출 완료")
            return unique_articles
            
        except Exception as e:
            self._update_status(f"⚠️ 게시글 추출 중 오류: {e}")
            return []
    
    def scrape_article_detail(self, article_url: str, include_nicks: List[str] = None, exclude_nicks: List[str] = None) -> Dict[str, Any]:
        """개별 게시글 상세 정보 수집"""
        try:
            self._update_status(f"게시글 상세 수집: {article_url}")
            
            self._switch_to_default_content()
            self.driver.get(article_url)
            self._random_delay(2, 4)
            
            self._switch_to_cafe_iframe()
            self._random_delay(1, 2)
            
            # 카페 ID, 게시글 ID 추출
            cafe_id = article_url.split("cafe.naver.com/")[1].split("/")[0] if "cafe.naver.com" in article_url else "unknown"
            article_id = article_url.split("/")[-1] if "/" in article_url else "unknown"
            
            # 제목 추출
            title_selectors = [
                ".title_text", ".se-title-text", "h3.title", ".article_title",
                ".board_title", ".article_title_text", "h1", "h2", "h3"
            ]
            title = self._safe_extract(title_selectors, default="제목을 찾을 수 없음")
            
            # 작성자 추출
            author_selectors = [
                ".nick", ".nickname", ".author", ".writer",
                ".nickname_text", ".author_name", ".writer_name"
            ]
            author = self._safe_extract(author_selectors, default="작성자를 찾을 수 없음")
            
            # 내용 추출
            content_selectors = [
                ".se-main-container", ".se-component-content", ".article_content",
                ".content", ".article_text", ".board_text", ".post_content"
            ]
            content_text = self._safe_extract(content_selectors, default="내용을 찾을 수 없음")
            content_html = self._safe_extract_html(content_selectors, default="<p>내용을 찾을 수 없음</p>")
            
            # 날짜 추출
            date_selectors = [
                ".date", ".time", ".created_at", ".article_date",
                ".post_date", ".board_date"
            ]
            posted_at = self._safe_extract(date_selectors, default=None)
            if posted_at == "알 수 없음":
                posted_at = None
            
            # 이미지 추출
            images = self._extract_images()
            
            # 댓글 추출
            comments = self._extract_comments(include_nicks, exclude_nicks)
            
            result = {
                "cafe_id": cafe_id,
                "article_id": article_id,
                "article_url": article_url,
                "title": title,
                "author_nickname": author,
                "posted_at": posted_at,
                "content_text": content_text,
                "content_html": content_html,
                "images_base64": images,
                "comments": comments,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            self._update_status(f"✅ 게시글 수집 완료: {title[:30]}...")
            return result
            
        except Exception as e:
            self._update_status(f"❌ 게시글 수집 실패: {e}")
            return {
                "article_url": article_url,
                "title": "수집 실패",
                "error": str(e),
                "scraped_at": None
            }
    
    def _safe_extract(self, selectors: List[str], timeout: int = 2, default: str = "알 수 없음") -> str:
        """안전하게 텍스트 추출"""
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
    
    def _safe_extract_html(self, selectors: List[str], timeout: int = 2, default: str = "<p>알 수 없음</p>") -> str:
        """안전하게 HTML 추출"""
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if element and element.get_attribute("innerHTML"):
                    return element.get_attribute("innerHTML").strip()
            except:
                continue
        return default
    
    def _extract_images(self, max_images: int = 10) -> List[Dict[str, Any]]:
        """이미지 추출 및 Base64 변환"""
        images = []
        try:
            image_elements = self.driver.find_elements(By.TAG_NAME, "img")
            
            if len(image_elements) > max_images:
                image_elements = image_elements[:max_images]
            
            for i, img in enumerate(image_elements):
                try:
                    src = img.get_attribute("src")
                    if not src or src.startswith("data:"):
                        continue
                    
                    response = requests.get(src, timeout=10)
                    if response.status_code == 200:
                        image_data = response.content
                        size_mb = len(image_data) / (1024 * 1024)
                        
                        if size_mb > 5.0:  # 5MB 제한
                            continue
                        
                        base64_data = base64.b64encode(image_data).decode('utf-8')
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
                except:
                    continue
        except Exception as e:
            self._update_status(f"⚠️ 이미지 추출 실패: {e}")
        
        return images
    
    def _extract_comments(self, include_nicks: List[str] = None, exclude_nicks: List[str] = None) -> List[Dict[str, Any]]:
        """댓글 추출 및 필터링"""
        comments = []
        try:
            comment_selectors = [
                ".comment", ".reply", ".comment_item",
                ".comment_list .comment", ".reply_list .reply"
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
                    text_element = comment_element.find_elements(By.CSS_SELECTOR, ".comment_text, .reply_text, .content")
                    text = text_element[0].text if text_element else "댓글 내용 없음"
                    
                    author_element = comment_element.find_elements(By.CSS_SELECTOR, ".nick, .nickname, .author")
                    author = author_element[0].text if author_element else "알 수 없음"
                    
                    date_element = comment_element.find_elements(By.CSS_SELECTOR, ".date, .time")
                    date = date_element[0].text if date_element else None
                    
                    # 필터링
                    should_include = True
                    
                    if include_nicks:
                        should_include = any(nick in author for nick in include_nicks)
                    
                    if exclude_nicks:
                        should_include = should_include and not any(nick in author for nick in exclude_nicks)
                    
                    if should_include:
                        comments.append({
                            "comment_id": f"comment_{len(comments)+1}",
                            "nickname": author.strip() if author else "알 수 없음",
                            "text": text.strip() if text else "댓글 내용 없음",
                            "created_at": date.strip() if date else None
                        })
                except:
                    continue
        except Exception as e:
            self._update_status(f"⚠️ 댓글 추출 실패: {e}")
        
        return comments
    
    def scrape_comments_only(self, cafe_url: str, comment_author_nickname: str, exclude_own_posts: bool = True, max_pages: int = 10, cutoff_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """댓글만 수집 - 특정 닉네임의 댓글이 있는 게시글 찾기"""
        self._update_status(f"댓글만 수집 모드: '{comment_author_nickname}' 닉네임의 댓글 찾기")
        
        articles = []
        self.navigate_to_cafe(cafe_url)
        
        # 게시판 목록 조회
        boards = self.get_cafe_boards(cafe_url)
        
        if not boards:
            self._update_status("⚠️ 게시판을 찾을 수 없습니다.")
            return articles
        
        self._update_status(f"발견된 게시판: {len(boards)}개")
        
        # 각 게시판을 순회하며 댓글 찾기
        for board_idx, board in enumerate(boards[:max_pages], 1):
            if len(articles) >= 100:  # 최대 100개로 제한
                break
            
            self._update_status(f"게시판 {board_idx}/{min(len(boards), max_pages)}: {board['menu_name']} 검색 중...")
            
            # 게시판 페이지별 순회
            for page in range(1, max_pages + 1):
                try:
                    if "?" in board['board_url']:
                        page_url = f"{board['board_url']}&page={page}"
                    else:
                        page_url = f"{board['board_url']}?page={page}"
                    
                    self._switch_to_default_content()
                    self.driver.get(page_url)
                    self._switch_to_cafe_iframe()
                    self._random_delay(2, 4)
                    
                    # 게시글 리스트 추출
                    page_articles = self._extract_article_links_from_board()
                    
                    if not page_articles:
                        break  # 더 이상 게시글이 없으면 다음 게시판으로
                    
                    # 각 게시글에서 댓글 확인
                    for article in page_articles:
                        # 날짜 필터링
                        if cutoff_date:
                            posted_at = article.get('posted_at')
                            if posted_at and self._is_date_before_cutoff(posted_at, cutoff_date):
                                continue
                        
                        # 게시글 상세 페이지로 이동하여 댓글 확인
                        try:
                            article_url = article['article_url']
                            self._switch_to_default_content()
                            self.driver.get(article_url)
                            self._switch_to_cafe_iframe()
                            self._random_delay(1, 2)
                            
                            # 게시글 작성자 확인
                            article_author = self._safe_extract([
                                ".nick", ".nickname", ".author", ".writer",
                                ".nickname_text", ".author_name", ".writer_name"
                            ], default="")
                            
                            # 자신의 게시글 제외 옵션
                            if exclude_own_posts and article_author == comment_author_nickname:
                                continue
                            
                            # 댓글 확인 (전체 댓글 추출)
                            all_comments = self._extract_comments(include_nicks=None, exclude_nicks=None)
                            
                            # 지정된 닉네임의 댓글이 있는지 확인
                            has_target_comment = any(
                                comment_author_nickname in comment.get('nickname', '') 
                                for comment in all_comments
                            )
                            
                            if has_target_comment:
                                articles.append(article)
                                self._update_status(f"✅ 발견: {article.get('title', '')[:30]}... ({len(all_comments)}개 댓글)")
                                
                                if len(articles) >= 100:
                                    break
                            
                        except Exception as e:
                            self._update_status(f"⚠️ 게시글 확인 실패: {e}")
                            continue
                        
                        self._random_delay(1, 3)  # 게시글 간 딜레이
                    
                    if len(articles) >= 100:
                        break
                    
                    self._random_delay(2, 4)  # 페이지 간 딜레이
                    
                except Exception as e:
                    self._update_status(f"⚠️ 페이지 {page} 처리 실패: {e}")
                    break
        
        self._update_status(f"댓글 수집 완료: {len(articles)}개 게시글 발견")
        return articles
    
    def scrape_multiple_articles(self, article_urls: List[str], include_nicks: List[str] = None, exclude_nicks: List[str] = None) -> List[Dict[str, Any]]:
        """여러 게시글 상세 수집"""
        results = []
        total = len(article_urls)
        
        for i, url in enumerate(article_urls, 1):
            self._update_status(f"[{i}/{total}] 게시글 수집 중...")
            
            result = self.scrape_article_detail(url, include_nicks, exclude_nicks)
            results.append(result)
            
            if i < total:
                self._random_delay(3, 10)  # 게시글 간 딜레이
        
        return results
    
    def close(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self._update_status("브라우저 종료 완료")
