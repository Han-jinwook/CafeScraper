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
    print("Testing Jindo member menu layer click inside iframe...")
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
        
        # Go to CafeProfileView.nhn directly
        club_id = "14358379"
        url = f"https://cafe.naver.com/CafeProfileView.nhn?clubid={club_id}"
        print(f"Navigating to CafeProfileView directly: {url}")
        crawler.driver.get(url)
        time.sleep(5.0)
        
        # Inject test IDs to anchors inside the iframe
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
        injected_count = crawler.driver.execute_script(inject_js)
        print(f"Injected test IDs to {injected_count} anchors inside iframe")
        
        # Click the nickname (캠핑퍼스트매니저) using coordinates to trigger Jindo layer
        click_nick_js = """
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
        click_res = crawler.driver.execute_script(click_nick_js)
        print(f"Click response: {click_res}")
        time.sleep(2.0)
        
        # Detect any newly created layers or #memberHtmlLayer inside iframe or parent
        detect_layers_js = """
        (function() {
            var iframe = document.getElementById('cafe_main');
            var docIframe = iframe ? (iframe.contentDocument || iframe.contentWindow.document) : null;
            var docParent = document;
            
            var results = {};
            var docs = { "iframe": docIframe, "parent": docParent };
            
            for (var name in docs) {
                var doc = docs[name];
                if (!doc) continue;
                
                var candidates = [
                    "memberHtmlLayer", "memberHtmlLayer_0", "memberHtmlLayer_1", 
                    "div.per_layer", "ul.layer_list", "#memberHtmlLayer"
                ];
                
                for (var i = 0; i < candidates.length; i++) {
                    var sel = candidates[i];
                    var el = sel.startsWith('.') || sel.startsWith('#') || sel.indexOf(' ') > -1
                        ? doc.querySelector(sel)
                        : doc.getElementById(sel);
                    if (el) {
                        results[name + "_" + sel] = {
                            html: el.outerHTML.substring(0, 1000),
                            visible: el.offsetHeight > 0
                        };
                    }
                }
                
                // Find all active/visible divs
                var divs = doc.querySelectorAll('div');
                var active = [];
                for (var j = 0; j < divs.length; j++) {
                    var d = divs[j];
                    if (d.offsetHeight > 0) {
                        var id = d.getAttribute('id') || "";
                        var cls = d.getAttribute('class') || "";
                        if (id.toLowerCase().indexOf('layer') > -1 || cls.toLowerCase().indexOf('layer') > -1) {
                            active.push({ id: id, class: cls, html: d.outerHTML.substring(0, 300) });
                        }
                    }
                }
                results[name + "_active_divs"] = active;
            }
            return JSON.stringify(results);
        })()
        """
        layers_detected = crawler.driver.execute_script(detect_layers_js)
        print(f"Layers detected:\n{layers_detected}")
        
        crawler.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
