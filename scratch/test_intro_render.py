import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout for utf-8 output to prevent cp949 emoji errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

os.environ["CAFESCRAPER_SESSION0_BYPASS"] = "1"

from app.products.scraper.crawler import NaverCafeCrawler

def main():
    print("Testing CafeProfileView redirection and rendering...")
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
        
        # Go to legacy CafeProfileView.nhn URL which redirects to Next.js/Vue introduction page
        club_id = "14358379"
        url = f"https://cafe.naver.com/CafeProfileView.nhn?clubid={club_id}"
        print(f"Navigating to: {url}")
        crawler.driver.get(url)
        
        # Monitor rendering for 10 seconds
        for i in range(10):
            time.sleep(1.0)
            current_url = crawler.driver.current_url
            page_src = crawler.driver.page_source
            has_container_data = "manager" in page_src.lower() or "staff" in page_src.lower() or "매니저" in page_src or "스탭" in page_src
            print(f"[{i+1}s] URL: {current_url} | Has Data: {has_container_data} | HTML Length: {len(page_src)}")
            if has_container_data:
                # Save to file
                with open("scratch/intro_rendered_success.html", "w", encoding="utf-8") as f:
                    f.write(page_src)
                print("Saved successfully rendered HTML to scratch/intro_rendered_success.html")
                
                # Check for manager and staff links/nicknames
                import re
                links = re.findall(r"href=['\"](.*?)['\"].*?>(.*?)</a>", page_src)
                print("Found links in rendered page:")
                for href, text in links[:15]:
                    if "member" in href.lower() or "members" in href.lower():
                        print(f"  Href: {href} | Text: {text}")
                break
                
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
