import re

file_path = r'd:\CafeScraper\app\products\scraper\crawler.py'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. ADD _get_member_id_via_spa_profile BEFORE extract_cafe_leaders
spa_profile_code = """
    def _get_member_id_via_spa_profile(self, club_id: str, member_key: str, nickname: str) -> str:
        \"\"\"Vue SPA 멤버 프로필 페이지로 이동하여 API 응답을 가로채어 Naver ID를 획득합니다.\"\"\"
        if not member_key or member_key == "unknown":
            return "unknown"
            
        try:
            profile_url = f"https://m.cafe.naver.com/ca-fe/cafes/{club_id}/members/{member_key}"
            
            inject_js = \"\"\"
            window._api_responses = [];
            const originalFetch = window.fetch;
            window.fetch = async function(...args) {
                const response = await originalFetch.apply(this, args);
                try {
                    const cloned = response.clone();
                    cloned.text().then(text => {
                        let url = args[0];
                        if (url && typeof url === 'object' && url.url) {
                            url = url.url;
                        }
                        window._api_responses.push({
                            url: url,
                            body: text
                        });
                    }).catch(e => {});
                } catch(e) {}
                return response;
            };
            \"\"\"
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': inject_js})
            
            self.driver.get(profile_url)
            import time
            time.sleep(3.0)
            
            responses = self.driver.execute_script('return window._api_responses || [];')
            for r in responses:
                url = r.get('url', '')
                if 'graphql' in url or 'members/' in url or 'Profile' in url:
                    body = r.get('body', '')
                    if '"memberId"' in body or '"userId"' in body or '"naverId"' in body:
                        # try to find naverId first
                        m = re.search(r'"(?:naverId|memberId|userId)"\s*:\s*"([^"]+)"', body)
                        if m:
                            return m.group(1)
                            
        except Exception as e:
            if self.debug_mode:
                self._update_status(f"[디버그] SPA 프로필 파싱 중 에러: {e}")
                
        return "unknown"

    def extract_cafe_leaders"""

text = text.replace("    def extract_cafe_leaders", spa_profile_code)

# 2. REWRITE extract_cafe_leaders
new_extract_leaders = """
    def extract_cafe_leaders(self, cafe_url_or_name: str) -> List[Dict[str, str]]:
        \"\"\"특정 카페의 운영진 네이버 ID 리스트를 수집합니다. (모바일 API 가로채기 방식)\"\"\"
        if not self.driver:
            raise Exception("브라우저가 실행되지 않았습니다.")
            
        s = str(cafe_url_or_name or "").strip()
        if not s:
            return []
            
        self._update_status(f"[운영진 추출] 대상 카페: {s}")
        
        if not s.startswith("http"):
            target_url = f"https://cafe.naver.com/{s}"
        else:
            target_url = s
            
        try:
            self.driver.get(target_url)
            import time
            time.sleep(2.0)
        except Exception as e:
            self._update_status(f"[운영진 추출] 카페 페이지 진입 실패: {e}")
            return []
            
        club_id = self._extract_club_id_from_url_string(self.driver.current_url)
        if not club_id:
            try:
                page_src = self.driver.page_source
                m = re.search(r"g_sClubId\s*=\s*['\\\"]?(\d+)['\\\"]?", page_src)
                if m:
                    club_id = m.group(1)
            except:
                pass
                
        if not club_id:
            self._update_status("[운영진 추출] 카페 고유 ID(clubid)를 획득하지 못했습니다.")
            return []
            
        self._last_known_club_id = str(club_id)
        self._update_status(f"[운영진 추출] 획득한 clubid: {club_id}")
        
        leaders_data = []
        try:
            staff_url = f"https://m.cafe.naver.com/ca-fe/cafes/{club_id}/members/staff"
            self._update_status("[운영진 추출] 모바일 스탭 페이지 API 가로채기 시도 중...")
            
            inject_js = \"\"\"
            window._api_responses = [];
            const originalFetch = window.fetch;
            window.fetch = async function(...args) {
                const response = await originalFetch.apply(this, args);
                try {
                    const cloned = response.clone();
                    cloned.text().then(text => {
                        let url = args[0];
                        if (url && typeof url === 'object' && url.url) {
                            url = url.url;
                        }
                        window._api_responses.push({
                            url: url,
                            body: text
                        });
                    }).catch(e => {});
                } catch(e) {}
                return response;
            };
            \"\"\"
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': inject_js})
            
            self.driver.get(staff_url)
            import time
            time.sleep(4.0)
            
            responses = self.driver.execute_script('return window._api_responses || [];')
            for r in responses:
                url = r.get('url', '')
                if 'graphql' in url or 'members/staff' in url or 'staff' in url:
                    body = r.get('body', '')
                    if '"nickname"' in body and ('"memberKey"' in body or '"memberId"' in body):
                        staff_matches = re.finditer(r'\\{[^{]*?"nickname"\\s*:\\s*"([^"]+)"[^{]*?"member(?:Key|Id)"\\s*:\\s*"([^"]+)"[^{]*?\\}', body)
                        for match in staff_matches:
                            nick = match.group(1)
                            m_key = match.group(2)
                            role = "카페 스탭"
                            if '"manager"' in match.group(0).lower(): role = "카페 매니저"
                            
                            if not any(d['nick'] == nick for d in leaders_data):
                                leaders_data.append({
                                    'nick': nick,
                                    'role': role,
                                    'm_key': m_key
                                })
        except Exception as e:
            self._update_status(f"[운영진 추출] 모바일 스탭 API 가로채기 실패: {e}")

        # Fallback to PC iframe if mobile API fails
        if not leaders_data:
            self._update_status("[운영진 추출] 모바일 API 파싱 실패. PC iframe 닉네임 수집 폴백...")
            intro_url = f"https://cafe.naver.com/CafeProfileView.nhn?clubid={club_id}"
            self.driver.get(intro_url)
            time.sleep(3.0)
            self.driver.switch_to.default_content()
            if self._switch_to_cafe_iframe():
                time.sleep(2.0)
                try:
                    page_src = self.driver.page_source
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(page_src, "html.parser")
                    for th in soup.find_all("th"):
                        th_text = th.get_text(strip=True)
                        if "카페 매니저" in th_text or "카페 스탭" in th_text:
                            tr = th.find_parent("tr")
                            if tr:
                                for a in tr.find_all("a"):
                                    nick = a.get_text(strip=True)
                                    if nick and not any(d['nick'] == nick for d in leaders_data):
                                        leaders_data.append({
                                            'nick': nick,
                                            'role': th_text,
                                            'm_key': ""
                                        })
                except:
                    pass
            
        self._update_status(f"[운영진 추출] 발견된 운영진 수: {len(leaders_data)}명. ID 역추출을 개시합니다.")
        
        results = []
        for item in leaders_data:
            nick = item['nick']
            role = item['role']
            m_key_extracted = item.get('m_key', '')
            
            naver_id = "unknown"
            
            if m_key_extracted:
                try:
                    self.driver.switch_to.default_content()
                    resolved_id = self._get_member_id_via_spa_profile(club_id, m_key_extracted, nick)
                    if resolved_id and resolved_id != "unknown":
                        naver_id = resolved_id
                        self._update_status(f"[디버그] m_key에서 추출 성공 -> {naver_id}")
                except Exception as e_href:
                    if self.debug_mode:
                        self._update_status(f"[디버그] m_key 해석 실패: {e_href}")
            
            if naver_id and naver_id != "unknown":
                email_addr = f"{naver_id}@naver.com"
                results.append({
                    "nickname": nick,
                    "role": role,
                    "naver_id": naver_id,
                    "email": email_addr
                })
                self._update_status(f"  └ [성공] {nick} ({role}) -> ID: {naver_id}")
            else:
                self._update_status(f"  └ [실패] {nick} ({role}) -> ID 추출 불가 (unknown)")
                
            import random
            time.sleep(random.uniform(0.5, 1.0))
            
        self._update_status(f"[운영진 추출 완료] 최종 추출 성공: {len(results)}명")
        return results

    def send_automatic_memo"""

# Using regex to replace the entire extract_cafe_leaders function block
text = re.sub(r'    def extract_cafe_leaders\(self.*?(?=    def send_automatic_memo)', lambda m: new_extract_leaders + '\n\n', text, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Patched successfully!')
