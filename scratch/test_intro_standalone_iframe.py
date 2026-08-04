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
    print("Testing Naver Cafe Intro page standalone iframe source...")
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
        
        # Navigate to CafeIntro standalone URL directly
        club_id = "14358379" # campingfirst
        intro_url = f"https://cafe.naver.com/CafeIntro.nhn?clubid={club_id}"
        print(f"Navigating directly to: {intro_url}")
        crawler.driver.get(intro_url)
        time.sleep(5.0)
        
        # Switch to cafe_main iframe
        crawler.driver.switch_to.default_content()
        switched = crawler._switch_to_cafe_iframe()
        if switched:
            print("Switched to cafe_main iframe.")
            
            # Wait for th elements to render
            print("Waiting for th elements to render...")
            for i in range(15):
                js_check = "document.querySelectorAll('th').length > 0"
                res_check = crawler._execute_js_via_cdp(js_check)
                if res_check == "true" or res_check is True:
                    print("th elements rendered!")
                    break
                time.sleep(0.5)
                
            # Save iframe page source
            page_src = crawler.driver.page_source
            output_file = "scratch/real_intro_iframe_source.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(page_src)
            print(f"Saved real intro iframe page source to {output_file} (length: {len(page_src)})")
            
            # Search for campingfirst manager name in the source
            if "캠핑퍼스트매니저" in page_src:
                print("Found '캠핑퍼스트매니저' in the real intro HTML!")
                idx = page_src.index("캠핑퍼스트매니저")
                start = max(0, idx - 600)
                end = min(len(page_src), idx + 600)
                print("--- Snippet around manager ---")
                print(page_src[start:end])
                print("------------------------------")
            else:
                print("Could not find '캠핑퍼스트매니저' in the real intro HTML.")
        else:
            print("Failed to switch to cafe_main iframe.")
            
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
