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
    print("Testing Naver Cafe JSP Member Profile Page direct access...")
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
        print(f"🔑 로그인 시도 중 (ID: {login_id})...")
        success, reason = auto_login_naver_with_js(crawler, login_id, login_pw)
        print(f"🔑 로그인 상태: {success}")
        time.sleep(2)
        
        # Go to JSP member profile page
        club_id = "14358379"
        member_key = "Ta4qKK0NoroVi-J5TrgF68zv7dzzefVlrfBfK1CZBA0"
        url = f"https://cafe.naver.com/CafeMemberNetworkView.nhn?m=view&clubid={club_id}&memberid={member_key}"
        print(f"Navigating to: {url}")
        crawler.driver.get(url)
        time.sleep(4.0)
        
        # Extract page source
        page_src = crawler.driver.page_source
        
        # Save to file
        with open("scratch/jsp_profile.html", "w", encoding="utf-8") as f:
            f.write(page_src)
        print("Saved to scratch/jsp_profile.html")
        
        # Search for blog.naver.com/
        matches = re.findall(r"blog\.naver\.com/([a-zA-Z0-9_-]+)", page_src)
        print(f"Found blog matches: {matches}")
        
        # Search for blogId=
        blog_ids = re.findall(r"blogId=([a-zA-Z0-9_-]+)", page_src)
        print(f"Found blogId matches: {blog_ids}")
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
