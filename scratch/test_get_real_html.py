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
    print("Extracting real CafeIntro iframe HTML via Selenium execute_script...")
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
        
        # Click on Cafe Intro button
        crawler.driver.switch_to.default_content()
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
            time.sleep(4.0)
        else:
            print("Intro button not found. Navigating to intro URL directly...")
            intro_url = "https://cafe.naver.com/CafeIntro.nhn?clubid=14358379"
            crawler.driver.get(intro_url)
            time.sleep(4.0)
            
        # Switch to iframe (actually we stay at top-level for CDP but we can switch for consistency)
        crawler.driver.switch_to.default_content()
        
        # Get iframe document outerHTML via CDP
        get_html_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            if (iframe) {
                var doc = iframe.contentDocument || iframe.contentWindow.document;
                return doc.documentElement.outerHTML;
            }
            return "IFRAME_NOT_FOUND";
        })()
        """
        inner_html = crawler._execute_js_via_cdp(get_html_js)
        
        if inner_html and inner_html != "IFRAME_NOT_FOUND":
            print("Successfully extracted iframe outerHTML.")
            output_file = "scratch/real_intro_iframe_outer.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(inner_html)
            print(f"Saved real iframe outerHTML to {output_file} (length: {len(inner_html)})")
            
            # Look for campingfirst manager name
            if "캠핑퍼스트매니저" in inner_html:
                print("Found '캠핑퍼스트매니저' in the outerHTML!")
                idx = inner_html.index("캠핑퍼스트매니저")
                start = max(0, idx - 600)
                end = min(len(inner_html), idx + 600)
                print("--- Snippet ---")
                print(inner_html[start:end])
                print("---------------")
            else:
                print("Could not find '캠핑퍼스트매니저' in the outerHTML.")
        else:
            print(f"Failed to switch to iframe or iframe not found. Result: {inner_html}")
            
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
