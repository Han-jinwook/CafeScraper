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
    print("Testing Jindo member popup layer search via CafeIntro...")
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
        
        # Go to CafeIntro URL
        club_id = "14358379"
        url = f"https://cafe.naver.com/CafeIntro.nhn?clubid={club_id}"
        print(f"Navigating to: {url}")
        crawler.driver.get(url)
        time.sleep(4.0)
        
        # Inject IDs to a tags in iframe
        inject_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            var a_tags = doc.querySelectorAll('a');
            var idx = 0;
            for (var i = 0; i < a_tags.length; i++) {
                var a = a_tags[i];
                var txt = (a.textContent || "").trim();
                if (txt === "캠핑퍼스트매니저" || txt === "두부") {
                    a.setAttribute('id', 'test-nick-' + idx);
                    idx++;
                }
            }
            return idx;
        })()
        """
        injected_count = crawler._execute_js_via_cdp(inject_js)
        print(f"Injected test IDs to {injected_count} anchors")
        
        # Click the first one (캠핑퍼스트매니저)
        click_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            var el = doc.getElementById('test-nick-0');
            if (el) {
                el.scrollIntoView({block: 'center'});
                var rect = el.getBoundingClientRect();
                var cx = Math.round(rect.left + rect.width / 2);
                var cy = Math.round(rect.top + rect.height / 2);
                
                var events = ["mousedown", "mouseup", "click"];
                for (var i = 0; i < events.length; i++) {
                    var evt = doc.createEvent("MouseEvents");
                    evt.initMouseEvent(
                        events[i], true, true, doc.defaultView || window, 1,
                        cx, cy, cx, cy, false, false, false, false, 0, null
                    );
                    el.dispatchEvent(evt);
                }
                return "CLICKED";
            }
            return "NOT_FOUND";
        })()
        """
        click_res = crawler._execute_js_via_cdp(click_js)
        print(f"Click response: {click_res}")
        time.sleep(2.0)
        
        # Check if #memberHtmlLayer exists in the iframe
        check_layer_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var doc = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : document;
            
            var results = {};
            
            // Check various ID/class candidates
            var ids = ["memberHtmlLayer", "memberHtmlLayer_0", "memberHtmlLayer_1"];
            for (var i = 0; i < ids.length; i++) {
                var el = doc.getElementById(ids[i]);
                if (el) {
                    results[ids[i]] = {
                        html: el.outerHTML.substring(0, 1000),
                        visible: el.offsetHeight > 0
                    };
                }
            }
            
            // Also search for any div containing "블로그" or "쪽지"
            var divs = doc.querySelectorAll('div');
            var list = [];
            for (var i = 0; i < divs.length; i++) {
                var div = divs[i];
                var id = div.getAttribute('id') || "";
                var cls = div.getAttribute('class') || "";
                if (id.indexOf('Layer') > -1 || id.indexOf('layer') > -1 || cls.indexOf('layer') > -1 || cls.indexOf('Layer') > -1) {
                    if (div.offsetHeight > 0) {
                        list.push({ id: id, class: cls, html: div.outerHTML.substring(0, 300) });
                    }
                }
            }
            results["active_layers"] = list;
            return JSON.stringify(results);
        })()
        """
        layer_res = crawler._execute_js_via_cdp(check_layer_js)
        print(f"Layer detection results:\n{layer_res}")
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
