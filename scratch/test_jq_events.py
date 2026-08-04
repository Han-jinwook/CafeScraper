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
    print("Testing jQuery events on nickname links...")
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
            time.sleep(3.0)
            
        crawler.driver.switch_to.default_content()
        switched = crawler._switch_to_cafe_iframe()
        if not switched:
            print("Failed to switch to iframe.")
            crawler.close()
            return
            
        # Wait for nickname element to render inside iframe
        print("Waiting for nickname elements to render...")
        for i in range(15):
            js_check = """
            (function() {
                var iframe = document.getElementById('cafe_main');
                var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
                var a_tags = doc.querySelectorAll('a.m-tcol-c');
                return a_tags.length > 0 ? "true" : "false";
            })()
            """
            res_check = crawler._execute_js_via_cdp(js_check)
            if res_check == "true" or res_check is True:
                print("Nickname elements rendered!")
                break
            time.sleep(0.5)
            
        # Let's run a script to add IDs to nickname links first
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
        
        # Let's inspect jQuery event listeners on temp-leader-marketer-0
        js_inspect_events = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            var el = doc.getElementById('temp-leader-marketer-0');
            if (!el) return "ELEMENT_NOT_FOUND";
            
            var info = {};
            info.outerHTML = el.outerHTML;
            
            // Check if jQuery exists inside the iframe context
            var win = iframe ? iframe.contentWindow : window;
            if (typeof win.jQuery !== 'undefined') {
                info.hasJquery = true;
                
                // Inspect standard events via jQuery._data
                var events = win.jQuery._data(el, "events");
                if (events) {
                    info.events = Object.keys(events);
                } else {
                    info.events = "NONE_ON_ELEMENT";
                }
                
                // Let's also check event delegation on parent elements
                var parent = el.parentNode;
                var parentsInfo = [];
                while (parent) {
                    var pEvents = win.jQuery._data(parent, "events");
                    if (pEvents) {
                        parentsInfo.push({
                            tag: parent.tagName,
                            className: parent.className,
                            id: parent.id,
                            events: Object.keys(pEvents)
                        });
                    }
                    parent = parent.parentNode;
                }
                info.parentsWithEvents = parentsInfo;
            } else {
                info.hasJquery = false;
            }
            return JSON.stringify(info);
        })()
        """
        events_res = crawler._execute_js_via_cdp(js_inspect_events)
        print("jQuery Events Inspection Result:")
        print(events_res)
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
