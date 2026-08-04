import os
import sys
import time
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing Naver Cafe Member Profile rendering via Selenium...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    try:
        crawler.start_browser()
        
        # 🔑 저장된 네이버 계정 정보 로드
        from app.utils.paths import get_config_path
        import json
        config_path = get_config_path()
        login_id, login_pw = "", ""
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                login_id = cfg.get("marketer_naver_id", "").strip()
                login_pw = cfg.get("marketer_naver_pw", "")
        
        # 🔑 자동 로그인 시도
        from app.utils.naver_login import auto_login_naver_with_js
        print(f"🔑 자동 로그인 시도 중 (ID: {login_id})...")
        success, reason = auto_login_naver_with_js(crawler, login_id, login_pw)
        print(f"🔑 로그인 상태: {success} ({reason})")
        time.sleep(2)
        
        # Go to member profile page
        club_id = "14358379"
        member_key = "Ta4qKK0NoroVi-J5TrgF68zv7dzzefVlrfBfK1CZBA0"
        url = f"https://cafe.naver.com/f-e/cafes/{club_id}/members/{member_key}"
        print(f"Navigating to: {url}")
        crawler.driver.get(url)
        time.sleep(4.0)
        
        # Get page source
        page_src = crawler.driver.page_source
        
        # Search for blog.naver.com in the rendered source
        blog_matches = re.findall(r"blog\.naver\.com/([a-zA-Z0-9_-]+)", page_src)
        print(f"Found blog matches: {blog_matches}")
        
        # Search for other potential Naver ID patterns
        print("Searching for naver links/IDs...")
        for pattern in [r"blogId=([a-zA-Z0-9_-]+)", r"blog\.naver\.com/([a-zA-Z0-9_-]+)", r"members/([a-zA-Z0-9_-]+)"]:
            m = re.findall(pattern, page_src)
            if m:
                print(f"Pattern {pattern} matches: {m}")
                
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
