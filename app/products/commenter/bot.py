"""
네이버 카페 자동 댓글러 (Auto Commenter) - "인간 지능" 버전
- 클립보드 복사/붙여넣기 방식 사용 (네이버 에디터 감지 우회)
- 랜덤 딜레이 및 업무 시간 준수
"""
import time
import random
import pyperclip
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 기존 크롤러의 강력한 브라우저/로그인 기능을 재사용하기 위해 임포트
from app.products.scraper.crawler import NaverCafeCrawler

class NaverCafeCommenter(NaverCafeCrawler):
    """
    Scraper의 기능을 상속받아 브라우저 제어 능력을 확보하고,
    댓글 작성에 특화된 기능을 추가한 클래스
    """
    def __init__(self, db_path: str = "", debug_mode: bool = False):
        super().__init__(output_dir="outputs", debug_mode=debug_mode)
        self.db_path = db_path

    def paste_text(self, text: str):
        """
        [핵심 기술] 클립보드 복사 -> Ctrl+V 붙여넣기
        - send_keys()는 로봇임이 들통날 수 있음
        - 이 방식이 가장 사람과 유사함
        """
        pyperclip.copy(text)
        
        # Mac은 Command, 윈도우는 Control
        cmd_key = Keys.COMMAND if 'darwin' in str(time.time()) else Keys.CONTROL # 간단한 OS 체크 대용(엄밀하진 않으나 보통 윈도우 환경)
        if "win" not in str(self.driver.capabilities['platformName']).lower():
             cmd_key = Keys.CONTROL # 윈도우 확신

        ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(0.5)

    def write_comment(self, article_url: str, template: str, nickname: str = "", title: str = "") -> dict:
        """
        게시글에 댓글 작성
        return: {"status": "success"|"fail", "message": "..."}
        """
        if not self.driver:
            return {"status": "fail", "message": "브라우저가 실행되지 않았습니다."}

        try:
            # 1. 이동
            normalized_url = self._normalize_article_url(article_url)
            self.driver.get(normalized_url)
            time.sleep(random.uniform(2.0, 4.0))

            # 2. Iframe 전환 (crawler.py의 기능 재사용)
            if not self._switch_to_cafe_iframe():
                return {"status": "fail", "message": "Iframe 전환 실패 (삭제된 글?)"}

            # 3. 템플릿 치환 (닉네임, 제목 등)
            # 예: "{닉네임}님 안녕하세요" -> "홍길동님 안녕하세요"
            final_text = template.replace("{닉네임}", nickname).replace("{제목}", title)
            
            # 4. 입력창 찾기
            # 네이버 카페 댓글 입력창 클래스들
            input_selectors = [
                ".comment_inbox_text", 
                "textarea.comment_inbox_text",
                ".CommentWriter .text_input",
                "textarea[placeholder*='댓글']"
            ]
            input_el = None
            for sel in input_selectors:
                try:
                    input_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if input_el: break
                except: continue
            
            if not input_el:
                return {"status": "fail", "message": "댓글 입력창을 찾을 수 없습니다. (권한 없음?)"}

            # 5. 클릭 후 붙여넣기
            input_el.click()
            time.sleep(0.5)
            self.paste_text(final_text)
            time.sleep(1.0)

            # 6. 등록 버튼 클릭
            btn_selectors = [
                ".btn_register", 
                ".btn_register.c_orange", # 구형
                ".CommentWriter .btn_submit", # 신형
                "a.btn_register"
            ]
            btn_el = None
            for sel in btn_selectors:
                try:
                    btn_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if btn_el: break
                except: continue
            
            if btn_el:
                btn_el.click()
                time.sleep(random.uniform(2.5, 4.0)) # 등록 대기
                return {"status": "success", "message": "작성 완료"}
            else:
                return {"status": "fail", "message": "등록 버튼을 못 찾았습니다."}

        except Exception as e:
            return {"status": "fail", "message": f"에러 발생: {str(e)}"}

    def go_to_member_management(self, target_url: str = "") -> dict:
        """
        카페 멤버관리 페이지로 이동 (단순 이동만 수행, 로그인 확인 안함)
        """
        if not self.driver:
            return {"status": "fail", "message": "브라우저가 실행되지 않았습니다."}
            
        try:
            # 1. 현재 URL에서 clubid 추출 시도
            current_url = self.driver.current_url
            clubid = None
            
            # 패턴 1: clubid 파라미터
            match = re.search(r'clubid=(\d+)', current_url)
            if match:
                clubid = match.group(1)
            
            # 패턴 2: URL 경로 (카페 ID가 숫자가 아닌 경우도 있으나, 네이버 카페는 보통 별칭 사용)
            # 하지만 멤버관리 페이지는 반드시 clubid(숫자)가 필요함.
            
            # 2. 실패 시, target_url이나 ArticleList로 이동해서 재시도
            if not clubid:
                # target_url이 있으면 우선 사용, 없으면 기본 ArticleList (불완전)
                fallback_url = target_url if target_url else "https://cafe.naver.com/ArticleList.nhn"
                
                # 이미 해당 페이지라면 새로고침 방지
                if fallback_url not in self.driver.current_url:
                    self.driver.get(fallback_url)
                    time.sleep(2.5) # 이동 대기
                
                # iframe 진입 시도 (카페 메인은 보통 main-area나 cafe_main iframe에 정보가 있음)
                try:
                    self._switch_to_cafe_iframe()
                except: pass
                
                # 다시 URL 확인 (iframe 내부 URL이거나 변경된 URL)
                # 드라이버의 current_url은 상위 프레임 기준일 수 있으므로 page_source나 frame URL 확인이 필요할 수도 있음
                # 하지만 보통 네이버 카페는 URL 파라미터에 clubid가 붙음.
                
                current_url = self.driver.current_url
                match = re.search(r'clubid=(\d+)', current_url)
                if match:
                    clubid = match.group(1)
                else:
                    # 페이지 소스 내에서 g_sClubId 등 변수 찾기 (최후의 수단)
                    try:
                        # 네이버 카페는 전역 변수 g_sClubId를 자주 사용
                        clubid = self.driver.execute_script("return typeof g_sClubId !== 'undefined' ? g_sClubId : null;")
                    except: pass

            if not clubid:
                return {"status": "fail", "message": "카페 ClubID를 찾을 수 없습니다. 브라우저에서 카페 메인화면에 접속해주세요."}
                
            # 3. 멤버관리 URL로 이동
            # https://cafe.naver.com/ManageMember.nhn?clubid=...
            manage_url = f"https://cafe.naver.com/ManageMember.nhn?clubid={clubid}"
            self.driver.get(manage_url)
            time.sleep(2)
            
            return {"status": "success", "message": "이동 완료"}
            
        except Exception as e:
            return {"status": "fail", "message": f"이동 실패: {e}"}

    def scrape_member_management_list(self, max_pages: int = 5) -> list:
        """
        멤버관리 페이지(Admin)의 현재 리스트를 스크래핑
        - 열려있는 모든 탭을 검색하여 '멤버 관리' 페이지를 찾음
        - 모든 프레임과 구조를 전수 조사
        """
        if not self.driver:
            self._update_status("❌ 브라우저가 연결되지 않았습니다.")
            return []
            
        targets = []
        try:
            self._update_status("🔍 '멤버 관리' 페이지가 열린 탭을 찾는 중...")
            
            # 0. 올바른 탭(Window) 찾기
            target_window = None
            original_window = self.driver.current_window_handle
            
            # 모든 탭 순회
            for handle in self.driver.window_handles:
                try:
                    self.driver.switch_to.window(handle)
                    url = self.driver.current_url
                    title = self.driver.title
                    
                    # 관리자 페이지 키워드 확인
                    if "Manage" in url or "멤버" in title or "Member" in url:
                        # 확실하게 하기 위해 페이지 내용 살짝 확인
                        if "멤버" in self.driver.page_source:
                            target_window = handle
                            self._update_status(f"✅ 타겟 탭 발견: {title[:20]}...")
                            break
                except: continue
            
            # 못 찾았으면 원래 탭에서라도 시도
            if not target_window:
                self.driver.switch_to.window(original_window)
                self._update_status("⚠️ 명확한 관리자 탭을 못 찾음. 현재 탭에서 시도합니다.")
            
            self._update_status("🔍 테이블 탐색 중...")
            
            # 테이블 찾기 전략 (순차 시도)
            # 1. 현재 프레임 (Main)
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            
            # 2. 데이터가 없으면 iframe(cafe_main) 전환 시도
            if not rows or len(rows) < 2:
                try:
                    self.driver.switch_to.default_content()
                    wait = WebDriverWait(self.driver, 3)
                    iframe = wait.until(EC.presence_of_element_located((By.ID, "cafe_main")))
                    self.driver.switch_to.frame(iframe)
                    rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                except:
                    pass
            
            # 3. 그래도 없으면 다시 Main으로 나와서 다른 Selector 시도
            if not rows or len(rows) < 2:
                 self.driver.switch_to.default_content()
                 rows = self.driver.find_elements(By.XPATH, "//tr[.//input[@type='checkbox']]") # 체크박스가 있는 행 찾기 (강력함)

            if not rows:
                self._update_status(f"❌ 테이블을 찾을 수 없습니다. (현재 탭: {self.driver.title})")
                return []
                
            self._update_status(f"✅ 테이블 발견! ({len(rows)}개 행)")
            
            for page in range(1, max_pages + 1):
                # stale element 방지
                if page > 1:
                    rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    if not rows:
                        rows = self.driver.find_elements(By.XPATH, "//tr[.//input[@type='checkbox']]")
                
                if not rows: break

                count_in_page = 0
                for row in rows:
                    try:
                        nickname = ""
                        member_id = "unknown"
                        
                        # 전략 1: onclick/data 속성에서 원본 ID 추출 (가장 정확)
                        try:
                            # 행 내부의 모든 요소에서 onclick이나 data-id 검색
                            # (a 태그뿐만 아니라 span, div 등도 확인)
                            all_els = row.find_elements(By.XPATH, ".//*")
                            for el in all_els:
                                # 1. onclick 분석
                                onclick = el.get_attribute("onclick") or ""
                                if "member" in onclick or "Member" in onclick or "ui(" in onclick:
                                    parts = [p.strip().replace("'", "").replace('"', "") for p in onclick.split(",")]
                                    for p in parts:
                                        # ID 후보군: 영문/숫자/특수문자 조합, 특정 키워드 제외
                                        if (len(p) >= 3 and 
                                            re.match(r"^[a-zA-Z0-9_.-]+$", p) and 
                                            p.lower() not in ['mng.member', 'clickcr', 'event', 'true', 'false', 'return', 'ui', 'layer']):
                                            member_id = p
                                            
                                            # 닉네임은 해당 요소의 텍스트에서 추출 시도
                                            txt = el.text.strip()
                                            if txt:
                                                nickname = txt.split("(")[0].strip()
                                            break
                                    if member_id != "unknown": break
                                
                                # 2. data-member-id 속성 확인 (일부 페이지)
                                data_id = el.get_attribute("data-member-id")
                                if data_id:
                                    member_id = data_id
                                    txt = el.text.strip()
                                    if txt: nickname = txt.split("(")[0].strip()
                                    break
                        except: pass

                        # 전략 2: 텍스트 파싱 (백업 - 정규식 개선)
                        if not nickname or member_id == "unknown":
                            text = row.text.strip()
                            # 줄바꿈이 있다면 첫 줄이 보통 닉네임(아이디)
                            first_line = text.split('\n')[0].strip()
                            
                            # Case A: "닉네임 (아이디)" 완전한 형태
                            match = re.search(r'(.+?)\s*\(([^)]+)\)', first_line)
                            if match:
                                nickname = match.group(1).strip()
                                member_id = match.group(2).strip()
                            else:
                                # Case B: "닉네임 (아이디..." 잘린 형태 (닫는 괄호 없음)
                                match_cut = re.search(r'(.+?)\s*\((.+)', first_line)
                                if match_cut:
                                    nickname = match_cut.group(1).strip()
                                    raw_id = match_cut.group(2).strip()
                                    # 뒤에 붙은 ... 이나 닫는 괄호 잔재 제거
                                    member_id = re.sub(r'[).…]+$', '', raw_id).strip()
                                else:
                                    # Case C: 괄호가 아예 없는 경우 (닉네임만 있음)
                                    # 헤더가 아니면 닉네임으로 간주
                                    if "별명" not in first_line and len(first_line) < 20:
                                        nickname = first_line

                        # 헤더 스킵
                        if "별명" in nickname and "아이디" in member_id: continue
                        if not nickname: continue

                        # 유효한 데이터면 추가
                        if nickname:
                            # ID 정제 (혹시 괄호나 점이 남아있다면)
                            if member_id and member_id != "unknown":
                                member_id = re.sub(r'[).…]+$', '', member_id).strip()
                            
                            # ID 없으면 임시 ID
                            if not member_id or member_id == "unknown":
                                member_id = f"unknown_{nickname}"
                            
                            # 중복 방지
                            if not any(t['member_id'] == member_id for t in targets):
                                targets.append({
                                    "nickname": nickname,
                                    "member_id": member_id,
                                    "status": "대기"
                                })
                                count_in_page += 1
                    except: continue
                
                self._update_status(f"✅ {page}페이지: {count_in_page}명 수집 (누적 {len(targets)}명)")
                
                if page < max_pages:
                    # 다음 페이지 이동
                    try:
                        next_btn = None
                        # '다음' 텍스트를 가진 링크를 가장 우선적으로 찾음 (가장 정확)
                        xpath_candidates = [
                            "//a[contains(text(), '다음')]",
                            "//a[contains(text(), 'Next')]",
                            "//a[@class='next']",
                            "//a[@class='pg_next']"
                        ]
                        for xp in xpath_candidates:
                            try:
                                btns = self.driver.find_elements(By.XPATH, xp)
                                for b in btns:
                                    if b.is_displayed():
                                        next_btn = b
                                        break
                                if next_btn: break
                            except: pass
                        
                        if next_btn:
                            self._update_status("➡️ 다음 페이지 클릭...")
                            next_btn.click()
                            time.sleep(2.5) # 페이지 로딩 대기
                        else:
                            self._update_status("⛔ 다음 버튼이 없어 종료합니다.")
                            break
                    except:
                        break
                        
        except Exception as e:
            self._update_status(f"❌ 에러 발생: {e}")
            print(f"Error: {e}")
            
        return targets
