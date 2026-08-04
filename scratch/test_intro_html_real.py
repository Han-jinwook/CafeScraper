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
    print("Testing Naver Cafe Intro page source extraction...")
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
        
        # Navigate to cafe first
        cafe_url = "https://cafe.naver.com/campingfirst"
        print(f"Navigating to Cafe URL: {cafe_url}")
        crawler.driver.get(cafe_url)
        time.sleep(4.0)
        
        # Switch to main iframe
        crawler.driver.switch_to.default_content()
        switched = crawler._switch_to_cafe_iframe()
        if switched:
            print("Switched to main iframe.")
            
        # Click on Cafe Intro button
        from selenium.webdriver.common.by import By
        btn = None
        for xpath in ["//a[contains(., '카페소개')]", "//a[contains(., '소개')]", "//a[contains(@href, 'CafeIntro.nhn')]"]:
            try:
                btn = crawler.driver.find_element(By.XPATH, xpath)
                if btn:
                    break
            except:
                continue
                
        if btn:
            print("Found intro button, clicking it...")
            crawler.driver.execute_script("arguments[0].click();", btn)
            time.sleep(1.0)
        else:
            print("Intro button not found. Navigating to intro URL directly...")
            intro_url = "https://cafe.naver.com/CafeIntro.nhn?clubid=14358379"
            crawler.driver.get(intro_url)
            time.sleep(3.0)
            
        # Wait for th tags inside iframe
        print("Waiting for th elements to render...")
        for i in range(25):
            crawler.driver.switch_to.default_content()
            switched = crawler._switch_to_cafe_iframe()
            if switched:
                # check th elements using CDP
                js_check = "document.querySelectorAll('th').length > 0"
                res_check = crawler._execute_js_via_cdp(js_check)
                if res_check == "true" or res_check is True:
                    print(f"th elements rendered successfully (iteration {i+1})")
                    break
            time.sleep(0.5)
            
        # Save page source of the iframe
        crawler.driver.switch_to.default_content()
        crawler._switch_to_cafe_iframe()
        page_src = crawler.driver.page_source
        
        output_file = "scratch/real_intro_source.html"
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
            
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
