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
    print("Testing parent document layer popup theory...")
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
            
        # Switch to iframe
        crawler.driver.switch_to.default_content()
        switched = crawler._switch_to_cafe_iframe()
        if not switched:
            print("Failed to switch to iframe.")
            crawler.close()
            return
            
        # Wait for nickname elements to render inside iframe
        print("Waiting for th elements to render...")
        for i in range(15):
            js_check = """
            (function() {
                var iframe = document.getElementById('cafe_main');
                var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
                var ths = doc.querySelectorAll('th');
                return ths.length > 0 ? "true" : "false";
            })()
            """
            res_check = crawler._execute_js_via_cdp(js_check)
            if res_check == "true" or res_check is True:
                print("th elements rendered!")
                break
            time.sleep(0.5)
            
        # Inject IDs to nickname links
        js_inject_ids = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            var ths = doc.querySelectorAll('th');
            var index = 0;
            for (var i = 0; i < ths.length; i++) {
                var th = ths[i];
                var th_text = (th.textContent || "").trim();
                if (th_text.indexOf('카페 매니저') > -1 || th_text.indexOf('카페 스탭') > -1) {
                    var parent_tr = th.parentNode;
                    for (var j = 0; j < 3; j++) {
                        if (parent_tr && parent_tr.tagName && parent_tr.tagName.toLowerCase() === 'tr') {
                            break;
                        }
                        if (parent_tr) parent_tr = parent_tr.parentNode;
                    }
                    if (parent_tr) {
                        var a_tags = parent_tr.querySelectorAll('a');
                        for (var k = 0; k < a_tags.length; k++) {
                            var a = a_tags[k];
                            if (a) {
                                a.setAttribute('id', 'temp-leader-marketer-' + index);
                                index++;
                            }
                        }
                    }
                }
            }
            return "OK";
        })()
        """
        crawler._execute_js_via_cdp(js_inject_ids)
        
        # Click the nickname element inside the iframe using standard el.click()
        click_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            var el = doc.getElementById('temp-leader-marketer-0');
            if (el) {
                el.scrollIntoView({block: 'center'});
                el.click();
                return "CLICKED";
            }
            return "NOT_FOUND";
        })()
        """
        click_res = crawler._execute_js_via_cdp(click_js)
        print(f"Click Result inside iframe: {click_res}")
        time.sleep(1.0)
        
        # Check if popup layer exists in parent document
        check_parent_js = """
        (function() {
            var layer = document.querySelector('div.per_layer') || 
                        document.querySelector('div[class*="per_layer"]') ||
                        document.querySelector('ul.layer_list');
            if (layer) {
                return JSON.stringify({
                    "found": true,
                    "outerHTML": layer.outerHTML
                });
            }
            return JSON.stringify({ "found": false });
        })()
        """
        parent_res = crawler._execute_js_via_cdp(check_parent_js)
        print(f"Popup Layer Check in Parent Document: {parent_res}")
        
        # Check if popup layer exists inside iframe document
        check_iframe_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            var layer = doc.querySelector('div.per_layer') || 
                        doc.querySelector('div[class*="per_layer"]') ||
                        doc.querySelector('ul.layer_list');
            if (layer) {
                return JSON.stringify({
                    "found": true,
                    "outerHTML": layer.outerHTML
                });
            }
            return JSON.stringify({ "found": false });
        })()
        """
        iframe_res = crawler._execute_js_via_cdp(check_iframe_js)
        print(f"Popup Layer Check in Iframe Document: {iframe_res}")
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
