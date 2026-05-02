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

    # ─── write_comment: editable sink 자동 탐색 + 입력 검증 + 등록 후 확인 ───

    def _get_element_length(self, el) -> int:
        """요소에 입력된 텍스트 길이 반환 (input/textarea: value, contenteditable: innerText)"""
        try:
            length = self.driver.execute_script(
                "var e=arguments[0];"
                "if(e.tagName==='TEXTAREA'||e.tagName==='INPUT') return (e.value||'').length;"
                "return (e.innerText||e.textContent||'').trim().length;",
                el,
            )
            return int(length or 0)
        except Exception:
            return 0

    def _find_editable_candidates(self) -> list:
        """
        현재 프레임에서 editable 후보를 모두 찾아 반환.
        각 항목: {"el": WebElement, "reason": str, "info": dict}
        """
        candidates = []
        seen_ids = set()

        def _add(el, reason):
            if el is None:
                return
            el_id = id(el)
            if el_id in seen_ids:
                return
            seen_ids.add(el_id)
            try:
                info = self.driver.execute_script("""
                    var e = arguments[0];
                    return {
                        tag: e.tagName, id: e.id, className: e.className,
                        role: e.getAttribute('role'),
                        ce: e.getAttribute('contenteditable'),
                        isCE: e.isContentEditable,
                        displayed: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
                    };
                """, el)
            except Exception:
                info = {}
            if info.get("displayed", True):
                candidates.append({"el": el, "reason": reason, "info": info})

        selectors_global = [
            ("textarea", "textarea"),
            ("input[type='text']", "input[text]"),
            ("[contenteditable='true']", "contenteditable"),
            ("[role='textbox']", "role=textbox"),
        ]
        for sel, reason in selectors_global:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    _add(el, f"global:{reason}")
            except Exception:
                pass

        for box_sel in [".comment_inbox_text", ".CommentWriter"]:
            try:
                boxes = self.driver.find_elements(By.CSS_SELECTOR, box_sel)
                for box in boxes:
                    _add(box, f"box:{box_sel}")
                    for sel, reason in selectors_global:
                        try:
                            for el in box.find_elements(By.CSS_SELECTOR, sel):
                                _add(el, f"inside:{box_sel}>{reason}")
                        except Exception:
                            pass
            except Exception:
                pass

        try:
            active = self.driver.execute_script("return document.activeElement;")
            _add(active, "activeElement")
        except Exception:
            pass

        return candidates

    def _try_input_on_element(self, el, text: str, _wc) -> bool:
        """
        후보 요소에 다양한 방법으로 text를 입력하고 검증.
        React 제어 컴포넌트 대응을 위해 native setter를 우선 시도.
        성공하면 True, 실패하면 False.
        """
        info = {}
        try:
            info = self.driver.execute_script("""
                var e = arguments[0];
                return {tag: e.tagName, id: e.id, ce: e.getAttribute('contenteditable'), isCE: e.isContentEditable};
            """, el)
        except Exception:
            pass
        tag = (info.get("tag") or "").upper()
        is_ce = info.get("isCE", False)

        # ── textarea/input: React 제어 컴포넌트 대응 ──
        if tag in ("TEXTAREA", "INPUT"):
            # 확실한 focus 확보
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'}); arguments[0].click(); arguments[0].focus();",
                    el)
                time.sleep(0.5)
            except Exception:
                pass

            # 1순위: send_keys (React가 실제 키보드 이벤트를 인식)
            try:
                ActionChains(self.driver).move_to_element(el).click().perform()
                time.sleep(0.3)
                # 기존 내용 선택 후 덮어쓰기 (clear() 사용 안 함 - React 상태 리셋 방지)
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
                time.sleep(0.1)
                ActionChains(self.driver).send_keys(text).perform()
                time.sleep(0.8)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ send_keys 성공 (len={self._get_element_length(el)})")
                    return True
                _wc(f"  send_keys: len=0")
            except Exception as e:
                _wc(f"  send_keys 실패: {e}")

            # 2순위: clipboard paste (Ctrl+V - 사람 동작)
            try:
                ActionChains(self.driver).move_to_element(el).click().perform()
                time.sleep(0.3)
                pyperclip.copy(text)
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
                time.sleep(0.1)
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                time.sleep(0.8)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ paste 성공 (len={self._get_element_length(el)})")
                    return True
                _wc(f"  paste: len=0")
            except Exception as e:
                _wc(f"  paste 실패: {e}")

            # 3순위: native setter (DOM만 바뀔 수 있음 - 마지막 수단)
            try:
                self.driver.execute_script("""
                    var e = arguments[0], text = arguments[1];
                    e.focus();
                    var proto = e.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    var nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    nativeSetter.call(e, text);
                    e.dispatchEvent(new Event('input', {bubbles: true}));
                    e.dispatchEvent(new Event('change', {bubbles: true}));
                """, el, text)
                time.sleep(0.5)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ native setter 성공 (len={self._get_element_length(el)}) ⚠ React 미반영 가능")
                    return True
                _wc(f"  native setter: len=0")
            except Exception as e:
                _wc(f"  native setter 실패: {e}")

            return False

        # ── contenteditable 요소 ──
        if is_ce:
            # 1순위: focus + send_keys
            try:
                el.click()
                time.sleep(0.3)
                el.send_keys(text)
                time.sleep(0.4)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ CE send_keys 성공 (len={self._get_element_length(el)})")
                    return True
            except Exception as e:
                _wc(f"  CE send_keys 실패: {e}")

            # 2순위: clipboard paste
            try:
                el.click()
                time.sleep(0.3)
                pyperclip.copy(text)
                ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                time.sleep(0.5)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ CE paste 성공 (len={self._get_element_length(el)})")
                    return True
            except Exception as e:
                _wc(f"  CE paste 실패: {e}")

            # 3순위: execCommand
            try:
                self.driver.execute_script("""
                    var e = arguments[0], text = arguments[1];
                    e.focus();
                    document.execCommand('selectAll', false, null);
                    document.execCommand('insertText', false, text);
                """, el, text)
                time.sleep(0.4)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ CE execCommand 성공 (len={self._get_element_length(el)})")
                    return True
            except Exception as e:
                _wc(f"  CE execCommand 실패: {e}")

            # 4순위: direct DOM injection + events
            try:
                self.driver.execute_script("""
                    var e = arguments[0], text = arguments[1];
                    e.focus();
                    e.innerText = text;
                    e.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
                    e.dispatchEvent(new Event('change', {bubbles: true}));
                """, el, text)
                time.sleep(0.4)
                if self._get_element_length(el) > 0:
                    _wc(f"  ✓ CE DOM inject 성공 (len={self._get_element_length(el)})")
                    return True
            except Exception as e:
                _wc(f"  CE DOM inject 실패: {e}")

            return False

        # ── 기타 요소 (div 등) ──
        try:
            el.click()
            time.sleep(0.3)
            el.send_keys(text)
            time.sleep(0.4)
            if self._get_element_length(el) > 0:
                _wc(f"  ✓ generic send_keys 성공 (len={self._get_element_length(el)})")
                return True
        except Exception:
            pass
        return False

    def _verify_comment_posted(self, comment_text: str, input_el=None) -> bool:
        """
        등록 성공 판정: textarea가 비워졌으면 서버가 수신한 것.
        DOM 텍스트 검색은 하지 않음 (기존 댓글과의 거짓 양성 방지).
        """
        if not input_el:
            return False
        # 네이버는 등록 성공 시 textarea를 자동 clear
        try:
            remaining = self._get_element_length(input_el)
            return remaining == 0
        except Exception:
            return False

    # 전체 write 시도 횟수 (동일 URL에 대해 처음부터 재시도)
    WRITE_MAX_ATTEMPTS = 2

    def write_comment(self, article_url: str, template: str, nickname: str = "", title: str = "") -> dict:
        """
        게시글에 댓글 작성 (editable sink 자동 탐색 + 입력 안정화 + 등록 후 확인)
        return: {"status": "success"|"fail", "message": "..."}
        """
        if not self.driver:
            return {"status": "fail", "message": "브라우저가 실행되지 않았습니다."}

        def _wc(msg: str) -> None:
            print(f"[commenter/write] {msg}", flush=True)

        last_fail_msg = ""
        for attempt in range(1, self.WRITE_MAX_ATTEMPTS + 1):
            result = self._write_comment_once(article_url, template, nickname, title, _wc, attempt)
            if result["status"] == "success":
                return result
            last_fail_msg = result["message"]
            _wc(f"시도 {attempt}/{self.WRITE_MAX_ATTEMPTS} 실패: {last_fail_msg}")
            if attempt < self.WRITE_MAX_ATTEMPTS:
                _wc("재시도 전 대기...")
                time.sleep(random.uniform(2.0, 3.0))

        return {"status": "fail", "message": last_fail_msg}

    def _write_comment_once(self, article_url: str, template: str, nickname: str, title: str, _wc, attempt: int) -> dict:
        """단일 시도 로직"""
        try:
            # ── 0. 팝업/새탭 방어: 원래 창으로 복귀 ──
            self._close_unexpected_windows()

            # ── 1. 게시글 이동 ──
            normalized_url = self._normalize_article_url(article_url)
            _wc(f"[시도{attempt}] GET {normalized_url[:100]}")
            self.driver.get(normalized_url)
            time.sleep(random.uniform(3.0, 5.0))

            # ── 2. Iframe 전환 ──
            if not self._switch_to_cafe_iframe():
                return {"status": "fail", "message": "Iframe 전환 실패 (삭제된 글?)"}

            # ── 3. 템플릿 치환 ──
            final_text = template.replace("{닉네임}", nickname).replace("{제목}", title)

            # ── 4. 댓글 영역 클릭 + 에디터 활성화 대기 ──
            self._activate_comment_editor(_wc)

            # ── 5. editable 후보 탐색 ──
            candidates = self._find_editable_candidates()
            _wc(f"editable 후보 {len(candidates)}개")
            for i, c in enumerate(candidates[:8]):
                _wc(f"  [{i}] {c['reason']} | {c['info'].get('tag','')} ce={c['info'].get('ce','')} cls={str(c['info'].get('className',''))[:40]}")

            if not candidates:
                return {"status": "fail", "message": "editable 후보 0개. 댓글창을 찾을 수 없습니다."}

            # ── 6. 후보별 입력 시도 ──
            success_el = None
            for i, c in enumerate(candidates):
                el = c["el"]
                _wc(f"후보[{i}] 입력 시도 ({c['reason']})")
                if self._try_input_on_element(el, final_text, _wc):
                    success_el = el
                    break
                try:
                    self.driver.execute_script(
                        "var e=arguments[0];"
                        "if(e.tagName==='TEXTAREA'||e.tagName==='INPUT') e.value='';"
                        "else e.textContent='';", el)
                except Exception:
                    pass

            if not success_el:
                _wc("모든 후보 실패 → activeElement 재탐색")
                try:
                    active = self.driver.execute_script("return document.activeElement;")
                    if active and self._try_input_on_element(active, final_text, _wc):
                        success_el = active
                except Exception:
                    pass

            if not success_el:
                return {"status": "fail", "message": f"입력 실패. 후보 {len(candidates)}개 모두 불가."}

            # ── 7. 입력 안정화 확인 (비동기 에디터 대응) ──
            # 입력 직후가 아닌, 1초 뒤에도 유지되는지 재확인
            time.sleep(1.0)
            stable_len = self._get_element_length(success_el)
            _wc(f"입력 안정화 확인 (1초 후): len={stable_len}")
            if stable_len == 0:
                _wc("⚠ 에디터가 입력을 무효화함 (비동기 clear)")
                return {"status": "fail", "message": "입력 후 에디터가 내용을 지움 (비동기 무효화)"}

            # ── 8. 등록 버튼 찾기 ──
            btn_el = self._find_register_button(_wc)
            if not btn_el:
                return {"status": "fail", "message": "등록 버튼을 못 찾았습니다."}

            # ── 9. 등록 직전 최종 길이 확인 ──
            pre_click_len = self._get_element_length(success_el)
            if pre_click_len == 0:
                return {"status": "fail", "message": "등록 직전 입력이 사라짐"}

            # ── 9.5 등록 전 textarea에 포커스 재확인 (네이버 등록 조건) ──
            try:
                self.driver.execute_script("arguments[0].focus();", success_el)
                time.sleep(0.2)
            except Exception:
                pass

            btn_el.click()
            _wc("등록 클릭 완료, DOM 반영 대기...")
            time.sleep(random.uniform(3.0, 5.0))

            # ── 10. 등록 후 검증 ──
            if self._verify_comment_posted(final_text, input_el=success_el):
                _wc("✓ 댓글 등록 확인 → success")
                return {"status": "success", "message": "작성 완료"}
            else:
                return {"status": "fail", "message": "등록 클릭했으나 댓글 미반영"}

        except Exception as e:
            _wc(f"예외: {e}")
            return {"status": "fail", "message": f"에러: {str(e)}"}

    def _close_unexpected_windows(self) -> None:
        """광고 팝업/N플레이스 등 예상치 못한 새 탭을 닫고 첫 번째 탭으로 복귀"""
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                main_handle = handles[0]
                for h in handles[1:]:
                    try:
                        self.driver.switch_to.window(h)
                        self.driver.close()
                    except Exception:
                        pass
                self.driver.switch_to.window(main_handle)
            else:
                self.driver.switch_to.window(handles[0])
        except Exception:
            pass

    def _activate_comment_editor(self, _wc) -> None:
        """
        댓글 textarea를 찾아 클릭하고, activeElement가 textarea가 될 때까지
        반복 시도. 네이버는 textarea에 focus가 잡혀야 등록이 동작함.
        """
        textarea_el = None
        for sel in ["textarea.comment_inbox_text", ".comment_inbox_text", "textarea[placeholder*='댓글']"]:
            try:
                textarea_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if textarea_el:
                    break
            except Exception:
                continue

        if not textarea_el:
            _wc("댓글 textarea 못 찾음")
            return

        # 최대 5회 클릭 시도하면서 activeElement가 textarea가 되는지 확인
        for i in range(5):
            try:
                # 스크롤 + 클릭
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
                    textarea_el
                )
                time.sleep(0.6)

                # activeElement 확인
                is_focused = self.driver.execute_script(
                    "return document.activeElement === arguments[0];", textarea_el
                )
                if is_focused:
                    _wc(f"댓글 textarea 포커스 확인 (시도 {i+1})")
                    return
            except Exception:
                pass

            # ActionChains로 재시도
            try:
                ActionChains(self.driver).move_to_element(textarea_el).click().perform()
                time.sleep(0.5)
                is_focused = self.driver.execute_script(
                    "return document.activeElement === arguments[0];", textarea_el
                )
                if is_focused:
                    _wc(f"댓글 textarea 포커스 확인 (ActionChains, 시도 {i+1})")
                    return
            except Exception:
                pass

        # 마지막 수단: JS로 강제 focus
        try:
            self.driver.execute_script("arguments[0].focus();", textarea_el)
            time.sleep(0.3)
            _wc("댓글 textarea JS focus() 강제 적용")
        except Exception:
            _wc("⚠ textarea 포커스 실패 (모든 방법)")

    def _find_register_button(self, _wc):
        """등록 버튼 탐색"""
        btn_selectors = [
            ".btn_register",
            ".btn_register.c_orange",
            ".CommentWriter .btn_submit",
            "a.btn_register",
            "button[class*='register']",
            "button[class*='submit']",
        ]
        for sel in btn_selectors:
            try:
                btn_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn_el:
                    try:
                        disp = btn_el.is_displayed()
                        enab = btn_el.is_enabled()
                    except Exception:
                        disp, enab = True, True
                    _wc(f"등록 버튼: {sel} displayed={disp} enabled={enab}")
                    return btn_el
            except Exception:
                continue
        return None

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
