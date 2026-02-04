"""
네이버 카페 크롤러 - Project DAYBREAK (최종 복구 및 ID 추출 강화 버전)
"""
import os
import time
import random
import re
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from collections import deque
from urllib.parse import urlparse, parse_qs
import json
import requests
from bs4 import BeautifulSoup, FeatureNotFound
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class NaverCafeCrawler:
    def __init__(self, chrome_profile_path: str = "", output_dir: str = "outputs", debug_mode: bool = False):
        self.chrome_profile_path = chrome_profile_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.driver: Optional[uc.Chrome] = None
        self.status_callback = None
        self.admin_nickname = "멀린"
        self.debug_mode = debug_mode

    def set_status_callback(self, callback):
        self.status_callback = callback
    
    def _update_status(self, message: str):
        if self.status_callback:
            self.status_callback(message)
        else:
            print(f"[INFO] {message}")

    def _extract_id_from_element(self, element) -> str:
        """요소에서 Naver ID (member_id)를 추출하는 통합 엔진"""
        try:
            # 1. onclick 속성 분석 (가장 정확)
            onclick = element.get_attribute("onclick") or ""
            patterns = [
                r"ui\(.*?'(.*?)'", 
                r"memberid['\s]*[:=]['\s]*([^'\"]+)",
                r"showMemberLayer\([^,]+,\s*'([^']+)'",
                r"openMemberInfo\(['\"]([^'\"]+)['\"]",
                r"memberId['\s]*[:=]['\s]*([^'\"]+)"
            ]
            for pattern in patterns:
                match = re.search(pattern, onclick)
                if match: return match.group(1)
            
            # 2. href 속성 분석 (백업)
            href = element.get_attribute("href") or ""
            # blogId=... 형태가 제일 "정직"한 ID
            try:
                parsed = urlparse(href)
                q = parse_qs(parsed.query)
                if "blogId" in q and q["blogId"] and q["blogId"][0]:
                    return q["blogId"][0]
            except:
                pass
            href_patterns = [
                r"memberid=([^&]+)",
                r"/members/([^/?#]+)",
                r"memberId=([^&]+)",
                r"cafe.naver.com/ca-fe/cafes/\d+/members/([^/?#]+)"
            ]
            for pattern in href_patterns:
                match = re.search(pattern, href, re.I)
                if match: return match.group(1)
                
            # 3. data 속성 확인
            for attr in ["data-member-id", "data-userid", "data-id"]:
                val = element.get_attribute(attr)
                if val: return val
        except: pass
        return "unknown"

    def _clean_text(self, s: str) -> str:
        if not s:
            return ""
        return re.sub(r"\s+", " ", str(s)).strip()

    def _normalize_nickname(self, nick: str) -> str:
        """
        닉네임 텍스트에서 UI 군더더기 제거.
        예) "봄의향기를 님의 게시글 더보기" -> "봄의향기를"
        """
        n = self._clean_text(nick or "")
        if not n:
            return ""

        # "X 님의 ..." 형태 제거
        m = re.match(r"^(.+?)\s*님의\s+.+$", n)
        if m:
            return self._clean_text(m.group(1))

        # "X 님 게시글/댓글 ..." 형태(드물게) 제거
        if any(token in n for token in ["더보기", "게시글", "댓글", "프로필", "보기"]):
            m2 = re.match(r"^(.+?)\s*님\s+.+$", n)
            if m2:
                return self._clean_text(m2.group(1))

        return n

    def _normalize_board_name(self, name: str) -> str:
        # 공백 제거 + 소문자 (예: "먹거리 / 맛집" == "먹거리/맛집")
        return re.sub(r"\s+", "", (name or "")).strip().lower()

    def _extract_text_from_element(self, element) -> str:
        """Selenium 요소에서 표시 텍스트를 최대한 복구(React/SPA 대비)."""
        if not element:
            return ""
        try:
            t = self._clean_text(element.text or "")
            if t:
                return self._normalize_nickname(t)
        except:
            pass

        for attr in ["textContent", "innerText", "title", "aria-label", "data-nickname", "data-name"]:
            try:
                v = element.get_attribute(attr)
                v = self._clean_text(v or "")
                if v:
                    return self._normalize_nickname(v)
            except:
                continue
        return ""

    def _deep_find_first_string(self, obj: Any, key_hints: List[str], max_depth: int = 5) -> str:
        """
        dict/list 중첩에서 key_hints(부분 문자열 포함)로 첫 문자열 값을 찾는다.
        - key_hints: ["nick", "name"] 처럼 힌트
        """
        try:
            key_hints_l = [k.lower() for k in key_hints]
            seen = set()
            q = [(obj, 0)]
            while q:
                cur, depth = q.pop(0)
                if id(cur) in seen:
                    continue
                seen.add(id(cur))
                if depth > max_depth:
                    continue
                if isinstance(cur, dict):
                    for k, v in cur.items():
                        kl = str(k).lower()
                        if any(h in kl for h in key_hints_l):
                            if isinstance(v, str) and self._clean_text(v):
                                return self._clean_text(v)
                        if isinstance(v, (dict, list)):
                            q.append((v, depth + 1))
                elif isinstance(cur, list):
                    for v in cur:
                        if isinstance(v, (dict, list)):
                            q.append((v, depth + 1))
        except:
            pass
        return ""

    def _strip_healing_diary_preamble(self, content: str) -> str:
        """
        '치유일기'류 게시글에 포함되는 고정 안내문을 본문에서 제거.
        - 성능 부담 거의 없음(문자열 탐색/슬라이싱만 수행)
        - 오탐 방지: 본문 앞부분에서 특정 키워드/문구가 여러 개 동시에 감지될 때만 동작
        """
        text = content or ""
        if not text.strip():
            return content

        head = text[:1200]  # 앞부분에서만 판별/절단
        # (2026-02) 썬드림 치유일기 고정 안내문 패턴
        must = ["조사기간/기본조사", "조사방법"]
        hints = [
            "집중조사",
            "조사거리",
            "시간",
            "부위",
            "육해채식",
            "올유",
            "멸치",
            "온습도",
            "피부질환의 경우",
            "노샤노보",
            "냉포마찰",
            "애로사항",
        ]

        if not all(m in head for m in must):
            return content

        hint_hits = sum(1 for h in hints if h in head)
        if hint_hits < 2:
            return content

        # 구분선(----) 기준으로 안전하게 자르기
        m = re.search(r"\n\s*-{5,}\s*\n", head)
        if m:
            return (text[m.end():]).lstrip()

        # 구분선이 없으면, 첫 몇 줄에서 안내문 라인들을 제거(보수적으로)
        lines = text.splitlines()
        drop_phrases = [
            "조사기간/기본조사",
            "집중조사",
            "조사거리",
            "조사방법",
            "육해채식",
            "올유",
            "멸치",
            "온습도",
            "피부질환의 경우",
            "노샤노보",
            "냉포마찰",
        ]
        new_lines = []
        dropped = 0
        for i, line in enumerate(lines):
            if i < 12 and any(p in line for p in drop_phrases):
                dropped += 1
                continue
            new_lines.append(line)

        if dropped >= 2:
            return "\n".join(new_lines).lstrip()
        return content

    def _get_user_agent(self) -> str:
        try:
            if self.driver:
                ua = self.driver.execute_script("return navigator.userAgent;")
                if isinstance(ua, str) and ua.strip():
                    return ua.strip()
        except:
            pass
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def _build_requests_session_from_driver(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": self._get_user_agent(),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        if not self.driver:
            return s

        try:
            for c in self.driver.get_cookies():
                try:
                    s.cookies.set(
                        c.get("name"),
                        c.get("value"),
                        domain=c.get("domain"),
                        path=c.get("path", "/"),
                    )
                except:
                    continue
        except:
            pass
        return s

    def _parse_club_article_ids(self, article_url: str) -> tuple[Optional[str], Optional[str]]:
        try:
            normalized = self._normalize_article_url(article_url or "")
            if "ArticleRead.nhn" in normalized:
                parsed = urlparse(normalized)
                q = parse_qs(parsed.query)
                club_id = q.get("clubid", [None])[0]
                article_id = q.get("articleid", [None])[0]
                if club_id and article_id:
                    return str(club_id), str(article_id)

            m = re.search(r"/cafes/(\d+)/articles/(\d+)", normalized)
            if m:
                return m.group(1), m.group(2)
        except:
            pass
        return None, None

    def _get_member_id_via_api(self, club_id: Optional[str], article_id: Optional[str]) -> str:
        """전략 2: apis.naver.com 모바일 API로 작성자 ID 추출 (상세 수집용)"""
        if not club_id or not article_id:
            return "unknown"
        try:
            info = self._get_writer_info_via_article_api(club_id, article_id)
            mid = info.get("member_id", "unknown")
            return mid if mid else "unknown"
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] API member_id 추출 실패: {e}")
        return "unknown"

    def _get_writer_info_via_article_api(self, club_id: Optional[str], article_id: Optional[str]) -> Dict[str, str]:
        """
        게시글 작성자 원본 정보(API 기반).
        - member_id: 네이버가 쓰는 긴 고유키(MemberKey 계열 포함)
        - nickname: 표시 닉네임
        """
        out = {"member_id": "unknown", "nickname": "unknown"}
        if not club_id or not article_id:
            return out
        try:
            s = self._build_requests_session_from_driver()
            url = f"https://apis.naver.com/cafe-web/cafe-article/v1/articles/{article_id}?useCafeId=false&buid={club_id}"
            headers = {
                "Referer": f"https://m.cafe.naver.com/ca-fe/web/cafes/{club_id}/articles/{article_id}",
                "Origin": "https://m.cafe.naver.com",
            }
            r = s.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                return out

            data = r.json()
            writer = (
                data.get("result", {})
                .get("article", {})
                .get("writer", {})
            )
            if not isinstance(writer, dict):
                return out

            # ID/Key 후보군(서비스 개편으로 필드명이 바뀌는 케이스 방어)
            for k in ["id", "memberId", "memberKey", "writerId", "userId", "blogId"]:
                v = writer.get(k)
                if isinstance(v, str) and v.strip():
                    out["member_id"] = v.strip()
                    break

            for k in ["nickname", "nickName", "writerNick", "writerName", "displayName", "name"]:
                v = writer.get(k)
                if isinstance(v, str) and v.strip():
                    out["nickname"] = v.strip()
                    break

            # 중첩 구조까지 탐색 (최근 구조 변경 대응)
            if out["nickname"] == "unknown":
                found = self._deep_find_first_string(writer, ["nick", "nickname", "display", "name"])
                if found:
                    out["nickname"] = found
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] API writer 정보 추출 실패: {e}")
        return out

    def _get_comments_via_commentview(self, club_id: Optional[str], article_id: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """
        댓글 JSON 우회 추출.
        - 구형이지만 여전히 많이 살아있는 엔드포인트: CommentView.nhn
        - 반환 형태: [{"writer_id":..., "nickname":..., "content":...}, ...]
        """
        if not club_id or not article_id:
            return None
        try:
            s = self._build_requests_session_from_driver()
            url = f"https://cafe.naver.com/CommentView.nhn?search.clubid={club_id}&search.articleid={article_id}"
            headers = {
                "Referer": f"https://cafe.naver.com/ArticleRead.nhn?clubid={club_id}&articleid={article_id}",
            }
            r = s.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                return None

            # JSON / JSONP 모두 방어
            data = None
            try:
                data = r.json()
            except:
                txt = (r.text or "").strip()
                # 예: callback({...})
                m = re.search(r"\((\{.*\})\)\s*;?\s*$", txt, re.S)
                if m:
                    data = json.loads(m.group(1))
                else:
                    # 그냥 JSON 본문일 수 있음
                    data = json.loads(txt)

            result = data.get("result") if isinstance(data, dict) else None
            items = None
            if isinstance(result, dict):
                items = result.get("list") or result.get("commentList") or result.get("comments")
            if not isinstance(items, list):
                return None

            out: List[Dict[str, Any]] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                # writer id 키 변형 방어
                writer_id = (
                    it.get("writerId")
                    or it.get("writer_id")
                    or it.get("writerid")
                    or it.get("memberKey")
                    or it.get("writerMemberKey")
                    or it.get("userKey")
                    or it.get("memberId")
                    or it.get("member_id")
                    or it.get("userId")
                    or it.get("userid")
                    or "unknown"
                )
                nickname = (
                    it.get("writerNick")
                    or it.get("writer_nick")
                    or it.get("nickName")
                    or it.get("nickname")
                    or it.get("writerName")
                    or it.get("name")
                    or "unknown"
                )
                if nickname == "unknown":
                    found = self._deep_find_first_string(it, ["nick", "nickname", "writerNick", "name"])
                    if found:
                        nickname = found
                content = (
                    it.get("content")
                    or it.get("commentContent")
                    or it.get("comment")
                    or it.get("text")
                    or ""
                )
                # html이 섞여 들어오는 경우 방어: 태그 제거(대충)
                if isinstance(content, str) and "<" in content and ">" in content:
                    content = re.sub(r"<[^>]+>", " ", content)
                    content = re.sub(r"\s+", " ", content).strip()

                out.append(
                    {
                        "writer_id": str(writer_id) if writer_id is not None else "unknown",
                        "nickname": str(nickname) if nickname is not None else "unknown",
                        "content": str(content) if content is not None else "",
                    }
                )

            return out
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] CommentView 댓글 추출 실패: {e}")
            return None

    def _get_member_id_via_js_state(self) -> str:
        """전략 3: SPA 전역 상태/Next.js 데이터에서 writer id 추출"""
        if not self.driver:
            return "unknown"
        try:
            js = r"""
                try {
                    // legacy
                    if (window.g_sUserId && typeof window.g_sUserId === "string") return window.g_sUserId;

                    // common SPA states
                    const candidates = [];
                    if (window.__INITIAL_STATE__) candidates.push(window.__INITIAL_STATE__);
                    if (window.__NEXT_DATA__) candidates.push(window.__NEXT_DATA__);
                    if (window.__APOLLO_STATE__) candidates.push(window.__APOLLO_STATE__);

                    function dig(obj, depth) {
                        if (!obj || depth > 6) return null;
                        if (typeof obj === "string") return null;
                        if (obj.writer && obj.writer.id && typeof obj.writer.id === "string") return obj.writer.id;
                        if (obj.article && obj.article.writer && obj.article.writer.id && typeof obj.article.writer.id === "string") return obj.article.writer.id;
                        if (obj.result && obj.result.article && obj.result.article.writer && obj.result.article.writer.id && typeof obj.result.article.writer.id === "string") return obj.result.article.writer.id;
                        // shallow scan
                        for (const k in obj) {
                            if (!Object.prototype.hasOwnProperty.call(obj, k)) continue;
                            const v = obj[k];
                            if (v && typeof v === "object") {
                                const found = dig(v, depth + 1);
                                if (found) return found;
                            }
                        }
                        return null;
                    }

                    for (const root of candidates) {
                        const found = dig(root, 0);
                        if (found) return found;
                    }
                    return null;
                } catch (e) { return null; }
            """
            mid = self.driver.execute_script(js)
            if isinstance(mid, str) and mid.strip():
                return mid.strip()
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] JS state member_id 추출 실패: {e}")
        return "unknown"

    def _get_member_id_via_layer(self, nickname_element) -> str:
        """전략 1: 닉네임 클릭 → 작성자 레이어에서 blogId 파싱 (리스트/댓글에서 특히 유용)"""
        if not self.driver or not nickname_element:
            return "unknown"

        before_handles = []
        try:
            before_handles = list(self.driver.window_handles)
        except:
            before_handles = []

        try:
            # 클릭 안정화: 스크롤 + ActionChains + JS click 백업
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", nickname_element)
            except:
                pass

            clicked = False
            try:
                ActionChains(self.driver).move_to_element(nickname_element).pause(0.05).click(nickname_element).perform()
                clicked = True
            except:
                pass
            if not clicked:
                try:
                    nickname_element.click()
                    clicked = True
                except:
                    pass
            if not clicked:
                try:
                    self.driver.execute_script("arguments[0].click();", nickname_element)
                    clicked = True
                except:
                    pass

            if not clicked:
                return "unknown"

            # 새 창이 뜨는 케이스 방어 (간혹 블로그로 바로 열림)
            try:
                time.sleep(0.15)
                after_handles = list(self.driver.window_handles)
                new_handles = [h for h in after_handles if h not in before_handles]
                if new_handles:
                    # 새 창은 닫고 원래 창으로 복귀
                    for h in new_handles:
                        try:
                            self.driver.switch_to.window(h)
                            self.driver.close()
                        except:
                            pass
                    if before_handles:
                        self.driver.switch_to.window(before_handles[0])
            except:
                pass

            wait = WebDriverWait(self.driver, 3)

            # 레이어 후보 셀렉터들을 순차 대기/탐색
            layer = None
            layer_selectors = [
                "div.per_layer ul.layer_list",
                "div.per_layer",
                "ul.layer_list",
                "div[class*='per_layer']",
                "div[class*='layer'] ul",
            ]

            for sel in layer_selectors:
                try:
                    layer = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, sel)))
                    if layer:
                        break
                except:
                    continue

            if not layer:
                return "unknown"

            # blogId가 담긴 링크 우선
            link_hrefs: List[str] = []
            try:
                for a in layer.find_elements(By.CSS_SELECTOR, "a"):
                    href = a.get_attribute("href") or ""
                    if href:
                        link_hrefs.append(href)
            except:
                pass

            # 1) blogId= 우선 파싱
            for href in link_hrefs:
                try:
                    parsed = urlparse(href)
                    q = parse_qs(parsed.query)
                    if "blogId" in q and q["blogId"] and q["blogId"][0]:
                        return q["blogId"][0]
                except:
                    continue

            # 2) 회원/작성자 링크에서 memberId/memberid 추출 백업
            for href in link_hrefs:
                try:
                    m = re.search(r"(?:memberid|memberId)=([^&]+)", href, re.I)
                    if m:
                        return m.group(1)
                except:
                    continue

        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] 레이어 click 추출 실패: {e}")
        finally:
            # 레이어 닫기 (ESC) - 다음 동작 방해 방지
            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ESCAPE)
            except:
                pass
        return "unknown"

    def _extract_member_id_from_nick(self, nick_el, prefer_layer: bool = False) -> str:
        """닉네임 요소에서 member_id를 하이브리드로 추출"""
        mid = "unknown"
        try:
            if nick_el:
                mid = self._extract_id_from_element(nick_el)
        except:
            mid = "unknown"
        if mid != "unknown":
            return mid

        if prefer_layer:
            mid = self._get_member_id_via_layer(nick_el)
            if mid != "unknown":
                return mid

        # 마지막 백업: JS 상태값 (상세 페이지에서 더 유효)
        mid = self._get_member_id_via_js_state()
        return mid if mid else "unknown"

    def start_browser(self) -> None:
        if self.driver:
            self._update_status("브라우저가 이미 실행 중입니다.")
            return
        
        try:
            self._update_status("🚀 undetected-chromedriver로 크롬 브라우저 시작 중...")
            
            # undetected_chromedriver 옵션 설정
            options = uc.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # undetected_chromedriver 인스턴스 생성 (자동화 탐지 우회)
            # version_main=144로 현재 Chrome 버전 명시
            # use_subprocess=True: 멀티프로세싱 에러 방지
            self.driver = uc.Chrome(options=options, version_main=144, use_subprocess=True)
            self.driver.set_page_load_timeout(30)
            
            self.driver.get("https://cafe.naver.com")
            self._update_status("✅ 브라우저 시작 완료. (탐지 우회 모드 활성화)")
            self._update_status("💡 브라우저에서 로그인을 확인한 후 2단계를 진행하세요.")
            
        except Exception as e:
            self._update_status(f"❌ 브라우저 시작 실패: {e}")
            raise

    def _switch_to_cafe_iframe(self) -> bool:
        try:
            self.driver.switch_to.default_content()
            current_url = self.driver.current_url
            
            # SPA 형식은 iframe 없음 (이미 URL 정규화했으므로 여기는 안 올 것)
            if "/ca-fe/" in current_url or "/f-e/" in current_url:
                if self.debug_mode:
                    self._update_status(f"[디버그] ⚠️ SPA URL 감지, iframe 스킵: {current_url[:50]}...")
                return True
            
            # 표준 PC 버전: cafe_main iframe 전환
            try:
                wait = WebDriverWait(self.driver, 5)
                iframe = wait.until(EC.presence_of_element_located((By.ID, "cafe_main")))
                self.driver.switch_to.frame(iframe)
                if self.debug_mode:
                    self._update_status(f"[디버그] ✅ iframe 전환 성공 (cafe_main)")
                return True
            except:
                if self.debug_mode:
                    self._update_status(f"[디버그] ⚠️ iframe 없음 (이미 본문 프레임?)")
                return True
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] ❌ iframe 전환 실패: {e}")
            return False

    def _random_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        time.sleep(random.uniform(min_sec, max_sec))

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str: return None
        date_str = date_str.strip()
        try:
            if "전" in date_str: return datetime.now()
            if ":" in date_str and "." not in date_str:
                return datetime.now().replace(hour=int(date_str.split(":")[0]), minute=int(date_str.split(":")[1]))
            
            clean_date = re.sub(r'[^0-9.]', '', date_str).strip('.')
            parts = clean_date.split('.')
            if len(parts) == 3:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
            return None
        except:
            return None

    def scrape_board_list(
        self,
        board_url: str,
        start_date: datetime,
        end_date: datetime,
        exclude_boards: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """게시판 리스트에서 날짜 범위 내 게시글 링크 추출 (undetected 버전)"""
        if not board_url:
            self._update_status("❌ 게시판 URL이 비어 있습니다.")
            return []

        exclude_norm = set()
        if exclude_boards:
            exclude_norm = {self._normalize_board_name(x) for x in exclude_boards if str(x).strip()}
            
        all_articles = []
        page = 1
        should_continue = True
        
        while should_continue and page <= 50:
            sep = "&" if "?" in str(board_url) else "?"
            target_page_url = f"{board_url}{sep}page={page}"
            
            self._update_status(f"🚀 {page}페이지 분석 시작 (누적: {len(all_articles)}개)")
            
            try:
                # 페이지 이동 (undetected는 알아서 부드럽게 처리)
                if self.driver.current_url != target_page_url:
                    self.driver.get(target_page_url)
                    time.sleep(3)  # 로딩 대기
                
                self._switch_to_cafe_iframe()
                
                # 스크롤하여 동적 콘텐츠 로딩
                self.driver.execute_script("window.scrollTo(0, 1000);")
                time.sleep(1.5)
                
                # 게시글 행 찾기 (최신 SPA 구조 우선)
                rows = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='ArticleItem'], li[class*='article'], div.article-board table tbody tr")
                
                if not rows:
                    self._update_status(f"⚠️ {page}페이지에서 게시글을 찾지 못했습니다.")
                    break
                    
                page_found_count = 0
                for idx, row in enumerate(rows):
                    try:
                        # 공지 스킵
                        row_class = (row.get_attribute("class") or "").lower()
                        if "notice" in row_class or "top" in row_class: continue
                        
                        # 날짜 추출
                        date_val = None
                        date_selectors = ["span[class*='Date']", "span.date", "td.td_date", ".date"]
                        for ds in date_selectors:
                            try:
                                el = row.find_element(By.CSS_SELECTOR, ds)
                                date_val = self._parse_date(el.text.strip())
                                if date_val: break
                            except: continue
                        
                        if not date_val:
                            date_match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2}|\d{1,2}\.\d{1,2}|\d{1,2}:\d{2})', row.text)
                            if date_match: date_val = self._parse_date(date_match.group(1))
                        
                        if not date_val: continue
                        if date_val > end_date: continue
                        if date_val < start_date:
                            self._update_status(f"⏱️ 시작일 이전 도달. 종료합니다.")
                            should_continue = False
                            break
                        
                        # 링크/제목
                        link_el = None
                        for ls in ["a[class*='ArticleLink']", "a.article", "a[href*='articleid']"]:
                            try:
                                link_el = row.find_element(By.CSS_SELECTOR, ls)
                                if link_el: break
                            except: continue
                            
                        if not link_el: continue
                        href = link_el.get_attribute("href")
                        title = link_el.text.strip()
                        
                        match = re.search(r'articleid=(\d+)', href) or re.search(r'/articles/(\d+)', href)
                        if not match: continue

                        # 게시판 이름 추출 (전체글보기에서 컬럼으로 존재)
                        board_name = ""
                        board_selectors = [
                            "a.board_name",
                            "a[class*='board_name']",
                            "td.td_board a",
                            "a[href*='/menus/']",
                        ]
                        for bs in board_selectors:
                            try:
                                b_el = row.find_element(By.CSS_SELECTOR, bs)
                                board_name = self._extract_text_from_element(b_el)
                                if board_name:
                                    break
                            except:
                                continue

                        # 제외 게시판 필터
                        if board_name and exclude_norm:
                            bn = self._normalize_board_name(board_name)
                            if bn in exclude_norm:
                                continue
                        
                        # 작성자 정보 추출 (통합 ID 추출 엔진 적용)
                        member_id = "unknown"
                        nickname = "unknown"
                        nick_selectors = [
                            "a[class*='Nickname']",
                            "span[class*='Nickname']",
                            ".nick a",
                            ".nick span",
                            "td.td_name a",
                            "a[class*='Writer']",
                            "span[class*='Writer']",
                            ".writer_nick a",
                            ".writer a",
                        ]
                        
                        for nick_sel in nick_selectors:
                            try:
                                nick_el = row.find_element(By.CSS_SELECTOR, nick_sel)
                                nickname = self._extract_text_from_element(nick_el) or "unknown"
                                # 리스트에서는 레이어 클릭이 가장 확실 (정규식 실패 시에만)
                                member_id = self._extract_member_id_from_nick(nick_el, prefer_layer=True)
                                if member_id != "unknown":
                                    break
                            except: continue
                        
                        all_articles.append({
                            "post_id": match.group(1),
                            "member_id": member_id,
                            "url": href,
                            "title": title,
                            "date": date_val.strftime("%Y-%m-%d"),
                            "nickname": nickname,
                            "board_name": board_name,
                        })
                        page_found_count += 1
                        
                    except: continue
                
                self._update_status(f"✅ {page}페이지 완료: {page_found_count}개 수집 (총 {len(all_articles)}개 누적)")
                
                if not should_continue: break
                page += 1
                time.sleep(random.uniform(3, 6))
                
            except Exception as e:
                self._update_status(f"❌ {page}페이지 처리 중 오류: {e}")
                break
            
        return all_articles

    def _normalize_article_url(self, article_url: str) -> str:
        if 'ArticleRead.nhn' in article_url or '/ArticleRead.nhn' in article_url:
            return article_url
        match = re.search(r'/cafes/(\d+)/articles/(\d+)', article_url)
        if match:
            return f"https://cafe.naver.com/ArticleRead.nhn?clubid={match.group(1)}&articleid={match.group(2)}"
        return article_url
    
    def scrape_article_detail(self, article_url: str, post_author_id: str, admin_nicks: List[str]) -> Dict[str, Any]:
        """본문 텍스트 추출 및 관계 중심 댓글 필터링"""
        try:
            article_url = self._normalize_article_url(article_url)
            self.driver.get(article_url)
            time.sleep(3)
            self._switch_to_cafe_iframe()

            # 상세에서는 API가 가장 빠르고 정확 (가능하면 여기서 writer id 확보)
            club_id, article_id = self._parse_club_article_ids(article_url)
            writer_info = self._get_writer_info_via_article_api(club_id, article_id)
            api_author_id = writer_info.get("member_id", "unknown")
            api_author_nick = writer_info.get("nickname", "unknown")
            if api_author_id and api_author_id != "unknown":
                post_author_id = api_author_id

            # 게시판 이름 (상세에서 복구)
            board_name = ""
            try:
                board_name_selectors = [
                    "a.board_name",
                    "a[href*='menuid=']",
                    "a[href*='/menus/']",
                    ".article_header a",
                    ".ArticleTopInfo__boardName a",
                ]
                for sel in board_name_selectors:
                    try:
                        el = self.driver.find_element(By.CSS_SELECTOR, sel)
                        t = self._extract_text_from_element(el)
                        if t and len(t) <= 40 and "http" not in t.lower():
                            board_name = t
                            break
                    except:
                        continue
            except:
                pass

            # 게시글 닉네임은 API에서 비어있는 경우가 있어서, DOM에서 한번 더 복구
            if api_author_nick == "unknown":
                try:
                    author_nick_selectors = [
                        ".ArticleWriter a",
                        ".ArticleWriter .nick",
                        ".article_writer a",
                        ".article_writer .nick",
                        ".writer a",
                        "a[class*='nickname']",
                        "span[class*='nickname']",
                        "a[class*='Nick']",
                        "span[class*='Nick']",
                    ]
                    for sel in author_nick_selectors:
                        try:
                            el = self.driver.find_element(By.CSS_SELECTOR, sel)
                            nick = self._extract_text_from_element(el)
                            if nick:
                                api_author_nick = nick
                                break
                        except:
                            continue
                except:
                    pass
            
            # 본문 추출
            content = ""
            content_selectors = [".se-main-container", "div[class*='ArticleContentBox']", "#articleBody", "div.article_viewer"]
            for content_sel in content_selectors:
                try:
                    content_area = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, content_sel)))
                    content = content_area.text.strip()
                    if content and len(content) > 10: break
                except: continue

            # 치유일기 고정 안내문 제거(해당 패턴일 때만)
            content = self._strip_healing_diary_preamble(content)
            
            # 작성자 ID 재추출 (리스트에서 실패한 경우)
            if post_author_id == "unknown":
                try:
                    author_selectors = [".ArticleWriter a", ".article_writer a", ".writer a", "a[class*='nickname']", "a[class*='Writer']"]
                    for author_sel in author_selectors:
                        try:
                            author_el = self.driver.find_element(By.CSS_SELECTOR, author_sel)
                            post_author_id = self._extract_member_id_from_nick(author_el, prefer_layer=True)
                            if post_author_id != "unknown": break
                        except: continue
                except: pass

            if post_author_id == "unknown":
                post_author_id = self._get_member_id_via_js_state()
            
            # 댓글 필터링
            filtered_comments = []
            try:
                # 1) 댓글 JSON 우회(가장 안정) 시도
                api_comments = self._get_comments_via_commentview(club_id, article_id)
                if api_comments:
                    for c in api_comments:
                        writer_id = c.get("writer_id", "unknown")
                        nick = c.get("nickname", "unknown")
                        is_author = (writer_id == post_author_id and post_author_id != "unknown")
                        is_admin = any(admin_nick.strip() in (nick or "") for admin_nick in admin_nicks)
                        if is_author or is_admin:
                            filtered_comments.append(
                                {
                                    "writer_id": writer_id,
                                    "nickname": nick,
                                    "content": c.get("content", ""),
                                    "is_target": 1,
                                }
                            )
                    return {"content": content, "comments": filtered_comments, "member_id": post_author_id, "nickname": api_author_nick, "board_name": board_name}

                # 2) 실패 시 Selenium DOM 방식으로 폴백
                comment_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.CommentItem, .comment_list li, div[class*='Comment']")
                layer_attempts = 0
                for item in comment_elements:
                    try:
                        nick_el = item.find_element(By.CSS_SELECTOR, ".comment_nickname a, .nick a, a[class*='nickname']")
                        nick = self._extract_text_from_element(nick_el) or "unknown"
                        writer_id = self._extract_id_from_element(nick_el)
                        
                        is_author = (writer_id == post_author_id and post_author_id != "unknown")
                        is_admin = any(admin_nick.strip() in nick for admin_nick in admin_nicks)

                        # 운영자 댓글인데 ID가 unknown이면, 레이어 클릭으로 보강 (너무 느려지지 않게 제한)
                        if writer_id == "unknown" and is_admin and layer_attempts < 5:
                            writer_id = self._get_member_id_via_layer(nick_el)
                            layer_attempts += 1
                            is_author = (writer_id == post_author_id and post_author_id != "unknown")
                        
                        if is_author or is_admin:
                            text_el = item.find_element(By.CSS_SELECTOR, ".comment_text_view, .txt, div[class*='comment_text']")
                            filtered_comments.append({
                                "writer_id": writer_id,
                                "nickname": nick,
                                "content": text_el.text.strip(),
                                "is_target": 1
                            })
                    except: continue
            except: pass
                
            return {"content": content, "comments": filtered_comments, "member_id": post_author_id, "nickname": api_author_nick, "board_name": board_name}
        except Exception as e:
            return {"content": "", "comments": [], "member_id": post_author_id if post_author_id else "unknown", "nickname": "unknown", "board_name": ""}

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


class VitaminDWikiCrawler:
    """
    VitaminDWiki 전수 조사 모드 크롤러 (requests + BeautifulSoup)
    - 카테고리 목록 -> 카테고리 페이지 -> 아티클 페이지 순회
    - visited 로 중복 방지
    - Category는 breadcrumbs/catlinks(카테고리 태그)에서 파싱(키워드 매칭 X)
    """

    BASE = "https://vitamindwiki.com"
    # 현재 사이트 구조 기준(2026-02): 아래 인덱스가 사실상 전수 목록 진입점
    DEFAULT_INDEX_URL = "https://vitamindwiki.com/pages/health-problems-and-d/"
    DEFAULT_SECONDARY_INDEX_URL = "https://vitamindwiki.com/pages/ways-to-improve-health/"

    def __init__(self, delay_sec: float = 0.5, debug_mode: bool = False, max_retries: int = 3):
        self.delay_sec = max(0.0, float(delay_sec))
        self.debug_mode = debug_mode
        self.max_retries = max(1, int(max_retries))
        self.status_callback = None
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9,ko-KR;q=0.8,ko;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def set_status_callback(self, callback):
        self.status_callback = callback

    def _update_status(self, message: str):
        if self.status_callback:
            self.status_callback(message)
        else:
            print(f"[INFO] {message}")

    def _sleep(self, mult: float = 1.0):
        if self.delay_sec <= 0:
            return
        jitter = random.uniform(0.0, 0.15)
        time.sleep(self.delay_sec * mult + jitter)

    def _normalize_url(self, url: str) -> str:
        u = (url or "").strip()
        if not u:
            return ""
        if u.startswith("//"):
            u = "https:" + u
        if u.startswith("/"):
            u = self.BASE.rstrip("/") + u
        # fragment 제거
        u = u.split("#", 1)[0]
        return u

    def _is_internal_article_link(self, url: str) -> bool:
        if not url:
            return False
        if not url.startswith(self.BASE):
            return False
        q = urlparse(url).query.lower()
        if "print=" in q or "share=" in q:
            return False
        path = urlparse(url).path
        return path.startswith("/pages/") or path.startswith("/tags/")

    def _fetch_html(self, url: str) -> Optional[str]:
        last_err = None
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(url, timeout=15)
                if r.status_code == 200 and r.text:
                    return r.text
                if r.status_code in (429, 500, 502, 503, 504):
                    last_err = f"HTTP {r.status_code}"
                    self._sleep(mult=(attempt + 1) * 2.0)
                    continue
                last_err = f"HTTP {r.status_code}"
                return None
            except Exception as e:
                last_err = str(e)
                self._sleep(mult=(attempt + 1) * 2.0)
                continue

        if self.debug_mode and last_err:
            self._update_status(f"[디버그] 요청 실패: {url} ({last_err})")
        return None

    def _soup(self, html: str) -> BeautifulSoup:
        try:
            return BeautifulSoup(html, "lxml")
        except FeatureNotFound:
            return BeautifulSoup(html, "html.parser")

    def _extract_title(self, soup: BeautifulSoup) -> str:
        t = soup.title.get_text(" ", strip=True) if soup.title else ""
        return t.replace(" - VitaminDWiki", "").strip()

    def _extract_summary(self, soup: BeautifulSoup, max_len: int = 800) -> str:
        content = soup.select_one("article .markdown-content") or soup.select_one(".markdown-content") or soup.select_one("article")
        if not content:
            return ""
        parts: List[str] = []
        for p in content.select("p"):
            txt = p.get_text(" ", strip=True)
            # 빈 문단/광고/좌표 같은 잡문 방어
            if not txt or len(txt) < 40:
                continue
            parts.append(txt)
            if sum(len(x) for x in parts) >= max_len:
                break
        summary = " ".join(parts).strip()
        summary = re.sub(r"\s+", " ", summary)
        return summary[:max_len]

    def _extract_full_content(self, soup: BeautifulSoup) -> str:
        """
        페이지 본문 전체 텍스트 추출(요약 아님).
        - markdown-content 내의 텍스트를 최대한 그대로 가져온다.
        """
        content = soup.select_one("article .markdown-content") or soup.select_one(".markdown-content") or soup.select_one("article")
        if not content:
            return ""

        # 불필요한 영역 제거
        for sel in ["script", "style", "nav", "footer", ".toc", "#post-toc"]:
            for el in content.select(sel):
                try:
                    el.decompose()
                except:
                    pass

        text = content.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        cats: List[str] = []
        for a in soup.select("div.tags a.tag, a.tag[href^='/tags/']"):
            t = a.get_text(" ", strip=True)
            if t:
                cats.append(t.strip())

        seen = set()
        out: List[str] = []
        for c in cats:
            key = c.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out

    def _extract_links(self, soup: BeautifulSoup, scope_selector: Optional[str] = None) -> List[str]:
        scope = soup.select_one(scope_selector) if scope_selector else soup
        if not scope:
            return []
        links = []
        for a in scope.select("a[href]"):
            href = a.get("href") or ""
            href = self._normalize_url(href)
            if not href:
                continue
            if self._is_internal_article_link(href):
                links.append(href)
        # dedupe keep order
        seen = set()
        out = []
        for u in links:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    def _is_tag_page(self, url: str) -> bool:
        return urlparse(url).path.startswith("/tags/")

    def _get_tag_name_from_url(self, url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        parts = path.split("/")
        if len(parts) >= 3 and parts[1] == "tags":
            return parts[2]
        return ""

    def _extract_tag_members_and_pagination(self, soup: BeautifulSoup, base_url: str) -> tuple[List[str], List[str]]:
        members: List[str] = []
        pages: List[str] = []
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if not href:
                continue
            if href.startswith("/pages/"):
                members.append(self._normalize_url(href))
            if "?page=" in href:
                if href.startswith("?"):
                    pages.append(self._normalize_url(base_url + href))
                else:
                    pages.append(self._normalize_url(href))

        def dedupe(xs: List[str]) -> List[str]:
            s = set()
            o = []
            for x in xs:
                if x in s:
                    continue
                s.add(x)
                o.append(x)
            return o

        return dedupe(members), dedupe(pages)

    def crawl_full(
        self,
        start_url: Optional[str] = None,
        max_pages: Optional[int] = None,
        initial_visited_urls: Optional[set[str]] = None,
    ):
        """
        generator: paper(dict) yield
        - max_pages: fetch limit (None이면 무제한)
        """
        seed = self._normalize_url(start_url or self.DEFAULT_INDEX_URL)
        secondary = self._normalize_url(self.DEFAULT_SECONDARY_INDEX_URL)
        q = deque([(seed, None), (secondary, None)])  # (url, context_category)
        visited: set[str] = set()
        # DB 기반 resume: 이미 수집한 /pages URL은 재방문하지 않음
        if initial_visited_urls:
            try:
                for u in initial_visited_urls:
                    nu = self._normalize_url(u)
                    if nu:
                        visited.add(nu)
            except:
                pass
        fetched = 0

        self._update_status(f"🔎 시작 URL: {seed}")

        while q:
            url, ctx_cat = q.popleft()
            url = self._normalize_url(url)
            if not url or url in visited:
                continue
            visited.add(url)

            if max_pages is not None and fetched >= max_pages:
                self._update_status(f"⛔ 최대 페이지 제한 도달: {max_pages} (중단)")
                break

            html = self._fetch_html(url)
            fetched += 1
            if not html:
                if fetched < 5 or self.debug_mode:
                    self._update_status(f"⚠️ 페이지 로드 실패: {url}")
                continue

            soup = self._soup(html)
            title = self._extract_title(soup)

            if fetched % 30 == 0:
                self._update_status(f"⏳ 진행: {fetched}페이지 탐색 중... (큐 {len(q)}개)")

            # 1) 태그 페이지(/tags/*): 글 링크 + ?page= 페이지네이션
            if self._is_tag_page(url):
                tag = self._get_tag_name_from_url(url)
                members, pages = self._extract_tag_members_and_pagination(soup, url)
                if fetched < 5:
                    self._update_status(f"🏷️ 태그 '{tag}'에서 글 {len(members)}개 링크 발견")
                for pu in pages:
                    q.append((pu, tag))
                for mu in members:
                    q.append((mu, tag))
                self._sleep()
                continue

            # 2) 모든 페이지에서 /pages 및 /tags 링크를 큐에 추가 (전수 스크롤 역할)
            discovered_pages = 0
            discovered_tags = 0
            for a in soup.select("a[href]"):
                href = a.get("href") or ""
                if href.startswith("/pages/"):
                    q.append((self._normalize_url(href), ctx_cat))
                    discovered_pages += 1
                elif href.startswith("/tags/"):
                    q.append((self._normalize_url(href), None))
                    discovered_tags += 1
            if fetched <= 2:
                self._update_status(f"🔗 링크 발견: /pages {discovered_pages}개, /tags {discovered_tags}개")

            # 3) 일반 아티클 페이지: paper로 수집
            cats = self._extract_categories(soup)
            if ctx_cat and ctx_cat != "unknown":
                ctx_readable = ctx_cat.replace("-", " ").strip()
                if ctx_readable and all(ctx_readable.lower() != c.lower() for c in cats):
                    cats = [ctx_readable] + cats
            category_str = " | ".join(cats[:12])  # 너무 길어지는 것 방지
            full_content = self._extract_full_content(soup)
            # UI 표에는 미리보기용 요약이 있으면 편해서 유지(앞부분만 자름). "AI 요약"이 아님.
            summary = self._extract_summary(soup)
            collected_date = datetime.now().strftime("%Y-%m-%d")

            paper = {
                "title": title or url,
                "summary": summary,
                "content": full_content,
                "url": url,
                "category": category_str,
                "collected_date": collected_date,
            }
            if urlparse(url).path.startswith("/pages/"):
                yield paper
            self._sleep()
