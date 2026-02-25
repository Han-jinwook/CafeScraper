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
from urllib.parse import urlparse, parse_qs, parse_qsl, urlencode, urlunparse
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
        self.last_effective_start_page = 1
        self.last_scan_oldest_date = ""
        self.last_scanned_page = 0
        self.speed_profile = "stable"  # stable | fast

    def set_speed_profile(self, profile: str = "stable") -> None:
        try:
            p = str(profile or "stable").strip().lower()
        except:
            p = "stable"
        self.speed_profile = "fast" if p in ("fast", "high", "turbo") else "stable"

    def _speed_mult(self) -> float:
        # 고속형: 내부 고정 대기만 약 2배 단축
        return 0.5 if self.speed_profile == "fast" else 1.0

    def _sleep_scaled(self, seconds: float, floor: float = 0.15):
        try:
            s = float(seconds) * self._speed_mult()
        except:
            s = float(seconds)
        time.sleep(max(float(floor), s))

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

    def _deep_find_first_int(self, obj: Any, key_hints: List[str], max_depth: int = 6) -> Optional[int]:
        """
        dict/list 중첩에서 key_hints(부분 문자열 포함)로 첫 숫자 값을 찾는다.
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
                            if isinstance(v, (int, float)):
                                return int(v)
                            if isinstance(v, str):
                                m = re.search(r"\d+", v.replace(",", ""))
                                if m:
                                    return int(m.group(0))
                        if isinstance(v, (dict, list)):
                            q.append((v, depth + 1))
                elif isinstance(cur, list):
                    for v in cur:
                        if isinstance(v, (dict, list)):
                            q.append((v, depth + 1))
        except:
            pass
        return None

    def _deep_collect_ints(self, obj: Any, max_depth: int = 7) -> List[tuple[str, int]]:
        """
        중첩 dict/list에서 (정규화된 key, int value) 후보들을 전부 수집.
        - key 정규화: 소문자 + 비영숫자 제거
        """
        out: List[tuple[str, int]] = []
        try:
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
                        kl = re.sub(r"[^a-z0-9]", "", str(k).lower())
                        if isinstance(v, (int, float)):
                            out.append((kl, int(v)))
                        elif isinstance(v, str):
                            m = re.search(r"^\s*\d[\d,]*\s*$", v)
                            if m:
                                try:
                                    out.append((kl, int(v.replace(",", "").strip())))
                                except:
                                    pass
                        if isinstance(v, (dict, list)):
                            q.append((v, depth + 1))
                elif isinstance(cur, list):
                    for v in cur:
                        if isinstance(v, (dict, list)):
                            q.append((v, depth + 1))
        except:
            pass
        return out

    def _get_article_meta_via_article_api(self, club_id: Optional[str], article_id: Optional[str]) -> Dict[str, Any]:
        """
        게시글 메타(API 기반):
        - 조회수(view_count)
        - 좋아요(like_count)
        - 카테고리(category)  (말머리/카테고리명 후보)
        """
        out: Dict[str, Any] = {"view_count": 0, "like_count": 0, "category": ""}
        if not club_id or not article_id:
            return out
        try:
            s = self._build_requests_session_from_driver()
            url = f"https://apis.naver.com/cafe-web/cafe-article/v1/articles/{article_id}?useCafeId=false&buid={club_id}"
            headers = {
                "Referer": f"https://m.cafe.naver.com/ca-fe/web/cafes/{club_id}/articles/{article_id}",
                "Origin": "https://m.cafe.naver.com",
                "Accept": "application/json, text/plain, */*",
            }

            # 네이버가 간헐적으로 429/5xx 또는 HTML을 반환하는 경우가 있어 재시도/방어
            last_err: str | None = None
            data = None
            for attempt in range(3):
                try:
                    r = s.get(url, headers=headers, timeout=10)
                    if r.status_code == 200:
                        try:
                            data = r.json()
                            break
                        except Exception as json_err:
                            # JSON이 아닌 응답(예: HTML/빈본문)일 수 있음
                            last_err = f"json_decode_failed: {json_err}"
                    else:
                        last_err = f"http_{r.status_code}"
                        # 401/403/429/5xx는 잠깐 쉬고 재시도할 가치가 있음
                        if r.status_code in (401, 403, 408, 429, 500, 502, 503, 504):
                            time.sleep(0.8 * (attempt + 1))
                            continue
                except Exception as req_err:
                    last_err = f"request_failed: {req_err}"
                    time.sleep(0.8 * (attempt + 1))
                    continue

            if not isinstance(data, dict):
                if self.debug_mode and last_err:
                    self._update_status(f"[디버그] 메타 API 응답 실패: {last_err}")
                return out

            article = data.get("result", {}).get("article", {}) if isinstance(data, dict) else {}
            if not isinstance(article, dict):
                return out

            # 조회수: "view"가 다른 단어(review 등)에도 포함되어 오탐이 잦음 → 후보 수집 후 키 prefix 기반 선택
            candidates = self._deep_collect_ints(article, max_depth=7)
            view_keys = ("readcount", "readcnt", "viewcount", "viewcnt", "hitcount", "hit", "hits")
            view_vals = [v for (k, v) in candidates if any(k.startswith(p) for p in view_keys)]
            if view_vals:
                out["view_count"] = int(max(view_vals))
            else:
                # fallback: 아주 제한적으로만 (reviewCount 같은 오탐을 피하려고 startswith 사용)
                broad_vals = [v for (k, v) in candidates if k.startswith("read") or k.startswith("view") or k.startswith("hit")]
                out["view_count"] = int(max(broad_vals)) if broad_vals else 0

            # 좋아요: like* 후보 중 최댓값 선택
            like_keys = ("likecount", "likecnt", "likeitcount", "like")
            like_vals = [v for (k, v) in candidates if any(k.startswith(p) for p in like_keys)]
            out["like_count"] = int(max(like_vals)) if like_vals else 0

            cat = (
                article.get("headName")
                or article.get("headTitle")
                or article.get("categoryName")
                or article.get("category")
                or ""
            )
            if isinstance(cat, str) and cat.strip():
                out["category"] = self._clean_text(cat)
            else:
                found_s = self._deep_find_first_string(article, ["headname", "headtitle", "head", "categoryname", "category"])
                if found_s:
                    out["category"] = self._clean_text(found_s)

            if self.debug_mode:
                # 값이 0으로만 떨어질 때 디버그 힌트(상위 후보 일부)
                if out.get("view_count", 0) == 0:
                    top_view = sorted([(k, v) for (k, v) in candidates if "read" in k or "view" in k or "hit" in k], key=lambda x: x[1], reverse=True)[:8]
                    if top_view:
                        self._update_status(f"[디버그] view 후보(top): {top_view}")
                if out.get("like_count", 0) == 0:
                    top_like = sorted([(k, v) for (k, v) in candidates if "like" in k], key=lambda x: x[1], reverse=True)[:8]
                    if top_like:
                        self._update_status(f"[디버그] like 후보(top): {top_like}")
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] API 메타 추출 실패: {e}")
        return out

    def get_article_meta(self, article_url: str) -> Dict[str, Any]:
        """
        외부에서 호출 가능한 메타 추출 헬퍼.
        - 입력 URL이 f-e/ca-fe여도 club/article id를 파싱해 API로
          조회수/좋아요/카테고리 + 작성자 등급(member_level) 반환
        """
        try:
            normalized = self._normalize_article_url(article_url or "")
            club_id, article_id = self._parse_club_article_ids(normalized)
            api_meta = self._get_article_meta_via_article_api(club_id, article_id)
            writer_info = self._get_writer_info_via_article_api(club_id, article_id)
            api_meta["member_level"] = str(writer_info.get("member_level", "") or "").strip()

            # 네이버가 API 응답을 막거나(HTML/403/429) 필드를 바꾸면 0으로만 떨어질 수 있음.
            # 이 경우 화면(PC 버전) 기반 폴백을 한 번 더 시도한다. (가장 확실한 방법)
            if (
                (api_meta.get("view_count", 0) or 0) == 0
                and (api_meta.get("like_count", 0) or 0) == 0
            ):
                screen_meta = self._get_article_meta_via_screen(normalized)
                # screen_meta가 뭔가라도 건지면 그걸 우선 사용
                if (
                    (screen_meta.get("view_count", 0) or 0) != 0
                    or (screen_meta.get("like_count", 0) or 0) != 0
                ):
                    # 카테고리/등급은 API 값이 있으면 유지 (화면에서 긁기 어려울 수 있음)
                    if api_meta.get("category"):
                        screen_meta["category"] = api_meta["category"]
                    screen_meta["member_level"] = api_meta.get("member_level", "")
                    return screen_meta
            return api_meta
        except:
            return {"view_count": 0, "like_count": 0, "category": "", "member_level": ""}

    def get_article_member_level(self, article_url: str) -> str:
        """
        등급(member_level)만 빠르게 조회.
        - API 기반 작성자 정보만 사용 (브라우저 이동/화면 폴백 없음)
        - 대량 보강 시 속도 저하를 막기 위한 전용 경로
        """
        try:
            normalized = self._normalize_article_url(article_url or "")
            club_id, article_id = self._parse_club_article_ids(normalized)
            writer_info = self._get_writer_info_via_article_api(club_id, article_id)
            return str(writer_info.get("member_level", "") or "").strip()
        except:
            return ""

    def _get_article_meta_via_screen(self, article_url: str) -> Dict[str, Any]:
        """
        [최후의 수단] PC 버전 화면으로 직접 이동해서 화면에 보이는 숫자를 긁어온다.
        - API가 막혀도, 브라우저에 보이면 가져온다.
        """
        out: Dict[str, Any] = {"view_count": 0, "like_count": 0, "category": ""}
        if not self.driver:
            return out

        try:
            # PC 버전 URL로 이동 (로그인 세션 활용)
            self.driver.get(article_url)
            time.sleep(2.0)
            
            # iframe 전환
            if not self._switch_to_cafe_iframe():
                return out

            # 조회수 찾기 (다양한 Selector 시도)
            # 예: "조회 1,234" 텍스트에서 숫자만 추출
            view_selectors = [
                ".article_info .count",  # 신형
                ".article_tit .count",   # 구형
                "span.b",                # 아주 구형
                ".t_view",               # 일부 스킨
                ".p-view .num"           # 스마트에디터 등
            ]
            for sel in view_selectors:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        txt = el.text.strip()
                        # "조회 123" or "123"
                        if "조회" in txt or re.match(r"[\d,]+", txt):
                            nums = re.findall(r"\d+", txt.replace(",", ""))
                            if nums:
                                out["view_count"] = int(nums[0])
                                break
                    if out["view_count"] > 0:
                        break
                except:
                    continue

            # 좋아요 찾기 (동적 로딩 가능성 있음 - Wait 시도)
            # 보통 .u_cnt, .like_article, .like_count 등이 쓰임
            like_selectors = [
                "em.u_cnt",             # 네이버 공통 좋아요 카운트
                ".like_article .u_cnt", # 카페 좋아요
                ".like_area .num",      # 구형
                "#likeItCount",         # ID 기반
                ".u_likeit_list_module .u_cnt"
            ]
            
            # 좋아요는 늦게 뜰 수 있으므로 1초 정도 대기하며 확인
            for _ in range(5): # 0.2초 * 5회
                for sel in like_selectors:
                    try:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in els:
                            txt = el.text.strip()
                            if txt and txt.isdigit():
                                out["like_count"] = int(txt)
                                break
                        if out["like_count"] > 0:
                            break
                    except:
                        pass
                if out["like_count"] > 0:
                    break
                time.sleep(0.2)

            if self.debug_mode:
                self._update_status(
                    f"[디버그] 화면 스크래핑 결과: view={out['view_count']} like={out['like_count']}"
                )

        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] 화면 스크래핑 실패: {e}")
        
        return out

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
        - member_level: 등급명 (새싹멤버, 열심멤버 등)
        """
        out = {"member_id": "unknown", "nickname": "unknown", "member_level": ""}
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
            
            # 등급 추출
            for k in ["memberLevelName", "memberLevel", "levelName", "gradeName", "level"]:
                v = writer.get(k)
                if v:
                    if isinstance(v, str):
                        out["member_level"] = self._clean_text(v)
                    elif isinstance(v, dict) and "name" in v: # object인 경우
                        out["member_level"] = self._clean_text(v.get("name", ""))
                    if out["member_level"]:
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

                # 댓글 작성일(일자만) 추출: 필드명이 자주 바뀌므로 후보군 방어
                raw_date = (
                    it.get("regDate")
                    or it.get("registerDate")
                    or it.get("registeredDate")
                    or it.get("writeDate")
                    or it.get("writtenDate")
                    or it.get("createDate")
                    or it.get("createdDate")
                    or it.get("commentDate")
                    or it.get("commentRegDate")
                    or it.get("date")
                    or it.get("time")
                    or it.get("timestamp")
                )
                comment_ymd = self._to_ymd(raw_date)

                # 댓글 ID / 등급(멤버등급) 후보군 방어
                comment_id = (
                    it.get("commentId")
                    or it.get("comment_id")
                    or it.get("commentid")
                    or it.get("id")
                    or it.get("commentNo")
                    or it.get("commentNoEnc")
                    or ""
                )
                raw_level = (
                    it.get("memberLevelName")
                    or it.get("memberLevel")
                    or it.get("levelName")
                    or it.get("level")
                    or it.get("gradeName")
                    or it.get("grade")
                    or it.get("writerLevelName")
                    or it.get("writerGradeName")
                    or it.get("writerLevel")
                    or it.get("writerGrade")
                    or ""
                )
                level_name = self._clean_text(raw_level) if isinstance(raw_level, str) else str(raw_level or "").strip()
                if not level_name:
                    found_level = self._deep_find_first_string(it, ["level", "grade"])
                    if found_level:
                        level_name = self._clean_text(found_level)

                out.append(
                    {
                        "writer_id": str(writer_id) if writer_id is not None else "unknown",
                        "nickname": str(nickname) if nickname is not None else "unknown",
                        "content": str(content) if content is not None else "",
                        "date": comment_ymd,
                        "comment_id": str(comment_id) if comment_id is not None else "",
                        "level": level_name,
                    }
                )

            return out
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] CommentView 댓글 추출 실패: {e}")
            return None

    def get_all_comments_for_article(self, article_url: str) -> List[Dict[str, Any]]:
        """
        이벤트/분석용: 특정 게시글의 '모든 댓글'을 API 기반으로 수집.
        - 반환: [{"writer_id","nickname","content","date"}...]
        """
        try:
            normalized = self._normalize_article_url(article_url or "")
            club_id, article_id = self._parse_club_article_ids(normalized)
            api_comments = self._get_comments_via_commentview(club_id, article_id)
            return api_comments or []
        except:
            return []

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

    def _get_member_level_via_js_state(self) -> str:
        """전략: SPA 전역 상태에서 등급명(member level) 추출"""
        if not self.driver:
            return ""
        try:
            js = r"""
                try {
                    const roots = [];
                    if (window.__INITIAL_STATE__) roots.push(window.__INITIAL_STATE__);
                    if (window.__NEXT_DATA__) roots.push(window.__NEXT_DATA__);
                    if (window.__APOLLO_STATE__) roots.push(window.__APOLLO_STATE__);

                    const KEY_HINTS = ["memberlevelname","memberlevel","levelname","gradename","level","grade"];
                    const BAD = new Set(["", "null", "undefined", "unknown"]);

                    function clean(s) {
                        return String(s || "").replace(/\s+/g, " ").trim();
                    }

                    function isLikelyLevel(v) {
                        const t = clean(v);
                        if (!t) return false;
                        const tl = t.toLowerCase();
                        if (BAD.has(tl)) return false;
                        // 카페 등급명에서 자주 보이는 패턴 우선
                        return /멤버|매니저|부\s*매니저|스탭|운영|새싹|초급|중급|상급|정회원/.test(t);
                    }

                    function dig(obj, depth, seen) {
                        if (!obj || depth > 8 || typeof obj !== "object") return "";
                        if (seen.has(obj)) return "";
                        seen.add(obj);

                        if (Array.isArray(obj)) {
                            for (const v of obj) {
                                const found = dig(v, depth + 1, seen);
                                if (found) return found;
                            }
                            return "";
                        }

                        // 1) 키 힌트 기반 직접 추출
                        for (const [k, v] of Object.entries(obj)) {
                            const kl = String(k || "").toLowerCase();
                            if (KEY_HINTS.some(h => kl.includes(h))) {
                                if (typeof v === "string" && isLikelyLevel(v)) return clean(v);
                                if (v && typeof v === "object" && typeof v.name === "string" && isLikelyLevel(v.name)) return clean(v.name);
                            }
                        }

                        // 2) 재귀 탐색
                        for (const v of Object.values(obj)) {
                            if (v && typeof v === "object") {
                                const found = dig(v, depth + 1, seen);
                                if (found) return found;
                            }
                        }
                        return "";
                    }

                    for (const root of roots) {
                        const found = dig(root, 0, new WeakSet());
                        if (found) return found;
                    }
                    return "";
                } catch (e) {
                    return "";
                }
            """
            lvl = self.driver.execute_script(js)
            if isinstance(lvl, str):
                return self._clean_text(lvl)
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] JS state member_level 추출 실패: {e}")
        return ""

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
            # options.add_argument("--start-maximized")
            options.add_argument("--window-size=960,1080")  # 화면 절반 크기로 시작
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
            
            # 관리자 페이지(ManageMember)는 무조건 iframe 전환 시도해야 함 (구형 방식)
            if "ManageMember" in current_url:
                try:
                    wait = WebDriverWait(self.driver, 5)
                    iframe = wait.until(EC.presence_of_element_located((By.ID, "cafe_main")))
                    self.driver.switch_to.frame(iframe)
                    if self.debug_mode:
                        self._update_status(f"[디버그] ✅ 관리자 페이지 iframe 전환 성공")
                    return True
                except:
                    # iframe이 없을 수도 있음 (새 창 등)
                    pass

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
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                # 2자리 연도(YY) 보정: 1900년대일 확률은 낮으므로 2000을 더함
                if y < 100:
                    y += 2000
                return datetime(y, m, d)
            
            # (추가) MM.DD 형식 대응 (올해로 가정)
            if len(parts) == 2:
                m, d = int(parts[0]), int(parts[1])
                return datetime(datetime.now().year, m, d)

            return None
        except:
            return None

    def _to_ymd(self, raw: Any) -> str:
        """
        날짜 값을 YYYY-MM-DD로 정규화.
        - int/float: epoch seconds/ms 허용
        - str: 2026.02.05 / 2026-02-05 / 2026/02/05 등에서 날짜만 추출
        """
        try:
            if raw is None:
                return ""

            if isinstance(raw, (int, float)):
                v = int(raw)
                if v > 10_000_000_000:  # ms
                    dt = datetime.fromtimestamp(v / 1000.0)
                elif v > 1_000_000_000:  # sec
                    dt = datetime.fromtimestamp(v)
                else:
                    return ""
                return dt.strftime("%Y-%m-%d")

            s = str(raw).strip()
            if not s:
                return ""

            # YYYYMMDD 형태도 방어
            m0 = re.search(r"\b(\d{4})(\d{2})(\d{2})\b", s)
            if m0:
                y, mo, d = int(m0.group(1)), int(m0.group(2)), int(m0.group(3))
                return datetime(y, mo, d).strftime("%Y-%m-%d")

            m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return datetime(y, mo, d).strftime("%Y-%m-%d")
        except:
            return ""
        return ""

    def set_stop_check_callback(self, callback):
        self.stop_check_callback = callback

    def _should_stop(self):
        if self.status_callback and hasattr(self, 'stop_check_callback') and self.stop_check_callback:
            return self.stop_check_callback()
        return False

    def _convert_to_legacy_board_url(self, url: str) -> str:
        """
        SPA URL(f-e)을 Legacy URL(ArticleList.nhn)로 변환하여
        userDisplay=50 등의 파라미터가 잘 먹히도록 함.
        """
        try:
            # https://cafe.naver.com/f-e/cafes/27870803/menus/0
            if "/f-e/cafes/" in url and "/menus/" in url:
                m = re.search(r"/cafes/(\d+)/menus/(\d+)", url)
                if m:
                    club_id = m.group(1)
                    menu_id = m.group(2)
                    
                    # menu_id가 0이면(전체글보기), menuid 파라미터를 빼야 정상 동작할 수 있음
                    # 또는 search.menuid를 넣지 않고 clubid만으로 전체보기가 됨
                    base = f"https://cafe.naver.com/ArticleList.nhn?search.clubid={club_id}&search.boardtype=L"
                    if menu_id != "0":
                        base += f"&search.menuid={menu_id}"
                    
                    return base
        except:
            pass
        return url

    def _build_board_page_url(self, board_url: str, page_no: int, user_display: int = 50) -> str:
        """
        게시판 페이지 URL 생성.
        - Legacy(ArticleList.nhn): search.page 우선
        - 기타 URL: page 파라미터 사용
        - userDisplay=50 항상 강제
        """
        try:
            parsed = urlparse(str(board_url))
            q_items = parse_qsl(parsed.query, keep_blank_values=True)
            q: Dict[str, str] = {str(k): str(v) for k, v in q_items}

            q["userDisplay"] = str(int(user_display))
            if "ArticleList.nhn" in (parsed.path or ""):
                q["search.page"] = str(int(page_no))
                # 일부 환경 호환을 위해 page도 함께 유지
                q["page"] = str(int(page_no))
            else:
                q["page"] = str(int(page_no))

            new_query = urlencode(q, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        except:
            sep = "&" if "?" in str(board_url) else "?"
            return f"{board_url}{sep}page={int(page_no)}&userDisplay={int(user_display)}"

    def scrape_board_list(
        self,
        board_url: str,
        start_date: datetime,
        end_date: datetime,
        exclude_boards: Optional[List[str]] = None,
        start_page: int = 1,
        max_pages: int = 50,
    ) -> tuple[List[Dict[str, Any]], bool]:
        """
        게시판 리스트에서 날짜 범위 내 게시글 링크 추출 (배치 처리 지원)
        - start_page: 시작 페이지 번호
        - max_pages: 이번 호출에서 스캔할 최대 페이지 수 (배치 크기)
        - Returns: (collected_articles, is_finished)
          - is_finished: True면 더 이상 수집할 필요 없음 (날짜 초과 또는 게시판 끝)
        """
        if not board_url:
            self._update_status("❌ 게시판 URL이 비어 있습니다.")
            return [], True

        # (수정) URL을 레거시 포맷으로 변환하여 50개씩 보기가 확실히 적용되도록 함
        board_url = self._convert_to_legacy_board_url(board_url)

        exclude_norm = set()
        if exclude_boards:
            exclude_norm = {self._normalize_board_name(x) for x in exclude_boards if str(x).strip()}

        def _read_page_date_range(page_no: int) -> tuple[Optional[datetime], Optional[datetime], int, str]:
            """
            특정 페이지의 날짜 범위를 읽는다.
            Returns: (min_date, max_date, valid_row_count, first_post_id)
            - min_date: 페이지 내 가장 오래된 글 날짜
            - max_date: 페이지 내 가장 최신 글 날짜
            """
            page_url = self._build_board_page_url(board_url, page_no, user_display=50)
            try:
                if self.driver.current_url != page_url:
                    self.driver.get(page_url)
                    self._sleep_scaled(1.8)
                self._switch_to_cafe_iframe()
                self.driver.execute_script("window.scrollTo(0, 900);")
                self._sleep_scaled(0.7)

                rows_inner = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[class*='ArticleItem'], li[class*='article'], div.article-board table tbody tr"
                )
                if not rows_inner:
                    return None, None, 0, ""

                dates: List[datetime] = []
                first_post_id = ""
                for row_inner in rows_inner:
                    try:
                        row_class_inner = (row_inner.get_attribute("class") or "").lower()
                        is_notice_inner = False
                        if "notice" in row_class_inner or "top" in row_class_inner:
                            is_notice_inner = True
                        if not is_notice_inner:
                            try:
                                if row_inner.find_elements(By.CSS_SELECTOR, ".ico_notice, .icon_notice, .td_notice"):
                                    is_notice_inner = True
                                elif "공지" in row_inner.text[:12]:
                                    is_notice_inner = True
                            except:
                                pass
                        if is_notice_inner:
                            continue

                        if not first_post_id:
                            try:
                                link_el_inner = None
                                for ls_inner in ["a[class*='ArticleLink']", "a.article", "a[href*='articleid']"]:
                                    try:
                                        link_el_inner = row_inner.find_element(By.CSS_SELECTOR, ls_inner)
                                        if link_el_inner:
                                            break
                                    except:
                                        continue
                                if link_el_inner:
                                    href_inner = link_el_inner.get_attribute("href") or ""
                                    m_id = re.search(r'articleid=(\d+)', href_inner) or re.search(r'/articles/(\d+)', href_inner)
                                    if m_id:
                                        first_post_id = m_id.group(1)
                            except:
                                pass

                        dval_inner = None
                        for ds_inner in ["span[class*='Date']", "span.date", "td.td_date", ".date"]:
                            try:
                                el_inner = row_inner.find_element(By.CSS_SELECTOR, ds_inner)
                                dval_inner = self._parse_date(el_inner.text.strip())
                                if dval_inner:
                                    break
                            except:
                                continue
                        if not dval_inner:
                            m_inner = re.search(
                                r'(\d{4}\.\d{1,2}\.\d{1,2}|\d{1,2}\.\d{1,2}|\d{1,2}:\d{2})',
                                row_inner.text,
                            )
                            if m_inner:
                                dval_inner = self._parse_date(m_inner.group(1))
                        if dval_inner:
                            dates.append(dval_inner)
                    except:
                        continue

                if not dates:
                    return None, None, 0, first_post_id
                return min(dates), max(dates), len(dates), first_post_id
            except:
                return None, None, 0, ""

        def _auto_locate_start_page(target_end: datetime, initial_page: int) -> int:
            """
            목표 종료일(end_date)이 포함될 가능성이 높은 페이지를 자동 탐색.
            - 페이지 번호가 커질수록 더 과거 글이 나온다는 전제.
            - 반환 페이지는 경계 누락 방지를 위해 찾은 페이지의 1페이지 앞에서 시작.
            """
            if initial_page > 1:
                return initial_page

            self._update_status("🧭 해당 기간의 페이지를 찾는 중... (자동 점프 준비)")

            p1_min, p1_max, p1_cnt, p1_first_id = _read_page_date_range(1)
            if p1_cnt == 0:
                self._update_status("⚠️ 1페이지 날짜를 읽지 못해 자동 점프를 건너뜁니다.")
                return 1

            self._update_status(
                f"🧭 해당 기간의 페이지를 찾는 중... 1p 확인 "
                f"(범위: {p1_max.strftime('%Y-%m-%d')} ~ {p1_min.strftime('%Y-%m-%d')})"
            )

            if p1_min <= target_end <= p1_max:
                self._update_status("✅ 해당 기간의 페이지를 찾았습니다. 1페이지부터 시작합니다.")
                return 1

            # 목표가 1페이지보다 과거면(일반적인 과거 수집): 지수 탐색 후 이분 탐색
            if target_end < p1_min:
                lo = 1
                hi = 1
                hi_min = p1_min
                hi_first_id = p1_first_id
                max_probe_page = 5000

                while hi < max_probe_page and hi_min and target_end < hi_min:
                    if self._should_stop():
                        return lo
                    nxt = min(max_probe_page, hi * 2)
                    n_min, n_max, n_cnt, n_first_id = _read_page_date_range(nxt)
                    if n_cnt == 0:
                        # 게시판 끝을 만난 경우, 마지막 유효 구간에서 마무리 탐색
                        break
                    if hi_first_id and n_first_id and hi_first_id == n_first_id:
                        self._update_status("⚠️ 페이지 이동이 반영되지 않아 자동 점프를 중단합니다. (1페이지부터 순차 탐색)")
                        return 1
                    self._update_status(
                        f"🧭 해당 기간의 페이지를 찾는 중... {nxt}p 확인 "
                        f"(범위: {n_max.strftime('%Y-%m-%d')} ~ {n_min.strftime('%Y-%m-%d')})"
                    )
                    lo = hi
                    hi = nxt
                    hi_min = n_min
                    hi_first_id = n_first_id

                # hi가 목표보다 충분히 과거(또는 같은 날짜)인 구간이면 이분 탐색
                left = lo
                right = hi
                found = hi
                while left <= right:
                    if self._should_stop():
                        break
                    mid = (left + right) // 2
                    m_min, m_max, m_cnt, _ = _read_page_date_range(mid)
                    if m_cnt == 0 or not m_min:
                        right = mid - 1
                        continue
                    self._update_status(
                        f"🧭 해당 기간의 페이지를 찾는 중... {mid}p 확인 "
                        f"(범위: {m_max.strftime('%Y-%m-%d')} ~ {m_min.strftime('%Y-%m-%d')})"
                    )
                    if target_end < m_min:
                        left = mid + 1
                    else:
                        found = mid
                        right = mid - 1

                jump_page = max(1, int(found) - 1)
                self._update_status(
                    f"✅ 해당 기간의 페이지를 찾았습니다. {jump_page}페이지부터 수집을 시작합니다."
                )
                return jump_page

            # 목표 종료일이 1페이지보다 최신인 경우(아주 최근 범위): 1페이지 시작
            self._update_status("✅ 해당 기간이 최신 구간으로 판단되어 1페이지부터 시작합니다.")
            return 1
            
        all_articles = []
        page = _auto_locate_start_page(end_date, start_page)
        self.last_effective_start_page = int(page)
        self.last_scanned_page = max(0, int(page) - 1)
        end_page = page + max_pages - 1
        should_continue = True
        is_finished = False
        
        last_first_post_id = None # (추가) 무한 루프 방지용

        while should_continue and page <= end_page:
            self.last_scanned_page = int(page)
            # (추가) 중단 요청 확인
            if self._should_stop():
                self._update_status("🛑 사용자 요청으로 목록 수집을 중단합니다.")
                should_continue = False
                break

            # (수정) 페이지 파라미터를 URL 유형에 맞게 구성
            target_page_url = self._build_board_page_url(board_url, page, user_display=50)
            
            self._update_status(f"🚀 {page}페이지 분석 시작 (이번 배치 누적: {len(all_articles)}개)")
            
            # 20페이지마다 휴식 (리스트 수집 중 차단 방지)
            if page > 1 and page % 20 == 0:
                 self._update_status(f"☕ (리스트 수집) 네이버 차단 방지를 위해 5초간 휴식합니다... ({page}페이지 완료)")
                 self._sleep_scaled(5.0)
            
            try:
                # 페이지 이동 (undetected는 알아서 부드럽게 처리)
                if self.driver.current_url != target_page_url:
                    self.driver.get(target_page_url)
                    self._sleep_scaled(2.5)  # 로딩 대기
                
                self._switch_to_cafe_iframe()
                
                # 스크롤하여 동적 콘텐츠 로딩
                self.driver.execute_script("window.scrollTo(0, 1000);")
                self._sleep_scaled(1.0)
                
                # 게시글 행 찾기 (최신 SPA 구조 우선)
                # 고속 모드에서 간헐적으로 목록 렌더링이 늦게 붙는 경우가 있어, 빈 페이지는 짧게 재확인한다.
                row_selector = "div[class*='ArticleItem'], li[class*='article'], div.article-board table tbody tr"
                rows = []
                empty_retries = 3 if self.speed_profile == "fast" else 2
                for retry_idx in range(empty_retries):
                    rows = self.driver.find_elements(By.CSS_SELECTOR, row_selector)
                    if rows:
                        break
                    if retry_idx < empty_retries - 1:
                        self._update_status(
                            f"⏳ {page}페이지 목록 재확인 중... ({retry_idx + 1}/{empty_retries - 1})"
                        )
                        try:
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        except:
                            pass
                        self._sleep_scaled(1.2 + (retry_idx * 0.8), floor=0.6)
                        try:
                            self.driver.execute_script("window.scrollTo(0, 1000);")
                        except:
                            pass
                        self._sleep_scaled(0.5, floor=0.3)
                
                if not rows:
                    self._update_status(
                        f"⚠️ {page}페이지에서 게시글을 찾지 못했습니다. (재확인 후에도 비어 있음, 게시판 끝/로딩 지연 가능)"
                    )
                    is_finished = True
                    break
                
                # (추가) 50개씩 보기 적용 확인
                if len(rows) < 20 and len(rows) > 0:
                     self._update_status(f"⚠️ 경고: 페이지당 게시글이 {len(rows)}개만 감지됨. (50개 설정 미적용 가능성)")

                page_found_count = 0
                page_dates = [] # (추가) 페이지 내 유효한(공지 제외) 게시글 날짜 수집
                
                # (추가) 무한 루프(페이지 고착) 감지
                # 첫 번째 게시글(공지 제외)의 ID를 확인하여 이전 페이지와 동일하면 중단
                current_first_post_id = None

                for idx, row in enumerate(rows):
                    try:
                        # 공지 스킵 강화
                        row_class = (row.get_attribute("class") or "").lower()
                        is_notice = False
                        if "notice" in row_class or "top" in row_class: 
                            is_notice = True
                        
                        # (추가) 텍스트/아이콘 기반 공지 확인
                        if not is_notice:
                            try:
                                if row.find_elements(By.CSS_SELECTOR, ".ico_notice, .icon_notice, .td_notice"):
                                    is_notice = True
                                elif "공지" in row.text[:10]: # 텍스트 앞부분에 '공지' 포함 시
                                    is_notice = True
                            except: pass
                        
                        if is_notice: continue
                        
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
                        
                        # (추가) 무한 루프 감지용 ID 수집 (첫 번째 유효 게시글)
                        if current_first_post_id is None:
                            try:
                                # href에서 articleid 추출
                                link_el_temp = None
                                for ls in ["a[class*='ArticleLink']", "a.article", "a[href*='articleid']"]:
                                    try:
                                        link_el_temp = row.find_element(By.CSS_SELECTOR, ls)
                                        if link_el_temp: break
                                    except: continue
                                if link_el_temp:
                                    href_temp = link_el_temp.get_attribute("href")
                                    m_temp = re.search(r'articleid=(\d+)', href_temp) or re.search(r'/articles/(\d+)', href_temp)
                                    if m_temp:
                                        current_first_post_id = m_temp.group(1)
                            except: pass

                        # (추가) 유효한 게시글 날짜만 수집
                        page_dates.append(date_val)

                        if date_val > end_date: continue
                        if date_val < start_date:
                            # (수정) 여기가 실행되어야 멈추는데, 만약 날짜 파싱 오류로 date_val이 이상하면 안 멈출 수 있음
                            # 디버깅용 로그 추가
                            # self._update_status(f"[디버그] 날짜 도달: {date_val} < {start_date}")
                            self._update_status(f"⏱️ 시작일 이전 도달 ({date_val.strftime('%Y년 %m월 %d일')}). 종료합니다.")
                            should_continue = False
                            is_finished = True
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
                
                # (추가) 무한 루프 체크
                if current_first_post_id and current_first_post_id == last_first_post_id:
                    self._update_status(f"⚠️ 페이지 고착 감지: {page}페이지 내용이 이전 페이지와 동일합니다. (더 이상 글이 없거나 오류)")
                    is_finished = True
                    break
                last_first_post_id = current_first_post_id

                # self._update_status(f"✅ {page}페이지 완료: {page_found_count}개 수집 (배치 누적 {len(all_articles)}개)")
                
                # (수정) 사용자 안심용 로그: 수집된 게 없어도 현재 탐색 위치(날짜)를 알려줌
                if page_dates:
                    try:
                        self.last_scan_oldest_date = min(page_dates).strftime("%Y-%m-%d")
                    except:
                        pass

                if page_found_count == 0:
                     if page_dates:
                         # 공지가 아닌 유효 게시글 중 가장 오래된(과거) 날짜를 기준으로 표시
                         min_date = min(page_dates)
                         last_seen_date_str = min_date.strftime("%Y년 %m월 %d일")
                         self._update_status(f"🔎 {page}p 탐색 중... (현재 글 날짜: {last_seen_date_str} → 이전 수집 시작일: {start_date.strftime('%Y년 %m월 %d일')}까지 이동 중)")
                     elif 'last_seen_date_str' in locals():
                         # 이번 페이지엔 공지밖에 없었지만, 이전 페이지 기록이 있는 경우
                         self._update_status(f"🔎 {page}p 탐색 중... (공지/광고 스킵됨, 이전 기준: {last_seen_date_str} → 목표: {start_date.strftime('%Y년 %m월 %d일')})")
                     else:
                         self._update_status(f"🔎 {page}p 탐색 중... (현재 페이지에 유효한 날짜를 찾지 못함)")
                else:
                     # (수정) 50개씩 보기 모드임을 감안하여 로그 메시지 수정
                     self._update_status(f"✅ {page}페이지 완료 (50개씩 보기): {page_found_count}개 수집 (배치 누적 {len(all_articles)}개)")
                
                if not should_continue: break
                page += 1
                self._sleep_scaled(random.uniform(2, 4))
                
            except Exception as e:
                self._update_status(f"❌ {page}페이지 처리 중 오류: {e}")
                # 에러가 나도 다음 페이지 시도해볼 수 있으나, 연속 에러 방지 위해 일단 break?
                # 여기서는 배치 중단하고 현재까지 수집된 것 반환
                break
            
        return all_articles, is_finished

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
            self._sleep_scaled(3.0)
            self._switch_to_cafe_iframe()

            # 상세에서는 API가 가장 빠르고 정확 (가능하면 여기서 writer id 확보)
            club_id, article_id = self._parse_club_article_ids(article_url)
            writer_info = self._get_writer_info_via_article_api(club_id, article_id)
            meta_info = self._get_article_meta_via_article_api(club_id, article_id)
            
            # API가 실패했으면(0) 화면에서 재시도 (PC 버전 Selector)
            if (meta_info.get("view_count", 0) or 0) == 0 and (meta_info.get("like_count", 0) or 0) == 0:
                screen_meta = self._get_article_meta_via_screen(article_url)
                if screen_meta.get("view_count"): meta_info["view_count"] = screen_meta["view_count"]
                if screen_meta.get("like_count"): meta_info["like_count"] = screen_meta["like_count"]

            api_author_id = writer_info.get("member_id", "unknown")
            api_author_nick = writer_info.get("nickname", "unknown")
            api_member_level = writer_info.get("member_level", "")
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

            # 카테고리(말머리) DOM 백업
            category = str(meta_info.get("category") or "").strip()
            if not category:
                try:
                    for sel in [
                        "span.head",
                        "span[class*='Head']",
                        "span[class*='Category']",
                        ".ArticleTopInfo__head",
                        ".article_header .head",
                    ]:
                        try:
                            el = self.driver.find_element(By.CSS_SELECTOR, sel)
                            t = self._extract_text_from_element(el)
                            if t and len(t) <= 40:
                                category = t
                                break
                        except:
                            continue
                except:
                    pass
            
            # 등급(Level) DOM 백업
            writer_text = ""
            if not api_member_level:
                try:
                    level_selectors = [
                        "em.icon_level",
                        "img.icon_level",
                        ".nick_level",
                        ".level_icon",
                        ".ArticleWriter .level", # 추가
                        ".article_writer .level", # 추가
                    ]
                    for sel in level_selectors:
                        try:
                            el = self.driver.find_element(By.CSS_SELECTOR, sel)
                            # 텍스트가 있으면 텍스트, 없으면 title/alt/src 확인
                            txt = el.text.strip()
                            if not txt:
                                txt = el.get_attribute("title") or el.get_attribute("alt") or ""
                            # 이미지 src에서 등급 추출 (예: level_1.gif) 하는건 복잡하므로 일단 텍스트/타이틀 위주
                            if txt:
                                api_member_level = txt
                                break
                        except: continue
                    
                    # (추가) 텍스트 기반 등급 확인 (부 매니저 등)
                    if not api_member_level:
                         try:
                             # 닉네임 주변 텍스트에서 '매니저', '스탭' 등이 있는지 확인
                             writer_area = self.driver.find_element(By.CSS_SELECTOR, ".ArticleWriter, .article_writer")
                             writer_text = writer_area.text
                             wt = re.sub(r"\s+", "", str(writer_text or ""))
                             if "부매니저" in wt:
                                 api_member_level = "부 매니저"
                             elif "매니저" in wt:
                                 api_member_level = "매니저"
                             elif "스탭" in wt:
                                 api_member_level = "스탭"
                             elif "일반멤버" in wt:
                                 api_member_level = "일반멤버"
                             elif "열심멤버" in wt:
                                 api_member_level = "열심멤버"
                             elif "새싹멤버" in wt:
                                 api_member_level = "새싹멤버"
                             elif "초급자" in wt:
                                 api_member_level = "초급자"
                             elif "중급자" in wt:
                                 api_member_level = "중급자"
                             elif "상급자" in wt:
                                 api_member_level = "상급자"
                             elif "정회원" in wt:
                                 api_member_level = "정회원"
                         except: pass

                except: pass

            # (추가) JS 전역 상태 폴백: DOM/API가 비어도 levelName이 남아있는 경우 복구
            if not api_member_level:
                js_lvl = self._get_member_level_via_js_state()
                if js_lvl:
                    api_member_level = js_lvl
            
            # NOTE: 지난주 정상 동작 버전 기준으로, 여기서 강제 '탈퇴' 판정을 하지 않는다.
            # 등급 근거가 없으면 빈값을 유지하고 상위 로직(DB 기존값/보정맵)에서 처리한다.

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
                    return {
                        "content": content,
                        "comments": filtered_comments,
                        "member_id": post_author_id,
                        "nickname": api_author_nick,
                        "member_level": api_member_level,
                        "board_name": board_name,
                        "category": category,
                        "view_count": int(meta_info.get("view_count", 0) or 0),
                        "like_count": int(meta_info.get("like_count", 0) or 0),
                    }

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
                
            return {
                "content": content,
                "comments": filtered_comments,
                "member_id": post_author_id,
                "nickname": api_author_nick,
                "member_level": api_member_level,
                "board_name": board_name,
                "category": category,
                "view_count": int(meta_info.get("view_count", 0) or 0),
                "like_count": int(meta_info.get("like_count", 0) or 0),
            }
        except Exception as e:
            return {
                "content": "",
                "comments": [],
                "member_id": post_author_id if post_author_id else "unknown",
                "nickname": "unknown",
                "member_level": "",
                "board_name": "",
                "category": "",
                "view_count": 0,
                "like_count": 0,
            }

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
