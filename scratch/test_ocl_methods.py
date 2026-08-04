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
    print("Inspecting window.oCL methods and properties...")
    crawler = NaverCafeCrawler(debug_mode=True)
    
    try:
        crawler.start_browser()
        crawler.driver.get("https://cafe.naver.com/campingfirst")
        time.sleep(3.0)
        
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
            
        # Switch to iframe and wait for elements
        crawler.driver.switch_to.default_content()
        switched = crawler._switch_to_cafe_iframe()
        if not switched:
            print("Failed to switch to iframe.")
            crawler.close()
            return
            
        # Wait for elements
        for i in range(15):
            js_check = "document.querySelectorAll('a.m-tcol-c').length > 0"
            res_check = crawler._execute_js_via_cdp(js_check)
            if res_check == "true" or res_check is True:
                break
            time.sleep(0.5)
            
        # JS to inspect oCL and Jindo controlLayer
        js_inspect = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var win = iframe ? iframe.contentWindow : window;
            
            var result = {};
            if (win.oCL) {
                result.has_oCL = true;
                result.oCL_keys = Object.keys(win.oCL);
                
                // Inspect methods of oCL and its prototype
                var proto = Object.getPrototypeOf(win.oCL);
                if (proto) {
                    result.proto_keys = Object.keys(proto);
                    var proto_methods = [];
                    for (var k in proto) {
                        try {
                            if (typeof proto[k] === 'function') {
                                proto_methods.push(k);
                            }
                        } catch(e) {}
                    }
                    result.proto_methods = proto_methods;
                }
            } else {
                result.has_oCL = false;
            }
            
            if (win.Ju && win.Ju.controlLayer) {
                result.has_Ju_controlLayer = true;
                var ju_keys = [];
                for (var k in win.Ju.controlLayer.prototype) {
                    ju_keys.push(k);
                }
                result.ju_prototype = ju_keys;
            }
            
            return JSON.stringify(result);
        })()
        """
        res = crawler._execute_js_via_cdp(js_inspect)
        print("Inspection Result:")
        print(res)
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
